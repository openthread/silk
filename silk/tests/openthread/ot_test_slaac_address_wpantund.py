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

import random
import unittest
import time

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools import wpan_util
from silk.tools.wpan_util import verify, verify_within
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

PREFIX = "fd00:abba:beef:cafe::"
IP_ADDRESS = PREFIX + "1234"
IP_ADDRESS_2 = PREFIX + "2"

WAIT_INTERVAL = 5


class TestSlaacAddressWpantund(testcase.TestCase):
    """
  Test description: addition/removal of SLAAC IPv6 address by `wpantund`
  Test topology:
    r1 ---- r2
         |
         |
       fed1
  SLAAC prefix and user-added IPv6 addresses added are as follows:
  - On `r1` add `PREFIX`
  - On `r2` add `PREFIX`
  - On `r1` add user-added `IP_ADDRESS`
  - On `r2` add user-added `IP_ADDRESS_2`
  This test covers the behavior of SLAAC module in wpantund:
  - Before starting the test ensure that SLAAC module on NCP is disabled on all nodes
  - Verify that adding prefix with SLAAC flag on a node causes following:
    On this node: 2 entries for prefix are seen (1 as origin:ncp (with rloc16 of this node)
            and other as origin:user (with rloc:0x0000))
            Also corresponding SLAAC IPv6 address will be added
    On other nodes: 1 entry for this prefix are seen(origin:ncp (with rloc16 of the node the prefix was added to))
            Also corresponding SLAAC IPv6 address will be added
  - Verify resetting a node re-adds the SLAAC prefix and corresponding IP address back.
  - Verify that removing the prefix, would remove the SLAAC address.
  - Verify behavior when same prefix is added/removed on multiple nodes (with or without SLAAC flag).
    When a prefix is added without SLAAC flag no ipv6 addresses are added on any node
  - Check behavior when a user-added address with the same prefix already exists.
  - Ensure removal of SLAAC prefix does not remove user-added address with same prefix.
  """

    @classmethod
    def hardware_select(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.fed1 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.fed1]

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
    def tearDownClass(cls):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def check_prefix_and_slaac_address_are_added(self):
        wpan_util.verify_correct_prefix_among_similar_prefixes(self.all_nodes,
                                                               PREFIX,
                                                               stable=True,
                                                               on_mesh=True,
                                                               slaac=True)
        wpan_util.verify_address(self.all_nodes, PREFIX)

    def check_prefix_and_slaac_address_are_removed(self):
        wpan_util.verify_no_prefix(self.all_nodes, PREFIX)
        wpan_util.verify_no_address(self.all_nodes, PREFIX)

    @testcase.test_method_decorator
    def test01_pairing(self):
        # Form the test topology
        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)

        self.r2.allowlist_node(self.fed1)
        self.fed1.allowlist_node(self.r2)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.fed1.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        for _ in range(10):
            node_type = self.r2.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            self.logger.info(node_type == "router")

            if node_type == "router":
                self.logger.info("End-node moved up to a Router.")
                break
            time.sleep(10)
        else:
            self.assertFalse(True, "Router cannot get into router role after 100 seconds timeout")

    @testcase.test_method_decorator
    def test02_disable_slaac_on_ncp(self):
        # Disable slaac module on ncp on all nodes and verify it is disabled.
        for node in self.all_nodes:
            node.setprop(wpan.WPAN_OT_SLAAC_ENABLED, "false")
            verify(node.get(wpan.WPAN_OT_SLAAC_ENABLED) == "false")

    @testcase.test_method_decorator
    def test03_verify_prefix_added(self):
        # Add slaac prefix on r1
        self.r1.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=True)
        self.wait_for_completion(self.device_list)

        # Verify that all nodes get the prefix and add the SLAAC address.
        # r1 should add 2 entries for prefix, 1 as origin:ncp (with rloc16 of r1), 2nd as origin:user (with rloc:0x0000)
        # r2 and fed1 should have 1 related prefix entry seen as origin:ncp (with rloc16 of r1)
        # Due to slaac=True prefix all the nodes should add related ip address.
        verify_within(self.check_prefix_and_slaac_address_are_added, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test04_reset_ncp_remove_prefix(self):
        # Reset r1 and verify that prefix and SLAAC address are re-added
        self.r1.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        verify_within(self.check_prefix_and_slaac_address_are_added, WAIT_INTERVAL)

        # Remove the prefix on r1 and verify that the address and prefix are removed on all nodes.
        self.r1.remove_prefix(PREFIX)
        self.wait_for_completion(self.device_list)

        verify_within(self.check_prefix_and_slaac_address_are_removed, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test05_add_same_prefix(self):
        # Add prefix on r2 with SLAAC flag
        self.r2.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=True)
        self.wait_for_completion(self.device_list)

        # Verify the prefix and related address gets added
        verify_within(self.check_prefix_and_slaac_address_are_added, WAIT_INTERVAL)

        # Add same prefix on r1 with SLAAC flag verify addresses stay as before and related prefix entries gets
        # added on all the node.
        # r1 should have 3 prefix entries((1 as origin:ncp (with rloc16 of r1), 2nd as origin:user (with rloc:0x0000))
        # and 3rd as origin:ncp (with rloc16 of r2). Similarly 3 prefix entries should be on r2.
        # On fed1 there should be 2 entries each from origin:ncp with rloc16 of r1 and r2
        self.r1.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=True)
        self.wait_for_completion(self.device_list)

        verify_within(self.check_prefix_and_slaac_address_are_added, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test06_remove_prefix_with_different_slaac_flag(self):
        # Remove prefix on r1. Verify addresses stay as before (as r2 still has
        # the same prefix) and related prefix entries belonging to r1 are removed.
        self.r1.remove_prefix(PREFIX)
        self.wait_for_completion(self.device_list)
        verify_within(self.check_prefix_and_slaac_address_are_added, WAIT_INTERVAL)

        # Remove the prefix on r2 and verify that the address and prefix are now removed on all nodes.
        self.r2.remove_prefix(PREFIX)
        self.wait_for_completion(self.device_list)
        verify_within(self.check_prefix_and_slaac_address_are_removed, WAIT_INTERVAL)

        # Add prefix on r1 without SLAAC flag, and on r2 with SLAAC flag
        # Note: without SLAAC flag no ipv6 address gets added on any node only the prefix gets added.
        self.r1.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=False)
        self.r2.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=True)
        self.wait_for_completion(self.device_list)

        # Now r1 has 3 prefix entries(1 as origin:ncp (with rloc16 of r1),2nd as origin:user (with rloc:0x0000)
        # and 3rd as origin:ncp (with rloc16 of r2)). Similarly 3 such entries should be on r2.
        # On fed1 only 2 prefix entries should be present seen as origin:ncp (with rloc16 of r1) and
        # origin:ncp (with rloc16 of r2)

        # Verify due to slaac = True flag each node gets an ip address related to the prefix
        verify_within(self.check_prefix_and_slaac_address_are_added, WAIT_INTERVAL)

        self.logger.info("Remove the prefix on r2")
        self.r2.remove_prefix(PREFIX)
        self.wait_for_completion(self.device_list)

        self.logger.info("verify slaac address is removed on all nodes")

        def check_slaac_address_is_removed():
            wpan_util.verify_no_address(self.all_nodes, PREFIX)

        verify_within(check_slaac_address_is_removed, WAIT_INTERVAL)

        # Now remove the prefix on r1 and verify that all SLAAC prefix are removed
        self.r1.remove_prefix(PREFIX)
        self.wait_for_completion(self.device_list)

        verify_within(self.check_prefix_and_slaac_address_are_removed, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test07_add_ipv6_address_for_same_prefix(self):
        # Explicitly add an ipv6 address with the prefix on r1, this should add the prefix on all nodes
        # but no ipv6 address should be added on other nodes
        self.r1.add_ip6_address_on_interface(IP_ADDRESS)

        # Add the prefix on r2 (with SLAAC flag), this should add SLAAC prefix on all nodes. And slaac related
        # ipv6 address on all nodes except r1 as it already has an address with SLAAC prefix
        self.r2.add_prefix(PREFIX, stable=True, on_mesh=True, slaac=True)
        self.wait_for_completion(self.device_list)

        verify_within(self.check_prefix_and_slaac_address_are_added, WAIT_INTERVAL)

        # Verify that on r1 we do see the user-added address
        r1_addrs = wpan_table_parser.parse_list(self.r1.get(wpan.WPAN_IP6_ALL_ADDRESSES))
        verify(IP_ADDRESS in r1_addrs)

        # Also verify that adding the prefix on r2 did not add a SLAAC address for same prefix on r1
        r1_addrs.remove(IP_ADDRESS)
        self.logger.info("r1_addrs: {}".format(r1_addrs))
        self.wait_for_completion(self.device_list)

        verify(all([not addr.startswith(PREFIX[:-1]) for addr in r1_addrs]))

        # Remove the SLAAC PREFIX on r2.
        self.r2.remove_prefix(PREFIX)
        self.wait_for_completion(self.device_list)

        def check_ip6_addresses():
            # Verify that SLAAC addresses are removed on r2 and fed1
            wpan_util.verify_no_address([self.r2, self.fed1], PREFIX)
            # And that user-added address matching the prefix is not removed on r1
            r1_addrs = wpan_table_parser.parse_list(self.r1.get(wpan.WPAN_IP6_ALL_ADDRESSES))
            verify(IP_ADDRESS in r1_addrs)

        verify_within(check_ip6_addresses, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test08_ping_user_added_address(self):
        # Add a user-added address on r2 with the same prefix
        self.r2.add_ip6_address_on_interface(IP_ADDRESS_2)
        # Ping from r2 to user-added address on r1 verifying that the address is present on NCP
        self.ping6(self.r2, IP_ADDRESS, num_pings=10, allowed_errors=5, ping_size=200)


if __name__ == "__main__":
    unittest.main()
