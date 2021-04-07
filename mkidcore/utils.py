from functools import wraps
import inspect
import multiprocessing as mp
import astropy
from logging import getLogger
import ast

_manager = None


def parse_ditherlog(file):
    parsed_log = {}
    with open(file, 'r') as f:
        lines = f.readlines()
    for i, l in enumerate(lines):
        if not l.strip().startswith('starts'):
            continue
        try:
            assert lines[i + 1].strip().startswith('ends') and lines[i + 2].strip().startswith('path')
            starts = ast.literal_eval(l.partition('=')[2])
            ends = ast.literal_eval(lines[i + 1].partition('=')[2])
            pos = ast.literal_eval(lines[i + 2].partition('=')[2])
        except (AssertionError, IndexError, ValueError, SyntaxError):
            # Bad dither
            getLogger(__name__).error('Dither l{}:{} corrupt'.format(i - 1, lines[i - 1]))
            continue
        parsed_log[(min(starts), max(ends))] = starts, ends, pos
    return parsed_log


def manager(*args, **kwargs):
    global _manager
    if _manager is None:
        _manager = mp.Manager(*args, **kwargs)
    return _manager


def getnm(x):
    try:
        return astropy.units.Unit(x).to('nm')
    except astropy.units.UnitConversionError:
        return float(x)


def query(question, yes_or_no=False, default="no"):
    """
    Ask a question via raw_input() and return their answer.
    "question" is a string that is presented to the user.
    "yes_or_no" specifies if it is a yes or no question
    "default" is the presumed answer if the user just hits <Enter>.
    It must be "yes" (the default), "no" or None (meaning an answer is required of
    the user). Only used if yes_or_no=True.
    The "answer" return value is the user input for a general question. For a yes or
    no question it is True for "yes" and False for "no".
    """
    if yes_or_no:
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if not yes_or_no:
        prompt = ""
        default = None
    elif default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)
    while True:
        print(question + prompt)
        choice = input().lower()
        if not yes_or_no:
            return choice
        elif default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' (or 'y' or 'n').")


def freeze(cls, msg="Class {cls} is frozen. Cannot set {key} = {value}"):
    """Wrap and freeze a class so that a=A(); a.foo=4 fails if .foo isn't defined by the class """
    cls.__frozen = False

    def frozensetattr(self, key, value):
        if self.__frozen and not hasattr(self, key):
            raise AttributeError(msg.format(cls=cls.__name__, key=key, value=value))
        else:
            object.__setattr__(self, key, value)

    def init_decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            func(self, *args, **kwargs)
            self.__frozen = True
        return wrapper

    cls.__setattr__ = frozensetattr
    cls.__init__ = init_decorator(cls.__init__)

    return cls


def caller_name(skip=2):
    """Get a name of a caller in the format module.class.method

       `skip` specifies how many levels of stack to skip while getting caller
       name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

       An empty string is returned if skipped levels exceed stack height
    """
    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
        return ''
    parentframe = stack[start][0]

    name = []
    module = inspect.getmodule(parentframe)
    # `modname` can be None when frame is executed directly in console
    if module:
        name.append(module.__name__)
    # detect classname
    if 'self' in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        #      be just a function call
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':  # top level usually
        name.append(codename)  # function or a method
    del parentframe
    return ".".join(name)


def derangify(s,delim=','):
    """
    Takes a range in form of "a-b" and generate a list of numbers between
    a and b inclusive.
    Also accepts comma separated ranges like "a-b,c-d,f" will build a
    list which will include
    Numbers from a to b, a to d and f
    http://code.activestate.com/recipes/577279-generate-list-of-
    numbers-from-hyphenated-and-comma/
    """
    s="".join(s.split())#removes white space
    r=set()
    for x in s.split(delim):
        t=x.split('-')
        if len(t) not in [1,2]:
            raise SyntaxError("'{}'".format(s)+
                              "does not seem to be derangeifyable")
        if len(t)==1:
            r.add(int(t[0]))
        else:
            r.update(set(range(int(t[0]),int(t[1])+1)))
    l=list(r)
    l.sort()
    return tuple(l)