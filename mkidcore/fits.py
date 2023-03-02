from astropy.io import fits
import numpy as np
import os
from datetime import datetime
from multiprocessing.pool import ThreadPool
from threading import Thread

try:
    from queue import Queue
except ImportError:
    from Queue import Queue
import time
from mkidcore.corelog import getLogger

from collections import namedtuple

ImgTuple = namedtuple('img', ['data', 'file', 'time'])

_pool = None


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
    data = np.sum(images, axis=0) / et
    if badmask is not None:
        data[badmask] = 0
    return data


def makeflat(images, dark, et, badmask=None):
    data = np.sum([i - dark for i in images], axis=0, dtype=float)
    data /= et
    if badmask is not None:
        data[badmask] = 0
    if not data.nonzero()[0].size:
        return data
    med = np.median(data[data > 0])
    flat = data / med
    flat[flat <= 0] = np.amin(flat[flat > 0])
    return flat


def _combineHDU(images, header={}, fname='file.fits', name='image', save=True):
    ret = fits.HDUList([fits.PrimaryHDU()] + list(images))  # Primaryhdu empty per fits std. doesn't REALLY matter
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
        self._images = None
        self.images = images
        self._dark = [dark]
        self._flat = [flat]
        self.kind = kind.lower()
        self._mask = [mask]

    def reset(self, image0, **kwargs):
        """kwargs are same as for __init__"""
        for k, v in kwargs.items():
            setattr(self, k, v)

    def add_image(self, image):
        getLogger(__name__).debug('Adding image to {} calfactory'.format(self.kind))
        self._images.append(image)

    @property
    def images(self):
        return self._images

    @images.setter
    def images(self, x):
        if not isinstance(x, (list, tuple)):
            x = (x,)
        self._images = list(x)

    def _file_data_thing(self, thing, defaultgen):
        if len(thing) == 1:
            if thing[0] is None or thing[0] is '':
                thing.append(defaultgen(self._images[0].data))
            elif isinstance(thing[0], str):
                try:
                    thing.append(fits.getdata(thing[0]))
                except (IOError, OSError):
                    getLogger(__name__).warning(f'Unable to load {thing[0]}, using zeros.')
                    return defaultgen(self._images[0].data)
            else:
                thing.append(thing[0].data)
        return thing[1]

    def _thing_name(self, thing):
        if thing[0] is None:
            return 'None'
        elif isinstance(thing[0], str):
            return os.path.basename(thing[0])
        else:
            return thing[0].header['filename']

    @property
    def dark(self):
        return self._file_data_thing(self._dark, np.zeros_like)

    @property
    def flat(self):
        return self._file_data_thing(self._flat, np.ones_like)

    @property
    def mask(self):
        return self._file_data_thing(self._mask, lambda x: np.zeros_like(x, dtype=bool))

    @property
    def darkname(self):
        return self._thing_name(self._dark)

    @property
    def flatname(self):
        return self._thing_name(self._flat)

    @property
    def maskname(self):
        return self._thing_name(self._mask)

    @dark.setter
    def dark(self, x):
        """ x may be None a file name, or an imageHDU with the header key filename and matching data size"""
        if x != self._dark[0]:
            self._dark[:] = [x]

    @flat.setter
    def flat(self, x):
        """ x may be None a file name, or an imageHDU with the header key filename and matching data size"""
        if x != self._flat[0]:
            self._flat[:] = [x]

    @mask.setter
    def mask(self, x):
        """ x may be None a file name, or an imageHDU with the header key filename and matching data size"""
        if x != self._mask[0]:
            self._mask[:] = [x]

    def generate(self, fname='calib.fits', name='calimage', badmask=None, dtype=float, bias=0, header={},
                 threaded=False, save=False, overwrite=False, maskvalue=np.nan, complete_callback=None):

        tic = time.time()
        spawn = isinstance(threaded, bool) and threaded

        sv = ' Will save to {}'.format(fname) if save else ''
        getLogger(__name__).debug(('Generating "{}" from {} images using method {} in {} thread.' +
                                   sv).format(name, len(self.images), self.kind, ('a new' if spawn else 'this')))
        if not self.images:
            return None

        if spawn:
            q = Queue()
            t = Thread(name='CalFactory Saver', target=self.generate, args=tuple(),
                       kwargs=dict(fname=fname, name=name, badmask=badmask,
                                   dtype=dtype, threaded=q, save=save,
                                   complete_callback=complete_callback))
            t.start()
            return q

        et = sum([i.header['exptime'] for i in self.images])
        idata = [i.data for i in self.images]

        ret = fits.PrimaryHDU(data=self.images[0].data.astype(dtype), header=self.images[0].header)
        ret.header.update(header)

        if self.kind == 'dark':
            ret.data = makedark(idata, et)
        elif self.kind == 'flat':
            ret.data = makeflat(idata, self.dark, et, badmask=badmask)
            ret.header['darkfile'] = self.darkname
        elif self.kind[:3] == 'avg':
            d = self.dark
            f = self.flat
            ret.data = (np.sum(idata, axis=0, dtype=float) / et - d)
            ret.data /= f
            ret.header['flatfile'] = self.flatname
            ret.header['darkfile'] = self.darkname
        elif self.kind[:3] == 'sum':
            d = self.dark
            f = self.flat
            ret.data = np.sum(idata, axis=0, dtype=float) - d * len(idata)
            ret.data /= f
            ret.header['darkfile'] = self.darkname
            ret.header['flatfile'] = self.flatname

        ret.data += bias
        ret.header['bias'] = bias
        ret.header['exptime'] = et
        ret.header['objtype'] = self.kind
        ret.header['filename'] = os.path.splitext(os.path.basename(fname))[0] + '.fits'
        ret.header['name'] = name

        ret.data[self.mask] = maskvalue

        if save:
            getLogger(__name__).debug('Saving fits to {}'.format(fname))
            ret.writeto(fname, overwrite=overwrite)

        getLogger(__name__).debug('Generation took {:.1f} ms'.format((time.time() - tic) * 1000))

        if complete_callback:
            complete_callback(fname)

        if isinstance(threaded, Queue):
            threaded.put(ret)
        else:
            return ret
