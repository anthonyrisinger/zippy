# encoding: utf-8

from .util import get_module

DistributionPath = get_module('distlib.database').DistributionPath
get_scheme = get_module('distlib.version').get_scheme
parse_requirement = get_module('distlib.util').parse_requirement


_dist_path = DistributionPath()


def load_entry_point(requirement, category, name):
    _dist = _dist_path.get_distribution(
        parse_requirement(requirement).name,
        )
    return _dist.exports[category][name].value


def get_entry_info(requirement, category, name):
    _dist = _dist_path.get_distribution(requirement)
    return _dist.exports[category][name]


def get_entry_map(requirement, category=None):
    _dist = _dist_path.get_distribution(requirement)
    return _dist.exports if category is None else _dist.exports.get(category)


def iter_entry_points(category, name=None):
    return _dist_path.get_exported_entries(category, name=None)
