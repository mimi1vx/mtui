#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import errno
import getopt
import logging
import shutil

from log import *
from prompt import *
from template import *

out = logging.getLogger('mtui')


def main():
    """parsing parameter list and initializing metadata"""

    md5 = None
    team = None
    location = 'default'
    directory = os.getenv('TEMPLATEDIR', '.')
    interactive = True
    state = 'enabled'
    timeout = 300
    attributes = ''

    targets = {}

    try:
        (opts, args) = getopt.getopt(sys.argv[1:], 'inhaedl:s:t:m:vw:', ['interactive', 'non-interactive', 'help', 'asia', 'emea', 'dryrun',
                                     'location=', 'templates=', 'md5=', 'search-hosts=', 'verbose', 'timeout'])
    except getopt.GetoptError, error:
        out.error('failed to parse parameter: %s' % str(error))
        usage()

    for (parameter, argument) in opts:
        if parameter in ('-h', '--help'):
            usage()
        elif parameter in ('-a', '--asia'):
            team = 'asia'
        elif parameter in ('-e', '--emea'):
            team = 'emea'
        elif parameter in ('-m', '--md5'):
            md5 = argument
        elif parameter in ('-d', '--dryrun'):
            state = 'dryrun'
        elif parameter in ('-l', '--location'):
            location = argument
        elif parameter in ('-t', '--templates'):
            directory = argument
        elif parameter in ('-i', '--interactive'):
            interactive = True
        elif parameter in ('-n', '--non-interactive'):
            interactive = False
        elif parameter in ('-s', '--search-hosts'):
            attributes = argument.replace(',', ' ')
        elif parameter in ('-v', '--verbose'):
            out.setLevel(level=logging.DEBUG)
        elif parameter in ('-w', '--timeout'):
            try:
                timeout = int(argument)
            except Exception:
                out.error('wrong timeout value')
                sys.exit(0)
        else:
            usage()

    if md5 is None:
        out.error('please specify an update identifier')
        usage()

    try:
        update = Template(md5, team, location, directory)
    except IOError:
        if raw_input('Template does not yet exist. Try to check it out? (y/N) ').lower() in ['y', 'yes']:
            os.system('cd %s; svn co svn+ssh://svn@qam.suse.de/testreports/%s' % (directory, md5))
            try:
                update = Template(md5, team, location, directory)
            except Exception:
                sys.exit(0)
        else:
            sys.exit(0)
    except Exception:
        usage()

    metadata = update.metadata

    for (host, system) in metadata.systems.items():
        try:
            targets[host] = Target(host, system, metadata.get_package_list(), state=state, timeout=timeout)
            targets[host].add_history(['connect'])
        except Exception:
            out.warning('failed to add host %s to target list' % host)
        except KeyboardInterrupt:
            out.warning('skipping host %s' % host)

    ignored = shutil.ignore_patterns('*.svn')

    try:
        shutil.copytree('%s/scripts' % os.path.dirname(__file__), '%s/scripts' % os.path.dirname(metadata.path), ignore=ignored)
    except OSError, error:
        if error.errno == errno.ENOENT:
            out.warning('scripts/ dir not found, please copy manually')
        else:
            pass

    prompt = CommandPromt(targets, metadata)

    while True:
        try:
            if interactive:
                if attributes:
                    prompt.do_autoadd(attributes)
                prompt.cmdloop()
            else:
                prompt.do_update('all')
                prompt.do_export(None)
                prompt.do_quit(None)
        except KeyboardInterrupt:
            print


def usage():
    print
    print 'Maintenance Test Update Installer'
    print '=' * 35
    print
    print sys.argv[0], '[parameter] {-m|--md5 update}'
    print
    print 'parameters:'
    print '\t-{short},--{long:20}{description}'.format(short='a', long='asia', description='use asia template')
    print '\t-{short},--{long:20}{description}'.format(short='e', long='emea', description='use emea template (default)')
    print '\t-{short},--{long:20}{description}'.format(short='l', long='location=', description='reference host location name')
    print '\t-{short},--{long:20}{description}'.format(short='t', long='template=', description='template directory')
    print '\t-{short},--{long:20}{description}'.format(short='m', long='md5=', description='md5 update identifier')
    print '\t-{short},--{long:20}{description}'.format(short='i', long='interactive', description='interactive update shell (default)')
    print '\t-{short},--{long:20}{description}'.format(short='n', long='non-interactive', description='non-interactive update shell')
    print '\t-{short},--{long:20}{description}'.format(short='d', long='dryrun', description='start in dryrun mode')
    print '\t-{short},--{long:20}{description}'.format(short='v', long='verbose', description='enable debugging output')
    print '\t-{short},--{long:20}{description}'.format(short='w', long='timeout', description='execution timeout in seconds')
    print '\t-{short},--{long:20}{description}'.format(short='s', long='search-hosts=', description='search for hosts matching comma separated tags')
    print

    sys.exit(0)


