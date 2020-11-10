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
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools.wpan_util import verify_channel, verify, verify_within, is_associated
from silk.utils import process_cleanup

hwr.global_instance()
POLL_INTERVAL = 500
WAIT_TIME = 20


class TestChannelManagerAnnounceRecovery(testcase.TestCase):
    # Test description: Orphaned node attach through MLE Announcement

    @classmethod
    def hardware_select(cls):
        cls.router = ffdb.ThreadDevBoard()
        cls.sc1 = ffdb.ThreadDevBoard()
        cls.sc2 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.router, cls.sc1, cls.sc2]

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

    @testcase.test_method_decorator
    def test01_pairing(self):
        # allowlisting between leader and other nodes
        for node in [self.sc1, self.sc2]:
            self.router.allowlist_node(node)
            node.allowlist_node(self.router)

        self.router.form(self.network_data, "router")
        self.router.permit_join(60 * len(self.device_list))
        self.wait_for_completion(self.device_list)

        self.logger.info(self.router.ip6_lla)
        self.logger.info(self.router.ip6_thread_ula)

        self.network_data.xpanid = self.router.xpanid
        self.network_data.panid = self.router.panid

        for end_node in [self.sc1, self.sc2]:
            end_node.join(self.network_data, "sleepy-end-device")
            end_node.set_sleep_poll_interval(POLL_INTERVAL)
            self.wait_for_completion([end_node])

        self.sc1.set(wpan.WPAN_THREAD_DEVICE_MODE, '5')
        self.sc2.set(wpan.WPAN_THREAD_DEVICE_MODE, '5')

    @testcase.test_method_decorator
    def test02_switch_channel_after_detaching_sc2(self):
        # Reset sc2 and keep it in detached state
        self.sc2.set('Daemon:AutoAssociateAfterReset', 'false')
        self.sc2.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        # Switch the rest of network to channel 26
        self.router.set(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL, '26')
        verify_channel([self.router, self.sc1], 26)

    @testcase.test_method_decorator
    def test03_verify_reenabled_sc2_attaches_via_mle_announcement(self):
        # Now re-enable sc2 and verify that it does attach to router and is on channel 26
        # sc2 would go through the ML Announce recovery.
        channel = self.network_data.channel
        self.sc2.set('Daemon:AutoAssociateAfterReset', 'true')
        self.sc2.reset_thread_radio()
        self.wait_for_completion(self.device_list)
        verify(int(self.sc2.get(wpan.WPAN_CHANNEL), 0) == channel)

        # Wait for 20s for sc2 to be attached/associated
        def check_c2_is_associated():
            verify(is_associated(self.sc2))

        verify_within(check_c2_is_associated, WAIT_TIME)

        # Check that sc2 is now on channel 26.
        verify(int(self.sc2.get(wpan.WPAN_CHANNEL), 0) == 26)


if __name__ == "__main__":
    unittest.main()
