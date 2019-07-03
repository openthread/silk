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

IP6_PREFIX = "fd00:abba::"

IP6_ADDR_1 = IP6_PREFIX + "1"
IP6_ADDR_2 = IP6_PREFIX + "2"


class TestSamePrefixonMultipleNodes(testcase.TestCase):
    poll_interval = 500

    @classmethod
    def hardwareSelect(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.sed2 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.sed2]

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
            psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
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

    def check_prefix(self):
        for node in [self.r1, self.r2]:
            prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))
            for p in prefixes:
                if p.prefix == IP6_PREFIX:
                    if (p.origin == 'ncp' and p.prefix_len == '64' and p.is_stable() and p.is_on_mesh()
                       and p.is_preferred() and not p.is_def_route() and not p.is_slaac() and not p.is_dhcp()
                       and not p.is_config() and p.priority == "med"):
                        break
            else:  # `for` loop finished without finding the prefix.
                raise wpan_util.VerifyError('Did not find prefix {} on node {}'.format(IP6_PREFIX, self.r1))

    @testcase.test_method_decorator
    def test01_Pairing(self):
        self.r1.whitelist_node(self.r2)
        self.r2.whitelist_node(self.r1)

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

        self.sed2.join(self.network_data, "sleepy-end-device")

        self.sed2.set_sleep_poll_interval(self.poll_interval)

        self.wait_for_completion(self.device_list)

        for _ in range(12):
            node_type = self.r2.wpanctl('get', 'get '+wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]
            print node_type == 'router'

            if node_type == 'router':
                print 'End-node moved up to a Router.'
                break
            time.sleep(5)
        else:
            self.assertFalse(True, 'Router cannot get into router role after 60 seconds timeout')

    @testcase.test_method_decorator
    def test02_Verify_Add_IPV6(self):

        # On `r2`   add `IP6_ADDR_1` with prefix `IP6_PREFIX_1`
        # On `fed1` add `IP6_ADDR_2` with prefix `IP6_PREFIX_2`
        # On `sed2` add `IP6_ADDR_3` with prefix `IP6_PREFIX_3`

        self.r2.add_ip6_address_on_interface(IP6_ADDR_2, prefix_len=64)
        self.wait_for_completion(self.device_list)

        # Check the addresses and prefixes (wait time 60 seconds)
        verify_within(self.check_prefix, 5)

    @testcase.test_method_decorator
    def test03_Add_same_Prefix(self):
        # After prefix is seen on r1, add an address with same prefix on r1.
        self.r1.add_ip6_address_on_interface(IP6_ADDR_1, prefix_len=64)

        # Verify that the prefix is still seen on both nodes.
        verify_within(self.check_prefix, 5)

    @testcase.test_method_decorator
    def test04_Remove_Prefix_Reset_NCP(self):
        # Save prefix length before removing
        prefixes_len_before_remove = {}
        for node in [self.r1, self.r2]:
            prefixes_len_before_remove[node] = len(
                wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES)))

        print prefixes_len_before_remove

        # Remove the address from r2 which should remove the corresponding the prefix as well
        # After this since r1 still has the address, the prefix should be present on both nodes.
        self.r2.remove_ip6_address_on_interface(IP6_ADDR_2, prefix_len=64)
        verify_within(self.check_prefix, 5)

        # Reset r1 and verify that the prefix is retained correctly (by wpantund).
        self.r1.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        verify_within(self.check_prefix, 8)

        # Remove the address on r1. Verify that prefix list has been decreased by 3.
        self.r1.remove_ip6_address_on_interface(IP6_ADDR_1, prefix_len=64)

        def check_empty_prefix_list():
            for node in [self.r1, self.r2]:
                prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))
                print len(prefixes), prefixes_len_before_remove[node]
                verify(len(prefixes) == prefixes_len_before_remove[node] - 3)

        verify_within(check_empty_prefix_list, 5)

    @testcase.test_method_decorator
    def test05_Add_Prefix_Back_To_Back(self):
        # Add both addresses back-to-back and check the prefix list to contain the prefix.
        self.r1.add_ip6_address_on_interface(IP6_ADDR_1, prefix_len=64)
        self.r2.add_ip6_address_on_interface(IP6_ADDR_2, prefix_len=64)
        verify_within(self.check_prefix, 5)


if __name__ == "__main__":
    unittest.main()
