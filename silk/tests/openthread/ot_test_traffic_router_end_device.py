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
"""Test traffic between router and end-device (link-local and mesh-local IPv6 addresses).
"""

import random
import unittest

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()


class TestTrafficRouterEndDevice(testcase.TestCase):
    """Test traffic between a router and an end device in a two node network.
    """

    @classmethod
    def hardware_select(cls: 'TestTrafficRouterEndDevice'):
        cls.router = ffdb.ThreadDevBoard()
        cls.end_device = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls: 'TestTrafficRouterEndDevice'):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.add_test_device(cls.router)
        cls.add_test_device(cls.end_device)

        for device in cls.device_list:
            device.set_logger(cls.logger)
            device.set_up()

        cls.network_data = WpanCredentials(network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
                                           psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
                                           channel=random.randint(11, 25),
                                           fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

        cls.thread_sniffer_init(cls.network_data.channel)

    @classmethod
    @testcase.teardown_class_decorator
    def tearDownClass(cls: 'TestTrafficRouterEndDevice'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    @testcase.test_method_decorator
    def test01_Pairing(self):
        # whitelisting between leader and end device
        self.end_device.whitelist_node(self.router)
        self.router.whitelist_node(self.end_device)

        self.router.form(self.network_data, "router")
        self.router.permit_join(60)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.router.ip6_lla)
        self.logger.info(self.router.ip6_thread_ula)

        self.network_data.xpanid = self.router.xpanid
        self.network_data.panid = self.router.panid

        self.end_device.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_NCP_State(self):
        self.assertEqual(self.router.getprop(wpan.WPAN_STATE), wpan.STATE_ASSOCIATED)
        self.assertEqual(self.router.getprop(wpan.WPAN_NAME), self.end_device.getprop(wpan.WPAN_NAME))
        self.assertEqual(self.router.xpanid, self.end_device.xpanid)
        self.assertEqual(self.router.panid, self.end_device.panid)

    @testcase.test_method_decorator
    def test03_Transmit_Receive(self):
        port = random.randint(10020, 12000)
        message = "Hi there"
        for dst in [self.end_device.ip6_lla, self.end_device.ip6_mla]:
            self.end_device.receive_udp_data(port, message)
            self.router.send_udp_data(dst, port, message)

        for dst in [self.router.ip6_lla, self.router.ip6_mla]:
            self.router.receive_udp_data(port, message)
            self.end_device.send_udp_data(dst, port, message)


if __name__ == "__main__":
    unittest.main()
