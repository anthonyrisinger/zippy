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

            locator = ctx._zippy_locator = locators.AggregatingLocator(
                JSONDirectoryLocator(env.top_xsrc, recursive=False),
                locators.JSONLocator(),
                locators.SimpleScrapingLocator(env.api_pypi, timeout=3.0),
                scheme='legacy',
                merge=False,
                )
            #FIXME: probably need to call add_distribution(...) on the results
            # so future lookups resolve to the same dist (so long as the
            # version is compatible) else we might return incompatible dupes
            finder = ctx._zippy_finder = locators.DependencyFinder(locator)
            ctx.zippy_dist_find = partial(finder.find, prereleases=True)
    return env
Context.Context.zpy = property(zpy)
