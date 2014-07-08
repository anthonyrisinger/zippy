# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

from waflib import ConfigSet
from zippy import json


#TODO: ask/needs upstream!
def _eat_your_pickles(module=(lambda x: x).__module__):
    load = ConfigSet.ConfigSet.load
    store = ConfigSet.ConfigSet.store

    if load.__module__ != module:
        load_orig = ConfigSet.ConfigSet.load
        def load_pickle(self, filename):
            data = None
            with suppress(pickle.UnpicklingError):
                data = pickle.loads(Utils.readf(filename, m='rb'))
            if data is None:
                data = load_orig(self, filename)
            if data:
                self.table.update(data)
            Logs.debug('env: %s' % str(self.table))
        ConfigSet.ConfigSet.load = load_pickle

    if store.__module__ != module:
        store_orig = ConfigSet.ConfigSet.store
        def store_pickle(self, filename):
            dirname, basename = os.path.split(filename)
            if basename == Options.lockfile:
                return store_orig(self, filename)
            Utils.check_dir(dirname)
            table = sorted(
                    kv
                    for kv in self.get_merged_dict().iteritems()
                        if kv[0] != 'undo_stack'
                    )
            Utils.writef(filename, pickle.dumps(table, 2), m='wb')
        ConfigSet.ConfigSet.store = store_pickle
#_eat_your_pickles()
#ConfigSet.Requirement = pkg_res.Requirement


def buffer(self, filename=None):
    mark = filename or self.table['bld_landmark']
    buf = self.buffer_cache.get(mark)
    if buf is None and mark.endswith('.json'):
        buf = self.buffer_cache[mark] = open(mark, mode='w+b')
    return buf
ConfigSet.ConfigSet.get_buffer = buffer
ConfigSet.ConfigSet.buffer_cache = dict()
ConfigSet.ConfigSet.buffer = property(buffer)
del buffer


load_config = ConfigSet.ConfigSet.load
def load(self, filename=None):
    fp = self.get_buffer(filename)
    if not fp:
        load_config(self, filename)
        return

    #FIXME: upstream!
    self.table = json.load(fp)
    fp.seek(0)
    return
ConfigSet.ConfigSet.load = load
del load


store_config = ConfigSet.ConfigSet.store
def store(self, filename=None):
    fp = self.get_buffer(filename)
    if not fp:
        store_config(self, filename)
        return

    json.dump(self.table, fp)
    fp.seek(0)
    return
ConfigSet.ConfigSet.store = store
del store
