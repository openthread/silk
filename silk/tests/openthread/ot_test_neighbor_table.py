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
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

NUM_ROUTERS = 2
NUM_CHILDREN = 1

NEIGHBOR_TABLE_AS_VALMAP_ENTRY = ("Age", "AverageRssi", "ExtAddress", "FullFunction", "FullNetworkData", "IsChild",
                                  "LastRssi", "LinkFrameCounter", "LinkQualityIn", "MleFrameCounter", "RLOC16",
                                  "RxOnWhenIdle", "SecureDataRequest")


class TestNeighborTable(testcase.TestCase):
    # Minimum Three devices: One each for leader, router, sed

    @classmethod
    def hardware_select(cls):
        cls.routers = []
        for _ in range(NUM_ROUTERS):
            cls.routers.append(ffdb.ThreadDevBoard())

        cls.children = []
        for _ in range(NUM_CHILDREN):
            cls.children.append(ffdb.ThreadDevBoard())

        # end-device per router used for quick promotion to router role
        cls.ed = [0]
        for _ in range(1, NUM_ROUTERS):
            cls.ed.append(ffdb.ThreadDevBoard())

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        for device in cls.routers + cls.children + cls.ed[1:]:
            cls.add_test_device(device)

        for device in cls.device_list:
            device.set_logger(cls.logger)
            device.set_up()

        total_networks = NUM_ROUTERS
        cls.network_data_list = []

        for _ in range(total_networks):
            cls.network_data_list.append(
                WpanCredentials(network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
                                psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
                                channel=random.randint(11, 25),
                                fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff))))

        cls.thread_sniffer_init(cls.network_data_list[0].channel)

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
    def test01_Form_Network(self):
        # allowlist all routers with one another
        for i in range(NUM_ROUTERS):
            for j in range(NUM_ROUTERS):
                if i != j:
                    self.routers[i].allowlist_node(self.routers[j])

        # All children should attach to routers[0]
        for num in range(NUM_CHILDREN):
            self.children[num].allowlist_node(self.routers[0])
            self.routers[0].allowlist_node(self.children[num])

        # allowlist the end-device ed with its corresponding router
        for num in range(1, NUM_ROUTERS):
            self.ed[num].allowlist_node(self.routers[num])
            self.routers[num].allowlist_node(self.ed[num])

        # Form the Network
        self.routers[0].form(self.network_data_list[0], "router")
        self.wait_for_completion(self.device_list)

        self.logger.info(self.routers[0].ip6_lla)
        self.logger.info(self.routers[0].ip6_thread_ula)

        self.network_data_list[0].xpanid = self.routers[0].xpanid
        self.network_data_list[0].panid = self.routers[0].panid

        for i, router in enumerate(self.routers[1:]):
            router.join(self.network_data_list[0], "router")
            self.wait_for_completion(self.device_list)

        for num in range(1, NUM_ROUTERS):
            self.ed[num].join(self.network_data_list[0], "end-node")
            self.wait_for_completion(self.device_list)

        for num in range(NUM_CHILDREN):
            self.children[num].join(self.network_data_list[0], "sleepy-end-device")
            self.children[num].set_sleep_poll_interval(300)
            self.wait_for_completion(self.device_list)

        for _ in range(10):
            node_type = self.routers[1].wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            print(node_type == "router")

            if node_type == "router":
                print("End-node moved up to a Router.")
                break
            time.sleep(10)
        else:
            self.assertFalse(True, "Router cannot get into router role after 100 seconds timeout")

        for device in self.device_list:
            ret = device.wpanctl("get", "status", 2)
            print(ret)

    @testcase.test_method_decorator
    def test02_Verify_Router_Type(self):
        for router in self.routers[1:]:
            node_type = router.get(wpan.WPAN_NODE_TYPE).strip()
            self.assertEqual(node_type, wpan.NODE_TYPE_ROUTER,
                             "Node Type is: {} vs expected: {}".format(node_type, wpan.NODE_TYPE_ROUTER))

    @testcase.test_method_decorator
    def test03_Verify_Children(self):
        neighbor_table = self.routers[0].wpanctl("get", "get " + wpan.WPAN_THREAD_NEIGHBOR_TABLE, 2)
        neighbor_table = wpan_table_parser.parse_neighbor_table_result(neighbor_table)

        print(neighbor_table)

        self.assertEqual(len(neighbor_table), len(self.routers) - 1 + len(self.children))

        # Verify that all children are seen in the neighbor table

        for child in self.children:
            ext_addr = child.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]

            for entry in neighbor_table:
                if entry.ext_address == ext_addr:
                    break
            else:
                self.assertTrue(0, "Failed to find a child entry for extended address {} in table".format(ext_addr))

            self.assertEqual(int(entry.rloc16, 16), int(child.getprop(wpan.WPAN_THREAD_RLOC16), 16))
            self.assertFalse(entry.is_ftd())
            self.assertFalse(entry.is_rx_on_when_idle())
            self.assertTrue(entry.is_child())

    @testcase.test_method_decorator
    def test04_Verify_Router(self):
        # Verify that all other routers are seen in the neighbor table
        neighbor_table = self.routers[0].wpanctl("get", "get " + wpan.WPAN_THREAD_NEIGHBOR_TABLE, 2)
        neighbor_table = wpan_table_parser.parse_neighbor_table_result(neighbor_table)

        print(neighbor_table)

        self.assertEqual(len(neighbor_table), len(self.routers) - 1 + len(self.children))

        # Verify that all children are seen in the neighbor table

        for router in self.routers[1:]:
            ext_addr = router.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]

            for entry in neighbor_table:
                if entry.ext_address == ext_addr:
                    break
            else:
                self.assertTrue(0, "Failed to find a router entry for extended address {} in table".format(ext_addr))
            self.assertEqual(int(entry.rloc16, 16), int(router.getprop(wpan.WPAN_THREAD_RLOC16), 16))

            self.assertTrue(entry.is_ftd())
            self.assertTrue(entry.is_rx_on_when_idle())
            self.assertFalse(entry.is_child())

    @testcase.test_method_decorator
    def test05_Verify_NeighborTable_AsValMap(self):
        neighbor_table = self.routers[0].wpanctl("get", "get " + wpan.WPAN_THREAD_NEIGHBOR_TABLE_ASVALMAP, 2)

        print(neighbor_table)

        total_neighbor_table_entry = len(self.routers) - 1 + len(self.children)

        for item in NEIGHBOR_TABLE_AS_VALMAP_ENTRY:
            self.assertEqual(neighbor_table.count(item), total_neighbor_table_entry)


if __name__ == "__main__":
    unittest.main()
