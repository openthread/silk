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

from typing import Dict, List, Tuple
import random
import unittest

from silk.tools.otns_manager import Event, EventType, RoleType
from silk.unit_tests.mock_device import MockThreadDevBoard
from silk.unit_tests.test_utils import random_string
from silk.unit_tests.testcase import SilkMockingTestCase


class OTNSUnitTest(SilkMockingTestCase):
    """Silk unit test case for OTNS manager.
    """

    def testEventEncodeDecode(self):
        """Test encoding and decoding an OTNS status event.
        """
        message = random_string(10)
        encoded_event = Event.status_event(message)
        self.assertEqual(encoded_event.event, EventType.OTNS_STATUS_PUSH.value)

        event_bytes = encoded_event.to_bytes()
        self.assertEqual(len(event_bytes), 11 + len(message))

        decoded_event = Event.from_bytes(event_bytes)
        self.assertEqual(encoded_event.data, decoded_event.data)
        self.assertEqual(message, decoded_event.message)

    def testAddDevice(self):
        """Test adding device.
        """
        device = MockThreadDevBoard(random.randint(1, 10))
        device_x, device_y = random.randint(100, 200), random.randint(100, 200)
        device.device.set_otns_vis_position(device_x, device_y)

        expect_thread = self.expect_grpc_commands([f"add router x {device_x} y {device_y} id {device.id}"])
        self.manager.add_node(device)
        self.wait_for_expect(expect_thread)

    def testRemoveDevice(self):
        """Test removing device.
        """
        device = MockThreadDevBoard(random.randint(1, 10))

        self.manager.add_node(device)

        expect_thread = self.expect_grpc_commands([f"del {device.id}"])
        self.manager.remove_node(device)
        self.wait_for_expect(expect_thread)

    def testSetOTNSProperties(self):
        """Test setting OTNS properties.
        """
        # speed
        speed = random.randint(2, 20)
        expect_thread = self.expect_grpc_commands([f"speed {speed}"])
        self.manager.set_replay_speed(speed)
        self.wait_for_expect(expect_thread)

        # OT NCP version
        version = random_string(10)
        expect_thread = self.expect_grpc_commands([f"netinfo version \"{version}\" real y"])
        self.manager.set_ncp_version(version)
        self.wait_for_expect(expect_thread)

        # test title
        title = random_string(10)
        expect_thread = self.expect_grpc_commands([f"title \"{title}\" x 0 y 20 fs 20"])
        self.manager.set_test_title(title)
        self.wait_for_expect(expect_thread)

    def testFixedPosition(self):
        """Test OTNS manager fixed position feature.
        """
        device_1_id, device_2_id = random.randint(1, 10), random.randint(11, 20)
        device_1 = MockThreadDevBoard(device_1_id)
        device_2 = MockThreadDevBoard(device_2_id)

        device_1_x, device_1_y = random.randint(100, 200), random.randint(100, 200)
        device_2_x, device_2_y = random.randint(100, 200), random.randint(100, 200)
        device_1.device.set_otns_vis_position(device_1_x, device_1_y)
        device_2.device.set_otns_vis_position(device_2_x, device_2_y)

        expect_thread = self.expect_grpc_commands([
            f"add router x {device_1_x} y {device_1_y} id {device_1_id}",
            f"add router x {device_2_x} y {device_2_y} id {device_2_id}"
        ])
        self.manager.add_node(device_1)
        self.manager.add_node(device_2)
        self.wait_for_expect(expect_thread)

    def testAutoLayout(self):
        """Test OTNS manager auto layout feature.
        """

        def expect_grpc_move_commands(coords: Dict[int, Tuple[int, int]]):
            commands = [f"move {node_id} {x} {y}" for node_id, (x, y) in coords.items()]
            return self.expect_grpc_commands(commands)

        def expect_node_vis_positions(nodes: List[MockThreadDevBoard], coords: Dict[int, Tuple[int, int]]):
            for node in nodes:
                if node.id in coords:
                    otns_node = self.manager.otns_node_map[node]
                    self.assertAlmostEqual(coords[node.id][0], otns_node.vis_x, delta=1)
                    self.assertAlmostEqual(coords[node.id][1], otns_node.vis_y, delta=1)

        layout_center_x = random.randint(100, 200)
        layout_center_y = random.randint(100, 200)
        layout_radius = random.randint(50, 100)

        device_1 = MockThreadDevBoard(1)
        device_2 = MockThreadDevBoard(2)
        device_3 = MockThreadDevBoard(3)
        device_4 = MockThreadDevBoard(4)

        devices = [device_1, device_2, device_3, device_4]

        for device in devices:
            device.device.set_otns_layout_parameter(layout_center_x, layout_center_y, layout_radius)

        self.manager.add_node(device_1)

        expected_coords = {
            device_1.id: (layout_center_x - layout_radius, layout_center_y),
            device_2.id: (layout_center_x + layout_radius, layout_center_y)
        }
        expect_thread = expect_grpc_move_commands(expected_coords)
        self.manager.add_node(device_2)
        self.wait_for_expect(expect_thread)
        expect_node_vis_positions(devices, expected_coords)

        expected_coords = {
            device_1.id: (layout_center_x, layout_center_y + layout_radius),
            device_2.id: (layout_center_x - layout_radius, layout_center_y),
            device_3.id: (layout_center_x, layout_center_y - layout_radius),
            device_4.id: (layout_center_x + layout_radius, layout_center_y)
        }
        expect_thread = expect_grpc_move_commands(expected_coords)
        self.manager.add_node(device_3)
        self.manager.add_node(device_4)
        self.wait_for_expect(expect_thread)
        expect_node_vis_positions(devices, expected_coords)

        expected_coords = {
            device_1.id: (layout_center_x, layout_center_y + layout_radius),
            device_2.id: (layout_center_x - layout_radius, layout_center_y),
            device_3.id: (layout_center_x, layout_center_y - layout_radius)
        }
        self.manager.remove_node(device_4)
        expect_node_vis_positions(devices, expected_coords)

        expected_coords = {
            device_1.id: (layout_center_x, layout_center_y + layout_radius),
            device_2.id: (layout_center_x - layout_radius, layout_center_y)
        }
        self.manager.remove_node(device_3)
        expect_node_vis_positions(devices, expected_coords)

    def testUpdateExtaddr(self):
        """Test updating node extaddr.
        """
        device = MockThreadDevBoard(random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        for _ in range(3):
            extaddr = random.getrandbits(64)
            expect_thread = self.expect_udp_messages([(f"extaddr={extaddr:016x}", device.id)])
            device.wpantund_process.emit_status(f"extaddr={extaddr:016x}")
            self.wait_for_expect(expect_thread)
            self.assertEqual(self.manager.otns_node_map[device].extaddr, extaddr)

    def testUpdateMode(self):
        """Test updating node mode, one of the properties OTNS manager does not track.
        """
        device = MockThreadDevBoard(random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        mode = "sn"
        expect_thread = self.expect_udp_messages([(f"mode={mode}", device.id)])
        device.wpantund_process.emit_status(f"mode={mode}")
        self.wait_for_expect(expect_thread)

    def testUpdateRole(self):
        """Test updating node role.
        """
        device = MockThreadDevBoard(random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        device.wpantund_process.emit_status(f"role={RoleType.LEADER.value:1d}")

        for role in RoleType:
            expect_thread = self.expect_udp_messages([(f"role={role.value:1d}", device.id)])
            device.wpantund_process.emit_status(f"role={role.value:1d}")
            self.wait_for_expect(expect_thread)
            self.assertEqual(self.manager.otns_node_map[device].role, role)

    def testUpdateRoleMultipleNodes(self):
        """Test updating role for multiple nodes.
        """
        device_1 = MockThreadDevBoard(random.randint(1, 10))
        device_2 = MockThreadDevBoard(random.randint(11, 20))

        self.manager.add_node(device_1)
        self.manager.add_node(device_2)
        self.manager.subscribe_to_node(device_1)
        self.manager.subscribe_to_node(device_2)

        device_1.wpantund_process.emit_status(f"role={RoleType.LEADER.value:1d}")
        device_2.wpantund_process.emit_status(f"role={RoleType.LEADER.value:1d}")

        for role in RoleType:
            for device in [device_1, device_2]:
                expect_thread = self.expect_udp_messages([(f"role={role.value:1d}", device.id)])
                device.wpantund_process.emit_status(f"role={role.value:1d}")
                self.wait_for_expect(expect_thread)
                self.assertEqual(self.manager.otns_node_map[device].role, role)

    def testUpdateRLOC16(self):
        """Test updating node RLOC16.
        """
        device = MockThreadDevBoard(random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        for _ in range(3):
            rloc16 = random.getrandbits(16)
            expect_thread = self.expect_udp_messages([(f"rloc16={rloc16}", device.id)])
            device.wpantund_process.emit_status(f"rloc16={rloc16}")
            self.wait_for_expect(expect_thread)

    def testAddRemoveChildren(self):
        """Test adding and removing children.
        """
        device_1 = MockThreadDevBoard(random.randint(1, 10))
        device_2 = MockThreadDevBoard(random.randint(11, 20))
        device_3 = MockThreadDevBoard(random.randint(21, 30))
        devices = [device_1, device_2, device_3]

        for device in devices:
            self.manager.add_node(device)
            self.manager.subscribe_to_node(device)
            device.wpantund_process.emit_status(f"extaddr={device.mock_extaddr:016x}")

        device_1_otns_node = self.manager.otns_node_map[device_1]
        expect_thread = self.expect_udp_messages([(f"child_added={device_2.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"child_added={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 1)
        self.assertIn(device_2.mock_extaddr, device_1_otns_node.children)
        self.assertNotIn(device_3.mock_extaddr, device_1_otns_node.children)

        expect_thread = self.expect_udp_messages([(f"child_added={device_3.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"child_added={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 2)
        self.assertIn(device_2.mock_extaddr, device_1_otns_node.children)
        self.assertIn(device_3.mock_extaddr, device_1_otns_node.children)

        expect_thread = self.expect_udp_messages([(f"child_removed={device_3.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"child_removed={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 1)
        self.assertIn(device_2.mock_extaddr, device_1_otns_node.children)
        self.assertNotIn(device_3.mock_extaddr, device_1_otns_node.children)

        expect_thread = self.expect_udp_messages([(f"child_removed={device_2.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"child_removed={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 0)
        self.assertNotIn(device_2.mock_extaddr, device_1_otns_node.children)
        self.assertNotIn(device_3.mock_extaddr, device_1_otns_node.children)

    def testAddRemoveNeighbors(self):
        """Test adding and removing neighbors.
        """
        device_1 = MockThreadDevBoard(random.randint(1, 10))
        device_2 = MockThreadDevBoard(random.randint(11, 20))
        device_3 = MockThreadDevBoard(random.randint(21, 30))
        devices = [device_1, device_2, device_3]

        for device in devices:
            self.manager.add_node(device)
            self.manager.subscribe_to_node(device)
            device.wpantund_process.emit_status(f"extaddr={device.mock_extaddr:016x}")

        device_1_otns_node = self.manager.otns_node_map[device_1]
        expect_thread = self.expect_udp_messages([(f"router_added={device_2.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"router_added={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 1)
        self.assertIn(device_2.mock_extaddr, device_1_otns_node.neighbors)
        self.assertNotIn(device_3.mock_extaddr, device_1_otns_node.neighbors)

        expect_thread = self.expect_udp_messages([(f"router_added={device_3.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"router_added={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 2)
        self.assertIn(device_2.mock_extaddr, device_1_otns_node.neighbors)
        self.assertIn(device_3.mock_extaddr, device_1_otns_node.neighbors)

        expect_thread = self.expect_udp_messages([(f"router_removed={device_3.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"router_removed={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 1)
        self.assertIn(device_2.mock_extaddr, device_1_otns_node.neighbors)
        self.assertNotIn(device_3.mock_extaddr, device_1_otns_node.neighbors)

        expect_thread = self.expect_udp_messages([(f"router_removed={device_2.mock_extaddr:016x}", device_1.id)])
        device_1.wpantund_process.emit_status(f"router_removed={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 0)
        self.assertNotIn(device_2.mock_extaddr, device_1_otns_node.neighbors)
        self.assertNotIn(device_3.mock_extaddr, device_1_otns_node.neighbors)

    def testSummary(self):
        """Verify generated summary by OTNS manager.
        """
        device_1 = MockThreadDevBoard(random.randint(1, 10))
        device_2 = MockThreadDevBoard(random.randint(11, 20))
        device_3 = MockThreadDevBoard(random.randint(21, 30))
        device_4 = MockThreadDevBoard(random.randint(31, 40))
        devices = [device_1, device_2, device_3, device_4]

        for device in devices:
            self.manager.add_node(device)
            self.manager.subscribe_to_node(device)
            device.wpantund_process.emit_status(f"extaddr={device.mock_extaddr:016x}")

        # make device_1 a leader, device_2 a router and device_3 and 4 children of device_2
        device_1.wpantund_process.emit_status(f"role={RoleType.LEADER.value}")
        device_2.wpantund_process.emit_status(f"role={RoleType.ROUTER.value}")
        device_3.wpantund_process.emit_status(f"role={RoleType.CHILD.value}")
        device_4.wpantund_process.emit_status(f"role={RoleType.CHILD.value}")

        parid = random.getrandbits(16)
        for device in devices:
            device.wpantund_process.emit_status(f"parid={parid:08x}")

        device_1.wpantund_process.emit_status(f"router_added={device_2.mock_extaddr:016x}")
        device_2.wpantund_process.emit_status(f"router_added={device_1.mock_extaddr:016x}")

        device_2.wpantund_process.emit_status(f"child_added={device_3.mock_extaddr:016x}")
        device_2.wpantund_process.emit_status(f"child_added={device_4.mock_extaddr:016x}")

        # detach the network and disable all nodes
        device_2.wpantund_process.emit_status(f"child_removed={device_3.mock_extaddr:016x}")
        device_2.wpantund_process.emit_status(f"child_removed={device_4.mock_extaddr:016x}")

        device_1.wpantund_process.emit_status(f"router_removed={device_2.mock_extaddr:016x}")
        device_2.wpantund_process.emit_status(f"router_removed={device_1.mock_extaddr:016x}")

        for device in devices:
            device.wpantund_process.emit_status(f"role={RoleType.DISABLED.value}")

        # Verify summaries. Elements at index 0 in the summary entries are history timestamps. For extaddr and role
        # histories, entry[1] is the value; for children and neighbors histories, entry[1] is bool (is_added) and
        # entry[2] is the extended address of the corresponding event.
        for device in devices:
            self.assertIn(device.mock_extaddr,
                          [entry[1] for entry in self.manager.node_summaries[device.id].extaddr_history])

        device_1_summary = self.manager.node_summaries[device_1.id]
        self.assertEqual([entry[1] for entry in device_1_summary.role_history], [RoleType.LEADER, RoleType.DISABLED])
        self.assertFalse(device_1_summary.children_history)
        self.assertEqual([(entry[1], entry[2]) for entry in device_1_summary.neighbors_history],
                         [(True, device_2.mock_extaddr), (False, device_2.mock_extaddr)])

        device_2_summary = self.manager.node_summaries[device_2.id]
        self.assertEqual([entry[1] for entry in device_2_summary.role_history], [RoleType.ROUTER, RoleType.DISABLED])
        self.assertEqual([(entry[1], entry[2]) for entry in device_2_summary.children_history],
                         [(True, device_3.mock_extaddr), (True, device_4.mock_extaddr), (False, device_3.mock_extaddr),
                          (False, device_4.mock_extaddr)])
        self.assertEqual([(entry[1], entry[2]) for entry in device_2_summary.neighbors_history],
                         [(True, device_1.mock_extaddr), (False, device_1.mock_extaddr)])

        device_3_summary = self.manager.node_summaries[device_3.id]
        self.assertEqual([entry[1] for entry in device_3_summary.role_history], [RoleType.CHILD, RoleType.DISABLED])
        self.assertFalse(device_3_summary.children_history)
        self.assertFalse(device_3_summary.neighbors_history)

        device_4_summary = self.manager.node_summaries[device_4.id]
        self.assertEqual([entry[1] for entry in device_4_summary.role_history], [RoleType.CHILD, RoleType.DISABLED])
        self.assertFalse(device_4_summary.children_history)
        self.assertFalse(device_4_summary.neighbors_history)


if __name__ == "__main__":
    unittest.main()
