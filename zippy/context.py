#!/usr/bin/env python

#TODO: re-link in build order

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

import sys, os

from functools import partial
from waflib import ConfigSet, Context

from .vendor.distlib.database import Distribution
from .vendor.distlib.metadata import Metadata
from .vendor.distlib.locators import (
    DependencyFinder,
    AggregatingLocator,
    DirectoryLocator, JSONLocator, SimpleScrapingLocator,
    )


#NOTE: maybe a bit funky, but this is 100% normal; dynamically splicing
# methods/attrs onto classes is *central* to using and understanding waf!
def zpy(ctx, _zpy=ConfigSet.ConfigSet()):
    env = ctx.env
    if not hasattr(ctx, 'zippy_dist_find'):
        if 'top_xsrc' in env:
            def dist_get(key=None, **kwds):
                if key and 'mapping' not in kwds:
                    kwds['mapping'] = env.dist[key]
                dist = Distribution(metadata=Metadata(**kwds))
                return dist
            ctx.zippy_dist_get = dist_get

            locator = ctx._zippy_locator = AggregatingLocator(
                DirectoryLocator(env.top_xsrc, recursive=False),
                JSONLocator(),
                SimpleScrapingLocator(env.api_pypi, timeout=3.0),
                scheme='legacy',
                merge=False,
                )
            finder = ctx._zippy_finder = DependencyFinder(locator)
            ctx.zippy_dist_find = partial(finder.find, prereleases=True)
    return env
Context.Context.zpy = property(zpy)
