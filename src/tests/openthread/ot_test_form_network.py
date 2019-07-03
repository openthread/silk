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
import src.hw.hw_resource as hwr
import src.tests.testcase as testcase
from src.utils import process_cleanup

import random
import unittest
import time

hwr.global_instance()


class TestFormNetwork(testcase.TestCase):
    poll_interval = 1000

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
        # whilte listing between leader and other nodes
        for end_node in self.joiner_list:
            end_node.whitelist_node(self.router)
            self.router.whitelist_node(end_node)

        self.router.form(self.network_data, 'router')
        self.router.permit_join(60*len(self.joiner_list))
        self.wait_for_completion(self.device_list)

        self.logger.info(self.router.ip6_lla)
        self.logger.info(self.router.ip6_thread_ula)

        self.network_data.xpanid = self.router.xpanid
        self.network_data.panid = self.router.panid

        for end_node in self.joiner_list[:-2]:
            end_node.join(self.network_data, "router")
            self.wait_for_completion([end_node])

        for end_node in self.joiner_list[:-2]:
            self.logger.info(end_node.ip6_lla)
            self.logger.info(end_node.ip6_thread_ula)

        for end_node in self.joiner_list[-2:]:
            end_node.join(self.network_data, "sleepy-end-device")
            end_node.set_sleep_poll_interval(2000)
            self.wait_for_completion([end_node])

    @testcase.test_method_decorator
    def test02_GetWpanStatus(self):
        leader_node_type = self.router.wpanctl('get', 'get '+wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]
        self.assertTrue(leader_node_type == 'leader', 'Leader is not created correctly!!!')

        for _ in range(30):
            router_list, sed_list = [], []

            for e in self.joiner_list[:-2]:
                router_list.append(e.wpanctl('get', 'get '+wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1])

            for e in self.joiner_list[-2:]:
                sed_list.append(e.wpanctl('get', 'get '+wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1])

            print router_list
            print sed_list

            if all(e == 'router' for e in router_list) and all(e == 'sleepy-end-device' for e in sed_list):
                print 'All End-node moved up to  Router.'
                break
            time.sleep(8)
        else:
            self.assertFalse(True, 'Router cannot get into router role after 240 seconds timeout')

    @testcase.test_method_decorator
    def test03_PingRouterLLA(self):
        self.ping6_multi_source(self.joiner_list, self.router.ip6_lla,
                                num_pings=10, allowed_errors=5, ping_size=200)

    @testcase.test_method_decorator
    def test04_PingRouterMLA(self):
        self.ping6_multi_source(self.joiner_list, self.router.ip6_mla,
                                num_pings=10, allowed_errors=5, ping_size=200)

    @testcase.test_method_decorator
    def test05_PingRouterULA(self):
        self.ping6_multi_source(self.joiner_list, self.router.ip6_thread_ula,
                                num_pings=10, allowed_errors=5, ping_size=200)


if __name__ == "__main__":
    unittest.main()
