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

from typing import Any, Dict, List, Tuple
import random
import time
import unittest

from otns.cli import OTNS

from silk.tools.otns_manager import OtnsManager
from silk.unit_tests.mock_device import MockThreadDevBoard
from silk.unit_tests.testcase import SilkTestCase


class OTNSIntegrationTest(SilkTestCase):
    """Silk integration test case for OTNS.
    """

    def setUp(self):
        """Test method set up.
        """
        self.ns = OTNS(otns_args=["-raw", "-real", "-ot-cli", "otns-silk-proxy", "-listen", ":9000", "-log", "debug"])
        # wait for OTNS gRPC server to start
        time.sleep(0.3)
        self.manager = OtnsManager("localhost", self.logger.getChild("OtnsManager"))
        self.manager.wait_for_grpc_channel_ready(10)

    def tearDown(self) -> None:
        """Test method tear down.
        """
        self.manager.unsubscribe_from_all_nodes()
        self.manager.remove_all_nodes()
        self.ns.close()
        # wait for OTNS gRPC server to stop
        time.sleep(0.2)

    def assert_device_positions(self, nodes_info: Dict[int, Dict[str, Any]], expected_coords: Dict[int, Tuple[int,
                                                                                                              int]]):
        """Helper method to assert auto layout position devices coordinates.

        Args:
            nodes_info (Dict[int, Dict[str, Any]]): nodes info dictionary.
            expected_coords (Dict[int, Tuple[int, int]]): dict mapping device id to coordinates to check.
        """
        for device_id, coords in expected_coords.items():
            self.assertAlmostEqual(nodes_info[device_id]["x"], coords[0], delta=1)
            self.assertAlmostEqual(nodes_info[device_id]["y"], coords[1], delta=1)

    def testAddDevice(self):
        """Test adding device.
        """
        ns = self.ns
        manager = self.manager

        device = MockThreadDevBoard(1)
        manager.add_node(device)
        ns.go(0.1)
        self.assertEqual(len(ns.nodes()), 1)

    def testRemoveDevice(self):
        """Test removing device.
        """
        ns = self.ns
        manager = self.manager

        device = MockThreadDevBoard(1)
        manager.add_node(device)
        ns.go(0.1)
        self.assertEqual(len(ns.nodes()), 1)

        manager.remove_node(device)
        ns.go(0.1)
        self.assertEqual(len(ns.nodes()), 0)

    def testSetSpeed(self):
        """Test setting speed display.
        """
        ns = self.ns
        manager = self.manager

        speed = random.randint(2, 20)
        manager.set_replay_speed(speed)
        self.assertAlmostEqual(ns.speed, speed)

        speed = random.randint(21, 40)
        manager.set_replay_speed(speed)
        self.assertAlmostEqual(ns.speed, speed)

    def testAddFixedPositionDevices(self):
        """Test adding fixed position nodes.
        """

        def assert_device_fixed_positions(devices: List[MockThreadDevBoard]):
            """Helper method to assert fixed position devices coordinates.

            Args:
                devices (List[MockThreadDevBoard]): list of devices to check.
            """
            for a_device in devices:
                self.assertEqual(nodes_info[a_device.id]["x"], a_device.x)
                self.assertEqual(nodes_info[a_device.id]["y"], a_device.y)

        ns = self.ns
        manager = self.manager

        device_1 = MockThreadDevBoard(random.randint(1, 10))
        device_2 = MockThreadDevBoard(random.randint(11, 20))
        device_3 = MockThreadDevBoard(random.randint(21, 30))

        for device in [device_1, device_2, device_3]:
            device.device.set_otns_vis_position(random.randint(100, 200), random.randint(100, 200))

        manager.add_node(device_1)
        manager.add_node(device_2)
        ns.go(0.1)

        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 2)
        assert_device_fixed_positions([device_1, device_2])

        manager.add_node(device_3)
        ns.go(0.1)

        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 3)
        assert_device_fixed_positions([device_1, device_2, device_3])

    def testAddAutoLayoutDevices(self):
        """Test adding auto layout nodes.
        """
        ns = self.ns
        manager = self.manager

        layout_center_x = random.randint(100, 200)
        layout_center_y = random.randint(100, 200)
        layout_radius = random.randint(50, 100)

        device_1 = MockThreadDevBoard(1)
        device_2 = MockThreadDevBoard(2)
        device_3 = MockThreadDevBoard(3)
        device_4 = MockThreadDevBoard(4)

        for device in [device_1, device_2, device_3, device_4]:
            device.device.set_otns_layout_parameter(layout_center_x, layout_center_y, layout_radius)

        manager.add_node(device_1)
        ns.go(0.1)

        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 1)
        # placing the first node alone
        expected_coords = {device_1.id: (layout_center_x + layout_radius, layout_center_y)}
        nodes_info = ns.nodes()
        self.assert_device_positions(nodes_info, expected_coords)

        manager.add_node(device_2)
        ns.go(0.1)

        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 2)
        # forming a horizontal line
        expected_coords = {
            device_1.id: (layout_center_x - layout_radius, layout_center_y),
            device_2.id: (layout_center_x + layout_radius, layout_center_y)
        }
        self.assert_device_positions(nodes_info, expected_coords)

        manager.add_node(device_3)
        manager.add_node(device_4)
        ns.go(0.1)

        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 4)
        # forming a cross shape
        expected_coords = {
            device_1.id: (layout_center_x, layout_center_y + layout_radius),
            device_2.id: (layout_center_x - layout_radius, layout_center_y),
            device_3.id: (layout_center_x, layout_center_y - layout_radius),
            device_4.id: (layout_center_x + layout_radius, layout_center_y)
        }
        self.assert_device_positions(nodes_info, expected_coords)

    def testRemoveAutoLayoutDevices(self):
        """Test that removing nodes keeps other nodes stationary with auto layout.
        """
        ns = self.ns
        manager = self.manager

        layout_center_x = random.randint(100, 200)
        layout_center_y = random.randint(100, 200)
        layout_radius = random.randint(50, 100)

        device_1 = MockThreadDevBoard(1)
        device_2 = MockThreadDevBoard(2)
        device_3 = MockThreadDevBoard(3)
        device_4 = MockThreadDevBoard(4)

        for device in [device_1, device_2, device_3, device_4]:
            device.device.set_otns_layout_parameter(layout_center_x, layout_center_y, layout_radius)
            manager.add_node(device)

        ns.go(0.1)

        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 4)
        expected_coords = {
            device_1.id: (layout_center_x, layout_center_y + layout_radius),
            device_2.id: (layout_center_x - layout_radius, layout_center_y),
            device_3.id: (layout_center_x, layout_center_y - layout_radius),
            device_4.id: (layout_center_x + layout_radius, layout_center_y)
        }
        self.assert_device_positions(nodes_info, expected_coords)

        manager.remove_node(device_4)
        ns.go(0.1)
        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 3)
        expected_coords = {
            device_1.id: (layout_center_x, layout_center_y + layout_radius),
            device_2.id: (layout_center_x - layout_radius, layout_center_y),
            device_3.id: (layout_center_x, layout_center_y - layout_radius)
        }
        self.assert_device_positions(nodes_info, expected_coords)

        manager.remove_node(device_3)
        ns.go(0.1)
        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 2)
        expected_coords = {
            device_1.id: (layout_center_x, layout_center_y + layout_radius),
            device_2.id: (layout_center_x - layout_radius, layout_center_y)
        }
        self.assert_device_positions(nodes_info, expected_coords)

        manager.remove_node(device_2)
        ns.go(0.1)
        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 1)
        expected_coords = {device_1.id: (layout_center_x, layout_center_y + layout_radius)}
        self.assert_device_positions(nodes_info, expected_coords)

        manager.add_node(device_2)
        manager.remove_node(device_1)
        ns.go(0.1)
        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 1)
        expected_coords = {device_2.id: (layout_center_x - layout_radius, layout_center_y)}
        self.assert_device_positions(nodes_info, expected_coords)

        manager.add_node(device_3)
        manager.remove_node(device_2)
        ns.go(0.1)
        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 1)
        expected_coords = {device_3.id: (layout_center_x, layout_center_y - layout_radius)}
        self.assert_device_positions(nodes_info, expected_coords)

        manager.add_node(device_4)
        manager.remove_node(device_3)
        ns.go(0.1)
        nodes_info = ns.nodes()
        self.assertEqual(len(nodes_info), 1)
        expected_coords = {device_4.id: (layout_center_x + layout_radius, layout_center_y)}
        self.assert_device_positions(nodes_info, expected_coords)

    def testUpdateExtaddr(self):
        """Test updating node extended address.

        Also tests updating before the OTNS manager subscribes to the node.
        """
        ns = self.ns
        manager = self.manager

        device_extaddr = random.getrandbits(64)
        device = MockThreadDevBoard(random.randint(1, 10))

        manager.add_node(device)
        ns.go(0.1)

        self.assertEqual(ns.nodes()[device.id]["extaddr"], device.id)

        device.wpantund_process.emit_status(f"extaddr={device_extaddr:016x}")
        ns.go(0.1)

        self.assertEqual(ns.nodes()[device.id]["extaddr"], device.id)

        manager.subscribe_to_node(device)
        device.wpantund_process.emit_status(f"extaddr={device_extaddr:016x}")
        ns.go(0.1)

        self.assertEqual(ns.nodes()[device.id]["extaddr"], device_extaddr)

    def testUpdateRLOC16(self):
        """Test updating node RLOC16.

        Also tests updating before the OTNS manager subscribes to the node.
        """
        ns = self.ns
        manager = self.manager

        device_rloc16 = random.getrandbits(16)
        device = MockThreadDevBoard(random.randint(1, 10))

        manager.add_node(device)
        ns.go(0.1)

        original_rloc16 = ns.nodes()[device.id]["rloc16"]

        device.wpantund_process.emit_status(f"rloc16={device_rloc16}")
        ns.go(0.1)

        self.assertEqual(ns.nodes()[device.id]["rloc16"], original_rloc16)

        manager.subscribe_to_node(device)
        device.wpantund_process.emit_status(f"rloc16={device_rloc16}")
        ns.go(0.1)

        self.assertEqual(ns.nodes()[device.id]["rloc16"], device_rloc16)

    def testFormPartition(self):
        """Test forming a partition.
        """
        ns = self.ns
        manager = self.manager

        device_1_parid = random.getrandbits(16)
        device_1 = MockThreadDevBoard(random.randint(1, 10))

        device_2_parid = random.getrandbits(16)
        device_2 = MockThreadDevBoard(random.randint(11, 20))

        manager.add_node(device_1)
        manager.add_node(device_2)

        manager.subscribe_to_node(device_1)
        manager.subscribe_to_node(device_2)

        device_1.wpantund_process.emit_status(f"parid={device_1_parid:08x}")
        device_2.wpantund_process.emit_status(f"parid={device_2_parid:08x}")
        ns.go(0.1)

        partitions_info = ns.partitions()
        self.assertEqual(len(partitions_info), 2)
        self.assertEqual(len(partitions_info[device_1_parid]), 1)
        self.assertEqual(len(partitions_info[device_2_parid]), 1)
        self.assertEqual(partitions_info[device_1_parid][0], device_1.id)
        self.assertEqual(partitions_info[device_2_parid][0], device_2.id)

        device_2.wpantund_process.emit_status(f"parid={device_1_parid:08x}")
        ns.go(0.1)

        partitions_info = ns.partitions()
        self.assertEqual(len(partitions_info), 1)
        self.assertEqual(len(partitions_info[device_1_parid]), 2)
        self.assertIn(device_1.id, partitions_info[device_1_parid])
        self.assertIn(device_2.id, partitions_info[device_1_parid])

        device_2.wpantund_process.emit_status(f"parid={device_2_parid:08x}")
        ns.go(0.1)

        partitions_info = ns.partitions()
        self.assertEqual(len(partitions_info), 2)
        self.assertEqual(len(partitions_info[device_1_parid]), 1)
        self.assertEqual(len(partitions_info[device_2_parid]), 1)
        self.assertEqual(partitions_info[device_1_parid][0], device_1.id)
        self.assertEqual(partitions_info[device_2_parid][0], device_2.id)

    # TODO: Add child & router table tests after adding query support to OTNS CLI


if __name__ == "__main__":
    unittest.main()
