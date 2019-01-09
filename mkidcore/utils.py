from functools import wraps
import inspect
import multiprocessing as mp

_manager = None


def manager(*args, **kwargs):
    global _manager
    if _manager is None:
        _manager = mp.Manager(*args, **kwargs)
    return _manager


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