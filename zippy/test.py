# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

import sys, os

from waflib import Logs
from waflib import Context


#TODO:
#Context.g_module.__dict__['test'] = test
def test(bld):
    """manually run all zippy tests (must be built already!)
    """
    tests = list()
    for key, fun in sorted(globals().iteritems()):
        if not key.lower().startswith('_test_'):
            continue
        key = key.replace('_', ' ').strip().title().split()
        desc = getattr(fun, '__doc__', '...testing ...???').strip()
        tests.append((' '.join(key[2:]), (desc,), tuple(), None, fun))

    if not tests:
        bld.msg('checking for tests', len(tests))
        return

    norm = Logs.colors.NORMAL
    bold = Logs.colors.BOLD
    col1 = Logs.colors.YELLOW
    col2 = bold + col1

    total = len(tests)
    n = len(str(total))
    n_min = (n * 2) + 2
    n_mod = n_min % 4
    n_buf = n_min + n_mod

    pfx = ' '*n_buf
    sp = ' '*2

    for i, (name, inputs, outputs, req, test) in enumerate(tests, 1):
        src_str = ('\n'+pfx).join(inputs)
        tgt_str = ('\n'+pfx+sp).join(outputs)
        sep0 = sep1 = ''
        if inputs:
            sep0 = '\n'+norm+col1+pfx
        if outputs:
            sep1 = '\n'+norm+col1+pfx+sp
        if req:
            name = '%s %s%s' % (name, norm, req)
        s = '%s%s%s%s%s\n' % (name, sep0, src_str, sep1, tgt_str)
        fs = '%s%%%dd/%%%dd %%s%%s%%s' % (' '*n_mod, n, n)
        out = fs % (i, total, col2, s, norm)

        sys.stderr.write(out)
        test(bld)


#---------------------------------------------------------------------( tests )


def _test_001_import_builtins(bld):
    """
    import everything from sys.builtin_module_names
    """
    cmd = [bld.env.O_PYTHON, '-c', (
        'import sys\n'
        'for m in sys.builtin_module_names:\n'
        '\tm = __import__(m, fromlist=True)\n'
        '\tf = getattr(m, "__file__", "(built-in)"); n = m.__name__\n'
        '\tprint("%s\t%s" % (f, n))\n'
        )]

    for i, modline in enumerate(bld.cmd_and_log(
            cmd, output=Context.STDOUT, env=bld.env.env or None
            ).strip().split('\n'), 1):
        fname, mname = modline.split('\t')
        mname = '{0:{width}}'.format(mname, width=36-len(fname))
        sep = '\n' if (i%2==0) else ''
        Logs.pprint('NORMAL', fname, sep='')
        Logs.pprint('BOLD_BLUE', mname, sep=sep)
    if i%2==1:
        sys.stderr.write('\n')
