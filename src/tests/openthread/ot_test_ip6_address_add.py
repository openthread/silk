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

from src.config import wpan_constants as wpan
from src.tools.wpan_util import verify, verify_within
from src.tools import wpan_util
from src.tools import wpan_table_parser

import src.node.fifteen_four_dev_board as ffdb
from src.node.wpan_node import WpanCredentials
import src.hw.hw_resource as hwr
import src.tests.testcase as testcase
from src.utils import process_cleanup

import random
import unittest
import time

hwr.global_instance()

IP6_PREFIX_1 = "fd00:c0de::"
IP6_PREFIX_2 = "fd00:deed::"
IP6_PREFIX_3 = "fd00:beef::"

IP6_ADDR_1  = IP6_PREFIX_1 + "1"
IP6_ADDR_2  = IP6_PREFIX_2 + "2"
IP6_ADDR_3  = IP6_PREFIX_3 + "3"


class TestAddIPV6Address(testcase.TestCase):
    # Test description: Adding/Removing IPv6 addresses on routers and SEDs on network interface.
    #
    # Test topology:
    #
    #     r1 ---- r2
    #     |       |
    #     |       |
    #    fed1    sed2
    #
    # IPv6 addresses are added as follows:
    # - On `r2`   add `IP6_ADDR_1` with prefix `IP6_PREFIX_1`
    # - On `fed1` add `IP6_ADDR_2` with prefix `IP6_PREFIX_2`
    # - On `sed2` add `IP6_ADDR_3` with prefix `IP6_PREFIX_3`
    #
    # The test then covers the following:
    # - Verify that the addresses are present in "IPv6:AllAddresses" wpantund property on the corresponding node.
    # - Verify that all prefixes are present in network data with correct configuration flags (on all nodes).
    # - Verify that `sed2`'s address is present in `r2` (its parent) "Thread:ChildTable:Addresses".
    # - Verify that addresses/prefixes are retained by wpantund over NCP reset.
    # - Verify that when an IPv6 address is removed from network interface, its corresponding prefix is also removed from
    #   all nodes.

    poll_interval = 1500

    @classmethod
    def hardwareSelect(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.fed1 = ffdb.ThreadDevBoard()
        cls.sed2 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.fed1, cls.sed2]

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        for device in cls.all_nodes:

            device.set_logger(cls.logger)
            cls.add_test_device(device)

            device.set_up()

        cls.network_data = WpanCredentials(
            network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk="00112233445566778899aabbccdd{0:04x}".
                format(random.randint(0, 0xffff)),
            channel=random.randint(11, 25),
            fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

        cls.thread_sniffer_init(cls.network_data.channel)

    @classmethod
    @testcase.teardown_class_decorator
    def tearDownClass(cls):
        for d in cls.device_list:
            d.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def check_addresses_and_prefixes(self):
        # Verify that the addresses are present in "IPv6:AllAddresses" wpantund property on the corresponding node.
        verify(self.r2.find_ip6_address_with_prefix(IP6_PREFIX_1) == IP6_ADDR_1)
        verify(self.fed1.find_ip6_address_with_prefix(IP6_PREFIX_2) == IP6_ADDR_2)
        verify(self.sed2.find_ip6_address_with_prefix(IP6_PREFIX_3) == IP6_ADDR_3)

        for node in self.all_nodes:
            node_on_mesh_prefixes = node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES)
            print node
            print node_on_mesh_prefixes

        print '#'*30
        # Verify that all prefixes are present in network data on all nodes (with correct flags).
        for prefix in [IP6_PREFIX_1, IP6_PREFIX_2, IP6_PREFIX_3]:
            for node in self.all_nodes:
                node_on_mesh_prefixes = node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES)
                print node_on_mesh_prefixes
                prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node_on_mesh_prefixes)
                print prefixes
                for p in prefixes:
                    if p.prefix == prefix:
                        verify(p.prefix_len == '64')
                        verify(p.is_stable())
                        verify(p.is_on_mesh() == True)
                        verify(p.is_preferred() == True)
                        verify(p.is_def_route() == False)
                        verify(p.is_slaac() == False)
                        verify(p.is_dhcp() == False)
                        verify(p.is_config() == False)
                        verify(p.priority == "med")
                        break
                else:  # `for` loop finished without finding the prefix.
                    raise wpan_util.VerifyError('Did not find prefix {} on node {}'.format(prefix, node))

        # Verify that IPv6 address of `sed2` is present on `r2` (its parent) "Thread:ChildTable:Addresses".
        addr_str = self.r2.get(wpan.WPAN_THREAD_CHILD_TABLE_ADDRESSES)
        # search for index on address in the `addr_str` and ensure it is non-negative.
        verify(addr_str.find(IP6_ADDR_3) >= 0)

    @testcase.test_method_decorator
    def test01_Pairing(self):
        self.r1.whitelist_node(self.r2)
        self.r2.whitelist_node(self.r1)

        self.r1.whitelist_node(self.fed1)
        self.fed1.whitelist_node(self.r1)

        self.r2.whitelist_node(self.sed2)
        self.sed2.whitelist_node(self.r2)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        # self.logger.info(self.former.wpanctl("manual-status-check", "status", 2))
        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, 'router')

        self.fed1.join(self.network_data, "end-node")
        self.sed2.join(self.network_data, "sleepy-end-device")

        self.sed2.set_sleep_poll_interval(self.poll_interval)

        self.wait_for_completion(self.device_list)

        for _ in range(18):
            node_type = self.r2.wpanctl('get', 'get '+wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]
            print node_type == 'router'

            if node_type == 'router':
                print 'Matched!!!!!!!!!!!!!'
                break
            time.sleep(10)
        else:
            self.assertFalse(True, 'Router cannot get into router role after 180 seconds timeout')

    @testcase.test_method_decorator
    def test02_Verify_Add_IPV6(self):

        # On `r2`   add `IP6_ADDR_1` with prefix `IP6_PREFIX_1`
        # On `fed1` add `IP6_ADDR_2` with prefix `IP6_PREFIX_2`
        # On `sed2` add `IP6_ADDR_3` with prefix `IP6_PREFIX_3`

        self.r2.add_ip6_address_on_interface(IP6_ADDR_1, prefix_len=64)
        self.fed1.add_ip6_address_on_interface(IP6_ADDR_2, prefix_len=64)
        self.sed2.add_ip6_address_on_interface(IP6_ADDR_3, prefix_len=64)
        self.wait_for_completion(self.device_list)

        # Check the addresses and prefixes (wait time 60 seconds)
        verify_within(self.check_addresses_and_prefixes, wait_time=60, delay_time=10)

    @testcase.test_method_decorator
    def test03_Reset_NCP(self):

        # Reset the nodes and verify that all addresses/prefixes are preserved.
        self.fed1.reset_thread_radio()
        self.sed2.reset_thread_radio()
        self.wait_for_completion(self.device_list)
        wpan_util.verify_within(self.check_addresses_and_prefixes, wait_time=60, delay_time=10)

        # Remove address from `r2`
        self.r2.remove_ip6_address_on_interface(IP6_ADDR_1, prefix_len=64)
        self.wait_for_completion(self.device_list)

        def check_address_prefix_removed():
            # Verify that address is removed from r2
            verify(self.r2.find_ip6_address_with_prefix(IP6_PREFIX_1) == '')
            # Verify that the related prefix is also removed on all nodes
            for node in self.all_nodes:
                prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))
                for p in prefixes:
                    verify(p.prefix != IP6_PREFIX_1)

        # Check the addresses and prefixes (wait time 15 seconds)
        wpan_util.verify_within(check_address_prefix_removed, wait_time=60, delay_time=10)


if __name__ == "__main__":
    unittest.main()
