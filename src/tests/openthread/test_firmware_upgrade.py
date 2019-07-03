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
import src.hw.hw_resource as hwr
import src.tests.testcase as testcase
from src.utils import process_cleanup
import time

FIRMWARE_FILE_CDC = '/opt/openthread_test/nrf52840_image/ot-ncp-ftd.hex'
FIRMWARE_FILE_CLI = '/opt/openthread_test/nrf52840_image/ot-cli-ftd.hex'

hwr.global_instance()


class TestFirmwareUpgrade(testcase.TestCase):

    @classmethod
    def hardwareSelect(cls):
        cls.device_list = []

        # Get all connected devices
        while True:
            try:
                device = ffdb.ThreadDevBoard()
            except Exception:
                break
            else:
                cls.device_list.append(device)
        print cls.device_list

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

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
    def test01_Firmware_upgrade(self):
        result_list = []
        for device in self.device_list:
            time.sleep(3)
            device.firmware_update(FIRMWARE_FILE_CDC)
            self.wait_for_completion(self.device_list)
            result_list.append((device.device.get_dut_serial(), device.flash_result))

        self.logger.info('Firmware upgrade results:')
        self.logger.info(result_list)

        overall_result = all(r for _, r in result_list)
        self.assertTrue(overall_result, 'Firmware upgrade failed on devices or all devices. Please check the log.')


