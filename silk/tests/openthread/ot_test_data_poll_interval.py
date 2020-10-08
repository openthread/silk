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

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools.wpan_util import verify
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

WAIT_TIME1 = 0.36  # in seconds
WAIT_TIME2 = 0.2  # in seconds


class TestDataPollInterval(testcase.TestCase):
    # Test description: Verify transmission of data polls and poll interval
    # change.
    #
    # Network Topology:
    #
    #    router
    #      |
    #      |
    #     sed
    #
    # Test covers the following situations:
    #
    # - Verify the default poll interval is proper i.e it should be smaller than
    #   child_timeout
    # - Verify number of data polls with different poll intervals
    # - Verify behavior when poll interval is switched from long to short.
    # - Verify setting poll interval zero should use default poll interval
    #   (depending on child timeout)
    # - Verify change in "child timeout" results in change in default poll
    #   interval

    child_timeout = None
    default_poll_interval = None

    @classmethod
    def hardware_select(cls):
        cls.router = ffdb.ThreadDevBoard()
        cls.sed = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.router.set_logger(cls.logger)
        cls.sed.set_logger(cls.logger)

        cls.add_test_device(cls.router)
        cls.add_test_device(cls.sed)

        cls.router.set_up()
        cls.sed.set_up()

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
    def test01_pairing(self):
        self.router.form(self.network_data, "router")
        self.router.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.router.ip6_lla)
        self.logger.info(self.router.ip6_thread_ula)

        self.network_data.xpanid = self.router.xpanid
        self.network_data.panid = self.router.panid

        self.sed.join(self.network_data, "sleepy-end-device")
        self.wait_for_completion(self.device_list)

        self.assertTrue(self.router.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        self.assertTrue(self.sed.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_SLEEPY_END_DEVICE)

    @testcase.test_method_decorator
    def test02_verify_default_poll_interval(self):
        # Verify the default poll interval is smaller than child_timeout
        TestDataPollInterval.child_timeout = int(self.sed.get(wpan.WPAN_THREAD_CHILD_TIMEOUT), 0) * 1000
        TestDataPollInterval.default_poll_interval = int(self.sed.get(wpan.WPAN_POLL_INTERVAL), 0)

        self.logger.info("verify condition: 0 < default_poll_interval <= child_timeout"
                         " i.e. 0 < {} <= {}".format(self.default_poll_interval, self.child_timeout))
        verify(0 < self.default_poll_interval <= self.child_timeout)

    @testcase.test_method_decorator
    def test03_verify_data_poll_with_different_poll_interval(self):
        # Check number of data polls with different poll intervals
        for poll_interval in [100, 200, 500, 50]:  # in milliseconds
            poll_count_before = int(self.sed.get(wpan.WPAN_NCP_COUNTER_TX_PKT_DATA_POLL), 0)

            self.sed.set(wpan.WPAN_POLL_INTERVAL, str(poll_interval))
            verify(int(self.sed.get(wpan.WPAN_POLL_INTERVAL), 0) == poll_interval)

            time.sleep(WAIT_TIME1)
            poll_count_after = int(self.sed.get(wpan.WPAN_NCP_COUNTER_TX_PKT_DATA_POLL), 0)
            actual_polls = poll_count_after - poll_count_before
            expected_polls = int(WAIT_TIME1 * 1000 / poll_interval)
            self.logger.info("poll interval {} ms, polls -> actual {}, expected {}".format(
                poll_interval, actual_polls, expected_polls))
            self.logger.info("verify condition: actual_polls >= expected_polls"
                             " i.e. {} >= {}".format(actual_polls, expected_polls))
            verify(actual_polls >= expected_polls)

    @testcase.test_method_decorator
    def test04_verify_data_poll_with_long_to_short_poll_interval(self):
        # Verify behavior when poll interval is switched from long to short.
        #
        #  - Poll interval set to 5 seconds
        #  - Wait for 200 ms
        #  - Change poll interval to 200 ms
        #  - This should immediately trigger a poll tx since 100 ms is
        #    already passed since last poll transmission.

        self.sed.set(wpan.WPAN_POLL_INTERVAL, "5000")
        time.sleep(WAIT_TIME2)
        poll_count_before = int(self.sed.get(wpan.WPAN_NCP_COUNTER_TX_PKT_DATA_POLL), 0)
        self.sed.set(wpan.WPAN_POLL_INTERVAL, str(WAIT_TIME2 * 1000))
        time.sleep(0.01)
        poll_count_after = int(self.sed.get(wpan.WPAN_NCP_COUNTER_TX_PKT_DATA_POLL), 0)
        self.logger.info("verify condition: poll count with poll interval 200ms > poll count with poll interval 5s"
                         " i.e. {} > {}".format(poll_count_after, poll_count_before))
        verify(poll_count_after > poll_count_before)

    @testcase.test_method_decorator
    def test05_verify_data_poll_with_poll_interval_zero(self):
        # Verify behavior when poll interval is set to zero.
        self.sed.set(wpan.WPAN_POLL_INTERVAL, "0")

        # Poll interval should use default interval again (based on child timeout).
        self.logger.info("verify condition: setting poll interval 0ms should use default poll interval"
                         " again (based on child timeout) i.e. {} == {}".format(
                             int(self.sed.get(wpan.WPAN_POLL_INTERVAL), 0), self.default_poll_interval))
        verify(int(self.sed.get(wpan.WPAN_POLL_INTERVAL), 0) == self.default_poll_interval)

    @testcase.test_method_decorator
    def test06_verify_data_poll_with_changed_child_timeout(self):
        # Change "child timeout" and verify that default interval also changes
        self.sed.set(wpan.WPAN_THREAD_CHILD_TIMEOUT, str(self.child_timeout / 1000 * 2))
        new_default_interval = int(self.sed.get(wpan.WPAN_POLL_INTERVAL), 0)

        self.logger.info("verify condition: default_poll_interval < new_default_poll_interval "
                         "(created by double child timeout) <= child_timeout * 2"
                         " i.e. {} < {} <= {}".format(self.default_poll_interval, new_default_interval,
                                                      self.child_timeout * 2))
        verify(self.default_poll_interval < new_default_interval <= self.child_timeout * 2)

        # reset the child timeout to default value
        self.sed.set(wpan.WPAN_THREAD_CHILD_TIMEOUT, str(self.child_timeout / 1000))
        verify(int(self.sed.get(wpan.WPAN_POLL_INTERVAL), 0) == self.default_poll_interval)


if __name__ == "__main__":
    unittest.main()
