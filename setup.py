#!/usr/bin/env python

# Copyright (c) 2013, C Anthony Risinger
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   1. Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#
#   2. Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#
#   3. Neither the name of zippy nor the names of its contributors may be
#      used to endorse or promote products derived from this software without
#      specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


_author = 'C Anthony Risinger'
_author_email = 'anthony@zippy.systems'
_url ='http://zippy.systems/',


from setuptools import setup
from setuptools import find_packages


# exclude=['build'] does not prevent setuptools from walking it
_packages = ['zippy'] + map('zippy.'.__add__, find_packages('zippy'))


setup(
    name='zippy',
    version='0.6.1',
    description='python environment application container/server',
    #TODO: .rst
    long_description='python environment application container/server',
    author=_author,
    author_email=_author_email,
    maintainer=_author,
    maintainer_email=_author_email,
    url=_url,
    license='New BSD',
    platforms=['any'],
    #FIXME: howto whitelist
    packages=_packages,
    #package_dir={'': ''},
    package_data={'zippy': []},
    #include_package_data=True,
    zip_safe=True,
    scripts=['scripts/activate'],
    #tests_require=[],
    #install_requires=[],
    #extras_require={
    #    'cjson': ['python-cjson'],
    #    },
    #cmdclass=cmdclasses,
    #data_files=[('zippy', ['wscript'])],
    #install_requires=['six'],
    #tests_require=['Django'],
    #test_suite='run_tests.main',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
        ],
)
