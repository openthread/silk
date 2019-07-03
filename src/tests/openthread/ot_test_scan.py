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
from src.tools import wpan_table_parser
from src.config import wpan_constants as wpan
from src.utils import process_cleanup

import random
import unittest
import time

hwr.global_instance()

SCAN_ITERATION = 3


class TestScan(testcase.TestCase):
    poll_interval = 1000

    @classmethod
    def hardwareSelect(cls):
        cls.scanner = ffdb.ThreadDevBoard()

        cls.leader_list = []

        while True:
            try:
                device = ffdb.ThreadDevBoard()
            except Exception:
                break
            else:
                cls.leader_list.append(device)
        print cls.leader_list

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.add_test_device(cls.scanner)

        for leader_node in cls.leader_list:
            cls.add_test_device(leader_node)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        total_networks = len(cls.device_list)

        cls.network_data_list = []
        for i in range(total_networks):
            cls.network_data_list.append(WpanCredentials(
                network_name = "SILK-{0:04X}".format(random.randint(0, 0xffff)),
                psk = "00112233445566778899aabbccdd{0:04x}".
                    format(random.randint(0, 0xffff)),
                channel = random.randint(11, 25),
                fabric_id = "{0:06x}dead".format(random.randint(0, 0xffffff))))

        cls.thread_sniffer_init(cls.network_data_list[0].channel)

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
        for i, device in enumerate(self.device_list):
            if i == 0:
                continue
            device.form(self.network_data_list[i], 'router')
            self.wait_for_completion(self.device_list)

        for device in self.device_list:
            ret = device.wpanctl("get", "status", 2)
            print ret

    @testcase.test_method_decorator
    def test02_Scan(self):
        # Perform active scan and check that all nodes are seen in the scan result.
        scan_result = []
        for _ in range(SCAN_ITERATION):
            scan_result.append(wpan_table_parser.parse_scan_result(self.scanner.get_active_scan()))
            time.sleep(5)

        print scan_result

        for device in self.device_list[1:]:
            self.assertTrue(wpan_table_parser.is_in_scan_result(device, scan_result),
                            'Device: {} is not seen in the scan result'.format(device.get(wpan.WPAN_NAME)[1:-1]))

    @testcase.test_method_decorator
    def test03_PermitJoin_Scan(self):
        # Make every other network joinable, scan and check the result.
        make_joinable = False
        for device in self.device_list[1:]:
            make_joinable = not make_joinable
            if make_joinable:
                device.permit_join(3600)
                self.wait_for_completion(self.device_list)

        scan_result = []
        for _ in range(SCAN_ITERATION):
            scan_result.append(wpan_table_parser.parse_scan_result(self.scanner.get_active_scan()))
            time.sleep(5)

        print scan_result

        for device in self.device_list[1:]:
            self.assertTrue(wpan_table_parser.is_in_scan_result(device, scan_result),
                            'Device: {} is not seen in the scan result'.format(device.get(wpan.WPAN_NAME)[1:-1]))

    @testcase.test_method_decorator
    def test04_Scan_from_Associated(self):
        # Scan from an already associated node.
        scan_result = []
        for _ in range(SCAN_ITERATION):
            scan_result.append(wpan_table_parser.parse_scan_result(self.device_list[1].get_active_scan()))
            time.sleep(5)

        print scan_result

        for device in self.device_list[2:]:
            self.assertTrue(wpan_table_parser.is_in_scan_result(device, scan_result),
                            'Device: {} is not seen in the scan result'.format(device.get(wpan.WPAN_NAME)[1:-1]))

        # Scan on a specific channel
        channel = self.device_list[1].get(wpan.WPAN_CHANNEL)

        scan_result = []
        for _ in range(SCAN_ITERATION):
            scan_result.append(wpan_table_parser.parse_scan_result(self.scanner.get_active_scan(channel=channel)))
            time.sleep(5)

        print scan_result

        device = self.device_list[1]
        self.assertTrue(wpan_table_parser.is_in_scan_result(device, scan_result),
                        'Device: {} is not seen in the scan result'.format(device.get(wpan.WPAN_NAME)[1:-1]))

    @testcase.test_method_decorator
    def test05_Discovery_Scan(self):
        scan_result = []

        for _ in range(SCAN_ITERATION):
            scan_result.append(wpan_table_parser.parse_scan_result(self.scanner.get_discover_scan()))
            time.sleep(5)

        print scan_result

        for device in self.device_list[1:]:
            self.assertTrue(wpan_table_parser.is_in_scan_result(device, scan_result),
                            'Device: {} is not seen in the scan result'.format(device.get(wpan.WPAN_NAME)[1:-1]))

    @testcase.test_method_decorator
    def test06_Discover_Scan_from_Associated(self):
        # Scan from an already associated node.
        scan_result = []
        for _ in range(SCAN_ITERATION):
            scan_result.append(wpan_table_parser.parse_scan_result(self.device_list[1].get_discover_scan()))
            time.sleep(5)

        print scan_result

        for device in self.device_list[2:]:
            self.assertTrue(wpan_table_parser.is_in_scan_result(device, scan_result),
                            'Device: {} is not seen in the scan result'.format(device.get(wpan.WPAN_NAME)[1:-1]))

        # Scan on a specific channel

        channel = self.device_list[1].get(wpan.WPAN_CHANNEL)
        scan_result = []
        for _ in range(SCAN_ITERATION):
            scan_result.append(wpan_table_parser.parse_scan_result(self.scanner.get_discover_scan(channel=channel)))
            time.sleep(5)

        print scan_result

        device = self.device_list[1]
        self.assertTrue(wpan_table_parser.is_in_scan_result(device, scan_result),
                        'Device: {} is not seen in the scan result'.format(device.get(wpan.WPAN_NAME)[1:-1]))

    #TODO add tc for energy scan, discover scan for joiner with xpanid as filter


if __name__ == "__main__":
    unittest.main()
