try:
    from json import dump
    from json import load
    from json import dumps
    from json import loads
except ImportError:
    def dump(o, fp, *args, **kwds):
        """json.dump substitute
        """
        return fp.write(dumps(o, *args, **kwds))

    def load(fp, *args, **kwds):
        """json.load substitute
        """
        return loads(fp.read(), *args, **kwds)

    def dumps(o, *args, **kwds):
        """json.dumps substitute
        """
        return pf(o)

    def loads(o, *args, **kwds):
        """json.loads substitute
        """
        try:
            # 0x20000: unicode_literals
            # 0x02000: division
            co = compile(o, '<json>', 'eval', 0x22000, True)
            ns = {'true': True, 'false': False, 'null': None}
            js = eval(co, ns)
            return js
        except (SyntaxError, NameError) as e:
            raise ValueError(*e)
