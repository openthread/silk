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
This module maintains the set of hardware resources available for testing.
"""

import ConfigParser
import hw_module
import os.path
import src.tests

DEFAULT_CONFIG_PATH = os.path.join(src.tests.__path__[0], "hwconfig.ini")


class HardwareNotFound(Exception):
    def __init__(self, model, name):
        self.model = model
        self.name = name

    def __str__(self):
        return 'HW Model {0} not found for {2}'.format(self.model, self.name)


class HwResource:
    def __init__(self, filename=None, create=False):
        self._hw_modules = []
        self._thread_sniffer_pool = []
        self._parser = ConfigParser.SafeConfigParser()
        self._filename = filename or DEFAULT_CONFIG_PATH
        self._create = create
        if not os.path.isfile(self._filename):
            print 'ERROR: No hw config file found at {0}'.format(self._filename)

    def load_config(self):
        """Returns a Config object from a given INI file"""
        self._create_config_if_needed()

        filenames = self._parser.read(self._filename)
        if len(filenames) == 0:
            raise RuntimeError("Failed to load objects from %s. Result %s" % (self._filename, str(filenames)))

        print 'Found {0} HW Config Resources from {1}...'.format(len(self._parser.sections()), self._filename)
        self._update_hw_modules()
        print 'Located {0} Physical Resources...'.format(len(self._hw_modules))

    def free_hw_module(self, module):
        """Free a particular module"""
        if module in self._hw_modules:
            module.free()
        else:
            print 'Module %s not found!' % module.name()

    def get_hw_module(self, model, sw_version=None, name=None):
        """Get a particular hardware module"""
        if name is None:
            name = model

        if len(self._hw_modules) == 0:
            self.load_config()

        m = None
        if sw_version is None:
            m = self._find_hw_module_unclaimed_by_model(model)

        if not m:
            raise HardwareNotFound(model, name)
        m.claim()

        return m

    def add_hw_module(self, module_name, model, interface_serial, interface_number):
        """Add a hardware module to the list of modules"""
        self._create_config_if_needed()

        if not self._parser.has_section(module_name):
            self._parser.add_section(module_name)
            module = hw_module.HwModule(module_name, self._parser, model, interface_serial, interface_number)
            with open(self._filename, "w") as fp:
                self._parser.write(fp)
                fp.close()
            self._add_hw_module(module)

    def print_hw_modules(self):
        for m in self._hw_modules:
            print m

    def _create_config_if_needed(self):
        if not os.path.isfile(self._filename) and self._create:
            with open(self._filename, "w") as fp:
                fp.close()

    def _find_hw_module_unclaimed_by_model(self, model):
        for m in self._hw_modules:
            if (not m.is_claimed()) and m.model() == model:
                return m

        return None

    def _update_hw_modules(self):
        for s in self._parser.sections():
            if not self._find_hw_module_by_name(s):
                try:
                    self._add_hw_module(hw_module.HwModule(s, self._parser))
                except RuntimeError as e:
                    print "Failed to add %s" % s
                    pass

    def _add_hw_module(self, module):
        self._hw_modules.append(module)

    def get_thread_sniffer(self):
        if len(self._thread_sniffer_pool) == 0 and len(self._hw_modules) == 0:
            self.load_config()
        for sniffer in self._thread_sniffer_pool:
            if not sniffer.is_claimed():
                sniffer.claim()
                return sniffer

        return None

    def _find_hw_module_by_name(self, name):
        retval = None

        for m in self._hw_modules:
            if m.name() == name:
                retval = m

        return retval


_global_instance = None


def global_instance(filename=None):
    """ Get the common global instance """
    global _global_instance

    if _global_instance is None:
        _global_instance = HwResource(filename)

    return _global_instance

