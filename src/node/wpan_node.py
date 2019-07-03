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
Base node profile for 6LowPAN networks (Thread, CIP)
"""
import base_node
from base_node import not_implemented

import src.tools.watchable as watchable

import src.postprocessing.wpan as mp_wpan


class WpanCredentials(object):
    """
    Class for storing WPAN credentials
    """
    def __init__(self, network_name='wpan', psk='0', channel=0, 
                 fabric_id='abdefabcdef', xpanid='000000000', panid=0):
        self.name = network_name
        self.psk = psk
        self.channel = channel
        self.fabric_id = fabric_id
        self.xpanid = xpanid
        self.panid = panid

    def __str__(self):
        return_string = "Network Name: %s\n" % self.name
        return_string += "PSK: %s\n" % self.psk
        return_string += "NCP:Channel: %s\n" % self.channel
        return_string += "Fabric ID: %s\n" % self.fabric_id
        return_string += "Network:PANID: %s\n" % self.panid
        return_string += "Network:XPANID: %s" % self.xpanid

        return return_string


class WpanNode(base_node.BaseNode):
    """
    Define the WPAN base node interface
    """
    def __init__(self, name='WpanNode'):
        super(WpanNode, self).__init__(name)

        wpan_network_state_watchable = watchable.WatchableWithHistory(name = "WPAN network state", logger = self.logger)
        self.store_data(wpan_network_state_watchable, self.wpan_network_state_label)
        wpan_network_version_watchable = watchable.WatchableWithHistory(name = "WPAN radio version", logger = self.logger)
        self.store_data(wpan_network_version_watchable, self.wpan_version_label)

        for address_type in mp_wpan.WPAN_ADDRESS_TYPES:
            address_watchable = watchable.WatchableWithHistory(name = address_type, logger = self.logger)
            self.store_data(address_watchable, self.__wpan_address_label(address_type))

    def reboot_trigger_invoked(self):
        super(WpanNode, self).reboot_trigger_invoked()
        self.wpan_network_state_clear()

    """ Data labels and getters """

    @property
    def wpan_network_state_label(self):
        return 'wpan_network_state'

    @property
    def wpan_network_state(self):
        return self.get_data(self.wpan_network_state_label)
    
    def wpan_network_state_clear(self):
        return self.wpan_network_state.set(mp_wpan.NETWORK_STATE_NO_NETWORK)

    @property
    def wpan_version_label(self):
        return 'wpan_version'

    @property
    def wpan_version(self):
        return self.get_data(self.wpan_version_label)

    def __wpan_address_label(self, address_type):
        return 'wpan_address(%s)' % address_type

    def _wpan_address(self, address_type):
        return self.get_data(self.__wpan_address_label(address_type))

    @property
    def ip6_legacy_ula_label(self):
        return self.__wpan_address_label(mp_wpan.WPAN_ADDRESS_WEAVE_LEGACY)

    @property
    def ip6_legacy_ula(self):
        """
        Legacy ULA Address (subnet 2).

        Used for alarming. This address starts with 0xFD and has the weave
        prefix.
        """
        return self.get_data(self.ip6_legacy_ula_label)

    @property
    def ip6_thread_ula_label(self):
        return self.__wpan_address_label(mp_wpan.WPAN_ADDRESS_WEAVE_THREAD)

    @property
    def ip6_thread_ula(self):
        """
        Thread ULA Address (subnet 6).

        This address starts with 0xFD and has the weave prefix.
        """
        return self.get_data(self.ip6_thread_ula_label)

    @property
    def wpan_mac_addr_label(self):
        return "wpan_mac_addr"

    @property
    def wpan_mac_addr(self):
        """
        MAC Address (Device HW address) for WPAN device.

        Removes any ':' from string
        """
        return self.get_data(self.wpan_mac_addr_label, default = '').replace(':','')

    @property
    def network_name_label(self):
        return "network_name"

    @property
    def network_name(self):
        return self.get_data(self.network_name_label)

    @property
    def panid_label(self):
        return "panid"

    @property
    def panid(self):
        return self.get_data(self.panid_label, 'hex-int', default=-1)

    @property
    def xpanid_label(self):
        return "xpanid"

    @property
    def xpanid(self):
        return self.get_data(self.xpanid_label)

    @property
    def channel_label(self):
        return "channel"

    @property
    def channel(self):
        return self.get_data(self.channel_label, int, default=0)

    @property
    def role_label(self):
        return "role"

    @property
    def role(self):
        return self.get_data(self.role_label)

    @property
    def psk_label(self):
        return "psk"

    @property
    def psk(self):
        return self.get_data(self.psk_label)

    @property
    def ip6_postfix_label(self):
        return "ip6_postfix"

    @property
    def ip6_postfix(self):
        return self.get_data(self.ip6_postfix_label)

    def ip6_postfix_process(self):
        mac_addr = self.get_data(self.ip6_postfix_label).split(':')
        postfix = ':'.join([i+j for i, j in zip(mac_addr[::2], mac_addr[1::2])])
        self.store_data(postfix[2:], self.ip6_postfix_label)

    @not_implemented
    def form(self, network, role):
        """
        Form a specified network
        At the end of the form process, the xpanid must be populated.
        The ip6_legacy_ula, ip6_thread_ula, and ip6_lla should be set as
        appropriate for the device role.
        """
        pass

    @not_implemented
    def join(self, network, role):
        """
        Join a specified network
        The ip6_legacy_ula, ip6_thread_ula, and ip6_lla should be set as
        appropriate for the device role.
        """
        pass
    
    @not_implemented
    def provisional_join(self, network, role):
        """
        Join a specified network without PSK
        """

    @not_implemented
    def complete_provisional_joining(self, network, role):
        """
        Completely join a provisionally-joined network 
        """

    @not_implemented
    def leave(self):
        """Leave the current network"""
        pass

    @not_implemented
    def resume(self):
        """Resume a previously connected network"""
        pass

    @not_implemented
    def permit_join(self, period):
        """Permit other devices to join the current network via this node"""
        pass

    @not_implemented
    def perform_active_scan(self):
        """Scan for nearby networks on all channels"""
        pass

    @not_implemented
    def wpan_expect_attached(self):
        pass
