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
from src.tools.wpan_util import verify, verify_within, is_associated, VerifyError
from src.utils import process_cleanup
import random
import unittest


hwr.global_instance()

WAIT_INTERVAL = 10
# Thread Mode for end-device and sleepy end-device
DEVICE_MODE_SLEEPY_END_DEVICE = wpan.THREAD_MODE_FLAG_FULL_NETWORK_DATA | wpan.THREAD_MODE_FLAG_SECURE_DATA_REQUEST
DEVICE_MODE_END_DEVICE = wpan.THREAD_MODE_FLAG_FULL_NETWORK_DATA | wpan.THREAD_MODE_FLAG_FULL_THREAD_DEV \
                         | wpan.THREAD_MODE_FLAG_SECURE_DATA_REQUEST | wpan.THREAD_MODE_FLAG_RX_ON_WHEN_IDLE


class TestChildModeChange(testcase.TestCase):
    poll_interval = 8000

    @classmethod
    def hardwareSelect(cls):
        cls.parent = ffdb.ThreadDevBoard()
        cls.child1 = ffdb.ThreadDevBoard()
        cls.child2 = ffdb.ThreadDevBoard()

        cls.children = [cls.child1, cls.child2]

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.add_test_device(cls.parent)
        cls.add_test_device(cls.child1)
        cls.add_test_device(cls.child2)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        cls.network_data = WpanCredentials(
            network_name = "SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
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

    def verify_child_table(self, parent, children):
        """
        This function verifies that child table on `parent` node contains all the entries in `children` list and the child
        table entry's mode value matches the children Thread mode.
        """
        child_table = wpan_table_parser.parse_child_table_result(parent.wpanctl("get", "get "+wpan.WPAN_THREAD_CHILD_TABLE, 2))
        print child_table

        verify(len(child_table) == len(children))
        for child in children:
            ext_addr = child.get(wpan.WPAN_EXT_ADDRESS)[1:-1]
            for entry in child_table:
                if entry.ext_address == ext_addr:
                    break
            else:
                raise VerifyError('Failed to find a child entry for extended address {} in table'.format(ext_addr))

            verify(int(entry.rloc16, 16) == int(child.get(wpan.WPAN_THREAD_RLOC16), 16))
            mode = int(child.get(wpan.WPAN_THREAD_DEVICE_MODE), 0)
            verify(entry.is_rx_on_when_idle() == (mode & wpan.THREAD_MODE_FLAG_RX_ON_WHEN_IDLE != 0))
            verify(entry.is_ftd() == (mode & wpan.THREAD_MODE_FLAG_FULL_THREAD_DEV != 0))
            verify(entry.is_full_net_data() == (mode & wpan.THREAD_MODE_FLAG_FULL_NETWORK_DATA != 0))
            verify(entry.is_sec_data_req() == (mode & wpan.THREAD_MODE_FLAG_SECURE_DATA_REQUEST != 0))

    def check_child_table(self):
        self.verify_child_table(self.parent, self.children)

    @testcase.test_method_decorator
    def test01_Pairing(self):
        self.parent.form(self.network_data, 'router')
        self.parent.permit_join(120)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.parent.ip6_lla)
        self.logger.info(self.parent.ip6_thread_ula)

        self.network_data.xpanid = self.parent.xpanid
        self.network_data.panid = self.parent.panid

        self.child1.join(self.network_data, "end-node")
        self.child1.set_sleep_poll_interval(self.poll_interval)

        self.child2.join(self.network_data, "sleepy-end-device")
        self.child2.set_sleep_poll_interval(self.poll_interval)

        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_Verify_Child_Mode(self):
        # Disable child supervision on all devices
        self.parent.set(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, '0')
        self.child1.set(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, '0')
        self.child2.set(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, '0')

        # Verify Thread Device Mode on both children
        verify(int(self.child1.get(wpan.WPAN_THREAD_DEVICE_MODE), 0) == DEVICE_MODE_END_DEVICE)
        verify(int(self.child2.get(wpan.WPAN_THREAD_DEVICE_MODE), 0) == DEVICE_MODE_SLEEPY_END_DEVICE)

        verify_within(self.check_child_table, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test03_Verify_Parent_Reset(self):

        # Reset parent and verify all children are recovered
        self.parent.reset_thread_radio()
        verify_within(self.check_child_table, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test04_Verify_Child_Mode_Change(self):

        # Change mode on both children (make child1 sleepy, and child2 non-sleepy)
        self.child1.set(wpan.WPAN_THREAD_DEVICE_MODE, str(DEVICE_MODE_SLEEPY_END_DEVICE))
        verify(int(self.child1.get(wpan.WPAN_THREAD_DEVICE_MODE), 0) == DEVICE_MODE_SLEEPY_END_DEVICE)

        self.child2.set(wpan.WPAN_THREAD_DEVICE_MODE, str(DEVICE_MODE_END_DEVICE))
        verify(int(self.child2.get(wpan.WPAN_THREAD_DEVICE_MODE), 0) == DEVICE_MODE_END_DEVICE)

        # Verify that the child table on parent is also updated
        verify_within(self.check_child_table, WAIT_INTERVAL)

    @testcase.test_method_decorator
    def test05_Verify_Parent_Reset(self):

        # Reset parent and verify all children are recovered
        self.parent.reset_thread_radio()
        verify_within(self.check_child_table, WAIT_INTERVAL)


if __name__ == "__main__":
    unittest.main()
