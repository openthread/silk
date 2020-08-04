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

import time

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.utils import process_cleanup

hwr.global_instance()


class TestJoinNetwork(testcase.TestCase):
    poll_interval = 1000

    @classmethod
    def hardwareSelect(cls):
        cls.joiner_list = []
        while True:
            try:
                device = ffdb.ThreadDevBoard()
            except Exception:
                break
            else:
                cls.joiner_list.append(device)

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        for end_node in cls.joiner_list:
            cls.add_test_device(end_node)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        cls.network_data = WpanCredentials(
            network_name = 'SILK-{0:04X}'.format(6666),
            psk='00112233445566778899aabbccdd{0:04x}'.format(8888),
            channel=24,
            xpanid=0x123456789abcdeff,
            panid=0x3333,
            fabric_id='{0:06x}dead'.format(9999))

        cls.thread_sniffer_init(cls.network_data.channel)

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.test_method_decorator
    def test01_join_network(self):
        for end_node in self.joiner_list[:-3]:
            end_node.join(self.network_data, 'router')
            self.wait_for_completion([end_node])

        for end_node in self.joiner_list[:-3]:
            self.logger.info(end_node.ip6_lla)
            self.logger.info(end_node.ip6_thread_ula)

        for end_node in self.joiner_list[-3:]:
            end_node.join(self.network_data, 'sleepy-end-device')
            end_node.set_sleep_poll_interval(2000)
            self.wait_for_completion([end_node])

    @testcase.test_method_decorator
    def test02_get_wpan_status(self):
        for _ in range(30):
            router_list, sed_list = [], []

            for e in self.joiner_list[:-3]:
                router_list.append(e.wpanctl(
                    'get', 'get ' + wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1])

            for e in self.joiner_list[-3:]:
                sed_list.append(e.wpanctl(
                    'get', 'get ' + wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1])

            if (all(e == 'router' for e in router_list) and
                    all(e == 'sleepy-end-device' for e in sed_list)):
                self.logger.info('All End-node moved up to Router.')
                break
            time.sleep(8)
        else:
            self.assertFalse(True, 'Router cannot get into router role after 240 seconds timeout')

    @testcase.test_method_decorator
    def test03_keep_running(self):
        while True:
            time.sleep(60)
