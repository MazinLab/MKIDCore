from astropy.io import fits
import numpy as np
import os
from datetime import datetime
from multiprocessing.pool import ThreadPool
from threading import Thread
from Queue import Queue
import time
from mkidcore.corelog import getLogger

from collections import namedtuple
ImgTuple = namedtuple('img', ['data', 'file', 'time'])

_pool = None


def addfitshdu(a,b, copy=False):
    """add the data of two fits hdus together and adjust their headers """
    if copy:
        raise NotImplementedError
    a.header.exptime += b.header.exptime
    a.data += b.data
    return a


def loadimg(file, ncol, nrow, **kwargs):
    """kwargs is an optional list of fits header keywords (must respect the standard),

    returntype kw is reserved for hdu,  hdul, or raw
    if raw a namedtuple of data, file, and time are returned

    imgtime and imgname will cause the defaults to be overwritten
    """
    rettype = kwargs.pop('returntype', 'hdu')

    try:
        with open(file, mode='rb') as f:
            image = np.fromfile(f, dtype=np.uint16).reshape(ncol, nrow).T
    except ValueError:
        time.sleep(.05)
        getLogger(__name__).debug('Retrying {}'.format(file))
        with open(file, mode='rb') as f:
            image = np.fromfile(f, dtype=np.uint16).reshape(ncol, nrow).T

    try:
        tstamp = int(os.path.basename(file).partition('.')[0])
    except Exception:
        tstamp = 0

    if 'hdu' in rettype:
        ret = fits.ImageHDU(data=image)
        ret.header['imgname'] = os.path.basename(file)
        ret.header['utc'] = datetime.utcfromtimestamp(tstamp).strftime('%Y-%m-%d %H:%M:%S')
        ret.header['exptime'] = 'NaN'
        for k, v in kwargs.items():
            ret.header[k] = v
        return fits.HDUList([fits.PrimaryHDU(), ret]) if rettype == 'hdul' else ret
    else:
        return ImgTuple(image, file, tstamp)


def summarize(hdu):
    """generate a nice textual summary"""
    return ("Total Counts: {:.0f}\n"
            "Exp. Time: {:.0f}\n"
            "Shape: {}x{}").format(hdu.data.sum(),
                                   hdu.header['exptime'],
                                   hdu.data.shape[0],
                                   hdu.data.shape[1])


def makedark(images, et, badmask=None):
    data = np.sum(images, axis=0)/et
    if badmask is not None:
        data[badmask] = 0
    return data


def makeflat(images, dark, et, badmask=None):
    data = np.sum([i - dark for i in images], axis=0, dtype=float)
    data /= et
    if badmask is not None:
        data[badmask]=0
    med = np.median(data[data>0])
    flat = data/med
    flat[flat<=0] = np.amin(flat[flat>0])
    return flat


def _combineHDU(images, header={}, fname='file.fits', name='image', save=True):
    ret = fits.HDUList([fits.PrimaryHDU()]+list(images))  # Primaryhdu empty per fits std. doesn't REALLY matter
    ret[0].header['filename'] = os.path.basename(fname)
    ret[0].header['name'] = os.path.basename(name)
    ret[0].header.update(header)
    if save:
        ret.writeto(fname)
    return ret


def combineHDU(images, header={}, fname='file.fits', name='image', save=True, threaded=True):
    if threaded:
        global _pool
        if _pool is None:
            _pool = ThreadPool(processes=2)
        async_result = _pool.apply_async(_combineHDU, (images,),
                                         dict(fname=fname, name=name, header=header, save=save))
        return async_result
    else:
        return _combineHDU(images, fname=fname, name=name, header=header, save=save)


class CalFactory(object):
    def __init__(self, kind, images=tuple(), dark=None, flat=None, mask=None):
        """kind = dark|flat|avg

        mask will be applied to output products if specified and must match the shape of the images
        """
        self.images = list(images)
        self.dark = dark
        self.flat = flat
        self.kind = kind.lower()
        self.mask = mask

    def reset(self, image0, **kwargs):
        """kwords are same as for __init__"""
        for k, v in kwargs.items():
            setattr(self, k, v)

    def add_image(self, image):
        getLogger(__name__).debug('Adding image to {} calfactory'.format(self.kind))
        self.images.append(image)

    def generate(self, fname='calib.fits', name='calimage', badmask=None, dtype=float, bias=0, header={},
                 threaded=False, save=False, overwrite=False, maskvalue=np.nan):

        tic = time.time()
        spawn = isinstance(threaded, bool) and threaded

        sv = ' Will save to {}'.format(fname) if save else ''
        getLogger(__name__).debug(('Generating "{}" from {} images using method {} in {} thread.'+
                                   sv).format(name, len(self.images), self.kind, ('a new' if spawn else 'this')))
        if not self.images:
            return None

        if spawn:
            q = Queue()
            t = Thread(target=self.generate, args=tuple(), kwargs=dict(fname=fname, name=name, badmask=badmask,
                                                                       dtype=dtype, threaded=q, save=save))
            t.start()
            return q

        et = sum([i.header['exptime'] for i in self.images])
        idata = [i.data for i in self.images]

        ret = fits.PrimaryHDU(data=self.images[0].data.astype(dtype), header=self.images[0].header)

        ret.header.update(header)

        if self.kind == 'dark':
            ret.data = makedark(idata, et)
        elif self.kind == 'flat':
            d = np.zeros_like(ret.data) if self.dark is None else self.dark.data
            ret.data = makeflat(idata, d, et, badmask=badmask)
            ret.header['darkfile'] = None if self.dark is None else self.dark.header['filename']
        elif self.kind[:3] == 'avg':
            d = np.zeros_like(ret.data) if self.dark is None else self.dark.data
            f = np.ones_like(ret.data) if self.flat is None else self.flat.data
            ret.data = (np.sum(idata, axis=0, dtype=float)/et - d)
            ret.data /= f
            # previously the flat was only applied at nonzero pixels
            # e.g. ret.data[ret.data>0] *= f[ret.data>0]
            ret.header['flatfile'] = None if self.flat is None else self.flat.header['filename']
            ret.header['darkfile'] = None if self.dark is None else self.dark.header['filename']
        elif self.kind[:3] == 'sum':
            d = np.zeros_like(ret.data) if self.dark is None else self.dark.data
            f = np.ones_like(ret.data) if self.flat is None else self.flat.data
            ret.data = np.sum(idata, axis=0, dtype=float) - d*len(idata)
            ret.data /= f
            # previously the flat was only applied at nonzero pixels
            # e.g. ret.data[ret.data>0] *= f[ret.data>0]
            ret.header['flatfile'] = None if self.flat is None else self.flat.header['filename']
            ret.header['darkfile'] = None if self.dark is None else self.dark.header['filename']

        ret.data += bias
        ret.header['bias'] = bias
        ret.header['exptime'] = et
        ret.header['objtype'] = self.kind
        ret.header['filename'] = os.path.splitext(os.path.basename(fname))[0]+'.fits'
        ret.header['name'] = name

        if self.mask is not None:
            ret.data[self.mask] = maskvalue

        if save:
            getLogger(__name__).debug('Saving fits to {}'.format(fname))
            ret.writeto(fname, overwrite=overwrite)

        getLogger(__name__).debug('Generation took {:.1f} ms'.format((time.time()-tic)*1000))

        if isinstance(threaded, Queue):
            threaded.put(ret)
        else:
            return ret


