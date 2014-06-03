# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

from waflib import Utils
from waflib import Task, TaskGen
from waflib.TaskGen import feature

from .vendor.distlib.database import make_graph

#...do not invoke default rule/ext methods!
TaskGen.feats['*'].clear()
feature('*')(Utils.nada)


@feature('zpy-requirements')
def zpy_requirements(gen):
    env = gen.env
    bld = gen.bld
    zpy = bld.zpy

    _tsk = getattr(gen, 'task', 'ZPyTask_Requirements')

    for dist in getattr(gen, 'source', tuple()):
        out = bld.bldnode.make_node(str(dist.key))
        tsk = gen.create_task(_tsk, tgt=out.make_node('setup.py'))
        tsk.dist = dist


@feature('zpy-update')
def zpy_update(gen):
    env = gen.env
    bld = gen.bld
    zpy = bld.zpy
    py = bld.py

    #   map patches to requirements
    patches = dict()
    for reqs in bld.path.ant_glob('extern/patches/*.requirements.txt'):
        node = reqs.change_ext('', ext_in='.requirements.txt')
        patches[node] = reqs.read().splitlines()

    task_last = None
    subst = dict(zpy)
    targets = Utils.to_list(gen.target)
    for req_name in targets:
        dist = bld.zippy_dist_get(req_name)
        dist_node = bld.bldnode.make_node(str(dist.key))
        for node, reqs in patches.items():
            for req in reqs:
                if dist.matches_requirement(req):
                    task = gen.create_task('ZPyTask_Patch', node)
                    task.cwd = dist_node.abspath()
                    task.dist = dist
                    node.sig = Utils.h_file(node.abspath())
                    if task_last:
                        task.set_run_after(task_last)
                    task_last = task
                    # check other patches, not addtl reqs to current patch
                    break

    for req_name in targets:
        dist = bld.zippy_dist_get(req_name)
        dist_node = bld.bldnode.make_node(str(dist.key))
        for req, rules in Task.classes['ZPyTask_Update'].x.iteritems():
            if dist.matches_requirement(req):
                for path, (fun, kwds) in rules.iteritems():
                    realpath = path % subst
                    finder = getattr(dist_node, kwds.get('finder', 'find_node'))
                    node = finder(realpath)
                    if node:
                        task = gen.create_task('ZPyTask_Update', node)
                        task.fun = fun
                        task.kwds = kwds
                        task.dist = dist
                        node.sig = task.uid()
                        #...updates should run after the last patch, if any
                        if task_last:
                            task.set_run_after(task_last)


@feature('zpy-profile')
def zpy_profile(gen):
    env = gen.env
    bld = gen.bld
    zpy = bld.zpy
    py = bld.py

    dist = bld.zippy_dist_get('python')
    gen.create_task('ZPyTask_Profile')
    for task in gen.tasks:
        task.dist = dist


@feature('zpy-extension')
def zpy_extension(gen):
    env = gen.env
    bld = gen.bld
    zpy = bld.zpy
    py = bld.py

    target = Utils.to_list(getattr(gen, 'target', tuple()))
    if not target:
        return None

    py_site = bld.root.make_node(zpy.o_lib_py_site)
    incl = Utils.to_list(getattr(gen, 'incl', tuple()))
    excl = Utils.to_list(getattr(gen, 'excl', tuple()))
    wanted = set(
        dist
        for fqn in target
        for dist in (bld.zippy_dist_get(fqn),)
            if dist
            and dist.key not in excl
            and (not incl or dist.key in incl)
        )

    graph = make_graph(wanted, scheme=bld._zippy_locator.scheme)
    ok, cycle = graph.topological_sort()
    if cycle:
        # sort the remainder on dependency count.
        cycle = sorted(
            cycle, reverse=True,
            key=lambda d: len(graph.reverse_list[d]),
            )
    wanted = ok + cycle

    _cache = dict()
    for dist in wanted:
        o_req = bld.bldnode.find_dir(str(dist.key))
        o_req_setup = o_req.find_node('setup.py')
        o_req_setup.sig = Utils.h_file(o_req_setup.abspath())
        o_req_wheel = o_req.make_node('pydist.json')
        tsk = _cache[dist] = gen.create_task(
            'ZPyTask_Extension',
            o_req_setup,
            o_req_wheel,
            )
        for dep, spec in graph.adjacency_list[dist]:
            tsk.run_after.add(_cache[dep])
        tsk.dist = dist


@feature('zpy-replay')
def zpy_replay(gen):
    env = gen.env
    bld = gen.bld
    zpy = bld.zpy
    py = bld.py

    dist = bld.zippy_dist_get('python')
    modsetup = py.make_node('Modules/Setup')
    gen.create_task('ZPyTask_Rewind', tgt=modsetup)
    gen.create_task('ZPyTask_Replay')
    for task in gen.tasks:
        task.dist = dist


@feature('zpy-final')
def zpy_final(gen):
    env = gen.env
    bld = gen.bld
    zpy = bld.zpy
    py = bld.py

    task = gen.create_task('ZPyTask_Final')


#TODO: ...
@feature('zpy-interpreters')
def zpy_interps(gen):
    spec = getattr(gen, 'spec', None)
    if spec:
        tsk = gen.create_task('ZPyTask_Interpreters')


#TODO: ...
@feature('zpy-artifacts')
def zpy_artifacts(gen):
    spec = getattr(gen, 'spec', None)
    if spec:
        tsk = gen.create_task('ZPyTask_Artifacts')
