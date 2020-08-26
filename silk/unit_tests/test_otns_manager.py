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

from silk.tools.otns_manager import OtnsManager, RoleType
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

    def expect_udp_message(self, message: str, source_port: int) -> threading.Thread:
        """Create a thread for an expecting UDP message.

        Args:
            message (str): expecting UDP message.
            source_port (int): expecting UDP message source port.

        Returns:
            threading.Thread: thread running the expectation.
        """
        expect_thread = threading.Thread(target=self.udp_server.expect_message, args=(message, source_port))
        expect_thread.start()
        return expect_thread

    def testAddDevice(self):
        """Test adding device.
        """
        device_id = random.randint(1, 10)
        device = MockThreadDevBoard("device", device_id)
        device_x, device_y = random.randint(100, 200), random.randint(100, 200)
        device.device.set_otns_vis_position(device_x, device_y)

        expect_thread = self.expect_grpc_commands([f"add router x {device_x} y {device_y} id {device_id}"])
        self.manager.add_node(device)
        self.wait_for_expect(expect_thread)

    def testRemoveDevice(self):
        """Test removing device.
        """
        device_id = random.randint(1, 10)
        device = MockThreadDevBoard("device", device_id)

        self.manager.add_node(device)

        expect_thread = self.expect_grpc_commands([f"del {device_id}"])
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

        device_1.device.set_otns_layout_parameter(layout_center_x, layout_center_y, layout_radius)
        device_2.device.set_otns_layout_parameter(layout_center_x, layout_center_y, layout_radius)
        device_3.device.set_otns_layout_parameter(layout_center_x, layout_center_y, layout_radius)
        device_4.device.set_otns_layout_parameter(layout_center_x, layout_center_y, layout_radius)

        self.manager.add_node(device_1)

        expected_coords = {
            device_1.id: (layout_center_x - layout_radius, layout_center_y),
            device_2.id: (layout_center_x + layout_radius, layout_center_y)
        }
        expect_thread = expect_grpc_move_commands(expected_coords)
        self.manager.add_node(device_2)
        self.wait_for_expect(expect_thread)

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

    def testUpdateExtaddr(self):
        """Test updating node extaddr.
        """
        device_id = random.randint(1, 10)
        device = MockThreadDevBoard("device", device_id)
        wpantund_process = MockWpantundProcess()
        device.wpantund_process = wpantund_process

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)
        device_otns_node = self.manager.otns_node_map[device]

        for _ in range(3):
            device_extaddr = random.getrandbits(64)
            expect_thread = self.expect_udp_message(f"extaddr={device_extaddr:016x}", 9000 + device_id)
            wpantund_process.emit_status(f"extaddr={device_extaddr:016x}")
            self.wait_for_expect(expect_thread)
            self.assertEqual(device_otns_node.extaddr, device_extaddr)

    def testUpdateRole(self):
        """Test updating node role.
        """
        device_id = random.randint(1, 10)
        device = MockThreadDevBoard("device", device_id)
        wpantund_process = MockWpantundProcess()
        device.wpantund_process = wpantund_process

        self.manager.add_node(device)
        self.manager.subscribe_to_node(device)
        device_otns_node = self.manager.otns_node_map[device]

        wpantund_process.emit_status(f"role={RoleType.LEADER.value:1d}")

        for role in RoleType:
            expect_thread = self.expect_udp_message(f"role={role.value:1d}", 9000 + device_id)
            wpantund_process.emit_status(f"role={role.value:1d}")
            self.wait_for_expect(expect_thread)
            self.assertEqual(device_otns_node.role, role)


if __name__ == "__main__":
    unittest.main()
