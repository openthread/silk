# Copyright 2020 Google LLC
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
""" Test verifies that address cache entry associated with a SED child addresses is removed
    from new parent node ensuring we would not have a routing loop.
"""

import random
import time
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify, verify_within
from silk.unit_tests.test_utils import random_string
from silk.utils import process_cleanup

hwr.global_instance()

PREFIX = "fd00:1234::"
POLL_INTERVAL = 400
INVALID_ROUTER_ID = 63
CHILD_SUPERVISION_CHECK_TIMEOUT = 2
PARENT_SUPERVISION_INTERVAL = 1
REATTACH_WAIT_TIME = 60
PREFIX_PROPAGATION_DELAY = 60


class TestClearAddressCacheTableForSed(testcase.TestCase):
    # This test verifies that address cache entry associated with a SED child
    # addresses is removed from new parent node ensuring we would not have a
    # routing loop.
    # -----------------------------------------------------------------------
    # Build network topology
    #
    #   r3 ---- r1 ---- r2
    #   |               |
    #   |               |
    #   ed3            sed
    #
    # sed is initially attached to r2 but it switches parent during test to r1 and then r3.
    # ed3 is just added to make sure r3 become router quickly (not involved in test).

    r1_address, r2_address, sed_address = None, None, None

    @classmethod
    def hardware_select(cls: 'TestClearAddressCacheTableForSed'):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.r3 = ffdb.ThreadDevBoard()
        cls.sed = ffdb.ThreadDevBoard()
        cls.ed3 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.r3, cls.sed, cls.ed3]

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        for device in cls.all_nodes:
            device.set_logger(cls.logger)
            cls.add_test_device(device)
            device.set_up()

        cls.network_data = WpanCredentials(network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
                                           psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
                                           channel=random.randint(11, 25),
                                           fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

        cls.thread_sniffer_init(cls.network_data.channel)

    @classmethod
    @testcase.teardown_class_decorator
    def tearDownClass(cls: 'TestClearAddressCacheTableForSed'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def get_ipv6_address_for_prefix(self):
        TestClearAddressCacheTableForSed.r1_address = self.r1.find_ip6_address_with_prefix(PREFIX)
        TestClearAddressCacheTableForSed.r2_address = self.r2.find_ip6_address_with_prefix(PREFIX)
        TestClearAddressCacheTableForSed.sed_address = self.sed.find_ip6_address_with_prefix(PREFIX)

    def transmit_receive_udp_message(self, addresses: list):
        timeout = 5
        delay = 1

        for i, (src, dst, src_address, dst_address) in enumerate(addresses):
            port = random.randint(10000 + i * 100, 10099 + i * 100)
            message = random_string(10)

            dst.receive_udp_data(port, message, timeout)
            time.sleep(delay)
            src.send_udp_data(dst_address, port, message, src_address)

            time.sleep(timeout - delay)

    @testcase.test_method_decorator
    def test01_pairing(self):
        # Create allowlisted nodes based on the topology.
        for node1, node2 in [(self.r1, self.r2), (self.r1, self.r3),
                             (self.r2, self.sed), (self.r3, self.ed3)]:
            node1.allowlist_node(node2)
            node2.allowlist_node(node1)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        for node in [self.r2, self.r3]:
            node.join(self.network_data, "router")
            self.wait_for_completion(self.device_list)

        self.sed.join(self.network_data, "sleepy-end-device")
        self.sed.set_sleep_poll_interval(POLL_INTERVAL)
        self.wait_for_completion(self.device_list)

        self.ed3.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_verify_node_type_and_parent(self):
        self.assertTrue(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        self.assertTrue(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        self.assertTrue(self.r3.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        self.assertTrue(self.ed3.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_END_DEVICE)
        self.assertTrue(self.sed.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_SLEEPY_END_DEVICE)

        r2_ext_address = self.r2.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        sed_parent = self.sed.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(sed_parent == r2_ext_address)

        r3_ext_address = self.r3.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        ed3_parent = self.ed3.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(ed3_parent == r3_ext_address)

    @testcase.test_method_decorator
    def test03_get_ipv6_addresses_for_prefix(self):
        # Add prefix on r1
        self.r1.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=True, preferred=True)
        self.wait_for_completion(self.device_list)

        # Wait for prefix to get added to all the nodes
        time.sleep(PREFIX_PROPAGATION_DELAY)

        self.get_ipv6_address_for_prefix()

    @testcase.test_method_decorator
    def test04_send_udp_msg_from_r1_to_sed(self):
        # Send a single UDP message from r1 to sed
        #
        # This adds an address cache entry on r1 for sed pointing to r2 (the current parent of sed).
        self.transmit_receive_udp_message([(self.r1, self.sed, self.r1_address, self.sed_address)])

    @testcase.test_method_decorator
    def test05_verify_sed_forced_switch_to_parent_r1(self):
        # Force sed to switch its parent from r2 to r1
        #
        #   r3 ---- r1 ---- r2
        #   |       |
        #   |       |
        #  ed3     sed

        self.sed.set(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, str(CHILD_SUPERVISION_CHECK_TIMEOUT))
        self.r2.set(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))
        self.r1.set(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))
        self.r3.set(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))

        self.r2.un_allowlist_node(self.sed)
        self.r1.allowlist_node(self.sed)
        self.sed.allowlist_node(self.r1)

        # Wait for sed to detach from r2 and attach to r1.

        def check_sed_is_removed_from_r2_child_table():
            child_table = self.r2.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
            child_table = wpan_table_parser.parse_child_table_address_result(child_table)
            verify(len(child_table) == 0)

        verify_within(check_sed_is_removed_from_r2_child_table, REATTACH_WAIT_TIME)

        # check that sed is now a child of r1
        child_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_address_result(child_table)
        verify(len(child_table) == 1)

    @testcase.test_method_decorator
    def test06_send_udp_msg_from_r2_to_sed(self):
        # Send a single UDP message from r2 to sed
        #
        # This adds an address cache entry on r2 for sed pointing to r1 (the current parent of sed).

        self.transmit_receive_udp_message([(self.r2, self.sed, self.r2_address, self.sed_address)])

    @testcase.test_method_decorator
    def test07_verify_sed_forced_switch_to_parent_r3(self):
        # Force sed to switch its parent from r1 to r3
        #
        #   r3 ---- r1 ---- r2
        #   | \
        #   |  \
        #   ed3  sed

        self.r1.un_allowlist_node(self.sed)
        self.r3.allowlist_node(self.sed)
        self.sed.allowlist_node(self.r3)

        # Wait for sed to detach from r1 and attach to r3.

        def check_sed_is_removed_from_r1_child_table():
            child_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
            child_table = wpan_table_parser.parse_child_table_address_result(child_table)
            verify(len(child_table) == 0)

        verify_within(check_sed_is_removed_from_r1_child_table, REATTACH_WAIT_TIME)

        # check that sed is now a child of r3 (r3 should have two child, sed and ed3)
        child_table = self.r3.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_address_result(child_table)
        verify(len(child_table) == 2)

    @testcase.test_method_decorator
    def test08_verify_r1_address_cache_entry_is_cleared(self):

        # Send a single UDP message from r1 to sed
        #
        # If the r1 address cache entry is not cleared when sed attached to r1,
        # r1 will still have an entry pointing to r2, and r2 will have an entry
        # pointing to r1, thus creating a loop (the msg will not be delivered to r3)

        self.transmit_receive_udp_message([(self.r1, self.sed, self.r1_address, self.sed_address)])


if __name__ == "__main__":
    unittest.main()
