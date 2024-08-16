from __future__ import print_function
import re
import ruamel.yaml
from pkg_resources import Requirement, resource_filename
from mkidcore.utils import caller_name
from mkidcore.corelog import getLogger
from multiprocessing import RLock
import copy
import time
import os
from datetime import datetime
try:
    from StringIO import StringIO
    import ConfigParser as configparser
except ImportError:
    import configparser
    from io import StringIO

RESERVED = ('._c', '._a')  #Internal keys hidden from the user for storing comments and

yaml = ruamel.yaml.YAML()
yaml_object = ruamel.yaml.yaml_object


class _BeamDict(dict):
    def __missing__(self, key):
        bfile = os.path.join(os.path.dirname(__file__), key.lower()+'.bmap')
        self[key] = bfile
        return bfile


DEFAULT_BMAP_CFGFILES = _BeamDict()


def defaultconfigfile():
    return resource_filename(Requirement.parse("mkidcore"), "default.yml")


def extract_from_node(loader, keys, node):
    """attempt extraction of keys from a ruamel.yaml mapping node and return as a dict,
    does not support tagged types"""
    d = {}
    listkeys = [keys] if not isinstance(keys, (list, tuple)) else keys

    for k in listkeys:
        try:
            d[k] = [nv.value if '!' not in nv.tag else loader.construct_object(nv, deep=True)
                    for nk, nv in node.value if nk.value == k][0]
        except IndexError:
            pass
    return d


class ConfigThing(dict):
    """
    This Class implements a YAML-backed, nestable configuration object. The general idea is that
    settings are registered, e.g. .register('a.b.c.d', thingA), updated e.g.
    .update('a.b.c.d', thingB), mutation is partially supported e.g .a.b.c.d.append(foo) works if
    a.b.c.d is a list, but .update would be preferred.

    .get may be used to support both default values (aside from None, which is not supported at
    present) and inheritance, though inheritance is not supported across nodes of other type.
    TODO what does this mean

    To handle defaults consider, e.g.
    for thing in config.namespace.thinglist:
        try:
            foo = thing.datafile
        except KeyError:
            foo = config.namespace.defaultdatafile

    Under the hood this is implemented as a subclass of dictionary so many tab completions show
    up as for python dictionaries and [] access will work...use these with caution! It is probably
    best not to think of this as a dictionary at all!

    Some functionality that isn't really implemented yet because it isn't clear HOW we will
    want it yet:
     -1 Updating a default load of settings with a subset from a user's file.
     -2 Controlling the breakup of the settings into multiple files.
     implement __str__

    """
    yaml_tag = u'!configdict'
    __frozen = False
    REQUIRED_KEYS = tuple()

    def __init__(self, *args, **kwargs):
        """
        If initialized with a list of tuples cannonization is not enforced on values
        in general you should call ConfigThing().registerfromkvlist() as __init__ will not
        break dotted keys out into nested namespaces.
        """
        lock = kwargs.pop('lock', None)
        if args:
            #TODO if args has one element and that element is a list of kv pairs then we need to update the
            # caller or update here to support the extra layer as well
            super(ConfigThing, self).update([(cannonizekey(k), v) for k, v in args])
        self._lock = RLock() if lock is None else lock
        self.__frozen = True

    @classmethod
    def to_yaml(cls, representer, node):
        import ruamel.yaml.comments
        cm = ruamel.yaml.comments.CommentedMap(node.asdict(keep_internal=False))
        for k, v in node.comment_dict().items():
            cm.yaml_add_eol_comment(v, key=k)
        return representer.represent_mapping(cls.yaml_tag, cm)

        # return representer.represent_mapping(cls.yaml_tag, node.asdict(keep_internal=False))

    @classmethod
    def from_yaml(cls, loader, node):
        # NB:
        # loader is ruamel.yaml.constructor.RoundTripConstructor
        # node is MappingNode(tag=u'!configdict', value=[(ScalarNode(tag=u'tag:yaml.org,2002:str', value=u'initgui'),
        # cls is ConfigThing
        d = cls(*loader.construct_pairs(node))
        d._setlock()
        return d

    def comment_dict(self):
        """return a dictionary of comments for the keys. will only include keys at the level e.g. if this.key is a
        nested config and this.key.value has a comment that comment will not be included, Get it by calling
        this.key.comment_dict() """
        return {k.partition('.')[0]: v for k, v in super().items() if '._c' in k}

    def asdict(self, keep_internal=False):
        """Return a copy of the config as a dictionary, unless keep_internal =True the dict will be purged of
        all ._c and ._a keys"""
        if keep_internal:
            return dict(self)
        else:
            return {k: v for k, v in super().items() if '._' not in k}

    #
    # def __copy__(self):
    #     ret = super(ConfigThing, self).__copy__()
    #     ret._
    #     return super(ConfigThing, self).__copy__()
    #
    # def __deepcopy__(self, memodict={}):
    #     ret = super(ConfigThing, self).__deepcopy__()
    #     copy.deepcopy(comp, memodict)
    """
    In order for a class to define its own copy implementation, it can define special methods __copy__() 
    and __deepcopy__(). The former is called to implement the shallow copy operation; no additional arguments 
    are passed. The latter is called to implement the deep copy operation; it is passed one argument, the memo 
    dictionary. If the __deepcopy__() implementation needs to make a deep copy of a component, it should call 
    the deepcopy() function with the component as first argument and the memo dictionary as second argument.
    """

    def copy(self):
        c = copy.deepcopy(self)
        c._setlock()
        return c

    def dump(self):
        """Dump the config to a YAML string"""
        with self._lock:
            out = StringIO()
            yaml.dump(self, out)
            return out.getvalue()

    def __getstate__(self):
        d = self.__dict__.copy()
        d.pop('_lock')
        return d

    def __setstate__(self, state):
        self.__dict__ = state
        self._setlock()

    def __getattr__(self, key):
        """
        Support dot notation of the config tree without default inheritance

        In a.b.c Python resolves a.b by calling this function on a then calls .c on the return of a.b,
        so it is nontrivial for the a.b code to trap any KeyError that would be raised in looking for .c
        and thus silently returning a.c. This is probably for the best as it makes the intent more
        explicit. Regardless no config inheritance when accessing with dot notation.

        Inheritance could be effected with a parital and some dynamic function wrapper but that adds
        complexity.
        """
        if key.startswith('__'):
            try:
                return self.__dict__[key]
            except KeyError:
                raise AttributeError(key)
        else:
            with self._lock:
                k1, _, krest = key.partition('.')
                try:
                    return self[k1][krest] if krest else self[k1]
                except KeyError:
                    raise AttributeError('{} not found. At this level: {}'.format(key, list(self.keys())))

    def __setattr__(self, key, value):
        if self.__frozen and not key.startswith('_'):
            if key in self:
                raise AttributeError('Use update to change configuration settings')
            else:
                raise AttributeError('Use register to add configuration settings')
        else:
            object.__setattr__(self, key, value)

    def __contains__(self, k):
        """Contains only implements explicit keys, inheritance is not checked."""
        with self._lock:
            k1, _, krest = k.partition('.')
            if krest in ('_a', '_c'):
                k1 = k
                krest = ''
            if super(ConfigThing, self).__contains__(k1):
                if krest:
                    return krest in self[k1]
                return True
            else:
                return False

    def get(self, name, default=None, inherit=True, all=False):
        """
        Retrieve a config key (i.e. a.config.namespace.key), with options for defaults and inheritance
        (i.e. a.config.key).

        This implements dot notation of the config tree with optional inheritance and optional
        default value. If a default is set (aside from None) it takes precedence over inherited values.

        all will return a tuple (value, comment, allowed)

        The empty string is a convenience for returning self

        Inheritance means that if cfg.beam.sweep.imgdir doesn't exist then cfg.beam.imgdir (or then cfg.imgdir)
        would be in its place, provided they are a leaf. If a name in the parent namespace is a config node
        then it is considered something discrete and not name is treated as not found.
        """
        with self._lock:
            k1, _, krest = name.partition('.')

            try:
                next = self[k1]
            except KeyError as e:
                if default is None:
                    raise e
                else:
                    next = default

            if not krest:
                if all:
                    comment, allowed = None, None
                    try:
                        comment = self[k1 + '._c']
                    except:
                        pass
                    try:
                        allowed = self[k1 + '._a']
                    except:
                        pass
                    return next, comment, allowed
                else:
                    return next
            else:  # fetch from child
                try:
                    return next.get(krest, default, inherit, all)
                except KeyError as e:
                    if default is not None:
                        return default
                    if not inherit:
                        raise e

            # inherit from self
            key = krest.rpartition('.')[2]
            if all:
                comment = None
                allowed = None
                try:
                    comment = self[key + '._c']
                except:
                    pass
                try:
                    allowed = self[key + '._a']
                except:
                    pass
                return self[key], comment, allowed
            else:
                return self[key]

    def keyisvalid(self, key, error=False):
        """Return true iff key may be used as a key. Keys must be strings"""
        if key.endswith(RESERVED) or key.startswith('.') or key.endswith('.'):
            if error:
                raise KeyError("Setting keys may not end with '{}'.".format(RESERVED))
            else:
                return False
        return True

    def keys(self):
        """Hide reserved keys"""
        return filter(lambda x: not (isinstance(x, str) and x.endswith(RESERVED)),
                      super(ConfigThing, self).keys())

    def items(self):
        """Hide reserved keys"""
        return filter(lambda x: not (isinstance(x[0],str) and x[0].endswith(RESERVED)),
                      super(ConfigThing, self).items())

    def update(self, key, value, comment=None):
        """ update will register iff the update would override an inherited value  e.g. if roaches.ip is set but
        roaches.r114.ip is not  roaches.r114.ip would yield roaches.ip but updating roaches.r114.ip would create a
        new setting unique to roaches.r114

        """
        with self._lock:
            if key in self:
                self._update(key, value, comment=comment)
            else:
                try:
                    _, c, a = self.get(key, inherit=True, all=True)
                    self._register(key, value, allowed=a, comment=c)
                except KeyError:
                    raise KeyError("Setting '{}' is not registered or inherited".format(key))

    def _update(self, key, value, comment=None):
        k1, _, krest = key.partition('.')

        if krest:
            self[k1]._update(krest, value, comment=comment)
        else:
            if not self.allowed(key, value):
                raise ValueError('{} is not an allowed value for {}'.format(value, key))
            self[k1] = value
            if comment is not None:
                self[k1+'._c'] = comment

    def allowed(self, key, value):
        if key+'._a' in self:
            getLogger(__name__).warning(str(key)+' has restrictions no allowed values but checking has not yet been '
                                        'implemented')
        return True

    def _register(self, key, initialvalue, allowed=None, comment=None):
        k1, _, krest = key.partition('.')
        if krest:
            cd = self.get(k1, ConfigThing(lock=self._lock))
            cd._register(krest, initialvalue, allowed=allowed, comment=comment)
            self[k1] = cd
            getLogger(__name__).debug('registered {}.{}={}'.format(k1, krest, initialvalue))
        else:
            if isinstance(initialvalue, ConfigThing):
                getLogger(__name__).debug('Updating lock for key {}'.format(key))
                initialvalue._setlock(lock=self._lock)

            self[k1] = initialvalue
            if comment:
                self[key + '._c'] = comment
            if allowed is not None:
                self[key + '._a'] = allowed
            getLogger(__name__).debug('registering {}={}'.format(k1, initialvalue))
        return self

    def comment(self, key):
        self.keyisvalid(key, error=True)
        if not key in self:
            raise KeyError("Setting '{}' is not registered.".format(key))
        try:
            tree, _, leaf = key.rpartition('.')
            return self.get(tree)[leaf+'._c']
        except KeyError:
            return None

    def register(self, key, initialvalue, allowed=None, comment=None, update=False):
        """Registers a key, true iff the key was registered. Does not update an existing key unless
        update is True."""
        with self._lock:
            self.keyisvalid(key, error=True)
            ret = not (key in self)
            if not ret and not update:
                return ret
            self._register(key, initialvalue, allowed=allowed, comment=comment)
            return ret

    def registersubdict(self, key, configdict):
        with self._lock:
            self[key] = configdict

    def unregister(self, key):
        with self._lock:
            self.keyisvalid(key, error=True)
            if '.' in key:
                root,_,end = key.rpartition('.')
                # d = self.get(root, {})
                # for k in [end]+[end+r for r in RESERVED]:
                #     d.pop(k, None)
                self.get(root).unregister(end)
            else:
                if key in self.REQUIRED_KEYS:
                    raise KeyError('{} is required and may not be deregistered'.format(key))
                for k in [key]+[key+r for r in RESERVED]:
                    self.pop(k, None)

    def todict(self):
        with self._lock:
            ret = dict(self)
            for k,v in ret.items():
                if isinstance(v, ConfigThing):
                    ret[k] = v.todict()
            return ret

    def save(self, file):
        with self._lock:
            with open(file, 'w') as f:
                yaml.dump(self, f)

    def registerfromconfigparser(self, cp, namespace=None):
        """
        Build a key:value list from a config parser object anre register with registerfromkvlist.
        Keys in DEFAULT will be placed at namespace.key, keys in sections will be placed at namespace.section.key

        Uses the callers name as the default namespace name.

        returns self. Threadsafe.
        """
        if namespace is None:
            namespace = caller_name().lower()
            getLogger(self.__class__).debug('Assuming namespace "{}"'.format(namespace))

        toreg = ([(k, v) for k, v in cp.items('DEFAULT')] +
                 [(s + '.' + k, v) for s in cp.sections() for k, v in cp.items(s)])

        return self.registerfromkvlist(toreg, namespace=namespace)

    def registerfromkvlist(self, kv, namespace=None):
        """
        Register all (key, value) pairs in the kv iterable. Existing keys will be updated.

        Uses the callers name as the default namespace name.

        returns self. Threadsafe.
        """
        with self._lock:
            if namespace is None:
                namespace = caller_name().lower()
                getLogger(self.__class__).debug('Assuming namespace "{}"'.format(namespace))

            namespace = namespace if namespace.endswith('.') else (namespace + '.' if namespace else '')
            for k, v in kv:
                self.register(cannonizekey(namespace + k), cannonizevalue(v), update=True)
            return self

    def _setlock(self, lock=None):
        """ Set the RLock for self and all nested configs"""
        self._lock = lock if lock is not None else RLock()
        for k,v in self.items():
            if isinstance(v, ConfigThing):
                v._setlock(lock=self._lock)


def cannonizekey(k):
    """ Enforce cannonicity of config keys lowercase, no spaces (replace with underscore)"""
    return k.strip().lower().replace(' ', '_')


def cannonizevalue(v):
    """ Make v into a float or int if possible, else remove any extraneous quotation marks from strings """
    if isinstance(v, (float, int)):
        return v
    try:
        v = dequote(v)
    except:
        pass
    try:
        if '.' in v:
            return float(v)
    except:
        pass
    try:
        return int(v)
    except:
        pass
    return v


def dequote(v):
    """Change strings like "'foo'" to "foo"."""
    if (v[0] == v[-1]) and v.startswith(("'", '"')):
        return v[1:-1]
    else:
        return v


def importoldconfig(config, cfgfile, namespace=None):
    """
    Load an old config file (.cfg) into the ConfigDict config such that settings are accessible by
    namespace.section.key
    Sections are coerced to lowercase and spaces are replaced with underscores.
    The default section keys are accessible as namespace.key. If called on successive
    configfiles any collisions will be handled silently by adopting the value
    of the most recently loaded config file. All settings are imported as strings.
    """
    cp = loadoldconfig(cfgfile)
    config.registerfromconfigparser(cp, namespace)


def loadoldconfig(cfgfile):
    """Get a configparser instance from an old-style config, including files that were handled by readdict"""
    cp = configparser.ConfigParser()
    try:
        cp.read(cfgfile)
    except configparser.MissingSectionHeaderError:
        #  Some files aren't configparser dicts, pretend they have a DEFUALTS section only
        with open(cfgfile, 'r') as f:
            data = f.readlines()

        for l in (l for l in data if l and l[0]!='#'):
            k, _, v =l.partition('=')
            if not k.strip():
                continue
            cp.set('DEFAULT', k.strip(), v.strip())
    return cp


def _consolidate_roach_config(cd):
    """Merge Roach and sweep sections into objects"""
    roaches, sweeps = {}, []
    for k in cd.keys():
        if 'roach_' in k:
            _, _, rnum = k.partition('_')
            cd.register('roachnum',rnum)
            roaches[rnum] = cd[k]
            cd.unregister(k)
        if re.match(r'sweep\d+', k):
            sweeps.append(cd[k])
            getLogger('mkidcore.config').debug('Matched sweep#: {}'.format(cd[k]))
            cd[k].register('num', int(k[5:]))
            cd.unregister(k)
    if roaches:
        assert 'roaches' not in cd
        cd.register('roaches', roaches)
    if sweeps:
        assert 'sweeps' not in cd
        cd.register('sweeps', sweeps)


yaml.register_class(ConfigThing)


def load(file, namespace=None):
    if not isinstance(file, str):
        return file

    if file.lower().endswith(('yaml', 'yml')):
        with open(file, 'r') as f:
            ret = yaml.load(f)
        try:
            if os.path.exists(ret.roaches.value):
                roach_f = ret.roaches.value
            else:
                roach_f = os.path.join(os.path.dirname(file), ret.roaches.value)
            with open(roach_f, 'r') as f:
                ret.update('roaches', yaml.load(f))
        except (KeyError, AttributeError):
            pass
        return ret
    elif namespace is None:
        raise ValueError('Namespace required when loading an old config')
    else:
        return ConfigThing().registerfromconfigparser(loadoldconfig(file), namespace)


def ingestoldconfigs(cfiles=('beammap.align.cfg', 'beammap.clean.cfg', 'beammap.sweep.cfg', 'dashboard.cfg',
                             'initgui.cfg', 'powersweep.ml.cfg',  'templar.cfg')):
    config = ConfigThing()
    for cf in cfiles:
        cp = loadoldconfig(cf)
        config.registerfromconfigparser(cp, cf[:-4])

    _consolidate_roach_config(config.beammap.sweep)
    _consolidate_roach_config(config.templar)
    _consolidate_roach_config(config.initgui)
    _consolidate_roach_config(config.dashboard)

    return config


def tagstr(x, cfg=None):
    """tag a string with canonical things {time}=time.time(), {utc}=UTC timestamp,
    {night}=UTCYYYMMDD of night start, {instrument}=MEC|DARKNESS, requires a config with .instrument.name"""
    #TODO implement night
    try:
        inst = cfg.instrument.name
    except (AttributeError, KeyError):
        inst = 'None'

    return x.format(time=int(time.time()), utc=datetime.utcnow().strftime("%Y%m%d%H%M"),
                    night='<UTCNight>', instrument=inst)

#TODO test .c .lc, .a

# #---------------------
#
# from glob import glob
# import os
# import StringIO
#
# cfiles = glob('/Users/one/ucsb/MKIDPipelineProject/data/*.cfg')
#
#
# for cf in cfiles:
#     importoldconfig(config, cf, os.path.basename(cf)[:-4])
#
# cp = configparser.ConfigParser(); cp.read(cfiles[-1])
# rs=[ConfigThing().registerfromkvlist(cp.items(rname),'') for rname in cp.sections() if 'Roach' in rname]
# config.register('templarconf.roaches', rs)
#
# out = StringIO.StringIO()
# yaml.dump(config, out)
#
# x = yaml.load(out.getvalue())
# # # #
# # # x['templarconf.roaches'][0].roachnum
