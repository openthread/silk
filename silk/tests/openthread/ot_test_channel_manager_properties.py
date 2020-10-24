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
from silk.utils import process_cleanup

hwr.global_instance()

WAIT_TIME = 20
ALL_CHANNELS_MASK = int('0x7fff800', 0)
CHAN_11_MASK = int('0x800', 0)
CHAN_11_TO_13_MASK = int('0x3800', 0)

all_gettable_props = [
    wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL,
    wpan.WPAN_CHANNEL_MANAGER_DELAY,
    wpan.WPAN_CHANNEL_MANAGER_CHANNEL_SELECT,
    wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_INTERVAL,
    wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED,
    wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK,
    wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK,
]


class TestChannelManagerProperties(testcase.TestCase):
    # Test description: This test verifies wpantund properties related to `ChannelManager` feature

    @classmethod
    def hardware_select(cls):
        cls.router = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.add_test_device(cls.router)

        for device in cls.device_list:
            device.set_logger(cls.logger)
            device.set_up()

        cls.network_data = WpanCredentials(network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
                                           psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
                                           channel=random.randint(11, 13),
                                           fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

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
        self.router.form(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), "false")

    @testcase.test_method_decorator
    def test02_verify_default_properties(self):
        # Check default property values

        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL), 0), 0)
        self.assertEqual(self.router.get(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED), 'false')
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK), 0), 0)
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK), 0), 0)

    @testcase.test_method_decorator
    def test03_verify_set_get(self):
        # Set different wpan Channel Manager properties and get and check the output

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_DELAY, '180')
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_DELAY), 0), 180)

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED, '1')
        self.assertEqual(self.router.get(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED), 'true')

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED, '0')
        self.assertEqual(self.router.get(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED), 'false')

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_INTERVAL, '1000')
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_INTERVAL), 0), 1000)

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK, str(ALL_CHANNELS_MASK))
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK), 0), ALL_CHANNELS_MASK)

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK, str(CHAN_11_MASK))
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK), 0), CHAN_11_MASK)

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK, str(CHAN_11_TO_13_MASK))
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK), 0), CHAN_11_TO_13_MASK)

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK, str(ALL_CHANNELS_MASK))
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK), 0), ALL_CHANNELS_MASK)

        self.router.set(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED, '1')
        self.assertEqual(self.router.get(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED), 'true')

    @testcase.test_method_decorator
    def test04_verify_properties_retained_after_reset(self):
        # Check to ensure the property values are retained after an NCP reset
        self.router.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        start_time = time.time()

        while self.router.get(wpan.WPAN_STATE) != wpan.STATE_ASSOCIATED:
            if time.time() - start_time > WAIT_TIME:
                print('Took too long to restore after reset ({}>{} sec)'.format(time.time() - start_time, WAIT_TIME))
                exit(1)
            time.sleep(2)

        self.assertEqual(self.router.get(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED), 'true')
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK), 0), ALL_CHANNELS_MASK)
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK), 0), CHAN_11_TO_13_MASK)
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_INTERVAL), 0), 1000)
        self.assertEqual(int(self.router.get(wpan.WPAN_CHANNEL_MANAGER_DELAY), 0), 180)


if __name__ == "__main__":
    unittest.main()
