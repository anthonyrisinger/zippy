# encoding: UTF-8

from __future__ import division, absolute_import, print_function

import sys, os
from os import environ as env


try:
    import setuptools
except ImportError:
    pass
import distutils
from distutils import core
from distutils import unixccompiler

default_compiler = unixccompiler.UnixCCompiler()


# objects               *.o
# libraries             -l
# build_temp            build/temp.linux-x86_64-2.7
# library_dirs          -L
# export_symbols        inituwsgi
# output_filename       build/lib.linux-x86_64-2.7/_struct.so
# runtime_library_dirs  -rpath
def l4sh(compiler, objects, output_filename, output_dir=None,
         libraries=None, library_dirs=None, runtime_library_dirs=None,
         export_symbols=None, debug=0, extra_preargs=None,
         extra_postargs=None, build_temp=None, target_lang=None):
    from pprint import pprint as pp
    compiler = compiler or default_compiler
    pth = os.path
    bld = ''
    bld = core._setup_distribution.command_obj['build']
    gen_lib_options = unixccompiler.gen_lib_options
    _l4sh = pth.abspath('l4sh')
    _ext = unixccompiler.UnixCCompiler.shared_lib_extension
    _filename = pth.abspath(output_filename)
    _basename = pth.relpath(output_filename,bld.build_platlib)
    _name = _basename.rpartition(_ext)[0].replace(os.sep, '.')
    _hashp = pth.join(_l4sh, '.objects')
    _path = pth.join(_l4sh, _name)
    _sig = pth.join(_path, '.sha1sums')
    _out = _path + '.o'
    _symi = 'init%s' % _name.rsplit('.', 1)[-1]
    _symo = '%s%s' % (
            ('tini' if '.' in _name else 'init'),
            _name.replace('.', '_'),
            )
    if not pth.exists(_hashp):
        #compiler.mkpath(_hashp, 755)
        os.makedirs(_hashp, 0755)
    if not pth.exists(_path):
        #compiler.mkpath(_path, 755)
        os.makedirs(_path, 0755)
    if pth.exists(_out):
        os.unlink(_out)

    #NOTE: subprocess/popen unavailable here...
    def mkargs(objs):
        return ' '.join(list((
            "'%s'" % o.replace("'", r"'\''")
            for o in objs
            )))
    _x_sig = 'sha1sum {0} > {1}'.format(mkargs(objects), _sig)
    _x_ldi = 'ld -i -o {0} {{0}}'.format(_out)
    #FIXME: ideally we'd localize everything *except* Py* + init*
    # but !Py* + !_Py* + !init* doesn't seem to work correctly...
    # appears it must be done manually :( ...punt for now
    _x_api = ' '.join(
            ['objcopy', '--wildcard',
                "--redefine-sym='%s=%s'" % (_symi, _symo)] +
            map("--keep-global-symbol='{0}'".format,
                ('Py*', '_Py*', _symi, _symo)) +
            [_out]
            )

    #...compute/save sigs! (ZERO conflict tolerance)
    #compiler.spawn(...)
    _obs = list()
    os.system(_x_sig)

    def split_sig(line):
        sha1 = line[:40]
        obj = orig = line[40:].strip()
        if build_temp and obj.startswith(build_temp):
            lbt = len(build_temp)
            obj = obj[:lbt+1] + obj[lbt+1:].replace('/', '.')
        return (sha1, orig, obj)

    for h, o, _o in map(
        split_sig,
        open(_sig).read().strip().split('\n'),
        ):
        _h = pth.join(_hashp, h)
        _o = pth.join(_path, pth.basename(_o))
        _o_lock = _o + '.lock'
        if not pth.exists(_h):
            with open(_h, mode='w+') as fd:
                fd.write(_o)
                fd.write('\n')
            _h = _o
        if _h == _o:
            _obs.append(_o)
        os.link(o, _o_lock)
        os.rename(_o_lock, _o)

    #...link final target
    os.system(_x_ldi.format(mkargs(_obs)))

    #...correct extern API
    os.system(_x_api)

    #...write Setup fragment
    setup_file = pth.join(_path, 'Setup')
    with open(setup_file, 'w') as fd:
        fd.write(' '.join(
            [_name] + gen_lib_options(compiler, library_dirs,
                runtime_library_dirs, libraries + compiler.libraries)
            ))
        fd.write('\n')

    return setup_file


if 'ZIPPY_BUILD' in env:
    if '-fprofile-generate' not in env.get('CFLAGS', ''):
        def link_shared_object(*args, **kwds):
            setup_file = l4sh(*args, **kwds)
            return unixccompiler.CCompiler.link_shared_object(*args, **kwds)
        unixccompiler.UnixCCompiler.link_shared_object = link_shared_object
