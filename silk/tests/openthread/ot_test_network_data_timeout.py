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
from silk.tools.wpan_util import (verify_within, verify_prefix_with_rloc16, verify_no_prefix_with_rloc16)
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

common_prefix = "fd00:cafe::"
prefix1 = "fd00:1::"
prefix2 = "fd00:2::"
prefix3 = "fd00:3::"

WAIT_TIME = 10  # in seconds
PREFIX_SYNC_WAIT_AFTER_ROUTER_REMOVAL = 240  # in seconds


class TestNetworkDataTimeout(testcase.TestCase):
    # Test description: Network Data (on-mesh prefix) timeout and entry removal
    #
    # Network topology:
    #
    #   r1 ----- r2
    #            |
    #            |
    #            sed1 (sleepy end device)
    #
    #
    # Test covers the following steps:
    #
    # - Every node adds a unique on-mesh prefix.
    # - Every node also adds a common on-mesh prefix (with different flags).
    # - Verify that all the unique and common prefixes are present on all nodes are associated with correct RLOC16.
    # - Remove `r2` from network (which removes `sed1` as well) from Thread partition created by `r1`.
    # - Verify that all on-mesh prefixes added by `r2` or `sed1` (unique and common) are removed on `r1`.

    poll_interval = 400

    @classmethod
    def hardware_select(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.sed1 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.sed1]

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

    @testcase.test_method_decorator
    def test01_pairing(self):
        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)

        self.r2.allowlist_node(self.sed1)
        self.sed1.allowlist_node(self.r2)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.sed1.join(self.network_data, "sleepy-end-device")
        self.sed1.set_sleep_poll_interval(self.poll_interval)
        self.wait_for_completion(self.device_list)

        for _ in range(10):
            node_type = self.r2.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            self.logger.info(node_type == "router")

            if node_type == "router":
                self.logger.info("Matched!!!!!!!!!!!!!")
                break
            time.sleep(10)
        else:
            self.assertFalse(True, "Router cannot get into router role after 100 seconds timeout")

    @testcase.test_method_decorator
    def test02_verify_prefix(self):
        # Add 4 prefixes(`prefix1`, `prefix2`, `prefix3` and `common_prefix`) and
        # verify they are present on all nodes with correct flags

        # Add a unique prefix on each node.
        self.logger.info(" Adding prefix1 i.e. {} on r1 i.e. {}".format(prefix1, self.r1.name))
        self.r1.add_prefix(prefix1, on_mesh=True, preferred=True, stable=True)
        self.logger.info(" Adding prefix2 i.e. {} on r2 i.e. {}".format(prefix2, self.r2.name))
        self.r2.add_prefix(prefix2, on_mesh=True, preferred=True, stable=True)
        self.logger.info(" Adding prefix3 i.e. {} on sed1 i.e. {}".format(prefix3, self.sed1.name))
        self.sed1.add_prefix(prefix3, on_mesh=True, preferred=True, stable=True)

        # Add `common_prefix` on all three nodes with different flags
        self.logger.info(" Adding common_prefix i.e. {} on r1 i.e. {}".format(common_prefix, self.r1.name))
        self.r1.add_prefix(common_prefix, on_mesh=True, preferred=True, stable=False)
        self.logger.info(" Adding common_prefix i.e. {} on r2 i.e. {}".format(common_prefix, self.r2.name))
        self.r2.add_prefix(common_prefix, on_mesh=True, preferred=True, stable=True)
        self.logger.info(" Adding common_prefix i.e. {} on sed1 i.e. {}".format(common_prefix, self.sed1.name))
        self.sed1.add_prefix(common_prefix, on_mesh=True, preferred=False, stable=True)

        # Wait for on-mesh prefixes to be updated
        self.wait_for_completion(self.device_list)

        # Get all nodes rloc16
        r1_rloc16 = int(self.r1.get(wpan.WPAN_THREAD_RLOC16), 0)
        r2_rloc16 = int(self.r2.get(wpan.WPAN_THREAD_RLOC16), 0)
        sed1_rloc16 = int(self.sed1.get(wpan.WPAN_THREAD_RLOC16), 0)

        def check_prefixes():
            # Verify that all three `prefix1`, `prefix2`, and `prefix3` are present on all nodes and
            # are respectively associated with `r1`, r2, and `sed1` nodes.
            self.logger.info(" verify prefix1 i.e. {} added by r1 i.e. {} having rloc16:{}"
                             " is present on all nodes".format(prefix1, self.r1.name, hex(r1_rloc16)))
            verify_prefix_with_rloc16([self.r1, self.r2, self.sed1],
                                      prefix1,
                                      r1_rloc16,
                                      on_mesh=True,
                                      preferred=True,
                                      stable=True)
            self.logger.info(" verify prefix2 i.e. {} added by r2 i.e. {} having rloc16:{}"
                             " is present on all nodes".format(prefix2, self.r2.name, hex(r2_rloc16)))
            verify_prefix_with_rloc16([self.r1, self.r2, self.sed1],
                                      prefix2,
                                      r2_rloc16,
                                      on_mesh=True,
                                      preferred=True,
                                      stable=True)
            self.logger.info(" verify prefix3 i.e. {} added by sed1 i.e.{} having rloc16:{}"
                             " is present on all nodes".format(prefix3, self.sed1.name, hex(sed1_rloc16)))
            verify_prefix_with_rloc16([self.r1, self.r2, self.sed1],
                                      prefix3,
                                      sed1_rloc16,
                                      on_mesh=True,
                                      preferred=True,
                                      stable=True)

            # Verify the presence of `common_prefix` associated with each node (with correct flags).
            self.logger.info(" verify common_prefix i.e. {} added by r1 i.e. {} having rloc16:{}"
                             " is present on all nodes".format(common_prefix, self.r1.name, hex(r1_rloc16)))
            verify_prefix_with_rloc16([self.r1, self.r2, self.sed1],
                                      common_prefix,
                                      r1_rloc16,
                                      on_mesh=True,
                                      preferred=True,
                                      stable=False)
            self.logger.info(" verify common_prefix i.e. {} added by r2 i.e. {} having rloc16:{}"
                             " is present on all nodes".format(common_prefix, self.r2.name, hex(r2_rloc16)))
            verify_prefix_with_rloc16([self.r1, self.r2, self.sed1],
                                      common_prefix,
                                      r2_rloc16,
                                      on_mesh=True,
                                      preferred=True,
                                      stable=True)
            self.logger.info(" verify common_prefix i.e. {} added by sed1 i.e.{} having rloc16:{}"
                             " is present on all nodes".format(common_prefix, self.sed1.name, hex(sed1_rloc16)))
            verify_prefix_with_rloc16([self.r1, self.r2, self.sed1],
                                      common_prefix,
                                      sed1_rloc16,
                                      on_mesh=True,
                                      preferred=False,
                                      stable=True)

        verify_within(check_prefixes, WAIT_TIME)

    @testcase.test_method_decorator
    def test03_verify_prefixes_on_r1_after_r2_leave(self):
        # Remove `r2` from the thread network. This should trigger all the prefixes added by it or its
        # child to timeout and be removed.
        self.logger.info("Get all nodes rloc16 before r2 leaves the network")
        r1_rloc16 = int(self.r1.get(wpan.WPAN_THREAD_RLOC16), 0)
        r2_rloc16 = int(self.r2.get(wpan.WPAN_THREAD_RLOC16), 0)
        sed1_rloc16 = int(self.sed1.get(wpan.WPAN_THREAD_RLOC16), 0)

        self.logger.info(" Remove r2 i.e. {} from the thread network".format(self.r2.name))
        self.r2.leave()
        self.wait_for_completion(self.device_list)

        self.logger.info("Wait for {}s for on-mesh prefix to be updated after r2's removal".format(
            PREFIX_SYNC_WAIT_AFTER_ROUTER_REMOVAL))
        time.sleep(PREFIX_SYNC_WAIT_AFTER_ROUTER_REMOVAL)

        def check_prefixes_on_r1_after_r2_leave():
            # Verify that entries added by r1 are still present
            self.logger.info(" verify prefix entries {} and {} added by r1 ({})"
                             "are still present".format(prefix1, common_prefix, self.r1.name))
            verify_prefix_with_rloc16([self.r1], prefix1, r1_rloc16, on_mesh=True, preferred=True, stable=True)
            verify_prefix_with_rloc16([self.r1], common_prefix, r1_rloc16, on_mesh=True, preferred=True, stable=False)

            self.logger.info(" verify prefix entries {}, {}, {} added by `r2` {} or `sed1` {} are removed".format(
                prefix2, prefix3, common_prefix, self.r2.name, self.sed1.name))
            verify_no_prefix_with_rloc16([self.r1], prefix2, r2_rloc16)
            verify_no_prefix_with_rloc16([self.r1], prefix3, sed1_rloc16)
            verify_no_prefix_with_rloc16([self.r1], common_prefix, r2_rloc16)
            verify_no_prefix_with_rloc16([self.r1], common_prefix, sed1_rloc16)

        verify_within(check_prefixes_on_r1_after_r2_leave, WAIT_TIME)


if __name__ == "__main__":
    unittest.main()
