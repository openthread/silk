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
"""This module contains mock service classes for tests.
"""

from typing import List, Tuple
import logging
import queue
import socket
import time

from silk.tools.otns_manager import Event, GRpcClient
from silk.unit_tests.test_utils import commands_almost_equal


class ExpectationError(Exception):
    """Test expectation error.
    """

    def __init__(self, error: str):
        """Initialize an expectation error with message.

        Args:
            error (str): error message.
        """
        super().__init__(error)


class MockGrpcClient(GRpcClient):
    """Mock gRPC Client for testing dependency injection.
    """

    def __init__(self, exception_queue: queue.Queue, logger: logging.Logger):
        """Initialize a mock gRPC client.

        Args:
            exception_queue (queue.Queue): queue to put exception into.
            logger (logging.Logger): logger for the client.
        """
        super().__init__("localhost", logger)
        self.exception_queue = exception_queue
        self.command_buffer = []

    def expect_commands(self, commands: List[str], timeout: int = 10):
        """Listen for expected gRPC commands.

        Args:
            commands (List[str]): expected gRPC commands.
            timeout (int, optional): wait timeout. Defaults to 10.
        """
        unseen_commands = set(commands)
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                self.exception_queue.put(ExpectationError("Expectation not fulfilled within time limit"))
                return
            if not unseen_commands:
                return
            for unseen_command in list(unseen_commands):
                for command in self.command_buffer:
                    if commands_almost_equal(unseen_command, command):
                        unseen_commands.discard(unseen_command)
            self.command_buffer.clear()
            time.sleep(0.1)

    def _send_command(self, command: str):
        """Send a Command gRPC request.

        Args:
            command (str): command content.
        """
        self.command_buffer.append(command)


class MockUDPServer(object):
    """Mock UDP server to simulate OTNS dispatcher functionalities.
    """

    def __init__(self, exception_queue: queue.Queue):
        """Initialize a mock UDP server.

        Args:
            exception_queue (queue.Queue): queue to put exception into.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.2)
        server_address = ("localhost", 9000)
        self.sock.bind(server_address)
        self._running = True
        self.exception_queue = exception_queue

    def close(self):
        """Shut down the mock UDP server.
        """
        self.sock.close()
        self._running = False

    def expect_messages(self, messages: List[Tuple[str, int]], timeout: int = 20):
        """Listen for expected UDP message.

        Args:
            messages (List[Tuple[str, int]]): list of expected UDP messages and corresponding source port.
            timeout (int, optional): wait timeout. Defaults to 20. With 0.01 delay the client can process at most
                2000 messages before raising an exception.
        """
        unseen_messages = set(messages)
        start_time = time.time()
        while self._running:
            if time.time() - start_time > timeout:
                self.exception_queue.put(ExpectationError("Expectation not fulfilled within time limit"))
                return
            if not unseen_messages:
                return
            try:
                data, address = self.sock.recvfrom(0xfff)
                received_message = Event.from_bytes(data).message
                for message, source_port in list(unseen_messages):
                    if message == received_message and source_port == address[1]:
                        unseen_messages.discard((message, source_port))
                time.sleep(0.01)
            except socket.timeout:
                pass
