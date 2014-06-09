# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function


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
