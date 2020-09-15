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
import time
import unittest

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify, verify_within
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()
ROLE_WAIT_TIME = 180
LEADER_CHANGE_WAIT_TIME = 5 * 60
NUM_CHILDREN = 1


class TestLeaderLoss(testcase.TestCase):
    # Test description: LeaderLoss
    #
    # Network Topology:
    #
    #       | --------  \/\/\/ -----------|
    #       |                             |
    #      r1 ---- / ---- r2 ----  / ---- r3
    #      |       \      |        \      |
    #      |       /      |        /      |
    #      fed1    \      fed2     \      fed3
    #
    #
    # Test covers the following situations:
    #
    # - r1 joined as leader, r2, r3 joined as router initially
    # - r1 reset, r1, r2 or r3 only has one leader, the rest ones stay as router
    # - unallowlist r1, and r1 leave the network, verify r2 or r3 is leader, the other one is router
    # - join r1 to the network, verify r1 becomes router role, r2 or r3 is leader, the other one is router
    #

    @classmethod
    def hardware_select(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.r3 = ffdb.ThreadDevBoard()
        cls.fed1 = ffdb.ThreadDevBoard()
        cls.fed2 = ffdb.ThreadDevBoard()
        cls.fed3 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.r3, cls.fed1, cls.fed2, cls.fed3]

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

    def _verify_device_role(self, device, expect_role):
        """
    verify device role
    """

        def check_device_role():
            node_type = device.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            self.logger.info("Node type for {} is {} currently, expect to be {}".format(
                device.device_path, node_type, expect_role))
            verify(node_type == expect_role)

        # verify device get expected role in ROLE_WAIT_TIME i.e. 180s
        return verify_within(check_device_role, ROLE_WAIT_TIME, delay_time=5)

    def _verify_devices_roles(self, devices_roles):
        # verify devices only one is leader and rest are routers
        leader_count = devices_roles.count("leader")
        router_count = devices_roles.count("router")
        if leader_count == 1 and router_count == len(devices_roles) - 1:
            return True
        else:
            self.logger.info("leader count is {}, should be 1".format(leader_count))
            self.logger.info("router count is {}, should be {}".format(router_count, len(devices_roles) - 1))
            return False

    def _verify_children(self, device, children_num):
        child_table = device.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_result(child_table)
        verify(len(child_table) == children_num)

    @testcase.test_method_decorator
    def test01_Pairing(self):

        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)

        self.r1.allowlist_node(self.fed1)
        self.fed1.allowlist_node(self.r1)

        self.r1.allowlist_node(self.r3)
        self.r3.allowlist_node(self.r1)

        self.r2.allowlist_node(self.fed2)
        self.fed2.allowlist_node(self.r2)

        self.r2.allowlist_node(self.r3)
        self.r3.allowlist_node(self.r2)

        self.r3.allowlist_node(self.fed3)
        self.fed3.allowlist_node(self.r3)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.r3.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.fed1.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        self.fed2.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        self.fed3.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        # print r1, r2, r3 device path here
        self.logger.info("r1 device path: {}, r2 device path: {}, r3 device path: {}".format(
            self.r1.device_path, self.r2.device_path, self.r3.device_path))
        # verify r1 role is leader
        r1_result = self._verify_device_role(self.r1, "leader")
        self.assertTrue(r1_result, "r1 cannot get into leader role after {} seconds timeout".format(ROLE_WAIT_TIME))

        # verify r2 role is router
        r2_result = self._verify_device_role(self.r2, "router")
        self.assertTrue(r2_result, "r2 cannot get into router role after {} seconds timeout".format(ROLE_WAIT_TIME))

        # verify r3 role is router
        r3_result = self._verify_device_role(self.r3, "router")
        self.assertTrue(r3_result, "r3 cannot get into router role after {} seconds timeout".format(ROLE_WAIT_TIME))

    @testcase.test_method_decorator
    def test02_reset_r1(self):
        """
        reset r1, verify r2 or r3 becomes leader, the other one stays as router
        """
        self.r1.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        # verify r2, r3 role, one of them change to be leader
        r1_role = self.r1.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
        r2_role = self.r2.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
        r3_role = self.r3.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
        devices_roles = [r1_role, r2_role, r3_role]
        roles_result = self._verify_devices_roles(devices_roles)
        self.assertTrue(
            roles_result,
            "r1, r2, r3 only one can be leader, r1 is {}, r2 is {}, r3 is {}".format(r1_role, r2_role, r3_role))

        # verify their children stayed with their parents
        self._verify_children(self.r1, NUM_CHILDREN)
        self._verify_children(self.r2, NUM_CHILDREN)
        self._verify_children(self.r3, NUM_CHILDREN)

    @testcase.test_method_decorator
    def test03_r1_leave_network(self):
        """
        unallowlist r1 out
        r1 leave the network
        verify either r2 or r3 is leader, the other one is router
        """
        self.r2.un_allowlist_node(self.r1)
        self.r3.un_allowlist_node(self.r1)
        self.r1.un_allowlist_node(self.r2)
        self.r1.un_allowlist_node(self.r3)

        self.r1.leave()
        self.wait_for_completion(self.device_list)
        # total wait for minutes (default is 5m) for one router to change
        # to leader, but it will break out if one router changed to leader early
        timeout = time.time() + LEADER_CHANGE_WAIT_TIME
        while True:
            if time.time() > timeout:
                break
            for device in self.all_nodes[1:]:
                node_type = device.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2)
                role = node_type.split("=")[1].strip()[1:-1]
            time.sleep(30)
            # verify r2, r3 role, one of them change to be leader
            r2_role = self.r2.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            r3_role = self.r3.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            roles_result = (r2_role == "leader" and r3_role == "router") or (r3_role == "leader" and
                                                                             r2_role == "router")
            if roles_result:
                break

        self.assertTrue(roles_result, f"r2, r3 nobody change to leader in 5m, r2 is {r2_role}, r3 is {r3_role}")

        # verify their children stayed with their parents
        self._verify_children(self.r2, NUM_CHILDREN)
        self._verify_children(self.r3, NUM_CHILDREN)

    @testcase.test_method_decorator
    def test04_r1_join_network(self):
        """
        r1 re-join network as router
        """
        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)

        self.r1.allowlist_node(self.fed1)
        self.fed1.allowlist_node(self.r1)

        self.r1.allowlist_node(self.r3)
        self.r3.allowlist_node(self.r1)
        self.wait_for_completion(self.device_list)

        self.r1.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        # verify r1 role is router
        r1_result = self._verify_device_role(self.r1, "router")
        self.assertTrue(r1_result, f"r1 cannot get into router role after {ROLE_WAIT_TIME} seconds timeout")
        time.sleep(120)

        # verify their children stayed with their parents
        self._verify_children(self.r1, NUM_CHILDREN)


if __name__ == "__main__":
    unittest.main()
