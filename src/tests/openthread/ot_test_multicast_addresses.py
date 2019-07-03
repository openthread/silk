# Copyright 2019 Google LLC
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

from src.config import wpan_constants as wpan
from src.tools.wpan_util import verify
from src.tools import wpan_table_parser

import src.node.fifteen_four_dev_board as ffdb
from src.node.wpan_node import WpanCredentials
import src.hw.hw_resource as hwr
import src.tests.testcase as testcase
from src.utils import process_cleanup

import random
import unittest

hwr.global_instance()

MCAST_ADDR = "ff02::114"


class TestMulticastAddresses(testcase.TestCase):
    poll_interval = 800

    @classmethod
    def hardwareSelect(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.fed= ffdb.ThreadDevBoard()
        cls.sed = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.fed, cls.sed]

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        for device in cls.all_nodes:

            device.set_logger(cls.logger)
            cls.add_test_device(device)

            device.set_up()

        cls.network_data = WpanCredentials(
            network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
            channel=random.randint(11, 25),
            fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

        cls.thread_sniffer_init(cls.network_data.channel)

    @classmethod
    @testcase.teardown_class_decorator
    def tearDownClass(cls):
        for d in cls.device_list:
            d.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def check_multicast_addresses(self, node, mcast_addr_list):
        addrs = wpan_table_parser.parse_list(node.get(wpan.WPAN_IP6_MULTICAST_ADDRESSES))

        for addr in mcast_addr_list:
            verify(addr in addrs)

    @testcase.test_method_decorator
    def test01_Pairing(self):
        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.fed.join(self.network_data, 'end-node')

        self.sed.join(self.network_data, "sleepy-end-device")

        self.sed.set_sleep_poll_interval(self.poll_interval)

        self.wait_for_completion(self.device_list)

        for device in self.device_list:
            print device.wpanctl("get", "status", 2)

    @testcase.test_method_decorator
    def test02_Verify_Multicast_Addresses(self):
        # Get the mesh-local prefix (remove the "/64" at the end of the string)
        ml_prefix = self.r1.get(wpan.WPAN_IP6_MESH_LOCAL_PREFIX)[1:-1].split('/')[0]

        # Derive the link-local/realm-local all thread nodes multicast addresses
        ll_all_thread_nodes_addr = 'ff32:40:' + ml_prefix + '1'
        rl_all_thread_nodes_addr = 'ff33:40:' + ml_prefix + '1'

        # List of multicast addresses subscribed by all nodes
        mcast_addrs = [
            "ff02::1",  # All nodes link-local
            "ff03::1",  # All nodes realm-local
            "ff03::fc",  # All MPL forwarder realm-local
            ll_all_thread_nodes_addr,
            rl_all_thread_nodes_addr
        ]

        # List of multicast addresses subscribed by routers only
        router_mcast_addrs = mcast_addrs + [
            "ff02::2",  # All routers link-local
            "ff03::2"  # All routers realm-local
        ]

        self.check_multicast_addresses(self.r1, router_mcast_addrs)
        self.check_multicast_addresses(self.fed, router_mcast_addrs)
        self.check_multicast_addresses(self.sed, mcast_addrs)

    @testcase.test_method_decorator
    def test03_Add_Mutilcast_Address(self):

        for node in self.device_list:
            node.add(wpan.WPAN_IP6_MULTICAST_ADDRESSES, MCAST_ADDR)
            addrs = wpan_table_parser.parse_list(node.get(wpan.WPAN_IP6_MULTICAST_ADDRESSES))
            verify(MCAST_ADDR in addrs)

            node.remove(wpan.WPAN_IP6_MULTICAST_ADDRESSES, MCAST_ADDR)
            addrs = wpan_table_parser.parse_list(node.get(wpan.WPAN_IP6_MULTICAST_ADDRESSES))
            verify(not MCAST_ADDR in addrs)


if __name__ == "__main__":
    unittest.main()
