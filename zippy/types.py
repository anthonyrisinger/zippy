from collections import Iterable, defaultdict


class nil(int):
    """Distinguish between `None` and nothing"""
nil = nil()


def _attrify(attr):
    def fun(self, *args, **kwds):
        try:
            return getattr(self, attr)(*args, **kwds)
        except KeyError, e:
            raise AttributeError(*e)
    fun.__name__ = attr
    return fun


class attrdict(defaultdict):

    __slots__ = tuple()
    __repr__ = dict.__repr__

    __setattr__ = _attrify('__setitem__')
    __getattr__ = _attrify('__getitem__')
    __delattr__ = _attrify('__delitem__')

    def __init__(self, *args, **kwds):
        if len(args)==0:
            args = (self.default_factory, tuple())
        elif len(args)==1:
            _iterable = isinstance(args[0], Iterable)
            args = (
                self.default_factory if _iterable else args[0],
                args[0] if _iterable else tuple(),
                )
        return super(attrdict, self).__init__(*args, **kwds)

    def __dir__(self):
        return sorted(set(self).union(*map(dir, self.__class__.__mro__)))

    def __copy__(self):
        return self.__class__(self)
    copy = __copy__

    @classmethod
    def _oper(cls, op, inst, other, default, inplace):
        try:
            ikeys = inst.viewkeys()
        except AttributeError:
            ikeys = frozenset(inst)
        try:
            okeys = other.viewkeys()
        except AttributeError:
            okeys = frozenset(other)

        oper = getattr(ikeys, op)
        keys = oper(okeys)
        if keys is NotImplemented:
            keys = oper(frozenset(okeys))
        if keys is NotImplemented:
            raise keys

        if inplace:
            for key in ikeys - keys:
                yield (key, nil)
        for key in keys:
            target = inst if key in ikeys else other
            try:
                attr = target.get(key)
            except AttributeError:
                attr = default and default()
            yield (key, attr)

    @classmethod
    def _op(cls, op, inst, other, default):
        try:
            updates = cls._oper(op, inst, other, default, inplace=False)
        except NotImplemented:
            return NotImplemented

        return cls(default, updates)

    @classmethod
    def _iop(cls, op, inst, other, default):
        try:
            updates = cls._oper(op, inst, other, default, inplace=True)
        except NotImplemented:
            return NotImplemented

        for key, attr in updates:
            if attr is nil:
                del inst[key]
            else:
                inst[key] = attr

        return inst

    def __or__(self, other):
        return self._op('__or__', self, other, self.default_factory)

    def __xor__(self, other):
        return self._op('__xor__', self, other, self.default_factory)

    def __and__(self, other):
        return self._op('__and__', self, other, self.default_factory)

    def __sub__(self, other):
        return self._op('__sub__', self, other, self.default_factory)

    def __ror__(self, other):
        return self._op('__or__', other, self, self.default_factory)

    def __rxor__(self, other):
        return self._op('__xor__', other, self, self.default_factory)

    def __rand__(self, other):
        return self._op('__and__', other, self, self.default_factory)

    def __rsub__(self, other):
        return self._op('__sub__', other, self, self.default_factory)

    def __ior__(self, other):
        return self._iop('__or__', self, other, self.default_factory)

    def __ixor__(self, other):
        return self._iop('__xor__', self, other, self.default_factory)

    def __iand__(self, other):
        return self._iop('__and__', self, other, self.default_factory)

    def __isub__(self, other):
        return self._iop('__sub__', self, other, self.default_factory)


class record(attrdict):
    """attribute-accessible dictionary

    specialized dictionary exposing keys as attributes::

        >>> a = record(one=1, two=2, true=True, none=None)
        >>> a
        >>> {'none': None, 'true': True, 'two': 2, 'one': 1}
        >>> a.true
            True
    """

    default_factory = None


class autodict(attrdict):
    """autovivificious dictionary

    specialized `record` that, when accessing `self.missing_key`, returns
    a new `self.__class__()` instead of throwing `KeyError`::

        >>> a = autodict()
        >>> a
        >>> {'s': {'d': {'f': {'g': {'h': {'j': {}}}}}}}
        >>> a.s.d.f.g.h['j'] is a.s.d.f.g.h.j
            True
    """

    @property
    def default_factory(self):
        return self.__class__
