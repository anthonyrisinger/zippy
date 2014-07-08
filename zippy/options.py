# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function


def options(opt):
    from waflib import Errors
    from waflib import Context
    from .patterns import suppress

    _ident = None
    _appname = getattr(Context.g_module, 'APPNAME', Context.APPNAME)
    with suppress(Errors.WafError):
        _ident = opt.cmd_and_log(
            ['git', 'rev-parse', '--short=8', 'HEAD'],
            output=Context.STDOUT,
            quiet=Context.BOTH,
            ).strip()

    grp = opt.add_option_group('%s options' % _appname)
    grp.add_option(
            '--debug',
            metavar='BOOL',
            action='store_true',
            default=False,
            help='debug build [default: %default]',
            )
    grp.add_option(
            '--identifier',
            metavar='HEX',
            action='store',
            default=_ident,
            help='variant identifier [default: %default]',
            )
    grp.add_option(
            '--requirements',
            metavar='URL',
            action='append',
            default=list(),
            help='guides external embeds',
            )
    grp.add_option(
            '--locator',
            metavar='URL',
            action='append',
            default=list(),
            help='prepends *Locator(URI) to the resolver',
            )
    grp.add_option(
            '--with-dynamic-load',
            metavar='REGEX',
            action='append',
            default=list(),
            help="matching projects' modules left out core python",
            )
