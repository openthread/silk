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
"""Test traffic flow to off-mesh addresses resulted from addition of off-mesh routes (on routers and FEDs).
"""

import enum
import random
import time
import unittest

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.utils import process_cleanup
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify_within
from silk.unit_tests.test_utils import random_string
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

WAIT_TIME = 10
NUM_ROUTES = 3
NUM_ROUTES_LOCAL = 1
ON_MESH_PREFIX = "fd00:1234::"
OFF_MESH_ROUTE_1 = "fd00:abba::"
OFF_MESH_ROUTE_2 = "fd00:cafe::"
OFF_MESH_ROUTE_3 = "fd00:baba::"
OFF_MESH_ADDR_1 = OFF_MESH_ROUTE_1 + "1"
OFF_MESH_ADDR_2 = OFF_MESH_ROUTE_2 + "2"
OFF_MESH_ADDR_3 = OFF_MESH_ROUTE_3 + "3"
POLL_INTERVAL = 400


class TestOffMeshRouteTraffic(testcase.TestCase):
    # Test description: Adding off-mesh routes (on routers and FEDs) and traffic flow to off-mesh addresses.
    #
    # Test topology:
    #
    #     r1 ---- r2
    #     |       |
    #     |       |
    #    fed1    sed2
    #
    # The off-mesh-routes are added as follows:
    # - `r1`   adds `OFF_MESH_ROUTE_1`,
    # - `r2`   adds `OFF_MESH_ROUTE_2`,
    # - `fed1` adds `OFF_MESH_ROUTE_3`.
    #
    # Traffic flow:
    # - From `sed2` to an address matching `OFF_MESH_ROUTE_1` (verify it is received on `r1`),
    # - From `r1`   to an address matching `OFF_MESH_ROUTE_2` (verify it is received on `r2`),
    # - From `r2`   to an address matching `OFF_MESH_ROUTE_3` (verify it is received on `fed1`)
    #

    @classmethod
    def hardware_select(cls: 'TestOffMeshRouteTraffic'):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.fed1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.sed2 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.fed1, cls.r2, cls.sed2]

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls: 'TestOffMeshRouteTraffic'):
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
    def tearDownClass(cls: 'TestOffMeshRouteTraffic'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    @testcase.test_method_decorator
    def test01_disable_autoupdate_interface_address_on_ncp(self):
        for node in self.all_nodes:
            # Disable `AutoUpdateInterfaceAddrsOnNCP` feature on wpantund
            # for all nodes. This ensures that added IPv6 address (on linux
            # interface) are not pushed to NCP (and therefore are not
            # on-mesh).
            node.setprop("Daemon:IPv6:AutoUpdateInterfaceAddrsOnNCP", "false")
            self.assertEqual(node.getprop("Daemon:IPv6:AutoUpdateInterfaceAddrsOnNCP"), "false")

    @testcase.test_method_decorator
    def test02_pairing(self):
        # allowlisting between leader and router
        self.r1.allowlist_node(self.r2)
        self.r2.allowlist_node(self.r1)

        # allowlisting between leader and end device
        self.r1.allowlist_node(self.fed1)
        self.fed1.allowlist_node(self.r1)

        # allowlisting between router and sleepy-end-device
        self.r2.allowlist_node(self.sed2)
        self.sed2.allowlist_node(self.r2)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(60)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.fed1.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        self.sed2.join(self.network_data, "sleepy-end-device")
        self.sed2.set_sleep_poll_interval(POLL_INTERVAL)
        self.wait_for_completion(self.device_list)

        self.assertTrue(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)

    @testcase.test_method_decorator
    def test03_verify_off_mesh_routes(self):
        # Add on-mesh prefix
        self.r1.config_gateway(ON_MESH_PREFIX)

        # The off-mesh-routes are added as follows:
        # - `r1` adds OFF_MESH_ROUTE_1,
        # - `r2` adds OFF_MESH_ROUTE_2,
        # - `fed1` adds OFF_MESH_ROUTE_3.

        self.r1.add_route_using_prefix(OFF_MESH_ROUTE_1)
        self.r1.add_ip6_address_on_interface(OFF_MESH_ADDR_1, prefix_len=64)
        self.wait_for_completion(self.device_list)

        self.r2.add_route_using_prefix(OFF_MESH_ROUTE_2)
        self.r2.add_ip6_address_on_interface(OFF_MESH_ADDR_2, prefix_len=64)
        self.wait_for_completion(self.device_list)

        self.fed1.add_route_using_prefix(OFF_MESH_ROUTE_3)
        self.fed1.add_ip6_address_on_interface(OFF_MESH_ADDR_3, prefix_len=64)
        self.wait_for_completion(self.device_list)

        # Wait till network data is updated on r1, r2, and sed2 and they all see all
        # the added off-mesh routes.
        time.sleep(WAIT_TIME)

        def check_off_mesh_routes():
            # If a node itself adds a route, the route entry will be seen twice in
            # its WPAN_THREAD_OFF_MESH_ROUTES list (one time as part of network-wide
            # network data and again as part of the local network data). Note that
            # `r1 and `r2` each add a route, while `sed2` does not.
            r1_routes = wpan_table_parser.parse_list(self.r1.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))
            self.assertEqual(len(r1_routes), NUM_ROUTES + NUM_ROUTES_LOCAL)

            r2_routes = wpan_table_parser.parse_list(self.r2.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))
            self.assertEqual(len(r2_routes), NUM_ROUTES + NUM_ROUTES_LOCAL)

            sed2_routes = wpan_table_parser.parse_list(self.sed2.get(wpan.WPAN_THREAD_OFF_MESH_ROUTES))
            self.assertEqual(len(sed2_routes), NUM_ROUTES)

        verify_within(check_off_mesh_routes, WAIT_TIME)

    @testcase.test_method_decorator
    def test04_transmit_receive(self):
        # Traffic from `sed2` to `OFF_MESH_ADDR_1` (verify that it is received on`r1`).
        # Traffic from `r1` to `OFF_MESH_ADDR_2` (verify that it is received on `r2`),
        # Traffic from `r2` to `OFF_MESH_ADDR_3` (verify that it is received on `fed1`)
        class AddressType(enum.Enum):
            Prefix = 0

        addresses = [
            (self.sed2, self.r1, AddressType.Prefix, OFF_MESH_ADDR_1),
            (self.r1, self.r2, AddressType.Prefix, OFF_MESH_ADDR_2),
            (self.r2, self.fed1, AddressType.Prefix, OFF_MESH_ADDR_3),
        ]

        timeout = 5
        delay = 1
        for i, (src, dst, src_type, dst_address) in enumerate(addresses):
            port = random.randint(10000 + i * 100, 10099 + i * 100)
            message = random_string(10)
            src_address = ""
            if src_type == AddressType.Prefix:
                src_address = src.find_ip6_address_with_prefix(ON_MESH_PREFIX)
                self.wait_for_completion(self.device_list)

            dst.receive_udp_data(port, message, timeout)
            time.sleep(delay)
            src.send_udp_data(dst_address, port, message, src_address)

            time.sleep(timeout - delay)


if __name__ == "__main__":
    unittest.main()
