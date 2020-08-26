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

from typing import List
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
        """Initialize a mock gRPC client.

        Args:
            exception_queue (queue.Queue): queue to put exception into.
        """
        self.exception_queue = exception_queue
        self.command_buffer = []

    def _command_almost_equal(self, command1: str, command2: str, delta: float = 1.0) -> bool:
        """Check if two commands are almost equal.

        Almost equal means we allow numerical parts in the commands to differ by the defined delta.

        Args:
            command1 (str): first command.
            command2 (str): second command.
            delta (float): allowed numerical delta.

        Returns:
            bool: if the two commands are almost equal.
        """
        if command1 == command2:
            return True

        command1_parts, command2_parts = command1.split(), command2.split()

        if len(command1_parts) != len(command2_parts):
            return False

        for part1, part2 in zip(command1_parts, command2_parts):
            if part1 == part2:
                continue
            else:
                try:
                    part1_int = int(part1)
                    part2_int = int(part2)
                    if abs(part1_int - part2_int) <= delta:
                        continue
                    else:
                        return False
                except ValueError:
                    return False
        
        return True

    def expect_commands(self, commands: List[str], timeout: int = 10):
        """Listen for expected gRPC commands.

        Args:
            message (List[str]): expected gRPC commands.
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
                    if self._command_almost_equal(unseen_command, command):
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
            try:
                data, address = self.sock.recvfrom(0xfff)
                if message == Event.from_bytes(data).message and address[1] == source_port:
                    return
                else:
                    time.sleep(0.1)
            except socket.timeout:
                pass
