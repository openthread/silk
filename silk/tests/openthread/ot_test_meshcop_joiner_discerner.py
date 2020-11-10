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

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify, verify_within, is_associated
from silk.utils import process_cleanup

hwr.global_instance()
WAIT_TIME = 2  # seconds

PSK1 = 'UNCHARTEDTHEL0STLEGACY'
PSK2 = 'UNCHARTED4ATH1EFSEND'
PSK3 = 'THELAST0FUS'

DISCERNER1 = '0x777'
D_LEN1 = 12

DISCERNER2 = '0x7777777'
D_LEN2 = 32

JOINER_TIMOUT = '500'  # in seconds


class TestMeshcopJoinerDiscerner(testcase.TestCase):
    """
    Test use of Joiner Discerner for commissioning
    """

    @classmethod
    def hardware_select(cls):
        cls.commissioner = ffdb.ThreadDevBoard()
        cls.joiner1 = ffdb.ThreadDevBoard()
        cls.joiner2 = ffdb.ThreadDevBoard()
        cls.joiner3 = ffdb.ThreadDevBoard()

        cls.all_nodes = [cls.commissioner, cls.joiner1, cls.joiner2, cls.joiner3]

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
    def test02_verify_discerner_value_after_device_reset(self):
        # Verify Discerner value after device reset on Joiner.
        verify(int(self.joiner1.get(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH), 0) == 0)
        verify(int(self.joiner1.get(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE), 0) == 0)

    @testcase.test_method_decorator
    def test03_set_joiner_discerner_on_joiner1_and_joiner2(self):
        # Set Joiner Discerner on `joiner1` and `joiner2`.
        self.joiner1.set(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH, str(D_LEN1))
        self.joiner1.set(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE, DISCERNER1)
        verify(int(self.joiner1.get(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH), 0) == D_LEN1)
        verify(int(self.joiner1.get(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE), 0) == int(DISCERNER1, 0))

        self.joiner2.set(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH, str(D_LEN2))
        self.joiner2.set(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE, DISCERNER2)
        verify(int(self.joiner2.get(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH), 0) == D_LEN2)
        verify(int(self.joiner2.get(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE), 0) == int(DISCERNER2, 0))

    @testcase.test_method_decorator
    def test04_verify_clearing_of_previously_set_joiner_discerner(self):
        # Set Joiner Discerner on `joiner3`.
        self.joiner3.set(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH, str(D_LEN2))
        self.joiner3.set(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE, DISCERNER2)
        verify(int(self.joiner3.get(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH), 0) == D_LEN2)
        verify(int(self.joiner3.get(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE), 0) == int(DISCERNER2, 0))

        # Clear Joiner Discerner on `joiner3`.
        self.joiner3.set(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH, '0')
        verify(int(self.joiner3.get(wpan.WPAN_THREAD_JOINER_DISCERNER_BIT_LENGTH), 0) == 0)
        verify(int(self.joiner3.get(wpan.WPAN_THREAD_JOINER_DISCERNER_VALUE), 0) == 0)

    @testcase.test_method_decorator
    def test05_add_joiners_on_commissioner(self):
        self.commissioner.commissioner_start()
        self.wait_for_completion(self.device_list)

        # Add `joiner1` and `joiner2` using joiner discerner.
        self.commissioner.commissioner_add_joiner_with_discerner(DISCERNER1, D_LEN1, PSK1, JOINER_TIMOUT)
        self.commissioner.commissioner_add_joiner_with_discerner(DISCERNER2, D_LEN2, PSK2, JOINER_TIMOUT)

        # Add `joiner3` using EUI64 Hardware Address of joiner3.
        joiner3_hw_addr = self.joiner3.get(wpan.WPAN_HW_ADDRESS)[1:-1]  # Remove the `[]`
        self.commissioner.commissioner_add_joiner(joiner3_hw_addr, PSK3, JOINER_TIMOUT)

        verify(len(wpan_table_parser.parse_list(self.commissioner.get(wpan.WPAN_THREAD_COMMISSIONER_JOINERS))) == 3)

    @testcase.test_method_decorator
    def test06_attach_joiners_to_commissioner(self):
        # Start `joiner2` first

        # Starting with `joiner2` verifies the behavior of Commissioner to prefer the Joiner entry with the longest
        # matching discriminator.
        # Note that `joiner2` uses a longer discriminator compared to `joiner1` with similar value.

        self.joiner2.joiner_join(PSK2)
        verify(self.joiner2.get(wpan.WPAN_STATE) == wpan.STATE_COMMISSIONED)
        self.joiner2.joiner_attach()

        def joiner2_is_associated():
            verify(is_associated(self.joiner2))
        verify_within(joiner2_is_associated, WAIT_TIME)

        # Start `joiner1`

        self.joiner1.joiner_join(PSK1)
        verify(self.joiner1.get(wpan.WPAN_STATE) == wpan.STATE_COMMISSIONED)
        self.joiner1.joiner_attach()

        def joiner1_is_associated():
            verify(is_associated(self.joiner1))
        verify_within(joiner1_is_associated, WAIT_TIME)

        # Start `joiner3`

        self.joiner3.joiner_join(PSK3)
        verify(self.joiner3.get(wpan.WPAN_STATE) == wpan.STATE_COMMISSIONED)
        self.joiner3.joiner_attach()

        def joiner3_is_associated():
            verify(is_associated(self.joiner3))
        verify_within(joiner3_is_associated, WAIT_TIME)


if __name__ == "__main__":
    unittest.main()
