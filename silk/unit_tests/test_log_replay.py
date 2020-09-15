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

    def verify_nodes_added(self, node_number: int) -> Dict[int, OtnsNode]:
        """Verify that a set number of nodes are created in the OTNS manager.

        Returns:
            Dict[int, OtnsNode]: a dictionary mapping from node ID to the OTNS nodes.
        """
        otns_nodes = {}
        self.assertEqual(node_number, len(self.manager.otns_node_map))
        for node in self.manager.otns_node_map.values():
            otns_nodes[node.node_id] = node
            self.assertNotEqual(node.node_id, node.extaddr)
            self.assertEqual(RoleType.DISABLED, node.role)
            self.assertFalse(node.children)
            self.assertFalse(node.neighbors)
        return otns_nodes

    def testReplayFormNetwork(self):
        """Test replaying the form network test case log.

        The log file runs with 7 nodes to form a Thread network, with 1 leader, 4 routers, and 2 SEDs.
        Nodes are numbered 2 to 8. Node 2 becomes the leader and nodes 3-6 become routers. 7-8 become SEDs and children
        of node 2.
        """

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
                self.assertEqual(4, len(nodes[node_id].neighbors))
                neighbors = [nodes[neighbor_id].extaddr for neighbor_id in range(2, 7) if neighbor_id != node_id]
                for neighbor_extaddr in neighbors:
                    self.assertIn(neighbor_extaddr, nodes[node_id].neighbors)

        test_class = "TestFormNetwork"
        test_phases = [
            "test01_Pairing", "test02_GetWpanStatus", "test03_PingRouterLLA", "test04_PingRouterMLA",
            "test05_PingRouterULA"
        ]

        replayer = self.create_replayer("form_network_log.txt")

        # setting up: nodes added
        line_number = replayer.run(stop_regex=fr"SET UP {test_class}.{test_phases[0]}")
        otns_nodes = self.verify_nodes_added(7)

        # pairing: node modes change; title changes
        udp_expect_thread = self.expect_udp_messages([("mode=sn", 7), ("mode=sn", 8)])
        grpc_expect_thread = self.expect_grpc_commands([f"title \"{test_class}.{test_phases[0]}\" x 0 y 20 fs 20"])
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[0]}")
        self.wait_for_expect(udp_expect_thread)
        self.wait_for_expect(grpc_expect_thread)
        self.assertEqual(
            7,
            len(self.manager.otns_node_map),
        )

        for phase in range(1, 5):
            line_number = replayer.run(start_line=line_number,
                                       stop_regex=fr"TEAR DOWN {test_class}.{test_phases[phase]}")
            assert_network_topology(otns_nodes)

        # tearing down: nodes removed
        expect_thread = self.expect_grpc_commands([f"del {i}" for i in range(2, 9)])
        replayer.run(start_line=line_number)
        self.wait_for_expect(expect_thread)
        self.assertFalse(self.manager.otns_node_map)

    def testReplayRouterTable(self):
        """Test replaying the router table test case log.

        The log file runs with 5 nodes to form a Thread network, with 1 leader, 3 routers and 1 SED.
        Nodes are numbered 2 to 8. Node 2 becomes leader, 3-5 become routers. Node 6 becomes a child of node 5.
        Nodes 2-4 forms full mesh, and node 5 becomes neighbor of node 4.
        """

        def assert_network_topology(nodes: Dict[int, OtnsNode]):
            """Assert that the network topology is as described above.

            Args:
                nodes (Dict[int, OtnsNode]) nodes from the OTNS manager.
            """
            self.assertEqual(RoleType.LEADER, nodes[2].role)
            for node_id in range(3, 6):
                self.assertEqual(RoleType.ROUTER, nodes[node_id].role)
            self.assertEqual(RoleType.CHILD, nodes[6].role)
            self.assertIn(nodes[6].extaddr, nodes[5].children)
            # nodes 2 and 3 has two neighbors
            for node_id in range(2, 4):
                self.assertEqual(2, len(nodes[node_id].neighbors))

        test_class = "TestRouterTable"
        test_phases = [
            "test01_Form_Network", "test02_Verify_Node_Type", "test03_Verify_r1_Router_Table",
            "test04_Verify_r3_Router_Table", "test05_Verify_r4_Router_Table"
        ]

        replayer = self.create_replayer("router_table_log.txt")

        # setting up: nodes added
        line_number = replayer.run(stop_regex=fr"SET UP {test_class}.{test_phases[0]}")
        otns_nodes = self.verify_nodes_added(5)

        # form network: node modes change; title changes
        udp_expect_thread = self.expect_udp_messages([("mode=sn", 6)])
        grpc_expect_thread = self.expect_grpc_commands([f"title \"{test_class}.{test_phases[0]}\" x 0 y 20 fs 20"])
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[0]}")
        self.wait_for_expect(udp_expect_thread)
        self.wait_for_expect(grpc_expect_thread)
        self.assertEqual(5, len(self.manager.otns_node_map))

        for phase in range(1, 5):
            line_number = replayer.run(start_line=line_number,
                                       stop_regex=fr"TEAR DOWN {test_class}.{test_phases[phase]}")
            assert_network_topology(otns_nodes)

        # tearing down: nodes removed
        expect_thread = self.expect_grpc_commands([f"del {i}" for i in range(2, 7)])
        replayer.run(start_line=line_number)
        self.wait_for_expect(expect_thread)
        self.assertFalse(self.manager.otns_node_map)

    def testReplayChildTable(self):
        """Test replaying the child table test case log.

        The log file runs with 7 nodes to form a Thread network, with 1 leader and 6 FEDs.
        Nodes are numbered 2 to 8. Node 2 becomes leader, 3-8 become children of node 2.
        """

        def assert_network_topology(nodes: Dict[int, OtnsNode]):
            """Assert that the network topology is as described above.

            Args:
                nodes (Dict[int, OtnsNode]) nodes from the OTNS manager.
            """
            self.assertEqual(RoleType.LEADER, nodes[2].role)
            for node_id in range(3, 9):
                self.assertEqual(RoleType.CHILD, nodes[node_id].role)
            self.assertEqual(6, len(nodes[2].children))
            # nodes 2 and 3 has two neighbors
            for node_id in range(3, 9):
                self.assertIn(nodes[node_id].extaddr, nodes[2].children)

        test_class = "TestChildTable"
        test_phases = [
            "test01_Pairing", "test02_Verify_ChildTable", "test03_Verify_ChildTableAddress",
            "test04_Verify_ChildTable_AsValMap"
        ]

        replayer = self.create_replayer("child_table_log.txt")

        # setting up: nodes added
        line_number = replayer.run(stop_regex=fr"SET UP {test_class}.{test_phases[0]}")
        otns_nodes = self.verify_nodes_added(7)

        # pairing
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[0]}")
        self.assertEqual(7, len(self.manager.otns_node_map))

        for phase in range(1, 4):
            line_number = replayer.run(start_line=line_number,
                                       stop_regex=fr"TEAR DOWN {test_class}.{test_phases[phase]}")
            assert_network_topology(otns_nodes)

        # tearing down: nodes removed
        expect_thread = self.expect_grpc_commands([f"del {i}" for i in range(2, 9)])
        replayer.run(start_line=line_number)
        self.wait_for_expect(expect_thread)
        self.assertFalse(self.manager.otns_node_map)

    def testReplayNeighborTable(self):
        """Test replaying the neighbor table test case log.

        The log file runs with 4 nodes to form a Thread network, with 1 leader, 1 router, 1 FED, and 1 SED.
        Nodes are numbered 2 to 5. Node 2 becomes leader, 3 becomes router, 4 becomes SED, and 5 becomes FED.
        Nodes 2 and 3 are neighbors, and 4 becomes a child of 2, while 5 becomes a child of 3.
        """

        def assert_network_topology(nodes: Dict[int, OtnsNode]):
            """Assert that the network topology is as described above.

            Args:
                nodes (Dict[int, OtnsNode]) nodes from the OTNS manager.
            """
            self.assertEqual(RoleType.LEADER, nodes[2].role)
            self.assertEqual(RoleType.ROUTER, nodes[3].role)
            for node_id in range(4, 6):
                self.assertEqual(RoleType.CHILD, nodes[node_id].role)
            self.assertEqual(1, len(nodes[2].neighbors))
            self.assertEqual(1, len(nodes[3].neighbors))
            self.assertEqual(1, len(nodes[2].children))
            self.assertEqual(1, len(nodes[3].children))
            self.assertIn(nodes[2].extaddr, nodes[3].neighbors)
            self.assertIn(nodes[3].extaddr, nodes[2].neighbors)
            self.assertIn(nodes[4].extaddr, nodes[2].children)
            self.assertIn(nodes[5].extaddr, nodes[3].children)

        test_class = "TestNeighborTable"
        test_phases = [
            "test01_Form_Network", "test02_Verify_Router_Type", "test03_Verify_Children", "test04_Verify_Router",
            "test05_Verify_NeighborTable_AsValMap"
        ]

        replayer = self.create_replayer("neighbor_table_log.txt")

        # setting up: nodes added
        line_number = replayer.run(stop_regex=fr"SET UP {test_class}.{test_phases[0]}")
        otns_nodes = self.verify_nodes_added(4)

        # form network: node modes change; title changes
        expect_thread = self.expect_udp_messages([("mode=sn", 4)])
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[0]}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(4, len(self.manager.otns_node_map))

        for phase in range(1, 5):
            line_number = replayer.run(start_line=line_number,
                                       stop_regex=fr"TEAR DOWN {test_class}.{test_phases[phase]}")
            assert_network_topology(otns_nodes)

        # tearing down: nodes removed
        expect_thread = self.expect_grpc_commands([f"del {i}" for i in range(2, 6)])
        replayer.run(start_line=line_number)
        self.wait_for_expect(expect_thread)
        self.assertFalse(self.manager.otns_node_map)

    def testReplayPartitionMerge(self):
        """Test replaying the partition merge test case log.

        The log file runs with 4 nodes to form a Thread network, with 1 leader, 1 router, and 2 FEDs.
        Nodes are numbered 2 to 5. Initially node 2 becomes leader, 3 becomes router, 4-5 become FED.
        Nodes 2 and 3 are neighbors, and 4 becomes a child of 2, while 5 becomes a child of 3. The test separates
        the two so that 3 becomes a leader on its own, then merge the partitions again.
        """

        def assert_network_topology_one_partition(nodes: Dict[int, OtnsNode]):
            """Assert that the network topology is as described above.

            Args:
                nodes (Dict[int, OtnsNode]) nodes from the OTNS manager.
            """
            self.assertEqual(RoleType.LEADER, nodes[2].role)
            self.assertEqual(RoleType.ROUTER, nodes[3].role)
            for node_id in range(4, 6):
                self.assertEqual(RoleType.CHILD, nodes[node_id].role)
            self.assertEqual(1, len(nodes[2].neighbors))
            self.assertEqual(1, len(nodes[3].neighbors))
            self.assertEqual(1, len(nodes[2].children))
            self.assertEqual(1, len(nodes[3].children))
            self.assertIn(nodes[2].extaddr, nodes[3].neighbors)
            self.assertIn(nodes[3].extaddr, nodes[2].neighbors)
            self.assertIn(nodes[4].extaddr, nodes[2].children)
            self.assertIn(nodes[5].extaddr, nodes[3].children)

        def assert_network_topology_two_partitions(nodes: Dict[int, OtnsNode]):
            """Assert that the network topology is as described above.

            Args:
                nodes (Dict[int, OtnsNode]) nodes from the OTNS manager.
            """
            self.assertEqual(RoleType.LEADER, nodes[2].role)
            self.assertEqual(RoleType.LEADER, nodes[3].role)
            for node_id in range(4, 6):
                self.assertEqual(RoleType.CHILD, nodes[node_id].role)
            self.assertFalse(nodes[2].neighbors)
            self.assertFalse(nodes[3].neighbors)
            self.assertEqual(1, len(nodes[2].children))
            self.assertEqual(1, len(nodes[3].children))
            self.assertNotIn(nodes[2].extaddr, nodes[3].neighbors)
            self.assertNotIn(nodes[3].extaddr, nodes[2].neighbors)
            self.assertIn(nodes[4].extaddr, nodes[2].children)
            self.assertIn(nodes[5].extaddr, nodes[3].children)

        test_class = "TestPartitionMerge"
        test_phases = [
            "test01_pairing", "test02_unallowlist_r1_r2", "test03_allowlist_r1_r2",
            "test04_verify_role_prefix_childTable"
        ]

        replayer = self.create_replayer("partition_merge_log.txt")

        # setting up: nodes added
        line_number = replayer.run(stop_regex=fr"SET UP {test_class}.{test_phases[0]}")
        otns_nodes = self.verify_nodes_added(4)

        # form network: routers added
        expect_thread = self.expect_udp_messages([(f"router_added={otns_nodes[2].extaddr:016x}", 3),
                                                  (f"router_added={otns_nodes[3].extaddr:016x}", 2)])
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[0]}")
        self.wait_for_expect(expect_thread)
        self.assertEqual(4, len(self.manager.otns_node_map))
        assert_network_topology_one_partition(otns_nodes)

        # unallowlist: separate partitions; routers links removed
        expect_thread = self.expect_udp_messages([(f"router_removed={otns_nodes[2].extaddr:016x}", 3),
                                                  (f"router_removed={otns_nodes[3].extaddr:016x}", 2)])
        line_number = replayer.run(start_line=line_number, stop_regex=fr"TEAR DOWN {test_class}.{test_phases[1]}")
        self.wait_for_expect(expect_thread)
        assert_network_topology_two_partitions(otns_nodes)

        for phase in range(2, 4):
            line_number = replayer.run(start_line=line_number,
                                       stop_regex=fr"TEAR DOWN {test_class}.{test_phases[phase]}")
            assert_network_topology_one_partition(otns_nodes)

        # tearing down: nodes removed
        expect_thread = self.expect_grpc_commands([f"del {i}" for i in range(2, 6)])
        replayer.run(start_line=line_number)
        self.wait_for_expect(expect_thread)
        self.assertFalse(self.manager.otns_node_map)


if __name__ == "__main__":
    unittest.main()
