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

import enum
import random
import time
import unittest

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.utils import process_cleanup
from silk.unit_tests.test_utils import random_string
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
        # allowlisting between leader and end device
        self.end_device.allowlist_node(self.router)
        self.router.allowlist_node(self.end_device)

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

        class AddressType(enum.Enum):
            LLA = 0
            MLA = 1

        addresses = [
            (self.router, self.end_device, AddressType.LLA, AddressType.LLA),
            (self.router, self.end_device, AddressType.LLA, AddressType.MLA),
            (self.router, self.end_device, AddressType.MLA, AddressType.MLA),
            (self.end_device, self.router, AddressType.LLA, AddressType.LLA),
            (self.end_device, self.router, AddressType.LLA, AddressType.MLA),
            (self.end_device, self.router, AddressType.MLA, AddressType.MLA)
        ]

        timeout = 5
        delay = 1
        for i, (src, dst, src_type, dst_type) in enumerate(addresses):
            port = random.randint(10000 + i * 100, 10099 + i * 100)
            message = random_string(10)

            src_address = f"{src.ip6_lla}%{src.netns}" if src_type == AddressType.LLA else None
            dst_address = dst.ip6_lla if dst_type == AddressType.LLA else dst.ip6_mla

            dst.receive_udp_data(port, message, timeout)
            time.sleep(delay)
            src.send_udp_data(dst_address, port, message, src_address)

            time.sleep(timeout - delay)


if __name__ == "__main__":
    unittest.main()
