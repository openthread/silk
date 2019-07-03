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

import src.node.fifteen_four_dev_board as ffdb
from src.node.wpan_node import WpanCredentials
import src.hw.hw_resource as hwr
import src.tests.testcase as testcase
from src.config import wpan_constants as wpan
from src.utils import process_cleanup

import random
import unittest
import time

hwr.global_instance()


class TestPermitJoin(testcase.TestCase):

    @classmethod
    def hardwareSelect(cls):
        cls.router = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.add_test_device(cls.router)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        cls.network_data = WpanCredentials(
            network_name = "SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
            channel=random.randint(11, 25),
            fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

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

    @testcase.test_method_decorator
    def test01_Form_Network(self):
        self.router.form(self.network_data, 'router')
        self.wait_for_completion(self.device_list)

        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), 'false')

    @testcase.test_method_decorator
    def test02_Permit_Join_enable(self):
        self.router.permit_join_new()
        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), 'true')

        self.router.permit_join_new('0')
        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), 'false')

        self.router.permit_join_new(port='1234')
        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), 'true')

        self.router.permit_join_new('0')
        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), 'false')

    @testcase.test_method_decorator
    def test03_Permit_Join_time(self):
        self.router.permit_join_new('10')
        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), 'true')

        time.sleep(11)

        self.assertEqual(self.router.getprop(wpan.WPAN_NETWORK_ALLOW_JOIN), 'false')


if __name__ == "__main__":
    unittest.main()
