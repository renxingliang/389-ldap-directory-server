# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2016 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---

import os
import ldap
import shutil
import sys
import pwd
import grp
import re
import socket
import subprocess
import getpass

from lib389 import _ds_shutil_copytree
from lib389._constants import *
from lib389.properties import *
from lib389.passwd import password_hash, password_generate

from lib389.nss_ssl import NssSsl

from lib389.configurations import get_config

from lib389.instance.options import General2Base, Slapd2Base

# The poc backend api
from lib389.backend import Backends
from lib389.utils import (
    assert_c,
    is_a_dn,
    ensure_bytes,
    ensure_str,
    socket_check_open,)

try:
    # There are too many issues with this on EL7
    # Out of the box, it's just outright broken ...
    import six.moves.urllib.request
    import six.moves.urllib.parse
    import six.moves.urllib.error
    import six
except ImportError:
    pass

MAJOR, MINOR, _, _, _ = sys.version_info

if MAJOR >= 3:
    import configparser
else:
    import ConfigParser as configparser


class SetupDs(object):
    """
    Implements the Directory Server installer.

    This maybe subclassed, and a number of well known steps will be called.
    This allows the inf to be shared, and for other installers to work in lock
    step with this.

    If you are subclassing you want to derive:

    _validate_config_2(self, config):
    _prepare(self, extra):
    _install(self, extra):

    If you are calling this from an INF, you can pass the config in
    _validate_config, then stash the result into self.extra

    If you have anything you need passed to your install helpers, this can
    be given in create_from_args(extra) if you are calling as an api.

    If you use create_from_inf, self.extra is passed to create_from_args for
    you. You only need to over-load the three methods above.

    A logging interface is provided to self.log that you should call.
    """

    def __init__(self, verbose=False, dryrun=False, log=None, containerised=False):
        self.verbose = verbose
        self.extra = None
        self.dryrun = dryrun
        # Expose the logger to our children.
        self.log = log.getChild('SetupDs')
        if self.verbose:
            self.log.info('Running setup with verbose')
        # This will indicate that start / stop / status should bypass systemd.
        self.containerised = containerised

    # Could be nicer if we did self._get_config_fallback_<type>?
    def _get_config_fallback(self, config, group, attr, value, boolean=False, num=False):
        try:
            if boolean:
                return config.getboolean(group, attr)
            elif num:
                return config.getint(group, attr)
            else:
                return config.get(group, attr)
        except ValueError:
            return value
        except configparser.NoOptionError:
            self.log.info("%s not specified:setting to default - %s" % (attr, value))
            return value

    def _validate_config_2(self, config):
        pass

    def _prepare(self, extra):
        pass

    def _install(self, extra):
        pass

    def _validate_ds_2_config(self, config):
        assert_c(config.has_section('slapd'), "Missing configuration section [slapd]")
        # Extract them in a way that create can understand.

        general_options = General2Base(self.log)
        general_options.parse_inf_config(config)
        general_options.verify()
        general = general_options.collect()

        if self.verbose:
            self.log.info("Configuration general %s" % general)

        slapd_options = Slapd2Base(self.log)
        slapd_options.parse_inf_config(config)
        slapd_options.verify()
        slapd = slapd_options.collect()

        if self.verbose:
            self.log.info("Configuration slapd %s" % slapd)

        backends = []
        for section in config.sections():
            if section.startswith('backend-'):
                be = {}
                # TODO: Add the other BACKEND_ types
                be[BACKEND_NAME] = section.replace('backend-', '')
                be[BACKEND_SUFFIX] = config.get(section, 'suffix')
                be[BACKEND_SAMPLE_ENTRIES] = config.get(section, 'sample_entries')
                backends.append(be)

        if self.verbose:
            self.log.info("Configuration backends %s" % backends)

        return (general, slapd, backends)

    def _validate_ds_config(self, config):
        # This will move to lib389 later.
        # Check we have all the sections.
        # Make sure we have needed keys.
        assert_c(config.has_section('general'), "Missing configuration section [general]")
        assert_c(config.has_option('general', 'config_version'), "Missing configuration config_version in section [general]")
        assert_c(config.get('general', 'config_version') >= '2', "config_version in section [general] should be 2 or greater")
        if config.get('general', 'config_version') == '2':
            # Call our child api to validate itself from the inf.
            self._validate_config_2(config)
            return self._validate_ds_2_config(config)
        else:
            assert_c(False, "Unsupported config_version in section [general]")

    def create_from_inf(self, inf_path):
        """
        Will trigger a create from the settings stored in inf_path
        """
        # Get the inf file
        if self.verbose:
            self.log.info("Using inf from %s" % inf_path)
        if not os.path.isfile(inf_path):
            self.log.error("%s is not a valid file path" % inf_path)
            return False
        config = None
        try:
            config = configparser.SafeConfigParser()
            config.read([inf_path])
        except Exception as e:
            self.log.error("Exception %s occured" % e)
            return False

        if self.verbose:
            self.log.info("Configuration %s" % config.sections())

        (general, slapd, backends) = self._validate_ds_config(config)

        # Actually do the setup now.
        self.create_from_args(general, slapd, backends, self.extra)

        return True

    def _prepare_ds(self, general, slapd, backends):

        assert_c(general['defaults'] is not None, "Configuration defaults in section [general] not found")
        if self.verbose:
            self.log.info("PASSED: using config settings %s" % general['defaults'])
        # Validate our arguments.
        assert_c(slapd['user'] is not None, "Configuration user in section [slapd] not found")
        # check the user exists
        assert_c(pwd.getpwnam(slapd['user']), "user %s not found on system" % slapd['user'])
        slapd['user_uid'] = pwd.getpwnam(slapd['user']).pw_uid
        assert_c(slapd['group'] is not None, "Configuration group in section [slapd] not found")
        assert_c(grp.getgrnam(slapd['group']), "group %s not found on system" % slapd['group'])
        slapd['group_gid'] = grp.getgrnam(slapd['group']).gr_gid
        # check this group exists
        # Check that we are running as this user / group, or that we are root.
        assert_c(os.geteuid() == 0 or getpass.getuser() == slapd['user'], "Not running as user root or %s, may not have permission to continue" % slapd['user'])

        if self.verbose:
            self.log.info("PASSED: user / group checking")

        assert_c(general['full_machine_name'] is not None, "Configuration full_machine_name in section [general] not found")
        assert_c(general['strict_host_checking'] is not None, "Configuration strict_host_checking in section [general] not found")
        if general['strict_host_checking'] is True:
            # Check it resolves with dns
            assert_c(socket.gethostbyname(general['full_machine_name']), "Strict hostname check failed. Check your DNS records for %s" % general['full_machine_name'])
            if self.verbose:
                self.log.info("PASSED: Hostname strict checking")

        assert_c(slapd['prefix'] is not None, "Configuration prefix in section [slapd] not found")
        if (slapd['prefix'] != ""):
            assert_c(os.path.exists(slapd['prefix']), "Prefix location '%s' not found" % slapd['prefix'])
        if self.verbose:
            self.log.info("PASSED: prefix checking")

        # We need to know the prefix before we can do the instance checks
        assert_c(slapd['instance_name'] is not None, "Configuration instance_name in section [slapd] not found")
        # Check if the instance exists or not.
        # Should I move this import? I think this prevents some recursion
        from lib389 import DirSrv
        ds = DirSrv(verbose=self.verbose)
        ds.containerised = self.containerised
        ds.prefix = slapd['prefix']
        insts = ds.list(serverid=slapd['instance_name'])
        assert_c(len(insts) == 0, "Another instance named '%s' may already exist" % slapd['instance_name'])

        if self.verbose:
            self.log.info("PASSED: instance checking")

        assert_c(slapd['root_dn'] is not None, "Configuration root_dn in section [slapd] not found")
        # Assert this is a valid DN
        assert_c(is_a_dn(slapd['root_dn']), "root_dn in section [slapd] is not a well formed LDAP DN")
        assert_c(slapd['root_password'] is not None, "Configuration root_password in section [slapd] not found")
        # Check if pre-hashed or not.
        # !!!!!!!!!!!!!!

        # Right now, the way that rootpw works on ns-slapd works, it force hashes the pw
        # see https://fedorahosted.org/389/ticket/48859
        if not re.match('^\{[A-Z0-9]+\}.*$', slapd['root_password']):
            # We need to hash it. Call pwdhash-bin.
            # slapd['root_password'] = password_hash(slapd['root_password'], prefix=slapd['prefix'])
            pass
        else:
            pass

        # Create a random string
        # Hash it.
        # This will be our temporary rootdn password so that we can do
        # live mods and setup rather than static ldif manipulations.
        self._raw_secure_password = password_generate()
        self._secure_password = password_hash(self._raw_secure_password, bin_dir=slapd['bin_dir'])

        if self.verbose:
            self.log.info("INFO: temp root password set to %s" % self._raw_secure_password)
            self.log.info("PASSED: root user checking")

        assert_c(slapd['port'] is not None, "Configuration port in section [slapd] not found")
        assert_c(socket_check_open('::1', slapd['port']) is False, "port %s is already in use" % slapd['port'])
        # We enable secure port by default.
        assert_c(slapd['secure_port'] is not None, "Configuration secure_port in section [slapd] not found")
        assert_c(socket_check_open('::1', slapd['secure_port']) is False, "secure_port %s is already in use" % slapd['secure_port'])
        if self.verbose:
            self.log.info("PASSED: network avaliability checking")

        # Make assert_cions of the paths?

        # Make assert_cions of the backends?

    def create_from_args(self, general, slapd, backends=[], extra=None):
        """
        Actually does the setup. this is what you want to call as an api.
        """
        # Check we have privs to run

        self.log.info("READY: Preparing installation for %s" % slapd['instance_name'])
        self._prepare_ds(general, slapd, backends)
        # Call our child api to prepare itself.
        self._prepare(extra)

        self.log.info("READY: Beginning installation for %s" % slapd['instance_name'])

        if self.dryrun:
            self.log.info("NOOP: Dry run requested")
        else:
            # Actually trigger the installation.
            self._install_ds(general, slapd, backends)
            # Call the child api to do anything it needs.
            self._install(extra)
        self.log.info("FINISH: Completed installation for %s" % slapd['instance_name'])

    def _install_ds(self, general, slapd, backends):
        """
        Actually install the Ds from the dicts provided.

        You should never call this directly, as it bypasses assert_cions.
        """
        # register the instance to /etc/sysconfig
        # We do this first so that we can trick remove-ds.pl if needed.
        # There may be a way to create this from template like the dse.ldif ...
        initconfig = ""
        with open("%s/dirsrv/config/template-initconfig" % slapd['sysconf_dir']) as template_init:
            for line in template_init.readlines():
                initconfig += line.replace('{{', '{', 1).replace('}}', '}', 1).replace('-', '_')
        try:
            os.makedirs("%s/sysconfig" % slapd['sysconf_dir'], mode=0o775)
        except FileExistsError:
            pass
        with open("%s/sysconfig/dirsrv-%s" % (slapd['sysconf_dir'], slapd['instance_name']), 'w') as f:
            f.write(initconfig.format(
                SERVER_DIR=slapd['lib_dir'],
                SERVERBIN_DIR=slapd['sbin_dir'],
                CONFIG_DIR=slapd['config_dir'],
                INST_DIR=slapd['inst_dir'],
                RUN_DIR=slapd['run_dir'],
                DS_ROOT='',
                PRODUCT_NAME='slapd',
            ))

        # Create all the needed paths
        # we should only need to make bak_dir, cert_dir, config_dir, db_dir, ldif_dir, lock_dir, log_dir, run_dir? schema_dir,
        for path in ('backup_dir', 'cert_dir', 'config_dir', 'db_dir', 'ldif_dir', 'lock_dir', 'log_dir', 'run_dir'):
            if self.verbose:
                self.log.info("ACTION: creating %s" % slapd[path])
            try:
                os.makedirs(slapd[path], mode=0o775)
            except OSError:
                pass
            os.chown(slapd[path], slapd['user_uid'], slapd['group_gid'])
        ### Warning! We need to down the directory under db too for .restore to work.
        # See dblayer.c for more!
        db_parent = os.path.join(slapd['db_dir'], '..')
        os.chown(db_parent, slapd['user_uid'], slapd['group_gid'])

        # Copy correct data to the paths.
        # Copy in the schema
        #  This is a little fragile, make it better.
        # It won't matter when we move schema to usr anyway ...

        _ds_shutil_copytree(os.path.join(slapd['sysconf_dir'], 'dirsrv/schema'), slapd['schema_dir'])
        os.chown(slapd['schema_dir'], slapd['user_uid'], slapd['group_gid'])

        # Copy in the collation
        srcfile = os.path.join(slapd['sysconf_dir'], 'dirsrv/config/slapd-collations.conf')
        dstfile = os.path.join(slapd['config_dir'], 'slapd-collations.conf')
        shutil.copy2(srcfile, dstfile)
        os.chown(dstfile, slapd['user_uid'], slapd['group_gid'])

        # Copy in the certmap configuration
        srcfile = os.path.join(slapd['sysconf_dir'], 'dirsrv/config/certmap.conf')
        dstfile = os.path.join(slapd['config_dir'], 'certmap.conf')
        shutil.copy2(srcfile, dstfile)
        os.chown(dstfile, slapd['user_uid'], slapd['group_gid'])

        # If we are on the correct platform settings, systemd
        if general['systemd'] and not self.containerised:
            # Should create the symlink we need, but without starting it.
            subprocess.check_call(["/usr/bin/systemctl",
                                    "enable",
                                    "dirsrv@%s" % slapd['instance_name']])
        # Else we need to detect other init scripts?

        # Bind sockets to our type?

        # Create certdb in sysconfidir
        if self.verbose:
            self.log.info("ACTION: Creating certificate database is %s" % slapd['cert_dir'])

        # Create dse.ldif with a temporary root password.
        # The template is in slapd['data_dir']/dirsrv/data/template-dse.ldif
        # Variables are done with %KEY%.
        # You could cheat and read it in, do a replace of % to { and } then use format?
        if self.verbose:
            self.log.info("ACTION: Creating dse.ldif")
        dse = ""
        with open(os.path.join(slapd['data_dir'], 'dirsrv', 'data', 'template-dse.ldif')) as template_dse:
            for line in template_dse.readlines():
                dse += line.replace('%', '{', 1).replace('%', '}', 1)

        with open(os.path.join(slapd['config_dir'], 'dse.ldif'), 'w') as file_dse:
            file_dse.write(dse.format(
                schema_dir=slapd['schema_dir'],
                lock_dir=slapd['lock_dir'],
                tmp_dir=slapd['tmp_dir'],
                cert_dir=slapd['cert_dir'],
                ldif_dir=slapd['ldif_dir'],
                bak_dir=slapd['backup_dir'],
                run_dir=slapd['run_dir'],
                inst_dir="",
                log_dir=slapd['log_dir'],
                fqdn=general['full_machine_name'],
                ds_port=slapd['port'],
                ds_user=slapd['user'],
                rootdn=slapd['root_dn'],
                # ds_passwd=slapd['root_password'],
                ds_passwd=self._secure_password,  # We set our own password here, so we can connect and mod.
                ds_suffix='',
                config_dir=slapd['config_dir'],
                db_dir=slapd['db_dir'],
            ))

        # open the connection to the instance.

        # Should I move this import? I think this prevents some recursion
        from lib389 import DirSrv
        ds_instance = DirSrv(self.verbose)
        ds_instance.containerised = self.containerised
        args = {
            SER_PORT: slapd['port'],
            SER_SERVERID_PROP: slapd['instance_name'],
            SER_ROOT_DN: slapd['root_dn'],
            SER_ROOT_PW: self._raw_secure_password,
            SER_DEPLOYED_DIR: slapd['prefix']
        }

        ds_instance.allocate(args)
        # Does this work?
        assert_c(ds_instance.exists(), "Instance failed to install, does not exist when expected")


        # Create a certificate database.
        tlsdb = NssSsl(dbpath=slapd['cert_dir'])
        if not tlsdb._db_exists():
            tlsdb.reinit()

        if slapd['self_sign_cert']:
            # If it doesn't exist, create a cadb.
            ssca_path = os.path.join(slapd['sysconf_dir'], 'dirsrv/ssca/')
            ssca = NssSsl(dbpath=ssca_path)
            if not ssca._db_exists():
                ssca.reinit()
                ssca.create_rsa_ca()

            csr = tlsdb.create_rsa_key_and_csr()
            (ca, crt) = ssca.rsa_ca_sign_csr(csr)
            tlsdb.import_rsa_crt(ca, crt)

        ## LAST CHANCE, FIX PERMISSIONS.
        # Selinux fixups?
        # Restorecon of paths?

        # Start the server
        ds_instance.start(timeout=60)
        ds_instance.open()

        # In some cases we may want to change log settings
        # ds_instance.config.enable_log('audit')

        # Create the configs related to this version.
        base_config = get_config(general['defaults'])
        base_config_inst = base_config(ds_instance)
        base_config_inst.apply_config(install=True)

        # Setup TLS with the instance.
        ds_instance.config.set('nsslapd-secureport', '%s' % slapd['secure_port'])
        if slapd['self_sign_cert']:
            ds_instance.config.set('nsslapd-security', 'on')

        # Create the backends as listed
        # Load example data if needed.
        for backend in backends:
            ds_instance.backends.create(properties=backend)

        # Make changes using the temp root
        # Change the root password finally

        # Initialise ldapi socket information. IPA expects this ....
        ds_instance.config.set('nsslapd-ldapifilepath', ds_instance.get_ldapi_path())
        ds_instance.config.set('nsslapd-ldapilisten', 'on')

        # Complete.
        ds_instance.config.set('nsslapd-rootpw',
                               ensure_str(slapd['root_password']))

        if self.containerised:
            # In a container build we need to stop DirSrv at the end
            ds_instance.stop()
        else:
            # Restart for changes to take effect - this could be removed later
            ds_instance.restart(post_open=False)

