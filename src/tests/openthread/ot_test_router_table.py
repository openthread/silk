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
from src.tools.wpan_util import verify, VerifyError, verify_within
from src.utils import process_cleanup

import random
import unittest
import time
hwr.global_instance()

WAIT_TIME = 30


class TestRouterTable(testcase.TestCase):
    # Minimum Five devices: One for leader, Three for router, one for sed
    # network topology

    # r1 ------ r2
    #  \        /
    #   \      /
    #    \    /
    #      r3 _____ r4
    #                 \
    #                  \
    #                    c1

    @classmethod
    def hardwareSelect(cls):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.r3 = ffdb.ThreadDevBoard()
        cls.r4 = ffdb.ThreadDevBoard()
        cls.c1 = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        for device in (cls.r1, cls.r2, cls.r3, cls.r4, cls.c1):
            cls.add_test_device(device)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        cls.network_data = WpanCredentials(
            network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk="00112233445566778899aabbccdd{0:04x}".
                format(random.randint(0, 0xffff)),
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
    def test01_Form_Network(self):
        # Form the Network
        self.r1.form(self.network_data, 'router')
        self.wait_for_completion(self.device_list)

        # whitelist all routers with each other
        self.r1.whitelist_node(self.r2)
        self.r2.whitelist_node(self.r1)

        self.r1.whitelist_node(self.r3)
        self.r3.whitelist_node(self.r1)

        self.r2.whitelist_node(self.r3)
        self.r3.whitelist_node(self.r2)

        self.r3.whitelist_node(self.r4)
        self.r4.whitelist_node(self.r3)

        # whitelist between r4 and c1
        self.r4.whitelist_node(self.c1)
        self.c1.whitelist_node(self.r4)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        for router in (self.r2, self.r3, self.r4):
            router.join(self.network_data, 'router')
            self.wait_for_completion(self.device_list)

        self.c1.join(self.network_data, 'sleepy-end-device')
        self.c1.set_sleep_poll_interval(2000)
        self.wait_for_completion(self.device_list)

        for _ in range(30):
            r2_node_type = self.r2.wpanctl('get', 'get '+wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]
            r3_node_type = self.r3.wpanctl('get', 'get ' + wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]
            r4_node_type = self.r4.wpanctl('get', 'get ' + wpan.WPAN_NODE_TYPE, 2).split('=')[1].strip()[1:-1]

            for e in (r2_node_type, r3_node_type, r4_node_type):
                print e

            if all(e == 'router' for e in (r2_node_type, r3_node_type, r4_node_type)):
                print 'All End-node moved up to  Router.'
                break
            time.sleep(5)
        else:
            self.assertFalse(True, 'Router cannot get into router role after 150 seconds timeout')

    @testcase.test_method_decorator
    def test02_Verify_Node_Type(self):
        verify(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        verify(self.r2.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        verify(self.r3.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)
        verify(self.r4.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)

    @testcase.test_method_decorator
    def test03_Verify_r1_Router_Table(self):

        r3_id = int(self.r3.get(wpan.WPAN_THREAD_ROUTER_ID), 0)

        r2_ext_addr = self.r2.get(wpan.WPAN_EXT_ADDRESS)[1:-1]
        r3_ext_addr = self.r3.get(wpan.WPAN_EXT_ADDRESS)[1:-1]

        r1_rloc = int(self.r1.get(wpan.WPAN_THREAD_RLOC16), 16)
        r2_rloc = int(self.r2.get(wpan.WPAN_THREAD_RLOC16), 16)
        r3_rloc = int(self.r3.get(wpan.WPAN_THREAD_RLOC16), 16)
        r4_rloc = int(self.r4.get(wpan.WPAN_THREAD_RLOC16), 16)

        def check_r1_router_table():
            router_table = wpan_table_parser.parse_router_table_result(self.r1.get(wpan.WPAN_THREAD_ROUTER_TABLE))
            verify(len(router_table) == 4)
            for entry in router_table:
                if entry.rloc16 == r1_rloc:
                    pass
                elif entry.rloc16 == r2_rloc:
                    # r1 should be directly connected to r2.
                    verify(entry.is_link_established())
                    verify(entry.ext_address == r2_ext_addr)
                elif entry.rloc16 == r3_rloc:
                    # r1 should be directly connected to r3.
                    verify(entry.is_link_established())
                    verify(entry.ext_address == r3_ext_addr)
                elif entry.rloc16 == r4_rloc:
                    # r1's next hop towards r4 should be through r3.
                    verify(not entry.is_link_established())
                    verify(entry.next_hop == r3_id)
                else:
                    raise (VerifyError("unknown entry in the router table of r1"))

        verify_within(check_r1_router_table, WAIT_TIME)

    @testcase.test_method_decorator
    def test04_Verify_r3_Router_Table(self):

        r1_ext_addr = self.r1.get(wpan.WPAN_EXT_ADDRESS)[1:-1]
        r2_ext_addr = self.r2.get(wpan.WPAN_EXT_ADDRESS)[1:-1]
        r4_ext_addr = self.r4.get(wpan.WPAN_EXT_ADDRESS)[1:-1]

        r1_rloc = int(self.r1.get(wpan.WPAN_THREAD_RLOC16), 16)
        r2_rloc = int(self.r2.get(wpan.WPAN_THREAD_RLOC16), 16)
        r3_rloc = int(self.r3.get(wpan.WPAN_THREAD_RLOC16), 16)
        r4_rloc = int(self.r4.get(wpan.WPAN_THREAD_RLOC16), 16)

        def check_r3_router_table():
            router_table = wpan_table_parser.parse_router_table_result(self.r3.get(wpan.WPAN_THREAD_ROUTER_TABLE))
            verify(len(router_table) == 4)
            for entry in router_table:
                if entry.rloc16 == r1_rloc:
                    # r3 should be directly connected to r1.
                    verify(entry.is_link_established())
                    verify(entry.ext_address == r1_ext_addr)
                elif entry.rloc16 == r2_rloc:
                    # r3 should be directly connected to r2.
                    verify(entry.is_link_established())
                    verify(entry.ext_address == r2_ext_addr)
                elif entry.rloc16 == r3_rloc:
                    pass
                elif entry.rloc16 == r4_rloc:
                    # r3 should be directly connected to r4.
                    verify(entry.is_link_established())
                    verify(entry.ext_address == r4_ext_addr)
                else:
                    raise (VerifyError("unknown entry in the router table of r3"))

        verify_within(check_r3_router_table, WAIT_TIME)

    @testcase.test_method_decorator
    def test05_Verify_r4_Router_Table(self):

        r3_id = int(self.r3.get(wpan.WPAN_THREAD_ROUTER_ID), 0)

        r3_ext_addr = self.r3.get(wpan.WPAN_EXT_ADDRESS)[1:-1]

        r1_rloc = int(self.r1.get(wpan.WPAN_THREAD_RLOC16), 16)
        r2_rloc = int(self.r2.get(wpan.WPAN_THREAD_RLOC16), 16)
        r3_rloc = int(self.r3.get(wpan.WPAN_THREAD_RLOC16), 16)
        r4_rloc = int(self.r4.get(wpan.WPAN_THREAD_RLOC16), 16)

        def check_r4_router_table():
            router_table = wpan_table_parser.parse_router_table_result(self.r4.get(wpan.WPAN_THREAD_ROUTER_TABLE))
            verify(len(router_table) == 4)
            for entry in router_table:
                if entry.rloc16 == r1_rloc:
                    # r4's next hop towards r1 should be through r3.
                    verify(not entry.is_link_established())
                    verify(entry.next_hop == r3_id)
                elif entry.rloc16 == r2_rloc:
                    # r4's next hop towards r2 should be through r3.
                    verify(not entry.is_link_established())
                    verify(entry.next_hop == r3_id)
                elif entry.rloc16 == r3_rloc:
                    # r4 should be directly connected to r3.
                    verify(entry.is_link_established())
                    verify(entry.ext_address == r3_ext_addr)
                elif entry.rloc16 == r4_rloc:
                    pass
                else:
                    raise (VerifyError("unknown entry in the router table of r4"))

        verify_within(check_r4_router_table, WAIT_TIME)


if __name__ == "__main__":
    unittest.main()
