# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2018 William Brown <william@blackhats.net.au>
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---

from lib389.plugins import Plugin

class PasswordPlugin(Plugin):
    _plugin_properties = {
        'nsslapd-pluginpath': 'libpwdstorage-plugin',
        'nsslapd-plugintype': 'pwdstoragescheme',
        'nsslapd-pluginEnabled' : 'on'
    }

    def __init__(self, instance, dn=None):
        super(PasswordPlugin, self).__init__(instance, dn)
        self._rdn_attribute = 'cn'
        self._must_attributes = [
            'nsslapd-pluginEnabled',
            'nsslapd-pluginPath',
            'nsslapd-pluginInitfunc',
            'nsslapd-pluginType',
            ]
        self._create_objectclasses = ['top', 'nsslapdplugin']
        # We'll mark this protected, and people can just disable the plugins.
        self._protected = True

class PBKDF2Plugin(PasswordPlugin):
    def __init__(self, instance, dn="cn=PBKDF2_SHA256,cn=Password Storage Schemes,cn=plugins,cn=config"):
        super(PBKDF2Plugin, self).__init__(instance, dn)

