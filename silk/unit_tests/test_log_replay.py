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

from pathlib import Path
import queue
import unittest

from silk.tools.otns_manager import OtnsManager
from silk.unit_tests.mock_service import MockGrpcClient, MockUDPServer
from silk.unit_tests.testcase import SilkTestCase


class OTNSLogReplayTest(SilkTestCase):
    """Silk unit test case for log replayer.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super(OTNSLogReplayTest, cls).setUpClass()

        path = Path(__file__).parent / "fixture/form_network_log.txt"
        cls.log_file = path.open()

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

    def testLogReplay(self):
        pass


if __name__ == "__main__":
    unittest.main()
