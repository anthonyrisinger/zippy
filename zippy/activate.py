from __future__ import print_function, absolute_import, division

import sys, pipes
from os import path as pth
from os import environ as env


class Activator(object):

    _deactivate_key = '__deactivate__'

    def __init__(self, seed=None, fp=None):
        self.seed = seed
        self.fp = fp or sys.stdout
        self.vbin = seed and pth.dirname(self.seed)
        self.venv = seed and pth.dirname(self.vbin)
        self.path = (env.get('PATH') or '').split(':')
        self.out = list()

    def _set_deactivate(self):
        """shell function to undo everything!"""
        fn = 'deactivate () { __deactivate__=%s . %s; unset deactivate; }\n'
        yield fn % (pipes.quote(self.venv), pipes.quote(self.seed))

    def run(self):
        """"""
        active_venv = env.get(self._deactivate_key)
        self.deactivate() if active_venv else self.activate()
        self.fp.writelines(self.out)

    def deactivate(self):
        """"""
        if self.venv:
            if self.venv == env.get('VIRTUAL_ENV'):
                self.out.extend(
                    self.unset('VIRTUAL_ENV'),
                    )
            if self.vbin in self.path:
                self.path.remove(self.vbin)
                self.out.extend(
                    self.export('PATH', ':'.join(self.path)),
                    )

    def activate(self):
        """"""
        if self.venv:
            if self.venv != env.get('VIRTUAL_ENV'):
                self.out.extend(
                    self.export('VIRTUAL_ENV', self.venv),
                    )
            if self.vbin not in self.path:
                self.path.insert(0, self.vbin)
                self.out.extend(
                    self.export('PATH', ':'.join(self.path)),
                    )
            self.out.extend(
                self._set_deactivate(),
                )

    def export(self, lval, rval):
        """
        write a shell-compatible variable export/unset to self.fp [stdout]

        export('VAR_A', None)           unset VAR_A
        export('VAR_B', False)          export VAR_B=0
        export('VAR_C', True)           export VAR_C=1
        export('VAR_D', 0)              export VAR_D=0
        export('VAR_E', 1)              export VAR_E=1
        export('VAR_F', 2)              export VAR_F=2
        export('VAR_G', '')             export VAR_G=''
        export('VAR_H', 'val')          export VAR_H=val
        export('VAR_I', '''v"a'l''')    export VAR_I='v"a'"'"'l'

        """
        verb = 'unset' if rval is None else 'export'
        rval = '%i' % rval if isinstance(rval, int) else rval
        rval = '' if rval is None else '=' + pipes.quote(rval)
        return (verb, ' ', lval, rval, '\n')

    def unset(self, lval):
        return self.export(lval, None)

    def exportall(self, iterable):
        iterator = (getattr(iterable, 'iteritems', None) or
                    getattr(iterable, '__iter__'))
        for expr in iterator():
            for chunk in self.export(*expr):
                yield chunk

    def unsetall(self, iterable):
        for export in map(self.export, iterable):
            for chunk in export:
                yield chunk


if __name__ == '__main__':
    seed = sys.argv[1:2] and pth.abspath(sys.argv[1]) or None
    Activator(seed).run()
