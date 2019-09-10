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

import re
import sys
import usbinfo
import collections

"""Config file key words"""
CONFIG_SERIAL_NUMBER = 'iSerialNumber'
CONFIG_INTERFACE_NUMBER = 'bInterfaceNumber'
CONFIG_DEVNAME = 'devname'
CONFIG_MANUFACTURER = 'iManufacturer'
CONFIG_PRODUCT_NAME = 'iProduct'
CONFIG_PID = 'idProduct'
CONFIG_VID = 'idVendor'


"""Regular expressions for parsing out serial number from the device name"""

# eg. /dev/tty.usbserial-14232A
DEVICE_NAME_SERIAL_REGEX = re.compile("/dev/tty\.usbserial\-(\w*)[A-Z]")

DEVICE_KNOWN_LIST = ('nRF52840_OpenThread_Device',)


def devname_get_serial(devname):
    serial = None

    match = DEVICE_NAME_SERIAL_REGEX.match(devname)
    if match:
        serial = match.group(1)

    return serial


def device_get_serial_from_devname(device):
    serial = None

    devname = device[CONFIG_DEVNAME]
    if len(devname):
        serial = devname_get_serial(devname)

    return serial


def device_get_serial(device):
    """
    Gets the serial number for a particular devcie
    """
    serial = device[CONFIG_SERIAL_NUMBER]
    if len(serial) == 0:
        serial = device_get_serial_from_devname(device)

    return serial


def device_get_interface_number(device):
    """
    Gets the interface number for a specified device
    """

    return int(device[CONFIG_INTERFACE_NUMBER])


def device_get_devname(device):
    """
    Gets the devname of the specified devcie
    """

    retval = None

    devname = device[CONFIG_DEVNAME]

    if len(devname) != 0:
        retval = devname

    # The device should mount as /dev/tty.usbserial-<serial#>
    # followed by a letter.  The letter starts at A and
    # incrememts on the interface_number.
    elif sys.platform == 'darwin':
        retval = '/dev/tty.usbserial-%s' % device_get_serial(device)
        retval += chr(ord('A') + int(device_get_interface_number(device)))

    return retval


def device_find_from_serial(device_type, serial, interface_number):
    devname = None

    devices = usbinfo.usbinfo()
    for device in devices:
        # Match the device serial number and interface number
        # from the config file.  This is wrapped in a try statement
        # because the interface number is sometimes returned as an
        # empty string.
        device_serial = device_get_serial(device)
        # print device_serial, serial
        if device_serial == serial:
            try:
                device_interface_number = device_get_interface_number(device)
                # print device_interface_number, interface_number
                if device_interface_number != interface_number:
                    continue
            except:
                continue

            devname = device_get_devname(device)
            if devname:
                break

    return devname, device


def get_all_connected_serial_devices():

    device_dict = collections.defaultdict(set)
    device_dict['Wpantund'] = {}

    devices = usbinfo.usbinfo()

    for device in devices:
        device_name = device['iProduct']

        if device_name in DEVICE_KNOWN_LIST:
            device_dict[device_name].add(device['iSerialNumber'])

    return device_dict