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
    Tests when the data poll interval is set to a value larger than child's timeout interval.
    In such case sleepy child would send a data poll within its timeout interval (ensuring that child stays in parent's
    child table).
"""
import random
import time
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools.wpan_util import verify
from silk.utils import process_cleanup

hwr.global_instance()

CHILD_TIMEOUT = 5  # in seconds


class TestChildTimeoutLargeDataPoll(testcase.TestCase):
    """
    Test description:

    This test covers the situation where the data poll interval is set to a value larger than child's timeout interval.
    The test verifies that the sleepy child would send a data poll within its timeout interval (ensuring that child
    stays in parent's child table).
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
    def test02_set_childtimeout_and_data_poll_on_child(self):
        # Set short child timeout interval
        self.child.set(wpan.WPAN_THREAD_CHILD_TIMEOUT, str(CHILD_TIMEOUT))

        # Set large data poll interval on child
        self.child.set_sleep_poll_interval(str(5 * CHILD_TIMEOUT * 1000))

        # Now join the child as sleepy-end-device to the thread network
        self.child.join(self.network_data, "sleepy-end-device")
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test03_verify_child_sends_data_poll(self):
        # Ensure data poll is sent by the child within Child Timeout.
        poll_count_before = int(self.child.get(wpan.WPAN_NCP_COUNTER_TX_PKT_DATA_POLL), 0)
        time.sleep(CHILD_TIMEOUT * 1.1)
        poll_count_after = int(self.child.get(wpan.WPAN_NCP_COUNTER_TX_PKT_DATA_POLL), 0)

        verify(poll_count_after > poll_count_before)


if __name__ == "__main__":
    unittest.main()
