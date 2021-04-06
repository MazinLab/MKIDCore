
def parse_dither_log(file):
    with open(file) as f:
        lines = f.readlines()

    tofloat = lambda x: list(map(float, x.replace('[', '').replace(']', '').split(',')))
    proc = lambda x: str.lower(str.strip(x))
    d = dict([list(map(proc, l.partition('=')[::2])) for l in lines])

    # Support legacy legacy names
    if 'endtimes' not in d:
        d['endtimes'] = d['stoptimes']

    inttime = int(d['inttime'])

    startt = tofloat(d['starttimes'])
    endt = tofloat(d['endtimes'])
    xpos = tofloat(d['xpos'])
    ypos = tofloat(d['ypos'])

    return startt, endt, list(zip(xpos, ypos)), inttime