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
import unittest
from typing import Dict

from silk.tests.silk_replay import SilkReplayer
from silk.tools.otns_manager import RoleType, OtnsNode
from silk.unit_tests.testcase import SilkMockingTestCase


class OTNSLogReplayTest(SilkMockingTestCase):
    """Silk unit test case for log replayer.

    In the test methods in this class, we pause at certain stages of the log parsing process to verify the status of
    OTNS manager to confirm the replayer correctly parses the log. The stop_regex is usually the end of current test
    phase or the start of next test phase.
    """

    def setUp(self):
        """Test method set up.
        """
        super().setUp()

        hwconfig_path = Path(__file__).parent / "fixture/hwconfig.ini"
        self.args = ["tests/silk_replay.py", "-v2", "-c", str(hwconfig_path), "-s", "localhost", "-p", "100"]

    def create_replayer(self, log_filename: str) -> SilkReplayer:
        """Prepare a replayer for a test.

        Args:
            log_filename (str): log file basename.

        Returns:
            SilkReplayer: a SilkReplayer prepared for a test.
        """
        log_path = str(Path(__file__).parent / f"fixture/{log_filename}")
        replayer = SilkReplayer(argv=self.args + [log_path], run_now=False)
        replayer.otns_manager = self.manager
        return replayer

    def testReplayFormNetwork(self):
        """Test replaying the form network test case log.

        The log file runs with 7 nodes to form a Thread network, with 1 leader, 4 routers, and 2 SEDs.
        Nodes are numbered 2 to 8. Node 2 becomes the leader and nodes 3-6 become routers. 7-8 become SEDs and children
        of node 2.
        """
        test_class = "TestFormNetwork"
        test_phases = [
            "test01_Pairing", "test02_GetWpanStatus", "test03_PingRouterLLA", "test04_PingRouterMLA",
            "test05_PingRouterULA"
        ]

        def assert_network_topology(nodes: Dict[int, OtnsNode]):
            """Assert that the network topology is as described above.

            Args:
                nodes (Dict[int, OtnsNode]) nodes from the OTNS manager.
            """
            self.assertEqual(RoleType.LEADER, nodes[2].role)
            children = [nodes[child_id].extaddr for child_id in range(7, 9)]
            for child_extaddr in children:
                self.assertIn(child_extaddr, nodes[2].children)
            for node_id in range(3, 7):
                self.assertEqual(RoleType.ROUTER, nodes[node_id].role)
            for node_id in range(7, 9):
                self.assertEqual(RoleType.CHILD, nodes[node_id].role)
            # fully meshed network, each of the 5 routers have 4 neighbors
            for node_id in range(2, 7):
                self.assertEqual(len(nodes[node_id].neighbors), 4)
                neighbors = [nodes[neighbor_id].extaddr for neighbor_id in range(2, 7) if neighbor_id != node_id]
                for neighbor_extaddr in neighbors:
                    self.assertIn(neighbor_extaddr, nodes[node_id].neighbors)

        replayer = self.create_replayer("form_network_log.txt")

        # setting up: nodes added
        line_number = replayer.run(stop_regex=fr"SET UP {test_class}.{test_phases[0]}")
        otns_nodes = {}
        self.assertEqual(len(self.manager.otns_node_map), 7)
        for node in self.manager.otns_node_map.values():
            otns_nodes[node.node_id] = node
            self.assertNotEqual(node.node_id, node.extaddr)
            self.assertEqual(RoleType.DISABLED, node.role)
            self.assertFalse(node.children)
            self.assertFalse(node.neighbors)

        # pairing: node modes change; title changes
        udp_expect_thread = self.expect_udp_messages([("mode=sn", 7), ("mode=sn", 8)])
        grpc_expect_thread = self.expect_grpc_commands([f"title \"{test_class}.{test_phases[0]}\" x 0 y 20 fs 20"])
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[0]}")
        self.wait_for_expect(udp_expect_thread)
        self.wait_for_expect(grpc_expect_thread)
        self.assertEqual(len(self.manager.otns_node_map), 7)

        # get WPAN status: waiting for the mesh to form
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[1]}")
        assert_network_topology(otns_nodes)

        # ping LLA
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[2]}")
        assert_network_topology(otns_nodes)

        # ping MLA
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[3]}")
        assert_network_topology(otns_nodes)

        # ping ULA
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[4]}")
        assert_network_topology(otns_nodes)

        # tearing down: nodes removed
        expect_thread = self.expect_grpc_commands([f"del {i}" for i in range(2, 9)])
        replayer.run(start_line=line_number)
        self.wait_for_expect(expect_thread)
        self.assertFalse(self.manager.otns_node_map)


if __name__ == "__main__":
    unittest.main()
