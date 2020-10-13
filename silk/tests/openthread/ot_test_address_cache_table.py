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
"""Test address cache table gets properly updated in case a node moves to a different parent
   in the same thread network.
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
from silk.tools.wpan_util import verify, verify_within, VerifyError
from silk.unit_tests.test_utils import random_string
from silk.utils import process_cleanup

hwr.global_instance()

PREFIX = "fd00:1234::"
POLL_INTERVAL = 400
ROUTER_TABLE_WAIT_TIME = 30
INVALID_ROUTER_ID = 63
CHILD_SUPERVISION_CHECK_TIMEOUT = 2
PARENT_SUPERVISION_INTERVAL = 1
REATTACH_WAIT_TIME = 60
ADDRESS_CACHE_TABLE_WAIT_TIME = 10
PREFIX_PROPAGATION_DELAY = 60


class TestAddressCacheTable(testcase.TestCase):
    # Build network topology
    #
    #     r1 ---- r2 ---- r3
    #     |       |       |
    #     |       |       |
    #     fed1    sed2   fed3
    #
    # fed1 and fed3 are FED children, sed2 is an SED which is first attached to r2 and
    # then forced to switch to r3.

    r2_rloc, r3_rloc, fed3_rloc = None, None, None
    r1_address, fed1_address, sed2_address, fed3_address = None, None, None, None

    @classmethod
    def hardware_select(cls: 'TestAddressCacheTable'):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.r3 = ffdb.ThreadDevBoard()
        cls.fed1 = ffdb.ThreadDevBoard()
        cls.sed2 = ffdb.ThreadDevBoard()
        cls.fed3 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.r3, cls.fed1, cls.sed2, cls.fed3]

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
    def tearDownClass(cls: 'TestAddressCacheTable'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def get_rloc_and_ipv6_address_for_prefix(self):
        TestAddressCacheTable.r2_rloc = int(self.r2.getprop(wpan.WPAN_THREAD_RLOC16), 16)
        TestAddressCacheTable.r3_rloc = int(self.r3.getprop(wpan.WPAN_THREAD_RLOC16), 16)
        TestAddressCacheTable.fed3_rloc = int(self.fed3.getprop(wpan.WPAN_THREAD_RLOC16), 16)
        TestAddressCacheTable.r1_address = self.r1.find_ip6_address_with_prefix(PREFIX)
        TestAddressCacheTable.fed1_address = self.fed1.find_ip6_address_with_prefix(PREFIX)
        TestAddressCacheTable.sed2_address = self.sed2.find_ip6_address_with_prefix(PREFIX)
        TestAddressCacheTable.fed3_address = self.fed3.find_ip6_address_with_prefix(PREFIX)

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
        for node1, node2 in [(self.r1, self.fed1), (self.r1, self.r2),
                             (self.r2, self.sed2), (self.r2, self.r3),
                             (self.r3, self.fed3)]:
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

        self.sed2.join(self.network_data, "sleepy-end-device")
        self.sed2.set_sleep_poll_interval(POLL_INTERVAL)
        self.wait_for_completion(self.device_list)

        for node in [self.fed1, self.fed3]:
            node.join(self.network_data, "end-node")
            self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_verify_node_type_and_parent(self):
        self.assertTrue(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        self.assertTrue(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        self.assertTrue(self.r3.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        self.assertTrue(self.fed1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_END_DEVICE)
        self.assertTrue(self.sed2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_SLEEPY_END_DEVICE)
        self.assertTrue(self.fed3.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_END_DEVICE)

        r1_ext_address = self.r1.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        fed1_parent = self.fed1.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(fed1_parent == r1_ext_address)

        r2_ext_address = self.r2.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        sed2_parent = self.sed2.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(sed2_parent == r2_ext_address)

        r3_ext_address = self.r3.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        fed3_parent = self.fed3.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(fed3_parent == r3_ext_address)

    @testcase.test_method_decorator
    def test03_verify_route_from_r1_to_r3(self):
        # Wait till we have a valid "next hop" route on r1 towards r3
        self.r1.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=True, preferred=True)
        self.wait_for_completion(self.device_list)

        # Wait for prefix to get added to all the nodes
        time.sleep(PREFIX_PROPAGATION_DELAY)

        self.get_rloc_and_ipv6_address_for_prefix()

        def check_r1_router_table():
            router_table = wpan_table_parser.parse_router_table_result(self.r1.get(wpan.WPAN_THREAD_ROUTER_TABLE))
            verify(len(router_table) == 3)

            for entry in router_table:
                if entry.rloc16 == self.r3_rloc:
                    verify(entry.next_hop != INVALID_ROUTER_ID)

        verify_within(check_r1_router_table, ROUTER_TABLE_WAIT_TIME)

    @testcase.test_method_decorator
    def test04_verify_address_cache_table_on_r1(self):
        # Send a single UDP message from r1 to sed2
        # Send a single UDP message from r1 to fed3
        self.transmit_receive_udp_message([(self.r1, self.sed2, self.r1_address, self.sed2_address),
                                           (self.r1, self.fed3, self.r1_address, self.fed3_address)])
        time.sleep(ADDRESS_CACHE_TABLE_WAIT_TIME)
        # The address cache table on r1 should contain two entries for sed2 and fed3 addresses.

        addr_cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        addr_cache_table = wpan_table_parser.parse_address_cache_table_result(addr_cache_table)
        verify(len(addr_cache_table) == 2)

        for entry in addr_cache_table:
            if entry.address == self.sed2_address:
                # Entry for sed2 should point towards its parent r2.
                verify(entry.rloc16 == self.r2_rloc)
            elif entry.address == self.fed3_address:
                # Entry for fed3 should point towards fed3 itself.
                verify(entry.rloc16 == self.fed3_rloc)
            else:
                raise VerifyError("Unknown entry in the address cache table")

    @testcase.test_method_decorator
    def test05_verify_sed2_forced_switch_to_parent_r3(self):
        # Force sed2 to switch its parent from r2 to r3
        self.sed2.setprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, str(CHILD_SUPERVISION_CHECK_TIMEOUT))
        self.r3.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))

        self.r2.un_allowlist_node(self.sed2)
        self.r3.allowlist_node(self.sed2)
        self.sed2.allowlist_node(self.r3)

        # Wait for sed2 to detach from r2 and attach to r3.
        #
        # Upon re-attach, previous parent r2 is notified and should remove sed2 from
        # its child table.

        def check_sed2_is_removed_from_r2_child_table():
            child_table = self.r2.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
            child_table = wpan_table_parser.parse_child_table_address_result(child_table)
            verify(len(child_table) == 0)

        verify_within(check_sed2_is_removed_from_r2_child_table, REATTACH_WAIT_TIME)

        # Verify that both sed2, fed3 are children of r3
        child_table = self.r3.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_address_result(child_table)
        verify(len(child_table) == 2)

    @testcase.test_method_decorator
    def test06_verify_address_cache_table_on_r1_removes_sed2(self):

        # New network topology
        #
        #     r1 ---- r2 ---- r3
        #     |               /\
        #     |              /  \
        #     fed1           sed2 fed3

        # From r1 send again to sed2 (which is now a child of r3).
        #
        # Note that r1 still has r2 as the destination for sed2's address in its address
        # cache table.  But since r2 is aware that sed2 is no longer its child, when it
        # receives the IPv6 message with sed2's address, r2 itself would do an address
        # query for the address and forward the IPv6 message.

        self.transmit_receive_udp_message([(self.r1, self.sed2, self.r1_address, self.sed2_address)])
        time.sleep(ADDRESS_CACHE_TABLE_WAIT_TIME)

        # The address cache table on r1 should have sed2's address removed.
        addr_cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        addr_cache_table = wpan_table_parser.parse_address_cache_table_result(addr_cache_table)
        verify(len(addr_cache_table) == 1)

        for entry in addr_cache_table:
            if entry.address == self.fed3_address:
                # Entry for fed3 should still point towards fed3
                verify(entry.rloc16 == self.fed3_rloc)
            else:
                raise VerifyError("Unknown entry in the address cache table")

    @testcase.test_method_decorator
    def test07_verify_address_cache_table_on_r1_adds_sed2(self):
        # Send a UDP message from r1 to sed2.
        self.transmit_receive_udp_message([(self.r1, self.sed2, self.r1_address, self.sed2_address)])

        time.sleep(ADDRESS_CACHE_TABLE_WAIT_TIME)
        # The address cache table on r1 should have both fed1 and sed2.

        addr_cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        addr_cache_table = wpan_table_parser.parse_address_cache_table_result(addr_cache_table)
        verify(len(addr_cache_table) == 2)

        for entry in addr_cache_table:
            if entry.address == self.sed2_address:
                # Entry for sed2 should point towards r3
                verify(entry.rloc16 == self.r3_rloc)
            elif entry.address == self.fed3_address:
                # Entry for fed3 should still point towards fed3
                verify(entry.rloc16 == self.fed3_rloc)
            else:
                raise VerifyError("Unknown entry in the address cache table")

    @testcase.test_method_decorator
    def test08_verify_sed2_forced_switch_to_parent_r2(self):
        # Force sed2 to switch its parent from r3 to r2
        self.sed2.setprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, str(CHILD_SUPERVISION_CHECK_TIMEOUT))
        self.r2.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))

        self.r3.un_allowlist_node(self.sed2)
        self.r2.allowlist_node(self.sed2)
        self.sed2.allowlist_node(self.r2)

        # Wait for sed2 to detach from r3 and attach to r2.
        #
        # Upon re-attach, previous parent r3 is notified and should remove sed2 from
        # its child table.
        def check_sed2_is_removed_from_r3_child_table():
            child_table = self.r3.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
            child_table = wpan_table_parser.parse_child_table_address_result(child_table)
            verify(len(child_table) == 1)

        verify_within(check_sed2_is_removed_from_r3_child_table, REATTACH_WAIT_TIME)

        # Verify that sed2 is a child of r2
        child_table = self.r2.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_address_result(child_table)
        verify(len(child_table) == 1)

    @testcase.test_method_decorator
    def test09_verify_address_cache_table_on_r1_updates_sed2(self):
        # New network topology
        #
        #     r1 ---- r2 ---- r3
        #     |       |       |
        #     |       |       |
        #     fed1    sed2   fed3

        # Send a UDP message from sed2 to fed1.
        # This message will be forwarded by r1 to its FED child fed1.
        self.transmit_receive_udp_message([(self.sed2, self.fed1, self.sed2_address, self.fed1_address)])
        time.sleep(ADDRESS_CACHE_TABLE_WAIT_TIME)

        # r1 upon receiving and forwarding the message from sed2 (through r2 now) should
        # update its address cache table for sed2 (address cache update through snooping).
        #
        # verify that the address cache table is updated correctly.
        addr_cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        addr_cache_table = wpan_table_parser.parse_address_cache_table_result(addr_cache_table)
        verify(len(addr_cache_table) == 2)

        for entry in addr_cache_table:
            if entry.address == self.sed2_address:
                # Entry for sed2's address should now point to r2
                verify(entry.rloc16 == self.r2_rloc)
            elif entry.address == self.fed3_address:
                # Entry for fed3's address should still point to fed3
                verify(entry.rloc16 == self.fed3_rloc)
            else:
                raise VerifyError("Unknown entry in the address cache table")

    @testcase.test_method_decorator
    def test10_verify_sed2_forced_switch_again_to_parent_r3(self):
        # Force sed2 to switch its parent from r2 to r3
        self.sed2.setprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, str(CHILD_SUPERVISION_CHECK_TIMEOUT))
        self.r3.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))

        self.r2.un_allowlist_node(self.sed2)
        self.r3.allowlist_node(self.sed2)
        self.sed2.allowlist_node(self.r3)

        # Wait for sed2 to detach from r2 and attach to r3.
        #
        # Upon re-attach, previous parent r2 is notified and should remove sed2 from its child table.

        def check_sed2_is_removed_from_r2_child_table():
            child_table = self.r2.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
            child_table = wpan_table_parser.parse_child_table_address_result(child_table)
            verify(len(child_table) == 0)

        verify_within(check_sed2_is_removed_from_r2_child_table, REATTACH_WAIT_TIME)

        # Verify that both sed2, fed3 are children of r3
        child_table = self.r3.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_address_result(child_table)
        verify(len(child_table) == 2)

    @testcase.test_method_decorator
    def test11_verify_address_cache_table_on_r1_again_updates_sed2(self):
        # New network topology
        #
        #     r1 ---- r2 ---- r3
        #     |               /\
        #     |              /  \
        #     fed1          sed2 fed3

        # Send a UDP message from sed2 to fed1.
        # This message will be forwarded by r1 to its FED child fed1.
        self.transmit_receive_udp_message([(self.sed2, self.fed1, self.sed2_address, self.fed1_address)])
        time.sleep(ADDRESS_CACHE_TABLE_WAIT_TIME)

        # r1 upon receiving and forwarding the message from sed2 (through r2 now) should
        # update its address cache table for sed2 (address cache update through snooping).
        #
        # verify that the address cache table is updated correctly.
        # The address cache table on r1 should have sed2's address removed.

        # The address cache table on r1 should have both fed1 and sed2.

        addr_cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        addr_cache_table = wpan_table_parser.parse_address_cache_table_result(addr_cache_table)
        verify(len(addr_cache_table) == 2)

        for entry in addr_cache_table:
            if entry.address == self.sed2_address:
                # Entry for sed2 should point towards r3
                verify(entry.rloc16 == self.r3_rloc)
            elif entry.address == self.fed3_address:
                # Entry for fed3 should still point towards fed3
                verify(entry.rloc16 == self.fed3_rloc)
            else:
                raise VerifyError("Unknown entry in the address cache table")


if __name__ == "__main__":
    unittest.main()
