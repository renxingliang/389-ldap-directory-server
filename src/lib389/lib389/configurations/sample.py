# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2017 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---

from lib389.utils import ensure_str

class sampleentries(object):
    def __init__(self, instance, basedn):
        self._instance = instance
        self._basedn = ensure_str(basedn)
        self.description = None

    def apply(self):
        self._apply()

    def _apply(self):
        raise Exception('Not implemented')
