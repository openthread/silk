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

from typing import Tuple
import queue
import random
import threading
import unittest

from otns.cli import OTNS

from silk.tools.otns_manager import OtnsManager
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

    def expect_grpc_command(self, command: str) -> threading.Thread:
        """Create a thread for an expecting gRPC command.

        Args:
            command (str): expecting gRPC command.

        Returns:
            threading.Thread: thread running the expectation.
        """
        expect_thread = threading.Thread(target=self.grpc_client.expect_command, args=(command,))
        expect_thread.start()
        return expect_thread

    def testAddDevice(self):
        """Test adding device.
        """
        device_id = random.randint(1, 10)
        device = MockThreadDevBoard("device", device_id)
        device_x, device_y = random.randint(100, 200), random.randint(100, 200)
        device.device.set_otns_vis_position(device_x, device_y)

        expect_thread = self.expect_grpc_command(f"add router x {device_x} y {device_y} id {device_id}")
        self.manager.add_node(device)
        self.wait_for_expect(expect_thread)

    def testRemoveDevice(self):
        """Test adding device.
        """
        device_id = random.randint(1, 10)
        device = MockThreadDevBoard("device", device_id)

        expect_thread = self.expect_grpc_command(f"del {device_id}")
        self.manager.add_node(device)
        self.manager.remove_node(device)
        self.wait_for_expect(expect_thread)


if __name__ == "__main__":
    unittest.main()
