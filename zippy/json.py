def loads(s, *args, **kwds):
    """json.loads substitute
    """
    # 0x20000: unicode_literals
    # 0x02000: division
    co = compile(s, '<json>', 'eval', 0x22000, True)
    ns = {'true': True, 'false': False, 'null': None}
    js = eval(co, ns)
    return js


def dumps(*args, **kwds):
    pass


def load(fp, *args, **kwds):
    return loads(fp.read(), *args, **kwds)


def dump(*args, **kwds):
    pass
