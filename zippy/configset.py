# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint


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
