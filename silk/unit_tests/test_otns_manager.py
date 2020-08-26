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
import queue
import random
import string
import threading
import unittest

from silk.tools.otns_manager import Event, EventType, OtnsManager, RoleType
from silk.unit_tests.mock_device import MockThreadDevBoard, MockWpantundProcess
from silk.unit_tests.mock_service import MockGrpcClient, MockUDPServer
from silk.unit_tests.testcase import SilkTestCase


class OTNSUnitTest(SilkTestCase):
    """Silk unit test case for OTNS manager.
    """

    def setUp(self) -> None:
        """Test method set up.
        """
        self.exception_queue = queue.Queue()

        self.manager = OtnsManager("localhost", self.logger.getChild("OtnsManager"))
        self.grpc_client = MockGrpcClient(self.exception_queue)
        self.manager.grpc_client = self.grpc_client

        self.udp_server = MockUDPServer(self.exception_queue)

    def tearDown(self):
        """Test method tear down. Clean up fixtures.
        """
        self.manager.unsubscribe_from_all_nodes()
        self.manager.remove_all_nodes()
        self.udp_server.close()

    def wait_for_expect(self, expect_thread: threading.Thread):
        """Wait for expectation to be fuilfilled.

        Args:
            expect_thread (threading.Thread): thread running expectation.
        """
        while True:
            try:
                exception = self.exception_queue.get(block=False)
            except queue.Empty:
                pass
            else:
                self.fail(exception)

            if expect_thread.is_alive():
                expect_thread.join(0.1)
            else:
                break

    def expect_grpc_commands(self, commands: List[str]) -> threading.Thread:
        """Create a thread for an expecting gRPC commands.

        Args:
            command (List[str]): expecting gRPC commands.

        Returns:
            threading.Thread: thread running the expectation.
        """
        expect_thread = threading.Thread(target=self.grpc_client.expect_commands, args=(commands,))
        expect_thread.start()
        return expect_thread

    def expect_udp_message(self, message: str, source_id: int) -> threading.Thread:
        """Create a thread for an expecting UDP message.

        Args:
            message (str): expecting UDP message.
            source_id (int): expecting UDP message source node ID.

        Returns:
            threading.Thread: thread running the expectation.
        """
        source_port = 9000 + source_id
        expect_thread = threading.Thread(target=self.udp_server.expect_message, args=(message, source_port))
        expect_thread.start()
        return expect_thread

    def testEventEncodeDecode(self):
        """Test encoding and decoing an OTNS status event.
        """
        message = ''.join(random.choice(string.ascii_letters) for i in range(10))
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
        device = MockThreadDevBoard("device", random.randint(1, 10))
        device_x, device_y = random.randint(100, 200), random.randint(100, 200)
        device.device.set_otns_vis_position(device_x, device_y)

        expect_thread = self.expect_grpc_commands([f"add router x {device_x} y {device_y} id {device.id}"])
        self.manager.add_node(device)
        self.wait_for_expect(expect_thread)

    def testRemoveDevice(self):
        """Test removing device.
        """
        device = MockThreadDevBoard("device", random.randint(1, 10))

        self.manager.add_node(device)

        expect_thread = self.expect_grpc_commands([f"del {device.id}"])
        self.manager.remove_node(device)
        self.wait_for_expect(expect_thread)

    def testSetOTNSProperties(self):
        # speed
        speed = random.randint(2, 20)
        expect_thread = self.expect_grpc_commands([f"speed {speed}"])
        self.manager.set_replay_speed(speed)
        self.wait_for_expect(expect_thread)

        # OT NCP version
        version = ''.join(random.choice(string.ascii_letters) for i in range(10))
        expect_thread = self.expect_grpc_commands([f"netinfo version \"{version}\" real y"])
        self.manager.set_ncp_version(version)
        self.wait_for_expect(expect_thread)

        # test title
        title = ''.join(random.choice(string.ascii_letters) for i in range(10))
        expect_thread = self.expect_grpc_commands([f"title \"{title}\" x 0 y 20 fs 20"])
        self.manager.set_test_title(title)
        self.wait_for_expect(expect_thread)

    def testFixedPosition(self):
        """Test OTNS manager fixed position feature.
        """
        device_1_id, device_2_id = random.randint(1, 10), random.randint(11, 20)
        device_1 = MockThreadDevBoard("device_1", device_1_id)
        device_2 = MockThreadDevBoard("device_2", device_2_id)

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
        def expect_grpc_move_commands(expected_coords: Dict[int, Tuple[int, int]]):
            commands = [f"move {node_id} {x} {y}" for node_id, (x, y) in expected_coords.items()]
            return self.expect_grpc_commands(commands)

        def expect_node_vis_positions(devices: List[MockThreadDevBoard], expected_coords: Dict[int, Tuple[int, int]]):
            for device in devices:
                if device.id in expected_coords:
                    otns_node = self.manager.otns_node_map[device]
                    self.assertAlmostEqual(expected_coords[device.id][0], otns_node.vis_x, delta=1)
                    self.assertAlmostEqual(expected_coords[device.id][1], otns_node.vis_y, delta=1)

        layout_center_x = random.randint(100, 200)
        layout_center_y = random.randint(100, 200)
        layout_radius = random.randint(50, 100)

        device_1 = MockThreadDevBoard("device_1", 1)
        device_2 = MockThreadDevBoard("device_2", 2)
        device_3 = MockThreadDevBoard("device_3", 3)
        device_4 = MockThreadDevBoard("device_4", 4)

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
        device = MockThreadDevBoard("device", random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        for _ in range(3):
            extaddr = random.getrandbits(64)
            expect_thread = self.expect_udp_message(f"extaddr={extaddr:016x}", device.id)
            device.wpantund_process.emit_status(f"extaddr={extaddr:016x}")
            self.wait_for_expect(expect_thread)
            self.assertEqual(self.manager.otns_node_map[device].extaddr, extaddr)

    def testUpdateMode(self):
        """Test updating node mode, one of the properties OTNS manager does not track.
        """
        device = MockThreadDevBoard("device", random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        mode = "sn"
        expect_thread = self.expect_udp_message(f"mode={mode}", device.id)
        device.wpantund_process.emit_status(f"mode={mode}")
        self.wait_for_expect(expect_thread)

    def testUpdateRole(self):
        """Test updating node role.
        """
        device = MockThreadDevBoard("device", random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        device.wpantund_process.emit_status(f"role={RoleType.LEADER.value:1d}")

        for role in RoleType:
            expect_thread = self.expect_udp_message(f"role={role.value:1d}", device.id)
            device.wpantund_process.emit_status(f"role={role.value:1d}")
            self.wait_for_expect(expect_thread)
            self.assertEqual(self.manager.otns_node_map[device].role, role)

    def testUpdateRoleMultipleNodes(self):
        """Test updating role for multiple nodes.
        """
        device_1 = MockThreadDevBoard("device_1", random.randint(1, 10))
        device_2 = MockThreadDevBoard("device_2", random.randint(11, 20))

        self.manager.add_node(device_1)
        self.manager.add_node(device_2)
        self.manager.subscribe_to_node(device_1)
        self.manager.subscribe_to_node(device_2)

        device_1.wpantund_process.emit_status(f"role={RoleType.LEADER.value:1d}")
        device_2.wpantund_process.emit_status(f"role={RoleType.LEADER.value:1d}")

        for role in RoleType:
            for device in [device_1, device_2]:
                expect_thread = self.expect_udp_message(f"role={role.value:1d}", device.id)
                device.wpantund_process.emit_status(f"role={role.value:1d}")
                self.wait_for_expect(expect_thread)
                self.assertEqual(self.manager.otns_node_map[device].role, role)

    def testUpdateRLOC16(self):
        """Test updating node RLOC16.
        """
        device = MockThreadDevBoard("device", random.randint(1, 10))

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)

        for _ in range(3):
            rloc16 = random.getrandbits(16)
            expect_thread = self.expect_udp_message(f"rloc16={rloc16}", device.id)
            device.wpantund_process.emit_status(f"rloc16={rloc16}")
            self.wait_for_expect(expect_thread)

    def testAddRemoveChildren(self):
        """Test adding and removing children.
        """
        device_1 = MockThreadDevBoard("device_1", random.randint(1, 10))
        device_2 = MockThreadDevBoard("device_2", random.randint(11, 20))
        device_3 = MockThreadDevBoard("device_3", random.randint(21, 30))
        devices = [device_1, device_2, device_3]

        for device in devices:
            self.manager.add_node(device)
            self.manager.subscribe_to_node(device)
            device.wpantund_process.emit_status(f"extaddr={device.mock_extaddr:016x}")

        device_1_otns_node = self.manager.otns_node_map[device_1]
        expect_thread = self.expect_udp_message(f"child_added={device_2.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"child_added={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 1)
        self.assertTrue(device_2.mock_extaddr in device_1_otns_node.children)
        self.assertTrue(device_3.mock_extaddr not in device_1_otns_node.children)

        expect_thread = self.expect_udp_message(f"child_added={device_3.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"child_added={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 2)
        self.assertTrue(device_2.mock_extaddr in device_1_otns_node.children)
        self.assertTrue(device_3.mock_extaddr in device_1_otns_node.children)

        expect_thread = self.expect_udp_message(f"child_removed={device_3.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"child_removed={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 1)
        self.assertTrue(device_2.mock_extaddr in device_1_otns_node.children)
        self.assertTrue(device_3.mock_extaddr not in device_1_otns_node.children)

        expect_thread = self.expect_udp_message(f"child_removed={device_2.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"child_removed={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.children), 0)
        self.assertTrue(device_2.mock_extaddr not in device_1_otns_node.children)
        self.assertTrue(device_3.mock_extaddr not in device_1_otns_node.children)

    def testAddRemoveNeighbors(self):
        """Test adding and removing neighbors.
        """
        device_1 = MockThreadDevBoard("device_1", random.randint(1, 10))
        device_2 = MockThreadDevBoard("device_2", random.randint(11, 20))
        device_3 = MockThreadDevBoard("device_3", random.randint(21, 30))
        devices = [device_1, device_2, device_3]

        for device in devices:
            self.manager.add_node(device)
            self.manager.subscribe_to_node(device)
            device.wpantund_process.emit_status(f"extaddr={device.mock_extaddr:016x}")

        device_1_otns_node = self.manager.otns_node_map[device_1]
        expect_thread = self.expect_udp_message(f"router_added={device_2.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"router_added={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 1)
        self.assertTrue(device_2.mock_extaddr in device_1_otns_node.neighbors)
        self.assertTrue(device_3.mock_extaddr not in device_1_otns_node.neighbors)

        expect_thread = self.expect_udp_message(f"router_added={device_3.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"router_added={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 2)
        self.assertTrue(device_2.mock_extaddr in device_1_otns_node.neighbors)
        self.assertTrue(device_3.mock_extaddr in device_1_otns_node.neighbors)

        expect_thread = self.expect_udp_message(f"router_removed={device_3.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"router_removed={device_3.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 1)
        self.assertTrue(device_2.mock_extaddr in device_1_otns_node.neighbors)
        self.assertTrue(device_3.mock_extaddr not in device_1_otns_node.neighbors)

        expect_thread = self.expect_udp_message(f"router_removed={device_2.mock_extaddr:016x}", device_1.id)
        device_1.wpantund_process.emit_status(f"router_removed={device_2.mock_extaddr:016x}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(len(device_1_otns_node.neighbors), 0)
        self.assertTrue(device_2.mock_extaddr not in device_1_otns_node.neighbors)
        self.assertTrue(device_3.mock_extaddr not in device_1_otns_node.neighbors)


if __name__ == "__main__":
    unittest.main()