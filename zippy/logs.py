# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

from waflib import Logs


#...use default name until we actually need multiple builds
#Configure.WAF_CONFIG_LOG = 'zpy_' + Configure.WAF_CONFIG_LOG
Logs.colors_lst['BLACK'] = '\x1b[30m'
Logs.colors_lst['RED'] = '\x1b[31m'
Logs.colors_lst['BLUE'] = '\x1b[34m'
for k, v in Logs.colors_lst.items():
    if isinstance(v, str) and k.isupper():
        Logs.colors_lst['BG_' + k] = v.replace('[3', '[4', 1)
        Logs.colors_lst['BOLD_' + k] = '\x1b[01;1m' + v
        Logs.colors_lst['BG_BOLD_' + k] = (
                '\x1b[01;1m' + v.replace('[3', '[4', 1)
                )
