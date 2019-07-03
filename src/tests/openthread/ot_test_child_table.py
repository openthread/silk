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

from src.config import wpan_constants as wpan
import src.node.fifteen_four_dev_board as ffdb
from src.node.wpan_node import WpanCredentials
from src.tools import wpan_table_parser
import src.hw.hw_resource as hwr
import src.tests.testcase as testcase
from src.utils import process_cleanup

import random
import unittest

hwr.global_instance()

CHILD_TABLE_AS_VALMAP_ENTRY = ("Age", "AverageRssi", "ExtAddress", "FullFunction", "FullNetworkData",
                               "LastRssi", "LinkQualityIn", "NetworkDataVersion", "RLOC16", "RxOnWhenIdle",
                               "SecureDataRequest", "Timeout",)


class TestChildTable(testcase.TestCase):

    @classmethod
    def hardwareSelect(cls):
        cls.router = ffdb.ThreadDevBoard()
        cls.joiner_list = []

        while True:
            try:
                device = ffdb.ThreadDevBoard()
            except Exception:
                break
            else:
                cls.joiner_list.append(device)
        print cls.joiner_list

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.add_test_device(cls.router)

        for end_node in cls.joiner_list:
            cls.add_test_device(end_node)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        cls.network_data = WpanCredentials(
            network_name = "SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk = "00112233445566778899aabbccdd{0:04x}".
                format(random.randint(0, 0xffff)),
            channel = random.randint(11, 25),
            fabric_id = "{0:06x}dead".format(random.randint(0, 0xffffff)))

        cls.thread_sniffer_init(cls.network_data.channel)

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
    def test01_Pairing(self):
        self.router.form(self.network_data, 'router')
        self.router.permit_join(60*len(self.joiner_list))
        self.wait_for_completion(self.device_list)

        self.logger.info(self.router.ip6_lla)
        self.logger.info(self.router.ip6_thread_ula)

        self.network_data.xpanid = self.router.xpanid
        self.network_data.panid = self.router.panid

        for end_node in self.joiner_list[:-1]:
            end_node.join(self.network_data, "sleepy-end-device")
            end_node.set_sleep_poll_interval(100)
            self.wait_for_completion([end_node])
            self.wait_for_completion(self.device_list)

        #The last one will join in as end-device
        self.joiner_list[-1].join(self.network_data, "end-node")
        self.joiner_list[-1].set_sleep_poll_interval(100)
        self.wait_for_completion(self.device_list)

        for end_node in self.joiner_list:
            self.logger.info(end_node.ip6_lla)
            self.logger.info(end_node.ip6_thread_ula)

        ret = self.router.wpanctl("get", "status", 2)
        print ret

        for end_node in self.joiner_list:
            ret = end_node.wpanctl("get", "status", 2)
            print ret

    @testcase.test_method_decorator
    def test02_Verify_ChildTable(self):
        childTable = self.router.wpanctl("get", "get "+wpan.WPAN_THREAD_CHILD_TABLE, 2)
        childTable = wpan_table_parser.parse_child_table_result(childTable)

        print childTable

        self.assertEqual(len(childTable), len(self.joiner_list))

        counter = 0
        for i, child in enumerate(self.joiner_list):
            ext_addr = child.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]

            for entry in childTable:
                if entry.ext_address == ext_addr:
                    self.assertEqual(int(entry.rloc16, 16), int(child.getprop(wpan.WPAN_THREAD_RLOC16), 16))
                    self.assertEqual(int(entry.timeout), int(child.getprop(wpan.WPAN_THREAD_CHILD_TIMEOUT)))

                    if i == len(self.joiner_list)-1:
                        self.assertTrue(entry.is_ftd())
                        self.assertTrue(entry.is_rx_on_when_idle())
                    else:
                        self.assertFalse(entry.is_ftd())
                        self.assertFalse(entry.is_rx_on_when_idle())
                    counter += 1

        missing_entry = len(self.joiner_list) - counter
        self.assertEqual(missing_entry, 0, 'Missing {} child entry in Child table'.format(str(missing_entry)))

    @testcase.test_method_decorator
    def test03_Verify_ChildTableAddress(self):
        childAddrTable = self.router.wpanctl("get", "get "+wpan.WPAN_THREAD_CHILD_TABLE_ADDRESSES, 2)
        childAddrTable = wpan_table_parser.parse_child_table_address_result(childAddrTable)

        print childAddrTable

        self.assertEqual(len(childAddrTable), len(self.joiner_list))

        counter = 0
        for child in self.joiner_list:
            ext_addr = child.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]

            for entry in childAddrTable:
                if entry.ext_address == ext_addr:
                    self.assertEqual(int(entry.rloc16, 16), int(child.getprop(wpan.WPAN_THREAD_RLOC16), 16))
                    counter += 1

        missing_entry = len(self.joiner_list) - counter
        self.assertEqual(missing_entry, 0, 'Missing {} child entry in Child table'.format(str(missing_entry)))

    @testcase.test_method_decorator
    def test04_Verify_ChildTable_AsValMap(self):
        childTable = self.router.wpanctl("get", "get "+wpan.WPAN_THREAD_CHILD_TABLE_ASVALMAP, 2)

        print childTable

        total_child_table_entry = len(self.joiner_list)
        for item in CHILD_TABLE_AS_VALMAP_ENTRY:
            self.assertEqual(childTable.count(item), total_child_table_entry)


if __name__ == "__main__":
    unittest.main()
