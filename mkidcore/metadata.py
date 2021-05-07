import numpy as np
from datetime import datetime
import copy
import os
from glob import glob
import json
from astropy.io.fits import Card, Header

from mkidcore.corelog import getLogger
import mkidcore.config
from astropy.time import Time
from astropy.time import TimezoneInfo
import astropy.units as u
from datetime import datetime

_metadata = {}

_KEYSDATA = """
CROP_EN1 I16 pixel End in X of the cropped window (pixel)
CROP_EN2 I16 pixel End in Y of the cropped window (pixel)
CROP_OR1 I16 pixel Origin in X of the cropped window (pixel)
CROP_OR2 I16 pixel Origin in Y of the cropped window (pixel)
CROPPED A16 NA Image windowed or full frame
DATA-TYP A30 NA Subaru-style exp. type
DET-TMP F20 K Detector temperature (K)
DETECTOR A20 NA Name of the detector
DETGAIN A16 NA Detector gain
DETMODE A16 NA Detector mode
EXPTIME F20 s Total integration time of the frame (sec)
FRAMEID A12 NA Image sequential number
FRATE F16 Hz Frame rate of the acquisition (Hz)
GAIN F20 e/ADU AD conversion factor (electron/ADU)
HST-END A12 NA HH:MM:SS.SS HST at exposure end
HST-STR A12 NA HH:MM:SS.SS HST at exposure start
MJD-END F20 J2000 Modified Julian Day at exposure end
MJD-STR F20 J2000 Modified Julian Day at exposure start
UT-END A12 NA HH:MM:SS.SS UTC at exposure end
UT-STR A12 NA HH:MM:SS.SS UTC at exposure start
UNIXSTR F20 s UNIX time at exposure start (UTC)
UNIXEND F20 s UNIX time at exposure start (UTC)
M_DEVANG A16 deg MKID device mounting angle
M_FLTPOS A16 NA The selected filter
M_FLPPOS A16 NA The flipper status
M_CXREFX F20 step Conex X position when source is at reference point
M_CXREFY F20 step Conex Y position when source is at reference point
M_PREFX F20 pixel The X position of the centroid of the source reference position 
M_PREFY F20 pixel The Y position of the centroid of the source reference position
M_FPGAFW A64 NA Git hash of readout software and firmware
M_FLTCAL A64 NA UUID of MKID Flatfield solution 
M_WAVCAL A64 NA UUID of MKID Wavelength solution 
M_WCSCAL A64 NA UUID of the WCS calibration
M_SPECAL A64 NA UUID of the applied spectrophotometirc calibration
M_BMAP A64 NA UUID of the active beammap
M_CFGDIR A64 NA The readout configuration path
M_BASELI bool NA Whether or not the baseline was remove from the data
M_GITHSH A8 NA Git hash of software producing the file
M_CFGHSH A64 NA Hash of config producing the output
AIRMASS F20 NA Air Mass at start
ALTITUDE deg Altitude of telescope pointing
AUTOGUID NA Auto guide on/off
AZIMUTH deg Azimuth of telescope pointing
DATE-OBS A30 NA UT date of Observation (yyyy-mm-dd)
DEC A12 NA DEC of telescope pointing (+/-DD:MM:SS.SS)
DOM-HUM % Dome humidity ( %)
DOM-PRS hpa Dome pressure (hpa)
DOM-TMP degC Dome temperature (C)
DOM-WND m/s Dome wind speed (m/sec)
EQUINOX F20 years Standard FK5 (years)
FOC-VAL F20 mm Encoder value of the focus unit (mm)
HST A12 NA HH:MM:SS.SS typical HST at exposure
M2-TIP NA 2nd mirror tip-tilt on-off
M2-TYPE NA 2nd mirror type
MJD F20 J2000 Modified Julian Day at typical time
OBSERVAT A20 NA Observatory
OUT-HUM % Outside humidity ( %)
OUT-PRS hpa Outside pressure (hpa)
OUT-TMP degC Outside temperature (C)
OUT-WND m/s Outside wind speed (m/sec)
RA A12 NA RA of telescope pointing (HH:MM:SS.SSS)
TELESCOP A30 NA Telescope/System which Inst. is attached
TELFOCUS A30 NA Focus where a beam is reachable
UT A12 NA HH:MM:SS.SS typical UTC at exposure
ZD F20 deg Zenith distance at typical time (deg)
D_HWADPA deg HOWFS ADC tracking position angle (deg)
D_HWADP mm HOWFS ADC stage position (mm)
D_HWADRA J2000 HOWFS ADC tracking right ascension (J2000)
D_HWADST NA HOWFS ADC tracking status
D_HWAF1 NA HOWFS acq cam. filter wheel#1 state
D_HWAF1P deg HOWFS acq cam. filter wheel#1 pos (deg)
D_HWAF2 NA HOWFS acq cam. filter wheel#2 state
D_HWAF2P deg HOWFS acq cam. filter wheel#2 pos (deg)
D_HWAPDA kcps/elem HOWFS APD Average Counts (kcps/elem)
D_HWHBS NA HOWFS hires cam. BS position
D_HWHBSP mm HOWFS hires cam. BS position (mm)
D_HWLAF NA HOWFS LA filter wheel position
D_HWLAFP deg HOWFS LA filter wheel pos (deg)
D_HWLASH NA HOWFS LA shutter state (OPEN CLOSE)
D_HWLAZ NA HOWFS LA focus stage position
D_HWLAZP mm HOWFS LA focus stage pos (mm)
D_HWLAP NA HOWFS LGS aperture name
D_HWLAPP mm HOWFS LGS aperture position (mm)
D_HWNAP NA HOWFS NGS aperture name
D_HWNAPP mm HOWFS NGS aperture position (mm)
D_HWPBS NA HOWFS pupil cam. BS position
D_HWPBSP mm HOWFS pupil cam. BS position (mm)
D_VMAP NA HOWFS VM aperture
D_VMAPS arcsec HOWFS VM aperture size (arcsec)
D_IMRANG deg IMR angle (deg)
D_IMRDEC J2000 IMR tracking declination (J2000)
D_IMRMOD NA IMR tracking mode (SID NON-SID ADI STOP OTHER)
D_IMRPAD deg IMR position angle of dec. axis (deg)
D_IMRPAP deg IMR pupil position angle (deg)
D_IMRRA J2000 IMR tracking right ascension (J2000)
D_IMR NA IMR tracking status (TRACKING SLEWING STAND-BY)
D_ADFG NA RTS AU1 defocus gain
D_DMCMTX NA RTS DM control matrix
D_DMGAIN NA RTS DM gain
D_HDFG NA RTS high order defocus gain
D_HTTG NA RTS high order TT gain
D_LDFG NA RTS low order defocus gain
D_LOOP NA RTS Loop state (ON OFF)
D_LTTG NA RTS low order TT gain
D_PSUBG NA RTS piston subtract gain
D_STTG NA RTS secondary TT gain
D_TTCMTX NA RTS TT control matrix
D_TTGAIN NA RTS TT offload gain
D_WTTG NA RTS HOWFS-TT gain
D_TTX V TT mount tip voltage (V)
D_TTY V TT mount tilt voltage (V)
D_WTTC1 V HOWFS TT ch1 voltage (V)
D_WTTC2 V HOWFS TT ch2 voltage (V)
D_VMDRV NA VM drive (ON OFF)
D_VMFREQ Hz VM frequency (Hz)
D_VMPHAS deg VM phase (deg)
D_VMVOLT V VM voltage (V)
OBS-ALOC A12 NA Observation or Standby
OBS-MOD A30 NA Observation Mode
OBSERVER A50 NA Observer
PROP-ID A8 NA Proposal ID
FOC-POS NA Focus where instrument is attached
OBJECT A30 NA Object
X_BUFPKO buffy_pickoff_st A16 NA BUFFYCAM pickoff state (HOME, IN, OUT)
X_BUFPKP buffy_pickoff F16 mm BUFFYCAM pickoff position (mm)
X_BUFPUP buffy_pup A16 NA BUFFYCAM pupil lens state (IN, OUT)
X_CHAPKO charis_pickoff_st A16 NA CHARIS pickoff wheel state
X_CHAPKP charis_pickoff_wheel F16 deg CHARIS pickoff wheel position (deg)
X_CHAPKT charis_pickoff_theta F16 deg CHARIS pickoff theta position (deg)
X_CHAWOL charis_wollaston A16 NA CHARIS Wollaston prism state (IN, OUT)
X_CHKPUP chuck_pup A16 NA CHUCKCAM pupil lens state (IN, OUT)
X_CHKPUF chuck_pup_fcs F16 mm CHUCKCAM pupil lens focus position (mm)
X_CHKPUS chuck_pup_fcs_st A16 NA CHUCKCAM pupil lens focus status 
X_COMPPL compplate A16 NA compensating plate pickoff state (IN, OUT)
X_DICHRO dichroic_st A16 NA Dichroic state (HOME, IN, OUT)
X_DICHRP dichroic F16 mm Dichroic position (mm)
X_FINPKO fibinj_pickoff_st A16 NA Fiber Injection pickoff state (HOME, IN, OUT)
X_FINPKP fibinj_pickoff F16 mm Fiber Injection pickoff position (mm)
X_FIRPKO first_pickoff_st A16 NA FIRST pickoff state
X_FIRPKP first_pickoff F16 mm FIRST pickoff position (mm)
X_FPM fpm_st A16 NA FPM wheel state
X_FPMF fpm_f I16 step FPM wheel f position (step)
X_FPMWHL fpm_wheel F16 deg FPM wheel position (deg)
X_FPMX fpm_x I16 step FPM wheel x position (step)
X_FPMY fpm_y I16 step FPM wheel y position (step)
X_FST field_stop_st A16 NA Field Stop state
X_FSTX field_stop_x F16 mm Field Stop x position (mm)
X_FSTY field_stop_y F16 mm Field Stop y position (mm)
X_GRDAMP grid_amp F16 um ASTROGRID amplitude (um)
X_GRDMOD grid_mod I16 Hz ASTROGRID modulation frequency (Hz)
X_GRDSEP grid_sep F16 lambda/D ASTROGRID separation (lambda/D)
X_GRDST grid_st A16 NA ASTROGRID status (ON, OFF)
X_HOTSPT hotspot A16 NA HOTSPOT alignment status 
X_INTSPH intsphere A16 NA Integration sphere state (IN, OUT)
X_IPIAA invpiaa_st A16 NA Inverse PIAA state
X_IPIPHI invpiaa_phi I16 step Inverse PIAA phi position (step)
X_IPITHE invpiaa_theta I16 step Inverse PIAA theta position (step)
X_IPIX invpiaa_x F16 mm Inverse PIAA x position (mm)
X_IPIY invpiaa_y F16 mm Inverse PIAA y position (mm)
X_IRCBLK ircam_block A16 NA IRCAMs block state (IN, OUT)
X_IRCFCS ircam_fcs_st A16 NA IRCAMs focusing stage state
X_IRCFCP ircam_fcs_f1 I16 step IRCAMs focusing stage position (step)
X_IRCFC2 ircam_fcs_f2 F16 mm IRCAMs lens2 focusing stage position (mm)
X_IRCFLC ircam_flc_st A16 NA IRCAMs FLC state (IN, OUT)
X_IRCFLP ircam_flc F16 deg IRCAMs FLC position (deg)
X_IRCFLT ircam_filter A16 NA IRCAMs filter state
X_IRCHWP ircam_hwp A16 NA IRCAMs HWP state (IN, OUT)
X_IRCHPP ircam_hwp_theta F16 deg IRCAMs HWP position (deg)
X_IRCPUP ircam_pupil_st A16 NA IRCAMs pupil mask state
X_IRCPUX ircam_pupil_x F16 mm IRCAMs pupil mask x position (mm)
X_IRCPUY ircam_pupil_y F16 mm IRCAMs pupil mask y position (mm)
X_IRCQWP ircam_qwp A16 NA IRCAMs QWP state (IN, OUT)
X_IRCWOL ircam_wollaston A16 NA IRCAMs Wollaston prism state (IN, OUT)
X_LOWBLK lowfs_block A16 NA LOWFS block state (IN, OUT)
X_LOWFCS lowfs_fcs I16 step LOWFS focus position (step)
X_LOWFRQ lowfs_freq I16 Hz LOWFS loop frequency (Hz)
X_LOWGN lowfs_gain F16 unitless LOWFS main gain (0-1)
X_LOWLK lowfs_leak F16 unitless LOWFS leak term (0-1)
X_LOWLP lowfs_loop A16 NA LOWFS loop status (OPEN, CLOSED, DM, ...)
X_LOWMOT lowfs_mtype A16 NA LOWFS mode types (ZERNIKE, FOURIER, ...)
X_LOWNMO lowfs_nmodes I16 unitless LOWFS number of modes 
X_LYOT lyot_st A16 NA LYOT wheel state
X_LYOWHL lyot_wheel F16 deg LYOT wheel position (deg)
X_LYOX lyot_x I16 step LYOT wheel x position (step)
X_LYOY lyot_y I16 step LYOT wheel y position (step)
X_MKIPKO mkids_pickoff_st A16 NA MKIDS pickoff wheel state
X_MKIPKP mkids_pickoff_wheel F16 deg MKIDS pickoff wheel position (deg)
X_MKIPKT mkids_pickoff_theta F16 deg MKIDS pickoff theta position (deg)
X_NPS11 nps1_1 A16 NA NPS1 status of port #1 (ON,OFF)
X_NPS12 nps1_2 A16 NA NPS1 status of port #2 (ON,OFF)
X_NPS13 nps1_3 A16 NA NPS1 status of port #3 (ON,OFF)
X_NPS14 nps1_4 A16 NA NPS1 status of port #4 (ON,OFF)
X_NPS15 nps1_5 A16 NA NPS1 status of port #5 (ON,OFF)
X_NPS16 nps1_6 A16 NA NPS1 status of port #6 (ON,OFF)
X_NPS17 nps1_7 A16 NA NPS1 status of port #7 (ON,OFF)
X_NPS18 nps1_8 A16 NA NPS1 status of port #8 (ON,OFF)
X_NPS21 nps2_1 A16 NA NPS2 status of port #1 (ON,OFF)
X_NPS22 nps2_2 A16 NA NPS2 status of port #2 (ON,OFF)
X_NPS23 nps2_3 A16 NA NPS2 status of port #3 (ON,OFF)
X_NPS24 nps2_4 A16 NA NPS2 status of port #4 (ON,OFF)
X_NPS25 nps2_5 A16 NA NPS2 status of port #5 (ON,OFF)
X_NPS26 nps2_6 A16 NA NPS2 status of port #6 (ON,OFF)
X_NPS27 nps2_7 A16 NA NPS2 status of port #7 (ON,OFF)
X_NPS28 nps2_8 A16 NA NPS2 status of port #8 (ON,OFF)
X_NPS31 nps3_1 A16 NA NPS3 status of port #1 (ON,OFF)
X_NPS32 nps3_2 A16 NA NPS3 status of port #2 (ON,OFF)
X_NPS33 nps3_3 A16 NA NPS3 status of port #3 (ON,OFF)
X_NPS34 nps3_4 A16 NA NPS3 status of port #4 (ON,OFF)
X_NPS35 nps3_5 A16 NA NPS3 status of port #5 (ON,OFF)
X_NPS36 nps3_6 A16 NA NPS3 status of port #6 (ON,OFF)
X_NPS37 nps3_7 A16 NA NPS3 status of port #7 (ON,OFF)
X_NPS38 nps3_8 A16 NA NPS3 status of port #8 (ON,OFF)
X_NULPKO nuller_pickoff_st A16 NA NULLER pickoff state (HOME, IN, OUT)
X_NULPKP nuller_pickoff F16 mm NULLER pickoff position (mm)
X_OAP1 oap1_st A16 NA First OAP state (HOME, INT, AO)
X_OAP1F oap1_f I16 step First OAP f position (step)
X_OAP1PH oap1_phi F16 deg First OAP y position (deg)
X_OAP1TH oap1_theta F16 deg First OAP x position (deg)
X_OAP4 oap4_st A16 NA OAP 4 state
X_OAP4PH oap4_phi F16 deg OAP 4 y position (deg)
X_OAP4TH oap4_theta F16 deg OAP 4 x position (deg)
X_PG1PKO PG1_pickoff A16 NA Point Grey 1 Pickoff state (IN, OUT)
X_PIAA1 piaa1_st A16 NA PIAA1 wheel state
X_PI1WHL piaa1_wheel F16 deg PIAA1 wheel position (deg)
X_PI1X piaa1_x I16 step PIAA1 wheel x position (step)
X_PI1Y piaa1_y I16 step PIAA1 wheel y position (step)
X_PIAA2 piaa2_st A16 NA PIAA2 wheel state
X_PI2F piaa2_f I16 step PIAA2 wheel foucs position (step)
X_PI2WHL piaa2_wheel F16 deg PIAA2 wheel position (deg)
X_PI2X piaa2_x I16 step PIAA2 wheel x position (step)
X_PI2Y piaa2_y I16 step PIAA2 wheel y position (step)
X_POLAR polarizer A16 NA Polarizer state (HOME, IN, OUT)
X_POLARP polarizer_theta F16 deg Polarizer angle (deg)
X_PUPIL pupil_st A16 NA Pupil wheel state
X_PUPWHL pupil_wheel F16 deg Pupil wheel angle (deg)
X_PUPX pupil_x I16 step Pupil wheel x position (step)
X_PUPY pupil_y I16 step Pupil wheel y position (step)
X_PYWCAL pywfs_cal A16 NA PYWFS calibration status (HO RM, LO RM, ...)
X_PYWCLP pywfs_cenloop A16 NA PYWFS flux centering loop status (OPEN, CLOSED)
X_PYWCOL pywfs_col I16 step PYWFS colimation position (step)
X_PYWDMO dmoffload A16 NA PYWFS DM Offload status (ON, OFF with channel)
X_PYWFCS pywfs_fcs I16 step PYWFS focus position (step)
X_PYWFPK pywfs_fcs_pickoff A16 NA PYWFS focal plane pickoff state (IN, OUT)
X_PYWFLT pywfs_filter A16 NA PYWFS filter state
X_PYWFRQ pywfs_freq I16 Hz PYWFS loop frequency (Hz)
X_PYWFST pywfs_fieldstop_st A16 NA PYWFS field stop state
X_PYWFSX pywfs_fieldstop_x F16 mm PYWFS field stop x position (mm)
X_PYWFSY pywfs_fieldstop_y F16 mm PYWFS field stop y position (mm)
X_PYWGN pywfs_gain F16 unitless PYWFS main loop gain (0-1)
X_PYWLK pywfs_leak F16 unitless PYWFS leak term (0-1)
X_PYWLP pywfs_loop A16 NA PYWFS loop status (OPEN, CLOSED)
X_PYWPKO pywfs_pickoff_st A16 NA PYWFS pickoff state
X_PYWPKP pywfs_pickoff F16 deg PYWFS pickoff position (deg)
X_PYWPLP pywfs_puploop A16 NA PYWFS pupil alignmnt loop status (OPEN, CLOSED)
X_PYWPPX pywfs_pup_x I16 step PYWFS pupil lens x position (step)
X_PYWPPY pywfs_pup_y I16 step PYWFS pupil lens y position (step)
X_PYWRAD pywfs_rad F16 mas PYWFS modulation radius (mas)
X_RCHFIB reach_fib_st A16 NA REACH fiber status
X_RCHFIF reach_fib_f F16 mm REACH fiber focus (mm)
X_RCHFIT reach_fib_theta F16 deg REACH fiber rotation (deg)
X_RCHFIX reach_fib_x I16 step REACH fiber x position (step)
X_RCHFIY reach_fib_y I16 step REACH fiber y position (step)
X_RCHOAP reach_oap_st A16 NA REACH OAP state
X_RCHOPH reach_oap_phi F16 deg REACH OAP phi angle (deg)
X_RCHOTH reach_oap_theta F16 deg REACH OAP theta angle (deg)
X_RCHPKO reach_pickoff_st A16 NA REACH pickoff state
X_RCHPKP reach_pickoff F16 mm REACH pickoff position (mm)
X_RHEPKO rhea_pickoff_st A16 NA RHEA pickoff state (HOME, IN, OUT)
X_RHEPKP rhea_pickoff F16 mm RHEA pickoff position (mm)
X_SPCFRQ sn_freq I16 Hz SPECKLE NULLING loop freqency (Hz)
X_SPCGN sn_gain F16 unitless SPECKLE NULLING loop gain (0-1)
X_SPCLP sn_loop A16 NA SPECKLE NULLING loop status (OPEN, CLOSED)
X_SRCFIB src_fib_st A16 NA internal source fiber stage (PINHOLE, IN, OUT)
X_SRCFIX src_fib_x F16 mm internal source fiber x stage position (mm)
X_SRCFIP src_fib_y F16 mm internal source fiber y stage position (mm)
X_SRCFFT src_flux_filter A16 NA internal source filter
X_SRCFIR src_flux_irnd A16 NA internal source ir nd
X_SRCFOP src_flux_optnd A16 NA internal source opt nd
X_SRCSEL src_select_st A16 NA internal source type
X_SRCSEP src_select F16 deg internal source selection position (deg)
X_STR steering_st A16 NA Steering mirror state
X_STRPHI steering_phi F16 deg steering mirror phi position (deg)
X_STRTHE steering_theta F16 deg steering mirror theta position (deg)
X_VAMFST vampires_fieldstop_st A16 NA VAMPIRES field stop state
X_VAMFSX vampires_fieldstop_x F16 mm VAMPIRES field stop x position (mm)
X_VAMFSY vampires_fieldstop_y F16 mm VAMPIRES field stop y position (mm)
X_ZAPFRQ zap_freq I16 Hz ZAP loop frequency (Hz)
X_ZAPGN zap_gain F16 unitless ZAP loop gain (0-1)
X_ZAPLP zap_loop A16 NA ZAP loop status (OPEN, CLOSED, RM, ...)
X_ZAPMOT zap_mtype A16 NA ZAP mode types (ZERNIKE, LWE, COMBO, ...)
X_ZAPNMO zap_nmodes I16 unitless ZAP number of modes 
P_RTAGL1 F16 deg Angle of retarder1 (deg)
RET-ANG1 F16 deg Position angle of first retarder plate (deg)
P_RTAGL2 F16 deg Angle of retarder2 (deg)
RET-ANG2 F16 deg Position angle of second retarder plate (deg)
P_STGPS1 F16 mm Position of stage1 (mm)
P_STGPS2 F16 mm Position of stage2 (mm)
P_STGPS3 F16 mm Position of stage3 (mm)
INSTRUME A8 NA Instrument name
POL-ANG1 I16 deg Position angle of first polarizer (deg)
POLARIZ1 A16 NA Identifier of first polarizer
RETPLAT1 A16 NA Identifier of first retarder plate
RETPLAT2 A16 NA Identifier of second retarder plate
Y_LSRALM A16 NA laser alarms
Y_LSRENB A16 NA is laserState enabled
Y_LSRPWR I16 percent laser power"""

DEFAULT_CARDSET = {}
for krec in _KEYSDATA.split('\n'):
    k, _, rest = krec.partition(' ')
    typ, _, rest = rest.partition(' ')
    unit, _, comment = rest.partition(' ')
    DEFAULT_CARDSET[k] = Card(keyword=k, value='', comment=comment)


def build_header(metadata=None):
    """ Build a header with all of the keys and their default values with optional updates via metadata. Additional
    novel cards may be included via metadata as well.

    metadata is a dict of keyword:value|Card pairs. Value for keys in the default cardset, Cards for novel keywords.

    raises ValueError if any novel keyword is not a Card
    """
    if metadata is not None:
        unix_start = metadata['UNIXSTR']
        unix_stop = metadata['UNIXEND']
        TIME_KEYS = ['HST-END', 'HST-STR', 'MJD-END', 'MJD-STR', 'UT-END', 'UT-STR']
        if not unix_start and not unix_stop:
            assert [metadata[key] is not None for key in TIME_KEYS], 'header must contain UNIXSTR, UNIXEND or all of {}'.format(TIME_KEYS)
        else:
            hst = TimezoneInfo(utc_offset=-10*u.hour)
            t1 = Time(unix_start, format='unix')
            t2 = Time(unix_stop, format='unix')
            dt1 = datetime.fromtimestamp(t1.value, tz=hst)
            dt2 = datetime.fromtimestamp(t2.value, tz=hst)
            metadata['HST-END'] = '{:02d}:{:02d}:{:02d}.{:02d}'.format(dt2.hour, dt2.day, dt2.second, dt2.microsecond)
            metadata['HST-STR'] = '{:02d}:{:02d}:{:02d}.{:02d}'.format(dt1.hour, dt1.day, dt1.second, dt1.microsecond)
            metadata['MJD-END'] = t2.mjd
            metadata['MJD-STR'] = t1.mjd
            metadata['UT-END'] = t2.iso[-12:-1]
            metadata['UT-STR'] = t1.iso[-12:-1]

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


def validate_metadata_dict(md, warn=True, error=False):
    missing = []
    for k in DEFAULT_CARDSET:
        if k not in md:
            missing.append(k)
    if warn and missing:
        getLogger(__name__).warning('Key(s) {} missing from {}'.format(str(missing), md))
    if error and missing:
        raise KeyError('Missing keys: {}'.format(str(missing)))

    return len(missing) != 0


def observing_metadata_for_timerange(start, duration, metadata_source=None):
    """
    Metadata that goes into an H5 consists of records within the duration

    requires metadata_source be an indexable iterable with an attribute utc pointing to a datetime
    """
    if not metadata_source:
        metadata_source = load_observing_metadata() #TODO load_observing_metadata requires a path
    # Select the nearest metadata to the midpoint
    start = datetime.fromtimestamp(start)
    time_since_start = np.array([(md.utc - start).total_seconds() for md in metadata_source])
    ok, = np.where((time_since_start < duration.duration) & (time_since_start >= 0))
    mdl = [metadata_source[i] for i in ok]
    return mdl


def parse_obslog(file):
    """Return a list of configthings for each record in the observing log filterable on the .utc attribute"""
    with open(file, 'r') as f:
        lines = f.readlines()
    ret = []
    for l in lines:
        ct = mkidcore.config.ConfigThing(json.loads(l).items())
        ct.register('utc', datetime.strptime(ct.utc, "%Y%m%d%H%M%S"), update=True)
        ret.append(ct)
    return ret


def load_observing_metadata(path, files=tuple(), use_cache=True):
    """Return a list of mkidcore.config.ConfigThings with the contents of the metadata from observing log files"""
    global _metadata

    # _metadata is a dict of file: parsed_file records
    files = set(files)
    if path:
        files.update(glob(os.path.join(path, 'obslog*.json')))

    if use_cache:
        for f in files:
            if f not in _metadata:
                _metadata[f] = mkidcore.metadata.parse_obslog(f)
        metad = _metadata
    else:
        metad = {f: mkidcore.metadata.parse_obslog(f) for f in files}

    metadata = []
    for f in files:
        metadata += metad[f]

    return metadata


