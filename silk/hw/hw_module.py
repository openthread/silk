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
This module allows tests to change configs, since some parameters specified
can be changed.
Configs will be locked when they are read to prevent concurrent use of a
device.
"""
from silk.tools import usbdevice

# HW Config file options

HW_MODEL_OPTION = "HwModel"
HW_LINUX_PORT_OPTION = "LinuxSerialPort"
HW_MAC_PORT_OPTION = "MacSerialPort"
INTERFACE_SERIAL = "InterfaceSerialNumber"
INTERFACE_NUMBER = "USBInterfaceNumber"
DUT_SERIAL_NUMBER = "DutSerial"
OTNS_VIS_POSITION = "OTNSVisPosition"

# HW Config Models

# Nordic Dev Board NRF52840
HW_NRF52840 = "nRF52840_OpenThread_Device"
HW_NORDIC_SNIFFER = "NordicSniffer"

# Silabs Dev Board EFR32
HW_EFR32 = "Efr32"

# Generic Virtual Device (for log replay purpose)
HW_GENERIC = "Generic"

DEV_DEVICES = [HW_NRF52840, HW_EFR32, HW_NORDIC_SNIFFER]


class HwModule(object):
    """Maintains usage of a hardware resource.
    """

    def __init__(self,
                 name,
                 parser,
                 node_id,
                 layout_center=None,
                 layout_radius=None,
                 model=None,
                 interface_serial=None,
                 interface_number=None,
                 port=None,
                 dut_serial=None,
                 jlink_serial=None,
                 virtual=False):
        self._name = name
        self._parser = parser
        self._claimed = False
        self._port = port
        self._model = model
        self._dut_serial = dut_serial
        self._node_id = node_id

        if not virtual:
            if model and interface_serial and interface_number:
                if port is None:
                    self.__set_options(model, interface_serial, int(interface_number))
            elif model or interface_serial or interface_number:
                raise ValueError(
                    "You must specify either all of model, interface_serial and interface_number or none. "
                    "Provided: %s" % ([model, interface_serial, interface_number]))

            if self._port is None:
                self.set_port()

        assert (layout_center is None) == (layout_radius is None)
        self._layout_center = layout_center
        self._layout_radius = layout_radius

    def is_claimed(self):
        return self._claimed

    def claim(self):
        if self._claimed:
            raise RuntimeError("HwModule %s already claimed." % self.name)
        self._claimed = True

    def free(self):
        if self._claimed is False:
            raise RuntimeError("HwModule %s is not claimed." % self.name)
        self._claimed = False

    def name(self):
        return self._name

    def model(self):
        if self._model is not None:
            return self._model
        else:
            return self.__get_option_str(HW_MODEL_OPTION)

    def interface_serial(self):
        return self.__get_option_str(INTERFACE_SERIAL)

    def interface_number(self):
        return int(self.__get_option_float(INTERFACE_NUMBER))

    def port(self):
        return self._port

    def get_dut_serial(self):
        return self.__get_option_str(DUT_SERIAL_NUMBER)

    def get_otns_vis_position(self):
        coord_str = self.__get_option_str(OTNS_VIS_POSITION)
        parts = coord_str.split(",")
        if len(parts) != 2:
            raise ValueError("Node position must have x and y coordinates. Provided: %s" % coord_str)

        return int(parts[0]), int(parts[1])

    def get_otns_vis_node_id(self):
        return self._node_id

    def get_otns_vis_layout_center(self):
        return self._layout_center

    def get_otns_vis_layout_radius(self):
        return self._layout_radius

    def find_device_from_serial(self, device_type, serial, interface_number):
        devname, device = usbdevice.device_find_from_serial(device_type, serial, interface_number)

        return devname

    def find_dev_board_from_serial(self, serial, interface_number, model):
        return self.find_device_from_serial(model, serial, interface_number)

    def set_port(self):
        serial_to_find = self.interface_serial()
        interface_number = self.interface_number()

        model = self.model()

        if model in DEV_DEVICES:
            self._port = self.find_dev_board_from_serial(serial_to_find, interface_number, model)
        else:
            raise RuntimeError("Device not supported %s" % model)

        if self._port is None:
            raise RuntimeError("Device not found %s" % self._name)

    def __str__(self):
        return_string = "[{!s}]\n".format(self.name())
        return_string += "model: {!s}\n".format(self.model())
        return_string += "port : {!s}\n".format(self.port())
        return_string += "claim: {!s}".format(self._claimed)

        return return_string

    def __set_options(self, model, interface_serial, interface_number):
        self._parser.set(self._name, HW_MODEL_OPTION, model)
        self._parser.set(self._name, INTERFACE_SERIAL, interface_serial)
        self._parser.set(self._name, INTERFACE_NUMBER, str(interface_number))

    def __get_option_str(self, option, default=""):
        if self._parser.has_option(self._name, option):
            return self._parser.get(self._name, option)
        return default

    def __get_option_float(self, option, default=0.0):
        if self._parser.has_option(self._name, option):
            return self._parser.getfloat(self._name, option)
        return default
