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

from silk.tests import silk_replay
from silk.tools.otns_manager import OtnsManager
from silk.unit_tests.mock_service import MockGrpcClient, MockUDPServer
from silk.unit_tests.testcase import SilkTestCase


class OTNSLogReplayTest(SilkTestCase):
    """Silk unit test case for log replayer.
    """

    def setUp(self) -> None:
        """Test method set up.
        """
        self.exception_queue = queue.Queue()

        self.manager = OtnsManager("localhost", self.logger.getChild("OtnsManager"))
        self.grpc_client = MockGrpcClient(self.exception_queue)
        self.manager.grpc_client = self.grpc_client

        self.udp_server = MockUDPServer(self.exception_queue)

        hwconfig_path = Path(__file__).parent / "fixture/hwconfig.ini"
        self.args = ["tests/silk_replay.py", "-v2", "-c", str(hwconfig_path), "-s", "localhost", "-p", "100"]

    def tearDown(self):
        """Test method tear down. Clean up fixtures.
        """
        self.manager.unsubscribe_from_all_nodes()
        self.manager.remove_all_nodes()
        self.udp_server.close()

    def get_log_path(self, basename: str) -> Path:
        """Generate path to a log file.

        Args:
            basename (str): log file basename.

        Returns:
            Path: Path to the log file.
        """
        return Path(__file__).parent / f"fixture/{basename}"

    def testReplayFormNetwork(self):
        """Test replaying the form network test case log.
        """
        log_path = str(self.get_log_path("form_network_log.txt"))
        replayer = silk_replay.SilkReplayer(argv=self.args + [log_path], run_now=False)
        replayer.otns_manager = self.manager
        # setting up
        line_number = replayer.run(stop_regex=r"Sent cmd: title \"TestFormNetwork.set_up\"")
        # pairing
        line_number = replayer.run(start_line=line_number,
                                   stop_regex=r"Sent cmd: title \"TestFormNetwork.test01_Pairing\"")
        # get WPAN status
        line_number = replayer.run(start_line=line_number,
                                   stop_regex=r"Sent cmd: title \"TestFormNetwork.test02_GetWpanStatus\"")
        # ping LLA
        line_number = replayer.run(start_line=line_number,
                                   stop_regex=r"Sent cmd: title \"TestFormNetwork.test03_PingRouterLLA\"")
        # ping MLA
        line_number = replayer.run(start_line=line_number,
                                   stop_regex=r"Sent cmd: title \"TestFormNetwork.test04_PingRouterMLA\"")
        # ping ULA
        line_number = replayer.run(start_line=line_number,
                                   stop_regex=r"Sent cmd: title \"TestFormNetwork.test05_PingRouterULA\"")
        # tearing down
        line_number = replayer.run(start_line=line_number, stop_regex=r"Sent cmd: title \"TestFormNetwork.tear_down\"")
        # finish
        replayer.run(start_line=line_number)


if __name__ == "__main__":
    unittest.main()
