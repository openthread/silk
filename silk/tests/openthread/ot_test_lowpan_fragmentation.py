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
from silk.node.wpan_node import WpanCredentials
from silk.unit_tests.test_utils import random_string
from silk.utils import process_cleanup

hwr.global_instance()

MSG_LEN_START = 100
MSG_LEN_END = 500


class TestLowpanFragmentation(testcase.TestCase):
    """
    Test description: This test verifies 6LoWPAN fragmentation code by exchanging IPv6 messages with
    many different lengths between two nodes.
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

        self.child.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_verify_lowpan_fragmentation(self):
        # Send and receive many different lengths IPv6 messages to ensure 6LoWPAN fragmentation is proper.

        port = random.randint(10000, 10099)
        timeout = 5
        delay = 1

        for msg_length in range(MSG_LEN_START, MSG_LEN_END):
            message = random_string(msg_length)

            src_address = f"{self.parent.ip6_lla}%{self.parent.netns}"
            dst_address = self.child.ip6_lla

            self.child.receive_udp_data(port, message, timeout)
            time.sleep(delay)
            self.parent.send_udp_data(dst_address, port, message, src_address)

            time.sleep(timeout - delay)


if __name__ == "__main__":
    unittest.main()
