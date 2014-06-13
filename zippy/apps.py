# encoding: UTF-8

import os
import sys
import shutil
from datetime import datetime
from .util import get_module

metadata = get_module('distlib.metadata')
database = get_module('distlib.database')
scripts = get_module('distlib.scripts')
wheel = get_module('distlib.wheel')


#TODO: hmm, should maybe be a context manager...
def _new_context(prefix=None):
    pydist = metadata.Metadata(path='pydist.json')
    tstamp = (
        os.environ.get('ZIPPY_BUILD')
        or datetime.utcnow().strftime('%F-%s')
        )
    if prefix is None:
        prefix = sys.prefix
        #TODO: drop this!
        if pydist.name != 'setuptools':
            prefix = os.path.join(
                __package__ + '.build-' + tstamp,
                'wheel',
                )
    purelib = os.path.join(prefix, 'lib')
    platlib = os.path.join(prefix, 'lib')
    scripts = os.path.join(prefix, 'scripts')
    headers = os.path.join(prefix, 'headers')
    data = os.path.join(prefix, 'data')
    distinfo = os.path.join(
        purelib,
        database.DistributionPath.distinfo_dirname(
            pydist.name,
            pydist.version,
            ))
    egginfo = distinfo.replace(
        database.DISTINFO_EXT,
        '-py{0}.{1}.egg-info'.format(*sys.version_info)
        )

    ctx = {
        'tstamp': tstamp,
        'pydist': pydist,
        'sections': {
            'prefix': prefix,
            'purelib': purelib,
            'platlib': platlib,
            'scripts': scripts,
            'headers': headers,
            'data': data,
            },
        'paths': {
            'egginfo': egginfo,
            'distinfo': distinfo,
            'buildbase': __package__ + '.build-' + tstamp,
            },
        }

    import errno
    for section in ['dist', distinfo] + ctx['sections'].values():
        try:
            os.makedirs(name=section, mode=0o700)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    return ctx


def create_wheel(cache_path):
    ctx = _new_context()
    pydist = ctx['pydist']
    sections = ctx['sections']
    prefix = ctx['sections']['prefix']
    egginfo = ctx['paths']['egginfo']
    distinfo = ctx['paths']['distinfo']
    buildbase = ctx['paths']['buildbase']
    ns = dict(globals(), **{
        '__name__': '__main__',
        '__file__': 'setup.py',
        '__package__': None,
        })

    sys.argv[:] = (
        'setup.py'
        '\0build'
        '\0--build-base={paths[buildbase]}'
        '\0--executable=python'
        '\0install'
        '\0--single-version-externally-managed'
        '\0--record={sections[prefix]}/installed-files.txt'
        '\0--install-purelib={sections[purelib]}'
        '\0--install-platlib={sections[platlib]}'
        '\0--install-headers={sections[headers]}'
        '\0--install-scripts={sections[scripts]}'
        '\0--install-data={sections[data]}'
        ).format(**ctx).split('\0')

    #TODO: drop this!
    # install setuptools directly
    if pydist.name == 'setuptools':
        sys.argv[sys.argv.index('install')+1:] = []

    for impl in (
        'setup.cpyext.py',
        'setup.py',
        ):
        if os.path.exists(impl):
            execfile(impl, ns)
            break

    # skip and bail on setuptools else it can't find it's own stuff after
    # installation and because we aren't bulding a setuptools wheel (for now)
    #TODO: setuptools-4.0.1-py2.py3-none-any.whl?
    #TODO: impl/replace pkg_resources?
    if pydist.name == 'setuptools':
        shutil.rmtree(distinfo)
        return

    # ensure exports are correct in case they differ from index-metadata
    # this happens when custom builds add new wrap_console scripts, etc
    entry_points = os.path.join(egginfo, 'entry_points.txt')
    kill = set()
    try:
        with open(entry_points) as fp:
            from ConfigParser import MissingSectionHeaderError
            read_exports = get_module('distlib.util').read_exports

            def conv(s):
                return s.split('=', 1)[-1].strip()

            ep_trans = {
                'console_scripts': 'wrap_console',
                'gui_scripts': 'wrap_gui',
                'prebuilt': 'prebuilt',
                }
            ep_map = pydist.dictionary
            ep_map = ep_map.setdefault('extensions', dict())
            ep_map = ep_map.setdefault('python.commands', dict())
            try:
                ep_new = read_exports(fp, conv=conv)
            except MissingSectionHeaderError:
                #FIXME: UPSTREAM distlib: could be indented!
                # entry_points setup keyword argument could be a str
                # gunicorn does this
                from textwrap import dedent
                fp.seek(0)
                ep_dedent = dedent(fp.read().strip('\n\r'))
                fp.seek(0)
                fp.truncate()
                fp.write(ep_dedent)
                fp.seek(0)
                ep_new = read_exports(fp, conv=conv)

            for k in ep_new:
                if k not in ep_trans:
                    continue

                k2 = ep_trans[k]
                ep_map[k2] = ep_new[k]
                if k2 != 'prebuilt':
                    kill.update(ep_new[k].keys())

            # check for accidental overlap with prebuilt (bad metadata)
            prebuilt = ep_map.get('prebuilt')
            if prebuilt:
                ep_map['prebuilt'] = [p for p in prebuilt if p not in kill]
                if not ep_map['prebuilt']:
                    del ep_map['prebuilt']
    except IOError:
        pass

    # drop all the scripts we know setuptools created
    for s in kill:
        s = os.path.join(sections['scripts'], s)
        os.unlink(s)

    # drop egg-info
    shutil.rmtree(egginfo)
    if os.path.exists(pydist.name + '.egg-info'):
        shutil.rmtree(pydist.name + '.egg-info')

    # [over]write metadata 2.x
    pydist.write(path='pydist.json')
    shutil.copy2('pydist.json', os.path.join(distinfo, 'pydist.json'))

    whl = wheel.Wheel()
    whl.dirname = 'dist'
    whl.metadata = pydist
    whl.version = pydist.version
    whl.name = pydist.name

    #FIXME: del one of purelib/platlib
    whl_file = whl.build(sections)
    shutil.copy2(whl_file, cache_path)

    #TODO: minor: move binary (or `sys.executable = None`?) to avoid this...
    #import sysconfig
    #sysconfig._INSTALL_SCHEMES['posix_prefix'].update({
    #    'prefix': '{base}',
    #    'include': '{base}/include/python{py_version_short}',
    #    'platinclude': '{platbase}/include/python{py_version_short}',
    #    })
    from distutils.command.install import INSTALL_SCHEMES
    from distutils.util import subst_vars
    info = {
        'base': sys.prefix,
        'platbase': sys.exec_prefix,
        'py_version_short': '%s.%s' % sys.version_info[0:2],
        'dist_name': pydist.name,
        }
    scheme = dict(INSTALL_SCHEMES['unix_prefix'], prefix='$base')
    sections = dict()
    for k,v in scheme.iteritems():
        sections[k] = subst_vars(v, info)

    maker = scripts.ScriptMaker(None, None)
    #maker.clobber = True
    #maker.executable = ''
    #maker.variants = set(('', 'X', 'X.Y'))
    whl.install(sections, maker)

    #FIXME
    #if pydist.name != __package__:
    #    return

    shutil.rmtree(buildbase, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(globals()[sys.argv.pop(1)](*sys.argv[1:]))
