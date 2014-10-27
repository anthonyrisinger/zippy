=====
Zippy
=====

Overview
--------

Zippy is a tool for bundling your application and all of its dependencies into
a single installable.

Zippifying Your Application
---------------------------

Zippifying applications is actually quite easy, but requires that your
application is setuptools compatible. The only other requirement is a
pydist.json file (PEP 426) with at least a name, version and list of
requirements.

From your zippy directory, invoke the ``install`` command from the ``zippy.zscript``
module and point it at your application:

    python -mzippy.zscript --prefix=/path/to/installdir --destdir=/path/to/destdir --reqirements=/path/to/application install

Zippy does not currently support git URLs for requirements, but it can process
requirements that can be sourced locally. You will need to use the ``--locator``
argument to direct zippy at your local versions.

For ``django-cloud``, here is how zippy is invoked (from the zippy subdirectory):

    python -mzippy.zscript --prefix=/opt/corvisa/zippy-django-cloud --destdir=build/zippy-django-cloud --requirements=.. --locator=../packages/\* install

This produces a packaged python binary in
``build/zippy-django-cloud/opt/corvisa/zippy-django-cloud/bin/python`` that can
be invoked directly that contains django-cloud and all of its dependencies:

    zippy $ ./build/zippy-django-cloud/opt/corvisa/zippy-django-cloud/bin/python
    Python 2.7.7 (default, Oct 23 2014, 21:46:09)
    [GCC 4.8.2] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> from corvisacloud import settings
    >>>

