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
import time
import unittest

hwr.global_instance()

CHILD_SUPERVISION_CHECK_TIMEOUT = 5
PARENT_SUPERVISION_INTERVAL = 60
CHILD_TIMEOUT = 600


class TestInformPreviousParent(testcase.TestCase):
    poll_interval = 300

    @classmethod
    def hardwareSelect(cls):
        cls.parent1 = ffdb.ThreadDevBoard()
        cls.parent2= ffdb.ThreadDevBoard()
        cls.child1 = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.add_test_device(cls.parent1)
        cls.add_test_device(cls.parent2)
        cls.add_test_device(cls.child1)

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

    def check_child_is_reattached(self):
        child_stat_ncp_changes = len(wpan_table_parser.parse_list(self.child1.get("stat:ncp")))
        print child_stat_ncp_changes

        verify(child_stat_ncp_changes > self.child_num_state_changes)

        verify(is_associated(self.child1))

    def check_child_is_removed_from_parent2_table(self):
        child_table = wpan_table_parser.parse_list(self.parent2.get(wpan.WPAN_THREAD_CHILD_TABLE))
        verify(len(child_table) == 0)

    @testcase.test_method_decorator
    def test01_Pairing(self):
        self.parent1.whitelist_node(self.parent2)
        self.parent2.whitelist_node(self.parent1)
        self.parent2.whitelist_node(self.child1)

        self.parent1.form(self.network_data, 'router')
        self.parent1.permit_join(120)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.parent1.ip6_lla)
        self.logger.info(self.parent1.ip6_thread_ula)

        self.network_data.xpanid = self.parent1.xpanid
        self.network_data.panid = self.parent1.panid

        self.parent2.join(self.network_data, "router")

        self.child1.join(self.network_data, "sleepy-end-device")
        self.child1.set_sleep_poll_interval(self.poll_interval)
        self.child1.setprop(wpan.WPAN_THREAD_CHILD_TIMEOUT, str(CHILD_TIMEOUT))

        self.wait_for_completion(self.device_list)

        for _ in range(10):
            node_type = self.parent2.wpanctl('get', 'get ' + wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]
            print node_type == 'router'

            if node_type == 'router':
                print 'End-node moved up to a Router.'
                break
            time.sleep(10)
        else:
            self.assertFalse(True, 'Router cannot get into router role after 100 seconds timeout')

    @testcase.test_method_decorator
    def test02_Verify_ChildTable(self):
        childTable = self.parent2.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        childTable = wpan_table_parser.parse_child_table_result(childTable)

        print childTable

        self.assertEqual(len(childTable), 1)

        childTable = self.parent1.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        childTable = wpan_table_parser.parse_child_table_result(childTable)
        self.assertEqual(len(childTable), 0)

    @testcase.test_method_decorator
    def test03_Change_Parent(self):
        # Remove the `child` from whitelist of `parent2` and add it to whitelist of `parent1` instead.
        self.child_num_state_changes = len(wpan_table_parser.parse_list(self.child1.get("stat:ncp")))

        print self.child_num_state_changes

        self.parent1.whitelist_node(self.child1)
        self.parent2.un_whitelist_node(self.child1)

        # Enable supervision check on the `child` and also on `parent1`.

        self.child1.setprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, str(CHILD_SUPERVISION_CHECK_TIMEOUT))
        self.parent1.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))

        # Since child supervision is not enabled on `parent2` and the `child` is
        # removed from whitelist on `parent2`, after the supervision check timeout
        # the `child` should realize that it can no longer talk to its current
        # parent (`parent2`) and try to reattach. All re-attach attempts to `parent2`
        # should fail (due to whitelist) and cause the `child` to get detached and
        # search for a new parent and then attach to `parent1`.
        #
        # To verify that the `child` does get detached and attach to a new parent, we
        # monitor the number of state changes using wpantund property "stat:ncp".

        verify_within(self.check_child_is_reattached, 60, 5)

    @testcase.test_method_decorator
    def test04_Verify_New_Parent(self):
        # Verify that the `child` is now attached to `parent1`
        child_table = self.parent1.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
        child_table = wpan_table_parser.parse_child_table_result(child_table)
        verify(len(child_table) == 1)

        # Finally verify that the `child` is removed from previous parent's child
        # table (which indicates that the `child` did indeed inform its previous
        # parent).

        verify_within(self.check_child_is_removed_from_parent2_table, 1)


if __name__ == "__main__":
    unittest.main()
