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
import queue
import threading
import tracemalloc
import unittest
from typing import List, Tuple

from silk.tools.otns_manager import OtnsManager
from silk.unit_tests.mock_service import MockGrpcClient, MockUDPServer

LOG_LINE_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"


class SilkTestCase(unittest.TestCase):
    """Silk unit test base case.
    """

    @classmethod
    def setUpClass(cls) -> None:
        tracemalloc.start()
        logging.basicConfig(level=logging.DEBUG, format=LOG_LINE_FORMAT)
        cls.logger = logging.Logger(cls.__name__)


class SilkMockingTestCase(SilkTestCase):
    """Silk test case with basic mocked OTNS and manager set up.
    """

    def setUp(self):
        """Test method set up.
        """
        self.exception_queue = queue.Queue()

        self.manager = OtnsManager("localhost", self.logger.getChild("OtnsManager"))
        self.grpc_client = MockGrpcClient(self.exception_queue, self.logger.getChild("MockGrpcClient"))
        self.manager.grpc_client = self.grpc_client

        self.udp_server = MockUDPServer(self.exception_queue)

    def tearDown(self):
        """Test method tear down. Clean up fixtures.
        """
        self.manager.unsubscribe_from_all_nodes()
        self.manager.remove_all_nodes()
        self.udp_server.close()

    def wait_for_expect(self, expect_thread: threading.Thread):
        """Wait for expectation to be fulfilled.

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
            commands (List[str]): expecting gRPC commands.

        Returns:
            threading.Thread: thread running the expectation.
        """
        expect_thread = threading.Thread(target=self.grpc_client.expect_commands, args=(commands,))
        expect_thread.start()
        return expect_thread

    def expect_udp_messages(self, messages: List[Tuple[str, int]]) -> threading.Thread:
        """Create a thread for an expecting UDP message.

        Args:
            messages (List[Tuple[str, int]]): list of expected UDP messages and corresponding source ID.

        Returns:
            threading.Thread: thread running the expectation.
        """
        # convert source IDs to source ports
        messages = [(message, 9000 + source_id) for message, source_id in messages]
        expect_thread = threading.Thread(target=self.udp_server.expect_messages, args=(messages,))
        expect_thread.start()
        return expect_thread
