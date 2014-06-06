#!/usr/bin/env python

#TODO: re-link in build order

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import sys, os

import json
import urllib
from functools import partial
from waflib import ConfigSet, Context

from .util import get_module
database = get_module('distlib.database')
metadata = get_module('distlib.metadata')
locators = get_module('distlib.locators')

import logging
logger = logging.getLogger(__name__)


#TODO: custom python locator
#class PythonLocator(...):
#    pass


#TODO: custom aggregating locator
#class CleanAggregatingLocator(...):
#    pass


class JSONDirectoryLocator(locators.DirectoryLocator):

    def _get_project(self, *args, **kwds):
        dists = super(JSONDirectoryLocator, self)._get_project(*args, **kwds)
        for dist in dists.values():
            if not dist.source_url or '://' in dist.source_url:
                continue

            pydist = dist.source_url + '.' + metadata.METADATA_FILENAME
            try:
                pydist = urllib.urlopen(pydist).read()
            except IOError:
                logger.warn('missing {0} for {1}'.format(
                    metadata.METADATA_FILENAME,
                    dist
                    ))
                continue

            try:
                pydist = json.loads(pydist)
            except ValueError:
                logger.warn('corrupt {0} for {1}'.format(
                    metadata.METADATA_FILENAME,
                    dist
                    ))
                continue

            #NOTE: forces metadata 2.x!
            dist.metadata._legacy = None
            dist.metadata._data = pydist
            dist.name = dist.metadata.name
        return dists


#NOTE: maybe a bit funky, but this is 100% normal; dynamically splicing
# methods/attrs onto classes is *central* to using and understanding waf!
def zpy(ctx, _zpy=ConfigSet.ConfigSet()):
    env = ctx.env
    if not hasattr(ctx, 'zippy_dist_find'):
        if 'top_xsrc' in env:
            def dist_get(key=None, **kwds):
                if key and 'mapping' not in kwds:
                    kwds['mapping'] = env.dist[key]
                dist = database.Distribution(
                    metadata=metadata.Metadata(**kwds),
                    )
                return dist
            ctx.zippy_dist_get = dist_get

            ctx.aggregating_locator = locators.AggregatingLocator(
                # extern/sources/*.pydist.json
                JSONDirectoryLocator(env.top_xsrc, recursive=False),
                # eg. https://www.red-dove.com/pypi/projects/U/uWSGI/
                locators.JSONLocator(),
                # eg. https://pypi.python.org/simple/uWSGI/
                locators.SimpleScrapingLocator(env.api_pypi, timeout=3.0),
                # scheme here applies to the loose matching of dist version.
                # currently, most pypi dists are not PEP 426/440 compatible.
                # *DOES NOT* apply to returned [2.x] metadata!
                scheme='legacy',
                # return the first dist found in the stack and stop searching!
                merge=False,
                )
            ctx.dependency_finder = locators.DependencyFinder(
                ctx.aggregating_locator,
                )
    return env
Context.Context.zpy = property(zpy)
