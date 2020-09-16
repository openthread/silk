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

import random
import unittest
import time

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify
from silk.tools.wpan_util import verify_address, verify_prefix
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

prefix1 = "fd00:abba:cafe::"
prefix2 = "fd00:1234::"
NUM_CHILDREN = 1


class TestPartitionMerge(testcase.TestCase):
    # Test description: Partition formation and merge
    #
    # Network Topology:
    #
    #      r1 ---- / ---- r2
    #      |       \      |
    #      |       /      |
    #      fed1    \      fed2
    #
    #
    # Test covers the following situations:
    #
    # - r2 forming its own partition when it can no longer hear r1
    # - Partitions merging into one once r1 and r2 can talk again
    # - Adding on-mesh prefixes on each partition and ensuring after
    #   merge the info in combined.

    @classmethod
    def hardware_select(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.fed1 = ffdb.ThreadDevBoard()
        cls.fed2 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.fed1, cls.fed2]

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

        cls.network_data = WpanCredentials(network_name="MORTAR-{0:04X}".format(random.randint(0, 0xffff)),
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

    def _verify_device_role(self, device_name, expect_role):
        if device_name == "r1":
            device = self.r1
        elif device_name == "r2":
            device = self.r2
        else:
            raise RuntimeError("device name is not used in this function")

        for _ in range(18):
            node_type = device.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            self.logger.info("Node type for {} is {} currently, expect to be {}".format(
                device_name, node_type, expect_role))

            if node_type == expect_role:
                return True
            time.sleep(10)
        else:
            return False

    @testcase.test_method_decorator
    def test01_pairing(self):
        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)

        self.r1.allowlist_node(self.fed1)
        self.fed1.allowlist_node(self.r1)

        self.r2.allowlist_node(self.fed2)
        self.fed2.allowlist_node(self.r2)

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

        self.fed2.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        # verify r1 role is leader
        r1_result = self._verify_device_role("r1", "leader")
        self.assertTrue(r1_result, "r1 cannot get into leader role after 180 seconds timeout")

        # verify r2 role is router
        r2_result = self._verify_device_role("r2", "router")
        self.assertTrue(r2_result, "r2 cannot get into router role after 180 seconds timeout")

    @testcase.test_method_decorator
    def test02_unallowlist_r1_r2(self):
        """unallowlist r1 and r2, verify r2 become leader.
        """
        self.r1.un_allowlist_node(self.r2)
        self.r2.un_allowlist_node(self.r1)

        # verify r2 become leader
        r2_result = self._verify_device_role("r2", "leader")
        self.assertTrue(r2_result, "r2 cannot get into leader role after 180 seconds timeout")

        # verify r1 become leader
        r1_result = self._verify_device_role("r1", "leader")
        self.assertTrue(r1_result, "r1 cannot get into leader role after 180 seconds timeout")

        # Now add prefix2 with priority `high` on router r2 and check r2&fed2 nodes for the new prefix/address
        self.r2.config_gateway1(prefix2, default_route=True, priority="1")
        self.wait_for_completion(self.device_list)
        time.sleep(60)
        r2_network_nodes = [self.r2, self.fed2]
        verify_prefix(r2_network_nodes,
                      prefix2,
                      stable=True,
                      on_mesh=True,
                      slaac=True,
                      default_route=True,
                      priority="high")
        verify_address(r2_network_nodes, prefix2)

        # verify r1, r2 has different partition
        r1_partition = self.r1.wpanctl("get", "get " + wpan.WPAN_PARTITION_ID, 2).split("=")[1].strip()[1:-1]
        r2_partition = self.r2.wpanctl("get", "get " + wpan.WPAN_PARTITION_ID, 2).split("=")[1].strip()[1:-1]
        self.logger.info("r1 partition is {}, r2 partition is {}".format(r1_partition, r2_partition))
        self.assertFalse(r1_partition == r2_partition, "r1, r2 partition id are same after unallowlisting r1, r2")

    @testcase.test_method_decorator
    def test03_allowlist_r1_r2(self):
        # Add on-mesh prefix1 on router r1
        self.r1.config_gateway1(prefix1)
        self.wait_for_completion(self.device_list)
        time.sleep(60)
        r1_network_nodes = [self.r1, self.fed1]
        # Verify that the prefix1 and its corresponding address are present on all nodes
        verify_prefix(r1_network_nodes, prefix1, stable=True, on_mesh=True, slaac=True)
        verify_address(r1_network_nodes, prefix1)

        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)
        time.sleep(60)

        # verify partition id match
        r1_partition = self.r1.wpanctl("get", "get " + wpan.WPAN_PARTITION_ID, 2).split("=")[1].strip()[1:-1]
        r2_partition = self.r2.wpanctl("get", "get " + wpan.WPAN_PARTITION_ID, 2).split("=")[1].strip()[1:-1]
        self.logger.info("r1 partition is {}, r2 partition is {}".format(r1_partition, r2_partition))
        self.assertTrue(r1_partition == r2_partition, "r1, r2 partition id are not same after allowlisting r1, r2")

    @testcase.test_method_decorator
    def test04_verify_role_prefix_childTable(self):
        # Verify that the prefix1 and its corresponding address are present on all nodes
        verify_prefix(self.all_nodes, prefix1, stable=True, on_mesh=True, slaac=True)
        verify_address(self.all_nodes, prefix1)
        # Verify that the prefix1 and its corresponding address are present on all nodes
        verify_prefix(self.all_nodes,
                      prefix2,
                      stable=True,
                      on_mesh=True,
                      slaac=True,
                      default_route=True,
                      priority="high")
        verify_address(self.all_nodes, prefix2)

        # verify r1, r2 role, one of them is leader
        r1_role = self.r1.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
        r2_role = self.r2.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
        roles_result = (r1_role == "leader" and r2_role == "router") or (r2_role == "leader" and r1_role == "router")
        self.assertTrue(roles_result, "r1, r2 role is not right, r1 is {}, r2 is {}".format(r1_role, r2_role))

        # verify their children stayed with their parents
        child_table = self.r1.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_result(child_table)
        verify(len(child_table) == NUM_CHILDREN)

        child_table = self.r2.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_result(child_table)
        verify(len(child_table) == NUM_CHILDREN)


if __name__ == "__main__":
    unittest.main()
