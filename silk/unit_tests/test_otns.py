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

import logging
import random
import time
import unittest

from otns.cli import OTNS

from silk.tools.otns_manager import OtnsManager
from silk.unit_tests.testcase import SilkTestCase
from silk.unit_tests.mock_device import MockThreadDevBoard

class BasicTest(SilkTestCase):
  """Silk integration test case for OTNS.
  """
  def setUp(self) -> None:
    """Test method set up.
    """
    self.ns = OTNS(otns_args=[
        "-raw", "-real",
        "-ot-cli", "otns-silk-proxy",
        "-listen", ":9000",
        "-log", "debug"])
    # wait for OTNS gRPC server to start
    time.sleep(1)
    self.manager = OtnsManager("localhost", logging.Logger("OTNS Manager"))

  def tearDown(self) -> None:
    """Test method tear down.
    """
    self.manager.unsubscribe_from_all_nodes()
    self.manager.remove_all_nodes()
    self.ns.close()
    # wait for OTNS gRPC server to stop
    time.sleep(0.5)

  def testAddDevice(self):
    """Test adding device.
    """
    ns = self.ns
    manager = self.manager

    device = MockThreadDevBoard("device", 1)
    manager.add_node(device)
    ns.go(0.1)
    self.assertEqual(len(ns.nodes()), 1)

  def testRemoveDevice(self):
    """Test removing device.
    """
    ns = self.ns
    manager = self.manager

    device = MockThreadDevBoard("device", 1)
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
    ns = self.ns
    manager = self.manager

    device_1_id, device_2_id = random.randint(1, 10), random.randint(11, 20)
    device_1 = MockThreadDevBoard("device_1", device_1_id)
    device_2 = MockThreadDevBoard("device_2", device_2_id)

    device_1_x, device_1_y = random.randint(100, 200), random.randint(100, 200)
    device_2_x, device_2_y = random.randint(100, 200), random.randint(100, 200)
    device_1.device.set_otns_vis_position(device_1_x, device_1_y)
    device_2.device.set_otns_vis_position(device_2_x, device_2_y)

    manager.add_node(device_1)
    manager.add_node(device_2)
    ns.go(0.1)

    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 2)
    self.assertEqual(nodes_info[device_1_id]['x'], device_1_x)
    self.assertEqual(nodes_info[device_1_id]['y'], device_1_y)
    self.assertEqual(nodes_info[device_2_id]['x'], device_2_x)
    self.assertEqual(nodes_info[device_2_id]['y'], device_2_y)

    device_3_id = random.randint(21, 30)
    device_3 = MockThreadDevBoard("device_3", device_3_id)

    device_3_x, device_3_y = random.randint(100, 200), random.randint(100, 200)
    device_3.device.set_otns_vis_position(device_3_x, device_3_y)
  
    manager.add_node(device_3)
    ns.go(0.1)

    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 3)
    self.assertEqual(nodes_info[device_1_id]['x'], device_1_x)
    self.assertEqual(nodes_info[device_1_id]['y'], device_1_y)
    self.assertEqual(nodes_info[device_2_id]['x'], device_2_x)
    self.assertEqual(nodes_info[device_2_id]['y'], device_2_y)
    self.assertEqual(nodes_info[device_3_id]['x'], device_3_x)
    self.assertEqual(nodes_info[device_3_id]['y'], device_3_y)
  
  def testAddAutoLayoutDevices(self):
    """Test auto layout.
    """
    ns = self.ns
    manager = self.manager

    layout_center_x = random.randint(100, 200)
    layout_center_y = random.randint(100, 200)
    layout_radius = random.randint(50, 100)

    device_1_id = 1
    device_2_id = 2
    device_3_id = 3
    device_4_id = 4
    device_1 = MockThreadDevBoard("device_1", device_1_id)
    device_2 = MockThreadDevBoard("device_2", device_2_id)
    device_3 = MockThreadDevBoard("device_3", device_3_id)
    device_4 = MockThreadDevBoard("device_4", device_4_id)

    device_1.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)
    device_2.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)
    device_3.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)
    device_4.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)

    manager.add_node(device_1)
    ns.go(0.1)

    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 1)
    self.assertAlmostEqual(nodes_info[device_1_id]['x'],
                           layout_center_x + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_1_id]['y'],
                           layout_center_y, delta=1)

    manager.add_node(device_2)
    ns.go(0.1)

    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 2)
    self.assertAlmostEqual(nodes_info[device_1_id]['x'],
                           layout_center_x - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_1_id]['y'],
                           layout_center_y, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['x'],
                           layout_center_x + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['y'],
                           layout_center_y, delta=1)
    
    manager.add_node(device_3)
    manager.add_node(device_4)
    ns.go(0.1)

    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 4)
    self.assertAlmostEqual(nodes_info[device_1_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_1_id]['y'],
                           layout_center_y + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['x'],
                           layout_center_x - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['y'],
                           layout_center_y, delta=1)
    self.assertAlmostEqual(nodes_info[device_3_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_3_id]['y'],
                           layout_center_y - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_4_id]['x'],
                           layout_center_x + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_4_id]['y'],
                           layout_center_y, delta=1)

  def testRemoveAutoLayoutDevices(self):
    """Test that removing nodes keeps other nodes stationary with auto layout.
    """
    ns = self.ns
    manager = self.manager

    layout_center_x = random.randint(100, 200)
    layout_center_y = random.randint(100, 200)
    layout_radius = random.randint(50, 100)

    device_1_id = 1
    device_2_id = 2
    device_3_id = 3
    device_4_id = 4
    device_1 = MockThreadDevBoard("device_1", device_1_id)
    device_2 = MockThreadDevBoard("device_2", device_2_id)
    device_3 = MockThreadDevBoard("device_3", device_3_id)
    device_4 = MockThreadDevBoard("device_4", device_4_id)

    device_1.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)
    device_2.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)
    device_3.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)
    device_4.device.set_otns_layout_parameter(
        layout_center_x, layout_center_y, layout_radius)
    
    manager.add_node(device_1)
    manager.add_node(device_2)
    manager.add_node(device_3)
    manager.add_node(device_4)
    ns.go(0.1)

    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 4)
    self.assertAlmostEqual(nodes_info[device_1_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_1_id]['y'],
                           layout_center_y + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['x'],
                           layout_center_x - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['y'],
                           layout_center_y, delta=1)
    self.assertAlmostEqual(nodes_info[device_3_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_3_id]['y'],
                           layout_center_y - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_4_id]['x'],
                           layout_center_x + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_4_id]['y'],
                           layout_center_y, delta=1)
    
    manager.remove_node(device_4)
    ns.go(0.1)
    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 3)
    self.assertAlmostEqual(nodes_info[device_1_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_1_id]['y'],
                           layout_center_y + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['x'],
                           layout_center_x - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['y'],
                           layout_center_y, delta=1)
    self.assertAlmostEqual(nodes_info[device_3_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_3_id]['y'],
                           layout_center_y - layout_radius, delta=1)

    manager.remove_node(device_3)
    ns.go(0.1)
    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 2)
    self.assertAlmostEqual(nodes_info[device_1_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_1_id]['y'],
                           layout_center_y + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['x'],
                           layout_center_x - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['y'],
                           layout_center_y, delta=1)

    manager.remove_node(device_2)
    ns.go(0.1)
    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 1)
    self.assertAlmostEqual(nodes_info[device_1_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_1_id]['y'],
                           layout_center_y + layout_radius, delta=1)

    manager.add_node(device_2)
    manager.remove_node(device_1)
    ns.go(0.1)
    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 1)
    self.assertAlmostEqual(nodes_info[device_2_id]['x'],
                           layout_center_x - layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_2_id]['y'],
                           layout_center_y, delta=1)

    manager.add_node(device_3)
    manager.remove_node(device_2)
    ns.go(0.1)
    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 1)
    self.assertAlmostEqual(nodes_info[device_3_id]['x'],
                           layout_center_x, delta=1)
    self.assertAlmostEqual(nodes_info[device_3_id]['y'],
                           layout_center_y - layout_radius, delta=1)

    manager.add_node(device_4)
    manager.remove_node(device_3)
    ns.go(0.1)
    nodes_info = ns.nodes()
    self.assertEqual(len(nodes_info), 1)
    self.assertAlmostEqual(nodes_info[device_4_id]['x'],
                           layout_center_x + layout_radius, delta=1)
    self.assertAlmostEqual(nodes_info[device_4_id]['y'],
                           layout_center_y, delta=1)


if __name__ == '__main__':
    unittest.main()
