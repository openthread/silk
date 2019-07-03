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
from src.tools.wpan_util import verify, verify_within, is_associated
from src.utils import process_cleanup

import random
import unittest

hwr.global_instance()

NUM_SLEEP_CHILDREN = 3
NUM_RX_ON_CHILDREN = 2

NUM_CHILDREN = NUM_SLEEP_CHILDREN + NUM_RX_ON_CHILDREN


class TestParentResetChildRecovery(testcase.TestCase):
    poll_interval = 4000

    @classmethod
    def hardwareSelect(cls):
        cls.router = ffdb.ThreadDevBoard()

        cls.sleepy_children = []
        cls.rx_on_children = []

        for num in range(NUM_SLEEP_CHILDREN):
            cls.sleepy_children.append(ffdb.ThreadDevBoard())

        for num in range(NUM_RX_ON_CHILDREN):
            cls.rx_on_children.append(ffdb.ThreadDevBoard())

        cls.all_children = cls.sleepy_children + cls.rx_on_children

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.add_test_device(cls.router)

        for end_node in cls.all_children:
            cls.add_test_device(end_node)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        cls.network_data = WpanCredentials(
            network_name = "SILK-{0:04X}".format(random.randint(0, 0xffff)),
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

    def check_child_table(self):
        # Checks the child table includes the expected number of children.
        child_table = self.router.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_result(child_table)

        print child_table

        verify(len(child_table) == NUM_CHILDREN)

    @testcase.test_method_decorator
    def test01_Pairing(self):
        self.router.form(self.network_data, 'router')
        self.router.permit_join(60*NUM_CHILDREN)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.router.ip6_lla)
        self.logger.info(self.router.ip6_thread_ula)

        self.network_data.xpanid = self.router.xpanid
        self.network_data.panid = self.router.panid

        for end_node in self.sleepy_children:
            end_node.join(self.network_data, "sleepy-end-device")
            end_node.set_sleep_poll_interval(self.poll_interval)

        for end_node in self.rx_on_children:
            end_node.join(self.network_data, "end-node")

        self.wait_for_completion(self.device_list)

        ret = self.router.wpanctl("get", "status", 2)
        print ret

        for end_node in self.all_children:
            ret = end_node.wpanctl("get", "status", 2)
            print ret

    @testcase.test_method_decorator
    def test02_Verify_ChildTable(self):

        self.check_child_table()

    @testcase.test_method_decorator
    def test03_Verify_Parent_Reset(self):
        # Remember number of NCP state changes (using "stat:ncp" property) per child
        child_num_state_changes = []
        for child in self.all_children:
            child_num_state_changes.append(len(wpan_table_parser.parse_list(child.get("stat:ncp"))))

        print child_num_state_changes

        # Reset the parent
        self.router.reset_thread_radio()
        self.wait_for_completion(self.device_list)

        def check_parent_is_associated():
            verify(is_associated(self.router))

        verify_within(check_parent_is_associated, 20, 3)

        # Verify that all the children are recovered and present in the parent's child table again (within 30 seconds).
        verify_within(self.check_child_table, 30, 5)

        # Verify that number of state changes on all children stays as before (indicating they did not get detached).
        for i in range(len(self.all_children)):
            verify(child_num_state_changes[i] == len(wpan_table_parser.parse_list(self.all_children[i].get("stat:ncp"))))


if __name__ == "__main__":
    unittest.main()
