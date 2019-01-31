from __future__ import print_function
import re, os
import ruamel.yaml
from pkg_resources import Requirement, resource_filename
from mkidcore.utils import caller_name
from mkidcore.corelog import getLogger, setup_logging
from multiprocessing import RLock
import copy
try:
    from StringIO import StringIO
    import ConfigParser as configparser
except ImportError:
    import configparser
    from io import StringIO

RESERVED = ('._c', '._a')

yaml = ruamel.yaml.YAML()
yaml_object = ruamel.yaml.yaml_object


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
    .update('a.b.c.d', thingB), mutated is partially supported e.g .a.b.c.d.append(foo) works if
    a.b.c.d is a list, but .update would be preferred. It is best not to think of this as a
    dictionary at all!

    .get may be used to support both default values (aside from None, which is not supported at
    present) and inheritance, though inheritance is no supported across nodes of other type.

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
    def __init__(self, *args):
        """
        If initialized with a list of tuples cannonization is not enforced on values
        in general you should call ConfigThing().registerfromkvlist() as __init__ will not
        break dotted keys out into nested namespaces.
        """
        if args:
            super(ConfigThing, self).update([(cannonizekey(k), v) for k, v in args[0]])
        self._lock = RLock()
        self.__frozen = True

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_mapping(cls.yaml_tag, dict(node))

    @classmethod
    def from_yaml(cls, loader, node):
        # NB:
        # loader is ruamel.yaml.constructor.RoundTripConstructor
        # node is MappingNode(tag=u'!configdict', value=[(ScalarNode(tag=u'tag:yaml.org,2002:str', value=u'initgui'),
        # cls is ConfigThing
        d = loader.construct_pairs(node)  #WTH this one line took half a day to get right
        d = cls(d)
        d._setlock()
        return d
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

    def __getstate__(self):
        d = self.__dict__.copy()
        d.pop('_lock')
        return d

    def __setstate__(self, state):
        self.__dict__ = state
        self._setlock()

    def dump(self):
        """Dump the config to a YAML string"""
        with self._lock:
            out = StringIO()
            yaml.dump(self, out)
            return out.getvalue()

    def __getattr__(self, key):
        """This implements dot notation of the config tree without default inheritance

        In a.b.c Python resolves a.b by calling this function then calls .c on the return of a.b,
        so it is nontrivial for the a.b code to trap any KeyError that would be raised in looking for .c
        and thus silently returning a.c. This is probably for the best as it makes the intent more
        explicit. Regardless no config inheritance when accessing with dot notation
        """
        if key.startswith('__'):
            try:
                return self.__dict__[key]
            except KeyError:
                raise AttributeError(key)
        else:
            with self._lock:
                k1, _, krest = key.partition('.')
                return self[k1][krest] if krest else self[k1]

    def __setattr__(self, key, value):
        if self.__frozen and not key.startswith('_'):
            raise AttributeError('Use register to add config attributes')
        else:
            object.__setattr__(self, key, value)

    def get(self, name, default=None, inherit=True, all=False):
        """This implements do notation of the config tree with optional inheritance and optional
        default value. Default values other han None take precedence over inheritance.

        all will return a tuple (value, comment, allowed

        The empty string is a convenience for returning self

        Inheritance means that if cfg.beam.sweep.imgdir doesn't exist but
        cfg.beam.imgdir (or then cfg.imgdir) would be returned provided they are leafs
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
                    allowed = self[k1 + '._a']
                except:
                    pass
                return self[key], comment, allowed
            else:
                return self[key]


    def __contains__(self, k):
        """Contains only implements explicit keys, inheritance is not checked."""
        with self._lock:
            k1, _, krest = k.partition('.')
            if super(ConfigThing, self).__contains__(k1):
                if krest:
                    return krest in self[k1]
                return True
            else:
                return False

    def registered(self, key, error=False):
        if key not in self:
            if error:
                raise KeyError("Setting '{}' is not registered.".format(key))
            return False
        return True

    def keyisvalid(self, key, error=False):
        if key.endswith(RESERVED) or key.startswith('.') or key.endswith('.'):
            if error:
                raise KeyError("Setting keys may not end with '{}'.".format(RESERVED))
            else:
                return False
        return True

    def keys(self):
        """Hide reserved keys"""
        return filter(lambda x: not (isinstance(x,str) and x.endswith(RESERVED)),
                      super(ConfigThing, self).keys())

    def items(self):
        """Hide reserved keys"""
        return filter(lambda x: not (isinstance(x[0],str) and x[0].endswith(RESERVED)),
                      super(ConfigThing, self).items())

    def update(self, key, value, comment=None):
        """ update will register iff the update would override an inherited value  e.g. if roaches.ip is set but
        roaches.r114.ip is not  roaches.r114.ip would yield roaches.ip but updateing roaches.r114.ip would create a
        new setting unique to roaches.r114

        """
        with self._lock:
            if self.registered(key):
                self._update(key, value, comment=comment)
            else:
                try:
                    _, c, a = self.get(key, inherit=True, all=True)
                    self._register(key, value, allowed=a, comment=c)
                except KeyError:
                    raise KeyError("Setting '{}' is not registered or inherited".format(key))

    def _update(self, key, value, comment=None, ):
        k1, _, krest = key.partition('.')

        if krest:
            self[k1]._update(krest, value, comment=comment)
        else:
            # TODO add checking against allowed
            self[k1] = value
            if comment is not None:
                self._dict[k1+'._c'] = comment

    def _register(self, key, initialvalue, allowed=None, comment=None):
        k1, _, krest = key.partition('.')
        if krest:
            cd = self.get(k1, ConfigThing())
            cd._register(krest, initialvalue, allowed=allowed, comment=comment)
            self[k1] = cd
            # getLogger('MKIDConfig').debug('registering {}.{}={}'.format(k1,krest, initialvalue))
        else:
            # getLogger('MKIDConfig').debug('registering {}={}'.format(k1, initialvalue))
            self[k1] = initialvalue
            if comment:
                self[key + '._c'] = comment
            if allowed is not None:
                self[key + '._a'] = allowed
        return self

    def comment(self, key):
        self.keyisvalid(key, error=True)
        self.registered(key, error=True)
        try:
            tree,_,leaf=key.rpartition('.')
            return self.get(tree)[leaf+'._c']
        except KeyError:
            return None

    def register(self, key, initialvalue, allowed=None, comment=None, update=False):
        """Registers a key, true iff the key was registered. Does not update an existing key unless
        update is True."""
        with self._lock:
            self.keyisvalid(key, error=True)
            ret = not self.registered(key)
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
                d = self.get(root, {})
                for k in [end]+[end+r for r in RESERVED]:
                    d.pop(k, None)
            else:
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
        """loads all data in the config parser object, overwriting any that already exist"""
        with self._lock:
            if namespace is None:
                namespace = caller_name().lower()
                getLogger('MKIDConfig').debug('Assuming namespace "{}"'.format(namespace))
            namespace = namespace if namespace.endswith('.') else (namespace + '.' if namespace else '')
            for k, v in cp.items('DEFAULT'):
                self.register(cannonizekey(namespace+k), cannonizevalue(v), update=True)
            for s in cp.sections():
                ns = namespace + s + '.'
                for k, v in cp.items(s):
                    self.register(cannonizekey(ns + k), cannonizevalue(v), update=True)
            return self

    def registerfromkvlist(self, kv, namespace=None):
        """loads all data in the keyvalue iterable, overwriting any that already exist"""
        with self._lock:
            if namespace is None:
                namespace = caller_name().lower()
                getLogger('MKIDConfig').debug('Assuming namespace "{}"'.format(namespace))
            namespace = namespace if namespace.endswith('.') else (namespace + '.' if namespace else '')
            for k, v in kv:
                self.register(cannonizekey(namespace + k), cannonizevalue(v), update=True)
            return self

    def _setlock(self, lock=None):
        self._lock = lock if lock is not None else RLock()
        for k,v in self.items():
            if isinstance(v, ConfigThing):
                v._setlock(lock=self._lock)


def cannonizekey(k):
    """Enforce cannonicity of config keys lowercase, no spaces (replace with underscore)"""
    return k.strip().lower().replace(' ', '_')


def cannonizevalue(v):
    try:
        v=dequote(v)
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
    Load an old config such that settings are accessible by namespace.section.key
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


def _consolidateconfig(cd):
    """Merge Roach and sweep sections into objects"""
    roaches, sweeps = {}, []
    for k in cd.keys():
        if 'roach_' in k:
            _, _, rnum = k.partition('_')
            cd.register('roachnum',rnum)
            roaches[rnum] = cd[k]
            cd.unregister(k)
        if re.match('sweep\d+', k):
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



# def _include_constructor(self, node):
#     print(node)
#     if isinstance(node, ruamel.yaml.ScalarNode):
#         with open(self.construct_scalar(node), 'r') as f:
#             return self.construct_document(f)
#     elif isinstance(node, ruamel.yaml.SequenceNode):
#         result = []
#         for filename in self.construct_sequence(node):
#             with open(filename, 'r') as f:
#                 result += self.construct_document(f)
#         return result
#     elif isinstance(node, ruamel.ruamel.MappingNode):
#         result = {}
#         for k, v in self.construct_mapping(node).iteritems():
#             with open(v, 'r') as f:
#                 result[k] = self.construct_document(f)
#         return result
#     else:
#         print("Error:: unrecognised node type in !include statement")
#         raise ruamel.yaml.constructor.ConstructorError
# ruamel.yaml.add_constructor(u'!include', _include_constructor)


# @yaml_object(yaml)
# class IncludeObject(object):
#     yaml_tag = u'!include'
#
#     def __init__(self, foo):
#         print(foo)
#         # self._root = os.path.split(stream.name)[0]
#
#     @classmethod
#     def from_yaml(cls, loader, node):
#         if isinstance(node, ruamel.yaml.ScalarNode):
#             import ipdb;ipdb.set_trace()
#             with open(loader.construct_scalar(node), 'r') as f:
#                 foo=loader.get_single_data(f)
#                 foo = yaml.load(f)
#         elif isinstance(node, ruamel.yaml.SequenceNode):
#             result = []
#             for filename in loader.construct_sequence(node):
#                 with open(filename, 'r') as f:
#                     result += yaml.load(f)
#             return result
#         elif isinstance(node, ruamel.yaml.MappingNode):
#             result = {}
#             for k, v in loader.construct_mapping(node).iteritems():
#                 with open(v, 'r') as f:
#                     result[k] = yaml.load(f)
#             return result
#         else:
#             raise ruamel.yaml.YAMLError("Unrecognised node type in !include")
#
#
# yaml.register_class(IncludeObject)


def load(file, namespace=None):
    if not isinstance(file, str):
        return file

    if file.lower().endswith(('yaml', 'yml')):
        with open(file, 'r') as f:
            ret = yaml.load(f)
        if 'roaches' in ret: #This is a horribly, dastardly dirty hack
            with open(ret.roaches.value, 'r') as f:
                ret.update('roaches', yaml.load(f))
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

    _consolidateconfig(config.beammap.sweep)
    _consolidateconfig(config.templar)
    _consolidateconfig(config.initgui)
    _consolidateconfig(config.dashboard)

    return config



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
