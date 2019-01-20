import string
from mkidcore.corelog import getLogger


def ask_for(key):
    s = raw_input("ReadDict: enter value for '%s': " % key)
    try:
        val = eval(s)
    except NameError:
        # allow people to enter unquoted strings
        val = s
    return val


class ReadDict(dict):
    def __init__(self, file='', ask=False):
        """
        @param ask if the dict doesn't have an entry for a key, ask for the associated value and assign
        """
        dict.__init__(self)
        self.ask = ask
        if file:
            self.readFromFile(file)

    def __getitem__(self, key):
        if key not in self:
            if self.ask:
                getLogger(__name__).info("Parameter '%s' not found" % key)
                val = ask_for(key)
                getLogger(__name__).info("Setting '%s' = %s" % (key, repr(val)))
                dict.__setitem__(self, key, val)
            else:
                return None
        return dict.__getitem__(self, key)

    def read_from_file(self, filename):
        with open(filename, 'r') as f:
            old = ''
            for line in f:
                line = line.strip()
                if len(line) == 0 or line[0] == '#':
                    continue
                s = line.split('#')
                line = s[0]
                s = line.split('\\')
                if len(s) > 1:
                    old = string.join([old, s[0]])
                    continue
                else:
                    line = string.join([old, s[0]])
                    old = ''
                for i in xrange(len(line)):
                    if line[i] != ' ':
                        line = line[i:]
                        break
                exec (line)
                s = line.split('=')
                if len(s) != 2:
                    getLogger(__name__).warning("Error parsing line:\n\t'{}'".format(line))
                    continue
                key = s[0].strip()
                val = eval(s[1].strip())  # XXX:make safer
                self[key] = val

    readFromFile = read_from_file
