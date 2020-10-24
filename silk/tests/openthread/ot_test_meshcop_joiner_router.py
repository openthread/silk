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

from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools.wpan_util import (verify, verify_within, is_associated)
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()

WAIT_TIME = 2  # in seconds
PSKd = '123456'


class TestMeshcopJoinerRouter(testcase.TestCase):
    # Test description: Test MeshCop Joiner, Commissioner and Joiner-router behavior
    # This test covers Thread commissioning with a commissioner, a joiner-router and joiner device.
    #
    # Network topology:
    #
    #       r1 ---------- r2
    #   (commissioner)   (joiner-router)
    #                     |
    #                     |
    #                     joiner

    @classmethod
    def hardware_select(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.c2 = ffdb.ThreadDevBoard()
        cls.joiner = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.r1, cls.r2, cls.c2, cls.joiner]

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
        self.r1.allowlist_node(self.r2)
        self.joiner.allowlist_node(self.r2)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        self.r2.join(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        self.c2.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        for _ in range(10):
            node_type = self.r2.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE, 2).split("=")[1].strip()[1:-1]
            self.logger.info(node_type == "router")

            if node_type == "router":
                self.logger.info("Matched!!!!!!!!!!!!!")
                break
            time.sleep(10)
        else:
            self.assertFalse(True, "Router cannot get into router role after 100 seconds timeout")

    @testcase.test_method_decorator
    def test02_start_commissioning(self):

        joiner_hw_addr = self.joiner.get(wpan.WPAN_HW_ADDRESS)[1:-1]  # Remove the `[]`

        # Start the commissioner and add joiner hw address along with PSKd
        self.r1.commissioner_start()
        self.wait_for_completion(self.device_list)

        self.r1.commissioner_add_joiner(joiner_hw_addr, PSKd)

        # Start Joiner
        self.joiner.joiner_join(PSKd)

        # Verify that Joiner succeeds in getting commissioned
        verify(self.joiner.get(wpan.WPAN_STATE) == wpan.STATE_COMMISSIONED)

    @testcase.test_method_decorator
    def test03_attach_joiner_to_commissioner(self):
        # Initiate the joiner attach process
        self.joiner.joiner_attach()

        def joiner_is_associated():
            verify(is_associated(self.joiner))

        verify_within(joiner_is_associated, WAIT_TIME)


if __name__ == "__main__":
    unittest.main()
