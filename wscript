#! /usr/bin/env python


import waflib
waflib.Configure.autoconfig = True

#TODO: pull from __init__.py like setup.py
#TODO: should this be different? embedded vs builder
VERSION = '0.6.1'
APPNAME = 'zippy'

top = '.'
out = 'build'


def options(opt):
	opt.load('zippy')


def configure(cnf):
	cnf.load('zippy')


def build(bld):
	bld.load('zippy')


# vim: set noexpandtab:
