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
"""
Test when a single parent exists in network with poor link quality the child can attach the parent.
"""

import random
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.utils import process_cleanup

hwr.global_instance()


class TestPoorLinkParentChildAttach(testcase.TestCase):
    """
    This test covers a situation where a single parent exists in network with poor link quality ensuring the child
    can attach the parent.
    """

    @classmethod
    def hardware_select(cls):
        cls.parent = ffdb.ThreadDevBoard()
        cls.child = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.parent.set_logger(cls.logger)
        cls.child.set_logger(cls.logger)

        cls.add_test_device(cls.parent)
        cls.add_test_device(cls.child)

        cls.parent.set_up()
        cls.child.set_up()

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

    @testcase.test_method_decorator
    def test01_form_network(self):
        self.parent.form(self.network_data, "router")
        self.parent.permit_join(60)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.parent.ip6_lla)
        self.logger.info(self.parent.ip6_thread_ula)

        self.network_data.xpanid = self.parent.xpanid
        self.network_data.panid = self.parent.panid

    @testcase.test_method_decorator
    def test02_verify_child_joins_on_poor_link(self):
        # Create a poor link between child and parent using MAC fixed RSSI filter

        self.parent.set(wpan.WPAN_MAC_FILTER_FIXED_RSSI, '-99')
        self.parent.add(wpan.WPAN_MAC_FILTER_ENTRIES, self.child.get(wpan.WPAN_EXT_ADDRESS)[1:-1])

        self.child.set(wpan.WPAN_MAC_FILTER_FIXED_RSSI, '-99')
        self.child.add(wpan.WPAN_MAC_FILTER_ENTRIES, self.parent.get(wpan.WPAN_EXT_ADDRESS)[1:-1])

        for node in [self.parent, self.child]:
            self.assertEqual(node.get(wpan.WPAN_MAC_FILTER_FIXED_RSSI), "-99")

        # Ensure child can still attach the single low-link quality parent
        self.child.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)


if __name__ == "__main__":
    unittest.main()

