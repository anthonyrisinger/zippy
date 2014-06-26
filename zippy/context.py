#!/usr/bin/env python

#TODO: re-link in build order

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import sys, os

import json
from functools import partial
from waflib import ConfigSet, Context

from .util import get_module
database = get_module('distlib.database')
metadata = get_module('distlib.metadata')
locators = get_module('distlib.locators')
compat = get_module('distlib.compat')

import logging
logger = logging.getLogger(__name__)

import glob
import urllib2
from base64 import b64encode


def open(self, *args, **kwds):
    request = compat.Request(*args, **kwds)
    if self.username or self.password:
        request.add_header('Authorization', 'Basic ' + b64encode(
            (self.username or '') + ':' + (self.password or '')
            ))
    fp = self.opener.open(request)
    return fp
locators.Locator.username = None
locators.Locator.password = None
locators.Locator.open = open
# unmask builtin
del open


class PythonLocator(locators.Locator):

    _distributions = frozenset(('Python',))

    def __init__(self, **kwds):
        self.avail = dict()
        self.url = kwds.pop(
            'url',
            'http://hg.python.org/cpython/tags?style=raw',
            )
        self.source_url = kwds.pop(
            'source_url',
            'http://hg.python.org/cpython/archive/{0}.zip',
            )
        super(PythonLocator, self).__init__(**kwds)

        fp = self.open(self.url)
        try:
            for line in fp.readlines():
                ver, rev = line.strip().split('\t', 2)
                ver = ver.lstrip('v')
                if ver and ver[0].isdigit():
                    dist = database.make_dist(
                        'Python', ver, summary='Placeholder for summary',
                        )
                    dist.metadata.source_url = self.source_url.format(rev)
                    self.avail[ver] = dist
        finally:
            fp.close()

    def _get_project(self, name):
        if name.title() not in self._distributions:
            return dict()

        return self.avail

    def get_distribution_names(self):
        return self._distributions


class GlobLocator(locators.Locator):

    def __init__(self, **kwds):
        #TODO: pass ref to ctx
        self.nodes = dict()
        self.distributions = dict()
        self.url = kwds.pop('url', None)
        self.ctx = kwds.pop('ctx', None)
        super(GlobLocator, self).__init__(**kwds)

        if self.url:
            if not self.url.path.endswith('/'):
                path = os.path.join(self.url.path, '')
                self.url = self.url._replace(path=path)
            potentials = glob.glob(self.url.path)
            for potential in potentials:
                path = os.path.join(potential, metadata.METADATA_FILENAME)
                if not os.path.exists(path):
                    continue

                # EggInfoDistribution?
                node = self.ctx.path.make_node(potential)
                pydist = metadata.Metadata(path=path)
                #NOTE: what if assigned Node here...?
                pydist.source_url = node.path_from(self.ctx.srcnode)
                dist = database.Distribution(metadata=pydist)
                info = self.distributions[dist.name] = {
                    dist.metadata.version: dist,
                    }

                dist_node = self.ctx.bldnode.make_node(str(node))
                nodes = self.nodes[dist.name] = (node, dist_node)

    def _get_project(self, name):
        if name not in self.distributions:
            return dict()

        info = self.distributions[name]
        node, dist_node = self.nodes[name]
        dist_path = dist_node.abspath()
        if not os.path.exists(dist_path):
            link = node.path_from(self.ctx.bldnode)
            try:
                # clear broken symlinks
                os.unlink(dist_path)
            except OSError:
                pass
            finally:
                os.symlink(link, dist_path)
        return info

    def get_distribution_names(self):
        names = self.distributions.viewkeys()
        return names


#TODO: custom aggregating locator
#class CleanAggregatingLocator(...):
#    ...
#    dist.metadata._legacy = None
#    dist.metadata._data = pydist
#    dist.name = dist.metadata.name
#    ...


class JSONDirectoryLocator(locators.DirectoryLocator):

    def _get_project(self, *args, **kwds):
        dists = super(JSONDirectoryLocator, self)._get_project(*args, **kwds)
        for dist in dists.values():
            if not dist.source_url:
                continue

            if '://' in dist.source_url and not 'file://' in dist.source_url:
                continue

            pydist = dist.source_url + '.' + metadata.METADATA_FILENAME
            try:
                pydist = self.open(pydist).read()
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
    if not hasattr(ctx, 'zippy_dist_get'):
        if 'top_xsrc' in env:
            def dist_get(key=None, **kwds):
                if key and 'mapping' not in kwds:
                    kwds['mapping'] = env.dist[key]
                dist = database.Distribution(
                    metadata=metadata.Metadata(**kwds),
                    )
                return dist
            ctx.zippy_dist_get = dist_get

            ctx.locators = list()
            for locator_str in env.opt['locator']:
                locator_url = compat.urlsplit(locator_str)
                if not locator_url.scheme:
                    locator_url = locator_url._replace(scheme='glob')
                locator_name = locator_url.scheme.title() + 'Locator'

                try:
                    locator = globals()[locator_name](
                        url=locator_url,
                        ctx=ctx,
                        )
                except KeyError:
                    raise ValueError('missing: {0}.{1} ({2})'.format(
                        __name__,
                        locator_name,
                        locator_str,
                        ))

                ctx.locators.append(locator)
            ctx.locators += [
                # eg. extern/sources/*.pydist.json
                JSONDirectoryLocator(env.top_xsrc, recursive=False),
                # eg. http://hg.python.org/cpython/archive/tip.zip
                PythonLocator(),
                # eg. https://www.red-dove.com/pypi/projects/U/uWSGI/
                locators.JSONLocator(),
                # eg. https://pypi.python.org/simple/uWSGI/
                locators.SimpleScrapingLocator(env.api_pypi, timeout=3.0),
                ]

            params = dict(
                # scheme here applies to the loose matching of dist version.
                # currently, most pypi dists are not PEP 426/440 compatible.
                # *DOES NOT* apply to returned [2.x] metadata!
                scheme='legacy',
                # return the first dist found in the stack and stop searching!
                merge=False,
                )
            ctx.aggregating_locator = locators.AggregatingLocator(
                *ctx.locators, **params
                )
            ctx.dependency_finder = locators.DependencyFinder(
                ctx.aggregating_locator,
                )
    return env
Context.Context.zpy = property(zpy)
