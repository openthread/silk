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
from silk.tools.wpan_util import (verify, verify_within, is_associated, check_neighbor_table)
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()
WAIT_INTERVAL = 6


class TestRouterLeaderResetRecovery(testcase.TestCase):
    # Test description: Verify sequential reset recovery of a router and leader
    #
    # Network topology
    #
    #   r1 ----- r2
    #            |
    #            |
    #            ed1 (end device)
    #
    # Test covers the following situations:
    #
    # -verify r1 and r2 are present in each other's neighbor table
    # -reset r2 and check that everything recover correctly, done
    #  by verifying it's association status and neighbor table
    # -reset r1 and check that everything recover correctly. Here also verify r2's association
    #  and neighbor table is proper.

    poll_interval = 400

    @classmethod
    def hardware_select(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.ed1 = ffdb.ThreadDevBoard()
        cls.all_nodes = [cls.r1, cls.r2, cls.ed1]

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

    def check_r1_neighbor_table(self):
        verify(is_associated(self.r1))
        check_neighbor_table(self.r1, [self.r2])

    def check_r2_neighbor_table(self):
        verify(is_associated(self.r2))
        check_neighbor_table(self.r2, [self.r1])

    @testcase.test_method_decorator
    def test01_pairing(self):
        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)

        self.r2.allowlist_node(self.ed1)
        self.ed1.allowlist_node(self.r2)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.ed1.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        for _ in range(10):
            node_type = self.r2.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            print(node_type == "router")

            if node_type == "router":
                print("Matched!!!!!!!!!!!!!")
                break
            time.sleep(10)
        else:
            self.assertFalse(True, "Router cannot get into router role after 100 seconds timeout")

    @testcase.test_method_decorator
    def test02_verify_neighbor_table(self):
        # Check that r1 and r2 are present in each other's neighbor table
        def check_neighbors_tables():
            check_neighbor_table(self.r1, [self.r2])
            check_neighbor_table(self.r2, [self.r1])

        verify_within(check_neighbors_tables, WAIT_INTERVAL)
        self.assertTrue(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        self.assertTrue(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)

    @testcase.test_method_decorator
    def test03_verify_router_reset_and_recovery(self):
        # Reset r2 and check that everything recover correctly. Wait for it to be associated.
        self.r2.reset_thread_radio()
        self.wait_for_completion(self.device_list)
        self.logger.info(
            "verify after router {} reset and recovery it has leader(r1) {} in it's neighbor table".format(
                self.r2.name, self.r1.name))
        verify_within(self.check_r2_neighbor_table, WAIT_INTERVAL)
        self.assertTrue(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        self.assertTrue(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)

    @testcase.test_method_decorator
    def test04_verify_leader_reset_and_recovery(self):
        # Reset leader (i.e. r1) and check that everything recover correctly.
        self.r1.reset_thread_radio()
        self.wait_for_completion(self.device_list)
        self.logger.info(
            "verify after leader {} reset and recovery it has router(r2) {} in it's neighbor table".format(
                self.r1.name, self.r2.name))
        verify_within(self.check_r1_neighbor_table, WAIT_INTERVAL)

        self.assertTrue(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        self.assertTrue(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        self.logger.info("After leader reset verify r2's neighbor table too")
        verify_within(self.check_r2_neighbor_table, WAIT_INTERVAL)


if __name__ == "__main__":
    unittest.main()
