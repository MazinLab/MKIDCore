import unittest
from unittest import TestCase

class TestImportable(TestCase):
    def test_imports(self):
        import mkidcore
        import mkidcore.config
        import mkidcore.corelog
        import mkidcore.metadata
        import mkidcore.pixelflags
        import mkidcore.utils

        from mkidcore.config import getLogger, yaml
        from mkidcore.instruments import CONEX2PIXEL, InstrumentInfo, compute_wcs_ref_pixel
        from mkidcore.legacy import parse_dither
        from mkidcore.metadata import DEFAULT_CARDSET, DEFAULT_MEC_CARDSET, DEFAULT_XKID_CARDSET, INSTRUMENT_KEY_MAP
        from mkidcore.metadata import MetadataSeries
        from mkidcore.objects import Beammap
        from mkidcore.pixelflags import FlagSet, BEAMMAP_FLAGS
        from mkidcore.utils import astropy_observer, derangify, mjd_to

        from mkidcore.binfile.mkidbin import extract, parse, PhotonCType, PhotonNumpyType

if __name__ == "__main__":
    unittest.main()
