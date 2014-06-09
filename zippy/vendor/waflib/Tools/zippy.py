# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

def I(**kwds):
	import sys
	sys.stdin = sys.stdout = open('/dev/tty', mode='r+b')

	from IPython.frontend.terminal.embed import InteractiveShellEmbed
	from IPython.frontend.terminal.ipapp import load_default_config
	from IPython.frontend.terminal.interactiveshell import (
		TerminalInteractiveShell
		)
	config = kwds.get('config')
	header = kwds.pop('header', u'')
	if config is None:
		config = load_default_config()
		config.InteractiveShellEmbed = config.TerminalInteractiveShell
		kwds['config'] = config
	return InteractiveShellEmbed(**kwds)(header=header, stack_depth=2)
__builtins__['I'] = I


#------------------------------------------------------------------( std defs )

__package__ = 'zippy'
__import__(__package__)
from .setup import setup
from .options import options
from .configure import configure
from .build import build
from .test import test
from .install import install


# vim: set noexpandtab:
