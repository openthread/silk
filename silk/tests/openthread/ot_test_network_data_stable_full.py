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

import random
import time
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify_within, verify, verify_prefix_with_rloc16, verify_no_prefix_with_rloc16
from silk.utils import process_cleanup

hwr.global_instance()

WAIT_TIME = 15
POLL_INTERVAL = 400

prefix1 = "fd00:1::"
prefix2 = "fd00:2::"
prefix3 = "fd00:3::"
no_rloc = 0xfffe


class TestNetworkDataStableFull(testcase.TestCase):
    # Test description: Network Data update and version changes (stable only vs. full version).
    #
    # Network topology
    #
    #      leader
    #      /  |  \
    #     /   |   \
    #    /    |    \
    #   ed1    ed2    sed1
    #
    #
    # sed1 is sleepy-end node and also configured to request stable Network Data only
    #
    # Test covers the following steps:
    # - Adding/removing prefixes (stable or temporary) on ed1
    # - Verifying that Network Data is updated on all nodes
    # - Ensuring correct update to version and stable version

    # The above steps are repeated over many different situations:
    # - Where the same prefixes are also added by other nodes
    # - Or the same prefixes are added as off-mesh routes by other nodes.

    @classmethod
    def hardware_select(cls):
        cls.leader = ffdb.ThreadDevBoard()
        cls.ed1 = ffdb.ThreadDevBoard()
        cls.ed2 = ffdb.ThreadDevBoard()
        cls.sed1 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.leader, cls.ed1, cls.ed2, cls.sed1]

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        for device in cls.all_nodes:

            device.set_logger(cls.logger)
            cls.add_test_device(device)

            device.set_up()

        cls.network_data = WpanCredentials(network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
                                           psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
                                           channel=random.randint(11, 25),
                                           fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

        cls.thread_sniffer_init(cls.network_data.channel)

    @classmethod
    @testcase.teardown_class_decorator
    def tearDownClass(cls):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def prefix_add_remove(self):
        # Tests adding and removing stable and temporary prefixes on r1
        # Verifies that all nodes in network do see the updates and that
        # Network Data version and stable version are updated correctly.

        old_version = int(self.leader.get(wpan.WPAN_THREAD_NETWORK_DATA_VERSION), 0)
        old_stable_version = int(self.leader.get(wpan.WPAN_THREAD_STABLE_NETWORK_DATA_VERSION), 0)
        self.logger.info(f"Thread network data version: {old_version}")
        self.logger.info(f"Thread stable network data version: {old_stable_version}")
        ed1_rloc = int(self.ed1.getprop(wpan.WPAN_THREAD_RLOC16), 16)

        self.logger.info(f"Add {prefix1} as stable prefix and verify all nodes add it")
        self.ed1.add_prefix(prefix1, stable=True)

        def check_prefix1():
            verify_prefix_with_rloc16(
                [self.leader, self.ed1, self.ed2],
                prefix1,
                ed1_rloc,
                stable=True, preferred=False
            )

            verify_prefix_with_rloc16(
                [self.sed1],
                prefix1,
                no_rloc,
                stable=True, preferred=False
            )

        verify_within(check_prefix1, WAIT_TIME)

        new_version = int(self.leader.get(wpan.WPAN_THREAD_NETWORK_DATA_VERSION), 0)
        new_stable_version = int(self.leader.get(wpan.WPAN_THREAD_STABLE_NETWORK_DATA_VERSION), 0)
        verify(new_version == ((old_version + 1) % 256))
        verify(new_stable_version == ((old_stable_version + 1) % 256))

        old_version = new_version
        old_stable_version = new_stable_version
        self.logger.info(f"Thread network data version: {old_version}")
        self.logger.info(f"Thread stable network data version: {old_stable_version}")

        self.logger.info(f"Add {prefix2} as temporary prefix and verify except sleepy node all nodes add it")
        self.ed1.add_prefix(prefix2, stable=False)

        def check_prefix2():
            verify_prefix_with_rloc16(
                [self.leader, self.ed1, self.ed2],
                prefix2,
                ed1_rloc,
                stable=False, preferred=False
            )

        verify_within(check_prefix1, WAIT_TIME)
        verify_within(check_prefix2, WAIT_TIME)

        new_version = int(self.leader.get(wpan.WPAN_THREAD_NETWORK_DATA_VERSION), 0)
        new_stable_version = int(self.leader.get(wpan.WPAN_THREAD_STABLE_NETWORK_DATA_VERSION), 0)
        verify(new_version == ((old_version + 1) % 256))
        verify(new_stable_version == old_stable_version)

        old_version = new_version
        old_stable_version = new_stable_version
        self.logger.info(f"Thread network data version: {old_version}")
        self.logger.info(f"Thread stable network data version: {old_stable_version}")

        self.logger.info("Verify removing stable prefix {prefix1} from ed1 removes it from all nodes")

        self.ed1.remove_prefix(prefix1)

        def check_no_prefix1():
            verify_no_prefix_with_rloc16([self.leader, self.ed1, self.ed2], prefix1, ed1_rloc)

        verify_within(check_no_prefix1, WAIT_TIME)
        verify_within(check_prefix2, WAIT_TIME)

        new_version = int(self.leader.get(wpan.WPAN_THREAD_NETWORK_DATA_VERSION), 0)
        new_stable_version = int(self.leader.get(wpan.WPAN_THREAD_STABLE_NETWORK_DATA_VERSION), 0)

        verify(new_version == ((old_version + 1) % 256))
        verify(new_stable_version == ((old_stable_version + 1) % 256))
        old_version = new_version
        old_stable_version = new_stable_version
        self.logger.info(f"Thread network data version: {old_version}")
        self.logger.info(f"Thread stable network data version: {old_stable_version}")

        self.logger.info("Verify removing temporary prefix {prefix2} from ed1 removes it from all nodes")
        self.ed1.remove_prefix(prefix2)

        def check_no_prefix2():
            verify_no_prefix_with_rloc16([self.leader, self.ed1, self.ed2], prefix2, ed1_rloc)

        verify_within(check_no_prefix1, WAIT_TIME)
        verify_within(check_no_prefix2, WAIT_TIME)

        new_version = int(self.leader.get(wpan.WPAN_THREAD_NETWORK_DATA_VERSION), 0)
        new_stable_version = int(self.leader.get(wpan.WPAN_THREAD_STABLE_NETWORK_DATA_VERSION), 0)

        verify(new_version == ((old_version + 1) % 256))
        verify(new_stable_version == old_stable_version)
        self.logger.info(f"Thread network data version: {new_version}")
        self.logger.info(f"Thread stable network data version: {new_stable_version}")

    @testcase.test_method_decorator
    def test01_clear_full_network_data_on_sed1(self):
        # Clear the "full network data" flag on sed1.
        self.sed1.set(wpan.WPAN_THREAD_DEVICE_MODE, '-')
        self.sed1.get(wpan.WPAN_THREAD_DEVICE_MODE, '-')

    @testcase.test_method_decorator
    def test02_pairing(self):
        # Create allowlisted nodes based on the topology.
        for node1, node2 in [(self.leader, self.ed1), (self.leader, self.ed2),
                             (self.leader, self.sed1)]:
            node1.allowlist_node(node2)
            node2.allowlist_node(node1)

        self.leader.form(self.network_data, "router")
        self.leader.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.leader.ip6_lla)
        self.logger.info(self.leader.ip6_thread_ula)

        self.network_data.xpanid = self.leader.xpanid
        self.network_data.panid = self.leader.panid

        for node in [self.ed1, self.ed2]:
            node.join(self.network_data, "end-node")
            self.wait_for_completion(self.device_list)

        self.sed1.join(self.network_data, "sleepy-end-device")
        self.wait_for_completion(self.device_list)
        self.sed1.set_sleep_poll_interval(POLL_INTERVAL)

    @testcase.test_method_decorator
    def test03_verify_network_data_on_prefix_add_remove(self):
        self.prefix_add_remove()

    @testcase.test_method_decorator
    def test04_verify_network_data_on_same_prefix_add_remove(self):
        # Repeat the `test_prefix_add_remove()` under different situations
        # where same prefix is added/removed by other nodes in the network
        # or added as an off-mesh route.

        num_routes = 0

        self.logger.info(f"========= Add same stable prefix {prefix1} on leader node =========")
        self.leader.add_prefix(prefix1, stable=False)
        self.prefix_add_remove()

        self.logger.info(f"========= Add same temporary prefix {prefix2} on leader node =========")
        self.leader.add_prefix(prefix2, stable=True)
        self.prefix_add_remove()

        self.logger.info(f"========= Remove stable prefix {prefix1} from leader node =========")
        self.leader.remove_prefix(prefix1)
        self.prefix_add_remove()

        self.logger.info(f"========= Remove temporary prefix {prefix2} from leader node =========")
        self.leader.remove_prefix(prefix2)
        self.prefix_add_remove()

        self.logger.info(f"-------- Add off-mesh route based on temporary prefix {prefix1} on leader node --------")
        self.leader.add_route_using_prefix(prefix1, stable=False)
        # Wait till network data is updated and all nodes see all the added off-mesh routes.
        time.sleep(WAIT_TIME)
        num_routes += 1
        self.prefix_add_remove()
        verify(len(wpan_table_parser.parse_list(self.ed2.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))) == num_routes)

        self.logger.info(f"-------- Add off-mesh route based on stable prefix {prefix2} on leader node --------")
        self.leader.add_route_using_prefix(prefix2, stable=True)
        # Wait till network data is updated and all nodes see all the added off-mesh routes.
        time.sleep(WAIT_TIME)
        num_routes += 1
        self.prefix_add_remove()
        verify(len(wpan_table_parser.parse_list(self.ed2.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))) == num_routes)

        self.logger.info(f"========= Add stable prefix {prefix3} on leader node =========")
        self.leader.add_prefix(prefix3, stable=True)
        # Wait till network data is updated and all nodes see all the added off-mesh routes.
        self.prefix_add_remove()
        verify(len(wpan_table_parser.parse_list(self.ed2.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))) == num_routes)

        self.logger.info(f"-------- Remove off-mesh route based on stable prefix {prefix2} on leader node --------")
        self.leader.remove_route(prefix2)
        # Wait till network data is updated and all nodes see all the added off-mesh routes.
        time.sleep(WAIT_TIME)
        num_routes -= 1
        self.prefix_add_remove()
        verify(len(wpan_table_parser.parse_list(self.ed2.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))) == num_routes)

        self.logger.info(f"-------- Remove off-mesh route based on temporary prefix {prefix1} on leader node --------")
        self.leader.remove_route(prefix1)
        # Wait till network data is updated and all nodes see all the added off-mesh routes.
        time.sleep(WAIT_TIME)
        num_routes -= 1
        self.prefix_add_remove()
        verify(len(wpan_table_parser.parse_list(self.ed2.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))) == num_routes)


if __name__ == "__main__":
    unittest.main()
