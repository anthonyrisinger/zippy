class suppress(object):
    """context manager and decorator that ignores specific Exceptions
    """

    def __init__(self, *exc):
        self.exc = exc
        for e in self.exc:
            if not (isinstance(e, type) and issubclass(e, BaseException)):
                raise TypeError('%s is not a valid exception type' % e)

    def __call__(self, f=None):
        # @suppress(OsError)
        # def never_raise_OsError(...):
        #     pass
        def g(*args, **kwds):
            with self:
                return f(*args, **kwds)
        g.__name__ = getattr(f, '__name__', g.__name__)
        g.__doc__ = getattr(f, '__doc__', g.__doc__)
        return g

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None and issubclass(exc_type, self.exc):
            return True
