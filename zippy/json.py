# encoding: utf-8


from __future__ import absolute_import


def _json_available():
    try:
        import json
        globals().update(vars(json))
    except ImportError:
        return False
    else:
        return True


def dump(o, fp, *args, **kwds):
    """json.dump substitute
    """
    if _json_available():
        return dump(o, fp, *args, **kwds)

    return fp.write(dumps(o, *args, **kwds))

def load(fp, *args, **kwds):
    """json.load substitute
    """
    if _json_available():
        return load(fp, *args, **kwds)

    return loads(fp.read(), *args, **kwds)

def dumps(o, *args, **kwds):
    """json.dumps substitute
    """
    if _json_available():
        return dumps(o, *args, **kwds)

    return pf(o)

def loads(o, *args, **kwds):
    """json.loads substitute
    """
    if _json_available():
        return loads(o, *args, **kwds)

    try:
        # 0x20000: unicode_literals
        # 0x02000: division
        co = compile(o, '<json>', 'eval', 0x22000, True)
        ns = {'true': True, 'false': False, 'null': None}
        js = eval(co, ns)
        return js
    except (SyntaxError, NameError) as e:
        raise ValueError(*e)


# kill fallback definitions immediately, if possible
_json_available()
