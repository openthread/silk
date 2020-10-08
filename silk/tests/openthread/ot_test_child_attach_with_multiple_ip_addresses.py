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
import time
import unittest

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import (verify, verify_within, is_associated, verify_address)
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

WAIT_TIME = 10  # in seconds
CHILD_SUPERVISION_CHECK_TIMEOUT = 1

prefix1 = "fd00:1::"
prefix2 = "fd00:2::"
prefix3 = "fd00:3::"
prefix4 = "fd00:4::"


class TestChildAttachWithMultipleIpAddresses(testcase.TestCase):
    # Test description:
    #
    # This test covers the situation for SED child (re)attaching to a parent
    # with multiple IPv6 addresses present on the child.
    #
    # Network topology:
    #
    #   leader ---- parent (router)
    #                 |
    #                 |
    #              child (sleepy)
    #
    # Test covers the following situations:
    # - Verify adding 4 slaac prefixes on leader results in each prefix adding a slaac address on sed child too.
    # - Verify removing child from parent's allowlist results in child getting detached.
    # - Verify after parent recovers from a reset and gets associated the child ia also able to reattach to it and all
    #   child addresses are seen on the parent.
    # - Verify disabling supervision checkout on child results in quick child re-attach after a parent reset.

    poll_interval = 400

    @classmethod
    def hardware_select(cls):
        cls.leader = ffdb.ThreadDevBoard()
        cls.parent = ffdb.ThreadDevBoard()
        cls.child = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.add_test_device(cls.leader)
        cls.add_test_device(cls.parent)
        cls.add_test_device(cls.child)

        for device in cls.device_list:
            device.set_logger(cls.logger)
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

    def check_child_addresses_on_parent(self):
        child_addrs = self.parent.get(wpan.WPAN_THREAD_CHILD_TABLE_ADDRESSES)
        verify(child_addrs.find(prefix1) > 0)
        verify(child_addrs.find(prefix2) > 0)
        verify(child_addrs.find(prefix3) > 0)
        verify(child_addrs.find(prefix4) > 0)

    @testcase.test_method_decorator
    def test01_pairing(self):
        self.leader.allowlist_node(self.parent)
        self.parent.allowlist_node(self.leader)

        self.parent.allowlist_node(self.child)
        self.child.allowlist_node(self.parent)

        self.leader.form(self.network_data, "router")
        self.parent.permit_join(120)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.leader.ip6_lla)
        self.logger.info(self.leader.ip6_thread_ula)

        self.network_data.xpanid = self.leader.xpanid
        self.network_data.panid = self.leader.panid

        self.parent.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.child.join(self.network_data, "sleepy-end-device")
        self.child.set_sleep_poll_interval(self.poll_interval)
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_add_prefixes(self):
        # Add 4 prefixes (all with SLAAC bit set).
        self.logger.info("Add 4 prefixes (all with SLAAC bit set) on leader {}".format(self.leader.name))
        self.leader.add_prefix(prefix1, on_mesh=True, slaac=True, configure=True)
        self.leader.add_prefix(prefix2, on_mesh=True, slaac=True, configure=True)
        self.leader.add_prefix(prefix3, on_mesh=True, slaac=True, configure=True)
        self.leader.add_prefix(prefix4, on_mesh=True, slaac=True, configure=True)
        self.wait_for_completion(self.device_list)

        self.logger.info("Verify that the sleepy child {} gets all 4 SLAAC addresses".format(self.child.name))

        def check_addresses_on_child():
            verify_address([self.child], prefix1)
            verify_address([self.child], prefix2)
            verify_address([self.child], prefix3)
            verify_address([self.child], prefix4)

        verify_within(check_addresses_on_child, WAIT_TIME)

    @testcase.test_method_decorator
    def test03_detach_child(self):
        # Remove child from parent's allowlist
        self.parent.remove(wpan.WPAN_MAC_ALLOWLIST_ENTRIES, self.child.get(wpan.WPAN_EXT_ADDRESS)[1:-1])
        self.wait_for_completion(self.device_list)
        # Enable supervision check on child, this ensures that child is detached soon.
        self.child.set(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, str(CHILD_SUPERVISION_CHECK_TIMEOUT))

        self.logger.info("verify child {} gets detached from parent {}".format(self.child.name, self.parent.name))

        def check_child_is_detached():
            verify(not is_associated(self.child))

        verify_within(check_child_is_detached, WAIT_TIME)

    @testcase.test_method_decorator
    def test04_child_re_attach_after_parent_reset(self):
        # Now reset parent and wait for it to be associated.
        self.parent.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        self.logger.info("check parent {} is associated after reset".format(self.parent.name))

        def check_parent_is_associated():
            verify(is_associated(self.parent))

        verify_within(check_parent_is_associated, WAIT_TIME)

        self.logger.info("verify that child attaches back by following full"
                         " process starting from 'sending parent request to routers'")

        self.logger.info("check child {} is associated after reset".format(self.child.name))

        def check_child_is_associated():
            verify(is_associated(self.child))

        verify_within(check_child_is_associated, WAIT_TIME)

        self.logger.info("check all the child addresses are seen in the parent"
                         " {} child table".format(self.parent.name))
        verify_within(self.check_child_addresses_on_parent, WAIT_TIME)

    @testcase.test_method_decorator
    def test05_child_quick_re_attach_after_parent_reset(self):
        # Check the child recovery after a parent reset using quick re-attach
        # achieved via "Child Update" exchange.

        self.logger.info("Disable supervision check on the child {}.".format(self.child.name))
        self.child.set(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, "1000")
        self.child.set(wpan.WPAN_POLL_INTERVAL, "10000")
        time.sleep(0.1)

        # We use the "stat:ncp" wpantund property to verify that child does not
        # get detached.
        child_num_state_changes = len(wpan_table_parser.parse_list(self.child.get("stat:ncp")))

        # Reset parent and wait for it to be associated.
        self.parent.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        def check_parent_is_associated():
            verify(is_associated(self.parent))

        verify_within(check_parent_is_associated, WAIT_TIME)

        self.child.set(wpan.WPAN_POLL_INTERVAL, "100")

        # Verify that we again see all the child addresses in the parent's child
        # table. Note that child should register its addresses using "Child Update
        # Request" exchange.
        verify_within(self.check_child_addresses_on_parent, WAIT_TIME)

        # Verify that there was no state change on child.
        self.assertEqual(child_num_state_changes, len(wpan_table_parser.parse_list(self.child.get("stat:ncp"))))


if __name__ == "__main__":
    unittest.main()
