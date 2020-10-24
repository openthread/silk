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
from silk.tools.wpan_util import verify_channel, verify
from silk.utils import process_cleanup

hwr.global_instance()
POLL_INTERVAL = 500


class TestChannelManagerChannelChange(testcase.TestCase):
    # Test description: verifies `ChannelManager` channel change process

    @classmethod
    def hardware_select(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.r3 = ffdb.ThreadDevBoard()
        cls.sc1 = ffdb.ThreadDevBoard()
        cls.ec1 = ffdb.ThreadDevBoard()
        cls.sc2 = ffdb.ThreadDevBoard()
        cls.sc3 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.r3, cls.sc1, cls.ec1, cls.sc2, cls.sc3]

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

        # Set OpenThread log level on all nodes to zero.
        for node in cls.all_nodes:
            node.set(wpan.WPAN_OT_LOG_LEVEL, '0')

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
        # Allowlisting between network nodes
        for node1, node2 in [(self.r1, self.r2), (self.r1, self.r3), (self.r1, self.sc1),
                             (self.r1, self.ec1), (self.r2, self.sc2), (self.r3, self.sc3)]:
            node1.allowlist_node(node2)
            node2.allowlist_node(node1)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(60 * len(self.device_list))
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        for end_node in [self.r2, self.r3]:
            end_node.join(self.network_data, "router")
            self.wait_for_completion([end_node])

        for end_node in [self.sc1, self.sc2, self.sc3]:
            end_node.join(self.network_data, "sleepy-end-device")
            end_node.set_sleep_poll_interval(POLL_INTERVAL)
            self.wait_for_completion([end_node])

        self.ec1.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_verify_channel_manager_delay(self):
        # The channel manager delay is set from "openthread-core-toranj-config.h".
        # Verify that it is 2 seconds.

        verify(int(self.r1.get(wpan.WPAN_CHANNEL_MANAGER_DELAY), 0) == 2)

    @testcase.test_method_decorator
    def test03_verify_channel_change(self):
        channel = self.network_data.channel
        verify(int(self.r1.get(wpan.WPAN_CHANNEL), 0) == channel)
        verify_channel(self.all_nodes, channel)

        # Request a channel change to channel 13 from router r1

        self.r1.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '13')
        verify(int(self.r1.get(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL), 0) == 13)
        verify_channel(self.all_nodes, 13)

    @testcase.test_method_decorator
    def test04_verify_same_channel_change_on_multiple_devices(self):
        # Request same channel change on multiple routers at the same time

        self.r1.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '14')
        self.r2.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '14')
        self.r3.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '14')
        verify_channel(self.all_nodes, 14)

    @testcase.test_method_decorator
    def test05_verify_different_channel_changes_from_r1(self):
        # Request different channel changes from same router (router r1).

        self.r1.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '15')
        verify_channel(self.all_nodes, 14)
        self.r1.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '16')
        verify_channel(self.all_nodes, 16)

    @testcase.test_method_decorator
    def test06_verify_different_channel_changes_from_r1_and_r2(self):
        # Request different channels from two routers (r1 and r2)

        self.r1.set(wpan.WPAN_CHANNEL_MANAGER_DELAY, '20')  # increase the time to ensure r1 change is in process
        self.r1.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '17')
        time.sleep(10.5)
        verify_channel(self.all_nodes, 16)
        self.r2.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '18')
        verify_channel(self.all_nodes, 18)


if __name__ == "__main__":
    unittest.main()
