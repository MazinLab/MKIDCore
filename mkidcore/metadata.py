import numpy as np
from astropy.io.fits import Card, Header
import pkg_resources as pkg
import copy


# TODO Build datafile: Key, default, comment, other, columns, of, info
# data = np.loadtxt(pkg.resource_filename('mkidcore', 'fitskeys.csv'))

keys = ('DATA-TYP','EXPTIME','FRAMEID','HST','HST-END','HST-STR','IMAGETYP','LONPOLE','MJD','MJD-END','MJD-STR',
        'TIMESYS','UT','UT-END','UT-STR','X_DICHRO','X_DICHRP','X_FINPKO','X_FINPKP','X_FPM','X_FPMF','X_FPMWHL',
        'X_FPMX','X_FPMY','X_FST','X_FSTX','X_FSTY','X_GRDAMP','X_GRDMOD','X_GRDSEP','X_GRDST','X_HOTSPT',
        'X_INTSPH','X_IPIAA','X_IPIPHI','X_IPITHE','X_IPIX','X_IPIY','X_IRCBLK','X_IRCFCS','X_IRCFCP','X_IRCFC2',
        'X_IRCFLC','X_IRCFLP','X_IRCFLT','X_IRCHWP','X_IRCHPP','X_IRCPUP','X_IRCPUX','X_IRCPUY','X_IRCQWP',
        'X_IRCWOL','X_LOWBLK','X_LOWFCS','X_LOWFRQ','X_LOWGN','X_LOWLK','X_LOWLP','X_LOWMOT','X_LOWNMO','X_LYOT',
        'X_LYOWHL','X_LYOX','X_LYOY','X_MKIPKO','X_MKIPKP','X_MKIPKT','X_NPS11','X_NPS12','X_NPS13','X_NPS14',
        'X_NPS15','X_NPS16','X_NPS17','X_NPS18','X_NPS21','X_NPS22','X_NPS23','X_NPS24','X_NPS25','X_NPS26',
        'X_NPS27','X_NPS28','X_NPS31','X_NPS32','X_NPS33','X_NPS34','X_NPS35','X_NPS36','X_NPS37','X_NPS38',
        'X_NULPKO','X_NULPKP','X_OAP1','X_OAP1F','X_OAP1PH','X_OAP1TH','X_OAP4','X_OAP4PH','X_OAP4TH','X_PG1PKO',
        'X_PG2PKO','X_PIAA1','X_PI1WHL','X_PI1X','X_PI1Y','X_PIAA2','X_PI2F','X_PI2WHL','X_PI2X','X_PI2Y','X_POLAR',
        'X_POLARP','X_PUPIL','X_PUPWHL','X_PUPX','X_PUPY','X_PYWCAL','X_PYWCLP','X_PYWCOL','X_PYWDMO','X_PYWFCS',
        'X_PYWFPK','X_PYWFLT','X_PYWFRQ','X_PYWFST','X_PYWFSX','X_PYWFSY','X_PYWGN','X_PYWLK','X_PYWLP','X_PYWPKO',
        'X_PYWPKP','X_PYWPLP','X_PYWPPX','X_PYWPPY','X_PYWRAD','X_RCHPKO','X_RCHPKP','X_SPCFRQ','X_SPCGN','X_SPCLP',
        'X_SRCFIB','X_SRCFIX','X_SRCFIP','X_SRCFFT','X_SRCFIR','X_SRCFOP','X_SRCSEL','X_SRCSEP','X_STR','X_STRPHI',
        'X_STRTHE','X_ZAPFRQ','X_ZAPGN','X_ZAPLP','X_ZAPMOT','X_ZAPNMO','AIRMASS','BIN-FCT1','BIN-FCT2','BLANK',
        'DATE-OBS','DEC','Dec-00','DETECTOR','DET-TMP','EQUINOX','EXP-ID','EXPTIME','EXTEND','FOC-POS',
        'FOC-VAL','GAIN','INSTRUME','LST','OBJECT','OBS-ALOC','OBS-MOD','OBSERVAT','OBSERVER','PROP-ID','RA',
        'RA2000','RADESYS','SIMPLE','TELESCOP','TELFOCUS','TIMESYS')

# This is a dictionary of name:Card pairs. The name is generally assumed to be the card name
DEFAULT_CARDSET = {k: Card(keyword=k, value='', comment='') for k in keys }


def build_header(metadata=None):
    """ Build a header with all of the keys and their default values with optional updates via metadata. Additional
    novel cards may be included via metadata as well.

    metadata is a dict of keyword:value|Card pairs. Value for keys in the default cardset, Cards for novel keywords.

    raises ValueError if any novel keyword is not a Card
    """

    novel = set(metadata.keys()).difference(set(DEFAULT_CARDSET.keys()))
    bad = [k for k in novel if not isinstance(metadata[k], Card)]
    if bad:
        raise ValueError('Keys {} are not known and must be passed as astropy.io.fits.Card'.format(bad))

    cardset = copy.deepcopy(DEFAULT_CARDSET)
    if metadata is not None:
        for k in metadata:
            try:
                cardset[k].value = metadata[k]
            except KeyError:
                cardset[k] = metadata[k]

    return Header(cardset.values())
