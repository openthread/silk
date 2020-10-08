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
"""This file contains Configuration management classes for use by the silk framework

"""

import json

DENYLIST_KEY = "denylist"
PORT_MAPPING = "port_mapping"

CONFIG_FILENAME_DEFAULT = "hwconfig.ini"


class Config(object):
    """Class that encapsulates configuration parameters.
    """

    def __init__(self, config_file=None):
        if not config_file:
            from os.path import expanduser
            config_file = expanduser("~") + "/" + CONFIG_FILENAME_DEFAULT

        self.config_file = config_file
        self.denylist = []
        self.port_mapping = {}

        self.load()

    def load(self):
        """Load configuration data from file.
        """
        try:
            with open(self.config_file, "r") as fd:
                try:
                    raw_dict = json.load(fd)
                except ValueError:
                    print("Writing new configuration file %s" % self.config_file)
                    raw_dict = {}
                    self.store()

                if DENYLIST_KEY in raw_dict:
                    self._load_denylist(raw_dict[DENYLIST_KEY])

                if PORT_MAPPING in raw_dict:
                    self._load_port_mapping(raw_dict[PORT_MAPPING])
        except IOError:
            self.store()

    def store(self):
        """
        Save configuration data to file
        """
        with open(self.config_file, "w") as fd:
            raw_dict = {DENYLIST_KEY: self.get_denylist(), PORT_MAPPING: self._get_port_mapping()}

            json.dump(raw_dict, fd)

    def update_port_mapping(self, device_serial, port):
        """
        Update the port mapping with the specified device
        """
        print("Adding device %s to %s to port mapping" % (device_serial, port))
        self.port_mapping[device_serial] = port

        self.store()

    def __str__(self):
        return self.str()

    def str(self):
        """Get a string version of the config.
        """

        retval = ""

        if self.denylist:
            retval += "Denylist: %s" % str(self.denylist)

        if self.port_mapping:
            retval += "Port mapping: %s" % str(self.port_mapping)

        return retval

    def denylist_mapped(self):
        """
        Determine whether the denylist has been mapped
        """

        return self._check_denylist()

    def _load_denylist(self, denylist):
        if denylist is None:
            denylist = []
        self.denylist = denylist

    def _load_port_mapping(self, port_mapping):
        if port_mapping is None:
            port_mapping = {}
        self.port_mapping = port_mapping

    def add_to_denylist(self, serial):
        """
        Add a serial number to the denylist
        """
        if serial not in self.denylist:
            self.denylist.append(serial)

        self.store()

    def get_denylist(self):
        """
        Get the denylist
        """

        return self.denylist

    def get_port(self, serial):
        """
        Get the port for a particular  serial
        """

        return self.port_mapping[serial]

    def get_unmapped_denylist(self):
        """
        Get a list of denylist serials for which we haven't mapped yet
        """

        unmapped = []
        for denylisted_serial in self.denylist:
            if not self._check_denylist_serial(denylisted_serial):
                unmapped.append(denylisted_serial)

        return unmapped

    def _get_port_mapping(self):
        return self.port_mapping

    def _check_denylist(self):
        mapped = True

        if self.denylist:
            for denylisted_serial in self.denylist:
                current_mapped = self._check_denylist_serial(denylisted_serial)

                if not current_mapped:
                    print("Device %s not in port mapping" % denylisted_serial)

                mapped &= current_mapped

        return mapped

    def _check_denylist_serial(self, denylisted_serial):
        mapped = True

        if self.port_mapping:
            if denylisted_serial not in self.port_mapping:
                mapped = False
        else:
            mapped = False

        return mapped
