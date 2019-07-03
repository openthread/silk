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

from src.tools.wpan_util import verify_address, verify_prefix, is_associated, verify

import random
import unittest
import time

hwr.global_instance()

prefix1 = 'fd00:abba:cafe::'
prefix2 = 'fd00:1234::'
prefix3 = 'fd00:deed::'
prefix4 = 'fd00:abcd::'


class TestOnMeshPrefixConfigGateway(testcase.TestCase):
    poll_interval = 200

    @classmethod
    def hardwareSelect(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.sc1 = ffdb.ThreadDevBoard()
        cls.sc2 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.sc1, cls.sc2]

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        for device in cls.all_nodes:

            device.set_logger(cls.logger)
            cls.add_test_device(device)

            device.set_up()

        cls.network_data = WpanCredentials(
            network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
            channel=random.randint(11, 25),
            fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

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
        self.r1.whitelist_node(self.r2)
        self.r2.whitelist_node(self.r1)

        self.r1.whitelist_node(self.sc1)
        self.r2.whitelist_node(self.sc2)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, 'router')

        self.sc1.join(self.network_data, "sleepy-end-device")
        self.sc2.join(self.network_data, "sleepy-end-device")

        self.sc1.set_sleep_poll_interval(self.poll_interval)
        self.sc2.set_sleep_poll_interval(self.poll_interval)

        self.wait_for_completion(self.device_list)

        for _ in range(18):
            node_type = self.r2.wpanctl('get', 'get '+wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]
            print node_type == 'router'

            if node_type == 'router':
                print 'Matched!!!!!!!!!!!!!'
                break
            time.sleep(10)
        else:
            self.assertFalse(True, 'Router cannot get into router role after 180 seconds timeout')

    @testcase.test_method_decorator
    def test02_Verify_Prefix(self):
        # Add on-mesh prefix1 on router r1
        self.r1.config_gateway1(prefix1)
        self.wait_for_completion(self.device_list)
        time.sleep(60)

        # Verify that the prefix1 and its corresponding address are present on all nodes
        verify_prefix(self.all_nodes, prefix1, stable=True, on_mesh=True, slaac=True)
        verify_address(self.all_nodes, prefix1)

        # Now add prefix2 with priority `high` on router r2 and check all nodes for the new prefix/address
        self.r2.config_gateway1(prefix2, default_route=True, priority='1')
        self.wait_for_completion(self.device_list)
        time.sleep(60)
        verify_prefix(self.all_nodes, prefix2, stable=True, on_mesh=True, slaac=True, default_route=True,
                      priority='high')
        verify_address(self.all_nodes, prefix2)

        # Add prefix3 on sleepy end-device and check for it on all nodes
        self.sc1.config_gateway1(prefix3, priority='-1')
        self.wait_for_completion(self.device_list)
        time.sleep(60)
        verify_prefix(self.all_nodes, prefix3, stable=True, on_mesh=True, slaac=True, priority='low')
        verify_address(self.all_nodes, prefix3)

    @testcase.test_method_decorator
    def test03_Verify_NCP_Reset(self):

        # Verify that prefix1 is retained by `wpantund` and pushed to NCP after a reset
        self.r1.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        # Wait for r1 to recover after reset
        start_time = time.time()
        wait_time = 5
        while not is_associated(self.r1):
            if time.time() - start_time > wait_time:
                print 'Took too long for node to recover after reset ({}>{} sec)'.format(time.time() - start_time,
                                                                                         wait_time)
                exit(1)
            time.sleep(0.25)

        # Wait for on-mesh prefix to be updated
        time.sleep(0.5)
        verify_prefix(self.all_nodes, prefix1, stable=True, on_mesh=True, slaac=True)
        verify_address(self.all_nodes, prefix1)

    @testcase.test_method_decorator
    def test04_Verify_Add_Remove_Prefix(self):
        # Test `add-prefix` and `remove-prefix`

        self.r1.add_prefix(prefix4, 48, priority="1", stable=False, on_mesh=True, slaac=False, dhcp=True,
                           configure=False, default_route=True, preferred=False)

        verify_prefix([self.r1], prefix4, 48, priority="high", stable=False, on_mesh=True, slaac=False, dhcp=True,
                      configure=False, default_route=True, preferred=False)

        # Remove prefix and verify that it is removed from list
        self.r1.remove_prefix(prefix4, 48)
        time.sleep(0.5)
        verify(self.r1.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES).find(prefix4) < 0)

        self.r1.add_prefix(prefix4, 48, priority="-1", stable=True, on_mesh=False, slaac=True, dhcp=False,
                           configure=True, default_route=False, preferred=True)

        verify_prefix([self.r1], prefix4, 48, priority="low", stable=True, on_mesh=False, slaac=True, dhcp=False,
                      configure=True, default_route=False, preferred=True)


if __name__ == "__main__":
    unittest.main()















