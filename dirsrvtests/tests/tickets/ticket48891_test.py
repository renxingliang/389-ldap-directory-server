# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2015 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---
#
import os
import time
import ldap
import logging
import pytest
from lib389 import DirSrv, Entry
from lib389._constants import *
from lib389.properties import *
from lib389.tasks import *
import fnmatch

log = logging.getLogger(__name__)

CONFIG_DN = 'cn=config'
RDN_VAL_SUFFIX = 'ticket48891.org'
MYSUFFIX = 'dc=%s' % RDN_VAL_SUFFIX
MYSUFFIXBE = 'ticket48891'

SEARCHFILTER = '(objectclass=person)'

OTHER_NAME = 'other_entry'
MAX_OTHERS = 10


class TopologyStandalone(object):
    def __init__(self, standalone):
        standalone.open()
        self.standalone = standalone


@pytest.fixture(scope="module")
def topology(request):
    '''
        This fixture is used to standalone topology for the 'module'.
    '''
    standalone = DirSrv(verbose=False)

    # Args for the standalone instance
    args_instance[SER_HOST] = HOST_STANDALONE
    args_instance[SER_PORT] = PORT_STANDALONE
    args_instance[SER_SERVERID_PROP] = SERVERID_STANDALONE
    args_standalone = args_instance.copy()
    standalone.allocate(args_standalone)

    # Get the status of the instance and restart it if it exists
    instance_standalone = standalone.exists()

    # Remove the instance
    if instance_standalone:
        standalone.delete()

    # Create the instance
    standalone.create()

    # Used to retrieve configuration information (dbdir, confdir...)
    standalone.open()

    def fin():
        standalone.delete()
    request.addfinalizer(fin)

    # Here we have standalone instance up and running
    return TopologyStandalone(standalone)


def test_ticket48891_setup(topology):
    """
    Check there is no core
    Create a second backend
    stop DS (that should trigger the core)
    check there is no core
    """
    log.info('Testing Ticket 48891 - ns-slapd crashes during the shutdown after adding attribute with a matching rule')

    # bind as directory manager
    topology.standalone.log.info("Bind as %s" % DN_DM)
    topology.standalone.simple_bind_s(DN_DM, PASSWORD)

    # check there is no core
    entry = topology.standalone.search_s(CONFIG_DN, ldap.SCOPE_BASE,
                                         "(cn=config)", ['nsslapd-errorlog'])
    assert entry
    path = entry[0].getValue('nsslapd-errorlog').replace('errors', '')
    log.debug('Looking for a core file in: ' + path)
    cores = fnmatch.filter(os.listdir(path), 'core.*')
    assert len(cores) == 0

    topology.standalone.log.info("\n\n######################### SETUP SUFFIX o=ticket48891.org ######################\n")

    topology.standalone.backend.create(MYSUFFIX, {BACKEND_NAME: MYSUFFIXBE})
    topology.standalone.mappingtree.create(MYSUFFIX, bename=MYSUFFIXBE)
    topology.standalone.add_s(Entry((MYSUFFIX, {
                                            'objectclass': "top domain".split(),
                                            'dc': RDN_VAL_SUFFIX})))

    topology.standalone.log.info("\n\n######################### Generate Test data ######################\n")

    # add dummy entries on both backends
    for cpt in range(MAX_OTHERS):
        name = "%s%d" % (OTHER_NAME, cpt)
        topology.standalone.add_s(Entry(("cn=%s,%s" % (name, SUFFIX), {
                                            'objectclass': "top person".split(),
                                            'sn': name,
                                            'cn': name})))
    for cpt in range(MAX_OTHERS):
        name = "%s%d" % (OTHER_NAME, cpt)
        topology.standalone.add_s(Entry(("cn=%s,%s" % (name, MYSUFFIX), {
                                            'objectclass': "top person".split(),
                                            'sn': name,
                                            'cn': name})))

    topology.standalone.log.info("\n\n######################### SEARCH ALL ######################\n")
    topology.standalone.log.info("Bind as %s and add the READ/SEARCH SELFDN aci" % DN_DM)
    topology.standalone.simple_bind_s(DN_DM, PASSWORD)

    entries = topology.standalone.search_s(MYSUFFIX, ldap.SCOPE_SUBTREE, SEARCHFILTER)
    topology.standalone.log.info("Returned %d entries.\n", len(entries))

    assert MAX_OTHERS == len(entries)

    topology.standalone.log.info('%d person entries are successfully created under %s.' % (len(entries), MYSUFFIX))
    topology.standalone.stop(timeout=1)

    cores = fnmatch.filter(os.listdir(path), 'core.*')
    for core in cores:
        core = os.path.join(path, core)
        topology.standalone.log.info('cores are %s' % core)
        assert not os.path.isfile(core)

    log.info('Testcase PASSED')


if __name__ == '__main__':
    # Run isolated
    # -s for DEBUG mode
    CURRENT_FILE = os.path.realpath(__file__)
    pytest.main("-s %s" % CURRENT_FILE)
