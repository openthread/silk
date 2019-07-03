# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
config.py

This file contains Configuration management classes for use by the silk framework

"""

import json

BLACKLIST_KEY = "blacklist"
PORT_MAPPING = "port_mapping"

CONFIG_FILENAME_DEFAULT = "hwconfig.ini"


class Config:
    """
    Class that encapsulates configuration parameters
    """

    def __init__(self, config_file=None):
        if not config_file:
            from os.path import expanduser
            config_file = expanduser("~") + "/" + CONFIG_FILENAME_DEFAULT

        self.config_file = config_file
        self.blacklist = []
        self.port_mapping = {}

        self.load()

    def load(self):
        """
        Load configuration data from file
        """
        try:
            with open(self.config_file,'r') as fd:
                try:
                    raw_dict = json.load(fd)
                except ValueError:
                    print "Writing new configuration file %s" % self.config_file
                    raw_dict = {}
                    self.store()

                if BLACKLIST_KEY in raw_dict:
                    self._load_blacklist(raw_dict[BLACKLIST_KEY])

                if PORT_MAPPING in raw_dict:
                    self._load_port_mapping(raw_dict[PORT_MAPPING])
        except IOError:
            self.store()

    def store(self):
        """
        Save configuration data to file
        """
        with open(self.config_file, 'w') as fd:
            raw_dict = {
                BLACKLIST_KEY : self.get_blacklist(),
                PORT_MAPPING : self._get_port_mapping()
            }

            json.dump(raw_dict, fd)

    def update_port_mapping(self, device_serial, port):
        """
        Update the port mapping with the specified device
        """
        print "Adding device %s to %s to port mapping" % (device_serial, port)
        self.port_mapping[device_serial] = port

        self.store()

    def __str__(self):
        return self.str()

    def str(self):
        """
        Get a string version of the config
        """

        retval = ""

        if self.blacklist:
            retval += "Blacklist: %s" % str(self.blacklist)

        if self.port_mapping:
            retval += "Port mapping: %s" % str(self.port_mapping)

        return retval

    def blacklist_mapped(self):
        """
        Determine whether the blacklist has been mapped
        """

        return self._check_blacklist()

    def _load_blacklist(self, blacklist):
        if blacklist is None:
            blacklist = []
        self.blacklist = blacklist

    def _load_port_mapping(self, port_mapping):
        if port_mapping is None:
            port_mapping = {}
        self.port_mapping = port_mapping

    def add_to_blacklist(self, serial):
        """
        Add a serial number to the blacklist
        """
        if serial not in self.blacklist:
            self.blacklist.append(serial)

        self.store()

    def get_blacklist(self):
        """
        Get the blacklist
        """

        return self.blacklist

    def get_port(self, serial):
        """
        Get the port for a particular  serial
        """

        return self.port_mapping[serial]

    def get_unmapped_blacklist(self):
        """
        Get a list of blacklist serials for which we haven't mapped yet
        """

        unmapped = []
        for blacklisted_serial in self.blacklist:
            if not self._check_blacklist_serial(blacklisted_serial):
                unmapped.append(blacklisted_serial)

        return unmapped

    def _get_port_mapping(self):
        return self.port_mapping

    def _check_blacklist(self):
        mapped = True

        if self.blacklist:
            for blacklisted_serial in self.blacklist:
                current_mapped = self._check_blacklist_serial(blacklisted_serial)

                if not current_mapped:
                    print "Device %s not in port mapping" % blacklisted_serial

                mapped &= current_mapped

        return mapped

    def _check_blacklist_serial(self, blacklisted_serial):
        mapped = True

        if self.port_mapping:
            if blacklisted_serial not in self.port_mapping:
                mapped = False
        else:
            mapped = False

        return mapped
