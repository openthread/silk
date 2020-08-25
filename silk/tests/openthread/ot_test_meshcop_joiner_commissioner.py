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

from silk.config import wpan_constants as wpan
from silk.tools.wpan_util import verify, verify_within, is_associated
from silk.utils import process_cleanup
import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase

hwr.global_instance()
WAIT_TIME = 2  # seconds

PSKd = "123456"


class TestMeshcopJoinerCommissioner(testcase.TestCase):
    # Test description: Test MeshCop Joiner and Commissioner behavior
    #
    # This test covers Thread commissioning with a single commissioner and joiner device.
    # Network Topology:
    #
    #     commissioner
    #          |
    #          |
    #        joiner
    #
    # Test covers the following situations:
    # Verify commissioner is able to get specified joiner commissioned.
    # Verify after commissioning joiner device is able to attach to commissioner successfully.

    @classmethod
    def hardware_select(cls):
        cls.commissioner = ffdb.ThreadDevBoard()
        cls.joiner = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.commissioner.set_logger(cls.logger)
        cls.joiner.set_logger(cls.logger)

        cls.add_test_device(cls.commissioner)
        cls.add_test_device(cls.joiner)

        cls.commissioner.set_up()
        cls.joiner.set_up()

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
    def test01_form_network_on_commissioner(self):
        self.network_name = "SILK-{0:04X}".format(random.randint(0, 0xffff))
        cmd = "form {}".format(self.network_name)
        self.commissioner.wpanctl_async("form", cmd, "Successfully formed!", 20)
        self.wait_for_completion(self.device_list)
        leader_node_type = self.commissioner.wpanctl("get", "get " + wpan.WPAN_NODE_TYPE,
                                                     2).split("=")[1].strip()[1:-1]
        self.assertTrue(leader_node_type == "leader", "Leader is not created correctly!!!")

    @testcase.test_method_decorator
    def test02_start_commissioning(self):
        self.logger.info("Get joiner {}'s hardware address, it is needed to let commissioner {} know which joiner"
                         " should be able to join.".format(self.joiner.name, self.commissioner.name))
        joiner_hw_addr = self.joiner.get(wpan.WPAN_HW_ADDRESS)[1:-1]  # Remove the `[]`

        # Start the commissioner and add joiner hw address along with PSKd
        self.commissioner.commissioner_start()
        self.wait_for_completion(self.device_list)

        self.commissioner.commissioner_add_joiner(joiner_hw_addr, PSKd)

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
