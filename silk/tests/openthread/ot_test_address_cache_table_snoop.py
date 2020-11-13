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
""" Test management of address cache table specifically snoop optimization, query timeout and query retry.
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
POLL_INTERVAL = 200
PORT = random.randint(10000, 10099)
MAX_SNOOPED_NON_EVICTABLE = 2
INITIAL_RETRY_DELAY = 4
MAX_CACHE_ENTRIES = 16
WAIT_TIME = 60
PREFIX_PROPAGATION_DELAY = 60

NUM_ADDRESSES = 4  # Number of addresses to add on r2, r3, c2, and c3
NUM_QUERY_ADDRS = 5
MAX_STAGGER_INTERVAL = 0.1
IP6_ADDR_1 = PREFIX + "1"
IP6_ADDR_2 = PREFIX + "2:"
IP6_ADDR_3 = PREFIX + "3:"
IP6_ADDR_4 = PREFIX + "c2:"
IP6_ADDR_5 = PREFIX + "c3:"


class TestAddressCacheTableSnoop(testcase.TestCase):
    # This test verifies the behavior of `AddressResolver` and how the cache table is managed.
    # In particular it verifies behavior query timeout and query retry and snoop optimization.

    # Build network topology
    #
    #  r3 ---- r1 ---- r2
    #  |               |
    #  |               |
    #  c3              c2
    #
    r2_rloc, r3_rloc, c2_rloc = None, None, None
    r1_address, r2_address = None, None

    @classmethod
    def hardware_select(cls: 'TestAddressCacheTableSnoop'):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.r3 = ffdb.ThreadDevBoard()
        cls.c2 = ffdb.ThreadDevBoard()
        cls.c3 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.r3, cls.c2, cls.c3]

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
    def tearDownClass(cls: 'TestAddressCacheTableSnoop'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def get_rloc_and_ipv6_address_for_prefix(self):
        TestAddressCacheTableSnoop.r2_rloc = int(self.r2.get(wpan.WPAN_THREAD_RLOC16), 16)
        TestAddressCacheTableSnoop.c2_rloc = int(self.c2.get(wpan.WPAN_THREAD_RLOC16), 16)
        TestAddressCacheTableSnoop.r3_rloc = int(self.r3.get(wpan.WPAN_THREAD_RLOC16), 16)

        TestAddressCacheTableSnoop.r1_address = self.r1.find_ip6_address_with_prefix(PREFIX)
        TestAddressCacheTableSnoop.r2_address = self.r2.find_ip6_address_with_prefix(PREFIX)

    def transmit_receive_udp_message(self, src, dst, src_address: str, dst_address: str, port: int,
                                     message: str = random_string(10), timeout: float = 0.05):

        dst.receive_udp_data(port, message, timeout)
        time.sleep(timeout)

        src.send_udp_data(dst_address, port, message, src_address, timeout=timeout)
        time.sleep(timeout)

    @testcase.test_method_decorator
    def test01_pairing(self):
        # Create allowlisted nodes based on the topology.
        for node1, node2 in [(self.r1, self.r2), (self.r1, self.r3),
                             (self.r2, self.c2), (self.r3, self.c3)]:
            node1.allowlist_node(node2)
            node2.allowlist_node(node1)

        self.r1.form(self.network_data, "router", add_ip_addr=False)
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        for node in [self.r2, self.r3]:
            node.join(self.network_data, "router", add_ip_addr=False)
            self.wait_for_completion(self.device_list)

        self.c3.join(self.network_data, "sleepy-end-device", add_ip_addr=False)
        self.c3.set_sleep_poll_interval(POLL_INTERVAL)
        self.wait_for_completion(self.device_list)

        self.c2.join(self.network_data, "end-node", add_ip_addr=False)
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_verify_node_type_and_parent(self):
        self.assertTrue(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        self.assertTrue(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        self.assertTrue(self.r3.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        self.assertTrue(self.c2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_END_DEVICE)
        self.assertTrue(self.c3.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_SLEEPY_END_DEVICE)

        r2_ext_address = self.r2.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        c2_parent = self.c2.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(c2_parent == r2_ext_address)

        r3_ext_address = self.r3.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        c3_parent = self.c3.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(c3_parent == r3_ext_address)

    @testcase.test_method_decorator
    def test03_add_prefix_and_ipv6_addresses(self):
        # Add prefix on r1
        self.r1.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=False, preferred=True)
        # Add IPv6 address on r1
        self.r1.add_ip6_address_on_interface(IP6_ADDR_1)
        self.wait_for_completion(self.device_list)

        # Add IPv6 addresses on different nodes.
        for num in range(NUM_ADDRESSES):
            self.r2.add_ip6_address_on_interface(IP6_ADDR_2 + str(num), prefix_len=64)
            self.r3.add_ip6_address_on_interface(IP6_ADDR_3 + str(num), prefix_len=64)
            self.c2.add_ip6_address_on_interface(IP6_ADDR_4 + str(num), prefix_len=64)
            self.c3.add_ip6_address_on_interface(IP6_ADDR_5 + str(num), prefix_len=64)
            self.wait_for_completion(self.device_list)

        # Wait for prefix to get added to all the nodes
        time.sleep(PREFIX_PROPAGATION_DELAY)
        self.get_rloc_and_ipv6_address_for_prefix()

    @testcase.test_method_decorator
    def test04_verify_cache_table_entries_in_query_state(self):
        # From r1 send msg to a group of addresses (not provided by any nodes in network).
        for num in range(NUM_QUERY_ADDRS):
            self.r1.send_udp_data(PREFIX + "800:" + str(num), PORT, random_string(10), self.r1_address, timeout=0.05)
            # Wait before next tx to stagger the address queries request ensuring different timeouts
            time.sleep(MAX_STAGGER_INTERVAL / NUM_QUERY_ADDRS)

        # Verify that we do see entries in cache table for all the addresses and all are in "query" state
        addr_cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        addr_cache_table = wpan_table_parser.parse_address_cache_table_result(addr_cache_table)
        verify(len(addr_cache_table) == NUM_QUERY_ADDRS)
        for entry in addr_cache_table:
            verify(entry.state == wpan.ADDRESS_CACHE_ENTRY_STATE_QUERY)
            verify(not entry.can_evict())
            verify(entry.timeout > 0)
            verify(entry.retry_delay >= INITIAL_RETRY_DELAY)

    @testcase.test_method_decorator
    def test05_verify_retry_query_behavior(self):
        # Wait till all the address queries time out and verify they enter "retry-query" state.
        def check_cache_entry_switch_to_retry_state():
            cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
            cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)
            for index in range(NUM_QUERY_ADDRS):
                self.logger.info(f"{cache_table[index].state}, {wpan.ADDRESS_CACHE_ENTRY_STATE_RETRY_QUERY}")
                verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_RETRY_QUERY)
                verify(cache_table[index].retry_delay >= 2 * INITIAL_RETRY_DELAY)

        verify_within(check_cache_entry_switch_to_retry_state, WAIT_TIME)

        # Try sending again to same addresses which are in "retry-delay" state.
        for num in range(NUM_QUERY_ADDRS):
            self.r1.send_udp_data(PREFIX + "800:" + str(num), PORT, random_string(10), self.r1_address, timeout=0.05)
        # Make sure the entries stayed in retry-delay as before.
        verify_within(check_cache_entry_switch_to_retry_state, WAIT_TIME)

        # Now wait for them to get to zero timeout.
        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)

        def check_cache_entry_in_retry_state_to_get_to_zero_timeout():
            cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
            cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)
            for index in range(NUM_QUERY_ADDRS):
                verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_RETRY_QUERY)
                verify(cache_table[index].timeout == 0)

        verify_within(check_cache_entry_in_retry_state_to_get_to_zero_timeout, WAIT_TIME)

        # Now try again using the same addresses.
        for num in range(NUM_QUERY_ADDRS):
            self.r1.send_udp_data(PREFIX + "800:" + str(num), PORT, random_string(10), self.r1_address, timeout=0.05)

        # We expect now after the delay to see retries for same addresses.
        def check_cache_entry_switch_to_query_state():
            cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
            cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)
            for index in range(NUM_QUERY_ADDRS):
                verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_QUERY)
                verify(cache_table[index].can_evict() == True)

        verify_within(check_cache_entry_switch_to_query_state, WAIT_TIME)

    @testcase.test_method_decorator
    def test06_verify_snoop_optimization(self):
        for num in range(NUM_ADDRESSES):
            self.transmit_receive_udp_message(self.r2, self.r1, PREFIX + "2:" + str(num), self.r1_address, PORT)

        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)

        # We expect to see new "snooped" entries at the top of list.
        # Also verify that only MAX_SNOOPED_NON_EVICTABLE of snooped entries are non-evictable.
        verify(len(cache_table) >= NUM_ADDRESSES)

        for index in range(NUM_ADDRESSES):
            verify(cache_table[index].address == PREFIX + "2:" + str(NUM_ADDRESSES - index - 1))
            verify(cache_table[index].rloc16 == self.r2_rloc)
            verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_SNOOPED)
            if index < NUM_ADDRESSES - MAX_SNOOPED_NON_EVICTABLE:
                verify(cache_table[index].can_evict() == True)
                verify(cache_table[index].timeout == 0)
            else:
                print(index)
                verify(cache_table[index].can_evict() == False)
                verify(cache_table[index].timeout > 0)

        # From r1 send to r2 using the addresses from snooped entries:
        for num in range(NUM_ADDRESSES):
            self.transmit_receive_udp_message(self.r1, self.r2, self.r1_address, PREFIX + "2:" + str(num), PORT)

        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)

        # We expect to see the entries to be in "cached" state now.
        verify(len(cache_table) >= NUM_ADDRESSES)

        for index in range(NUM_ADDRESSES):
            verify(cache_table[index].address == PREFIX + "2:" + str(NUM_ADDRESSES - index - 1))
            verify(cache_table[index].rloc16 == self.r2_rloc)
            verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_CACHED)

    @testcase.test_method_decorator
    def test07_verify_query_requests_last_transaction_time(self):
        # Check query requests, last transaction time

        # Send from r1 to all addresses on r3.
        for num in range(NUM_ADDRESSES):
            self.transmit_receive_udp_message(self.r1, self.r3, self.r1_address, PREFIX + "3:" + str(num), PORT)
            cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
            cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)

        # We expect to see the cache entries for the addresses pointing to r3.
        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)

        for index in range(NUM_ADDRESSES):
            verify(cache_table[index].address == PREFIX + "3:" + str(NUM_ADDRESSES - index - 1))
            verify(cache_table[index].rloc16 == self.r3_rloc)
            verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_CACHED)
            verify(cache_table[index].last_trans == 0)

        # Send from r1 to all addresses on c3 (sleepy child of r3)
        for num in range(NUM_ADDRESSES):
            self.transmit_receive_udp_message(self.r1, self.c3, self.r1_address, PREFIX + "c3:" + str(num), PORT)

        # We expect to see the cache entries for c3 addresses pointing to r3.
        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)

        for index in range(NUM_ADDRESSES):
            verify(cache_table[index].address == PREFIX + "c3:" + str(NUM_ADDRESSES - index - 1))
            verify(cache_table[index].rloc16 == self.r3_rloc)
            verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_CACHED)
            # SED's keep-alive period (`POLL_PERIOD`) is 200ms, `last_trans` should always be 0 as it is
            # the number of seconds since a keep-alive was last received from the child.
            verify(cache_table[index].last_trans == 0)

        # Send again to r2. This should cause the related cache entries to be moved to top of the list:
        for num in range(NUM_ADDRESSES):
            self.transmit_receive_udp_message(self.r1, self.r2, self.r1_address, PREFIX + "2:" + str(num), PORT)

        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)
        for index in range(NUM_ADDRESSES):
            verify(cache_table[index].address == PREFIX + "2:" + str(NUM_ADDRESSES - index - 1))
            verify(cache_table[index].rloc16 == self.r2_rloc)
            verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_CACHED)

        verify(len(cache_table) == MAX_CACHE_ENTRIES)

    @testcase.test_method_decorator
    def test08_verify_behavior_when_cache_table_is_full(self):
        # Check behavior when cache table is full.
        for num in range(NUM_QUERY_ADDRS):
            self.r1.send_udp_data(PREFIX + "900:" + str(num), PORT, random_string(10), self.r1_address, timeout=0.05)

        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)

        verify(len(cache_table) == MAX_CACHE_ENTRIES)

        # Send from c2 to r1 and verify that snoop optimization uses at most`MAX_SNOOPED_NON_EVICTABLE` entries.
        for num in range(NUM_ADDRESSES):
            self.transmit_receive_udp_message(self.c2, self.r1, PREFIX + "c2:" + str(num), self.r1_address, PORT)

        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)
        verify(len(cache_table) == MAX_CACHE_ENTRIES)

        snooped_entries = [entry for entry in cache_table if entry.state == wpan.ADDRESS_CACHE_ENTRY_STATE_SNOOPED]
        verify(len(snooped_entries) == MAX_SNOOPED_NON_EVICTABLE)

        for entry in snooped_entries:
            verify(entry.rloc16 == self.c2_rloc)
            verify(entry.state == wpan.ADDRESS_CACHE_ENTRY_STATE_SNOOPED)
            verify(entry.can_evict() == False)
            verify(entry.timeout > 0)

        # Now send from r1 to c2, some of the snooped entries would be used, others would go through full address query.
        for num in range(NUM_ADDRESSES):
            self.transmit_receive_udp_message(self.r1, self.c2, self.r1_address, PREFIX + "c2:" + str(num), PORT)

        cache_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_ADDRESS_CACHE_TABLE, 2)
        cache_table = wpan_table_parser.parse_address_cache_table_result(cache_table)
        verify(len(cache_table) == MAX_CACHE_ENTRIES)

        # Verify that c2 entries are now at the top of cache list.
        for index in range(NUM_ADDRESSES):
            verify(cache_table[index].address == PREFIX + "c2:" + str(NUM_ADDRESSES - index - 1))
            verify(cache_table[index].rloc16 == self.c2_rloc)
            verify(cache_table[index].state == wpan.ADDRESS_CACHE_ENTRY_STATE_CACHED)


if __name__ == "__main__":
    unittest.main()
