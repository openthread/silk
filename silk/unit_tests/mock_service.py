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

import queue
import socket
import time

from silk.tools.otns_manager import Event, GRpcClient


class ExpectationError(Exception):
    """Test expectation error.
    """

    def __init__(self, error: str):
        """Initialize an expectation error with message.

        Args:
            error (str): error message.
        """
        super(ExpectationError, self).__init__(error)


class MockGrpcClient(GRpcClient):
    """Mock gRPC Client for testing dependency injection.
    """

    def __init__(self, exception_queue: queue.Queue):
        self.exception_queue = exception_queue
        self.command_buffer = []

    def expect_command(self, command: str, timeout: int = 10):
        """Listen for expected gRPC.

        Args:
            message (str): expected gRPC command.
            timeout (int, optional): wait timeout. Defaults to 10.
        """
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                self.exception_queue.put(ExpectationError("Expectation not fulfilled within time limit"))
                return
            if command in self.command_buffer:
                return
            else:
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
            exception_queue (queue.Queue): queue to put exception onto.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = ("localhost", 9000)
        self.sock.bind(server_address)
        self._running = True
        self.exception_queue = exception_queue

    def close(self):
        """Shut down the mock UDP server.
        """
        self.sock.close()
        self._running = False

    def expect_message(self, message: str, source_port: int, timeout: int = 10):
        """Listen for expected UDP message.

        Args:
            message (str): expected UDP message.
            source_port (int): expected UDP source port.
            timeout (int, optional): wait timeout. Defaults to 10.
        """
        start_time = time.time()
        while self._running:
            if time.time() - start_time > timeout:
                self.exception_queue.put(ExpectationError("Expectation not fulfilled within time limit"))
                return
            data, address = self.sock.recvfrom(0xff)
            if message == Event.from_bytes(data).message and address[1] == source_port:
                return
            else:
                time.sleep(0.1)
