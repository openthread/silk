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
"""Test traffic over multi-hop in a network with chain topology.
"""

import enum
import random
import time
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify, verify_within
from silk.unit_tests.test_utils import random_string
from silk.utils import process_cleanup

hwr.global_instance()

NUM_ROUTERS = 4
NUM_FED_CHILDREN = 2
NUM_SED_CHILDREN = 4
MSG_LENS = [40, 100, 400, 800, 1000]
ROUTER_TABLE_WAIT_TIME = 30
INVALID_ROUTER_ID = 63
POLL_INTERVAL = 500


class TestMultiHopTraffic(testcase.TestCase):
    # Test description:
    #
    # Traffic over multi-hop in a network with chain topology
    #
    #       r1 ----- r2 ---- r3 ----- r4
    #       /\       |       |        /\
    #      /  \      |       |       /  \
    #    fed1 sed1  sed2    sed3   sed4 fed4
    #
    #
    # Traffic flow:
    #  - From first router to last router
    #  - From SED child of last router to SED child of first router
    #  - From FED child of first router to FED child of last router
    #
    # The test verifies the following:
    # - Verifies Address Query process to routers and FEDs.
    # - Verifies Mesh Header frame forwarding over multiple routers.
    # - Verifies forwarding of large IPv6 messages (1000 bytes) requiring lowpan fragmentation.

    @classmethod
    def hardware_select(cls: 'TestMultiHopTraffic'):
        cls.routers = []
        cls.sed_children = []
        cls.fed_children = []

        for _ in range(NUM_ROUTERS):
            cls.routers.append(ffdb.ThreadDevBoard())
            cls.sed_children.append(ffdb.ThreadDevBoard())

        for _ in range(NUM_FED_CHILDREN):
            cls.fed_children.append(ffdb.ThreadDevBoard())

        cls.all_nodes = cls.routers + cls.sed_children + cls.fed_children

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls: 'TestMultiHopTraffic'):
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
    def tearDownClass(cls: 'TestMultiHopTraffic'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    @testcase.test_method_decorator
    def test01_Pairing(self):
        # Allowlist routers with their corresponding sleepy children
        for index in range(NUM_ROUTERS):
            self.routers[index].allowlist_node(self.sed_children[index])
            self.sed_children[index].allowlist_node(self.routers[index])

        # Allowlist a FED child for the first and last routers
        self.routers[0].allowlist_node(self.fed_children[0])
        self.fed_children[0].allowlist_node(self.routers[0])

        self.routers[-1].allowlist_node(self.fed_children[-1])
        self.fed_children[-1].allowlist_node(self.routers[-1])

        # Allowlist routers at [index-1] and [index]
        for index in range(1, NUM_ROUTERS):
            self.routers[index - 1].allowlist_node(self.routers[index])
            self.routers[index].allowlist_node(self.routers[index - 1])

        self.routers[0].form(self.network_data, "router")
        self.routers[0].permit_join(60)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.routers[0].ip6_lla)
        self.logger.info(self.routers[0].ip6_thread_ula)

        self.network_data.xpanid = self.routers[0].xpanid
        self.network_data.panid = self.routers[0].panid

        self.sed_children[0].join(self.network_data, "sleepy-end-device")
        self.sed_children[0].set_sleep_poll_interval(POLL_INTERVAL)

        for index in range(1, NUM_ROUTERS):
            self.routers[index].join(self.network_data, "router")
            self.sed_children[index].join(self.network_data, "sleepy-end-device")
            self.sed_children[index].set_sleep_poll_interval(POLL_INTERVAL)
            self.wait_for_completion(self.device_list)

        for index in range(NUM_FED_CHILDREN):
            self.fed_children[index].join(self.network_data, "end-node")
            self.wait_for_completion(self.device_list)

        for index in range(1, NUM_ROUTERS):
            self.assertTrue(self.routers[index].get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)

    @testcase.test_method_decorator
    def test02_verify_link(self):
        # Wait till first router has either established a link or
        # has a valid "next hop" towards all other routers.
        r1_rloc = int(self.routers[0].getprop(wpan.WPAN_THREAD_RLOC16), 16)

        def check_r1_router_table():
            router_table = self.routers[0].get(wpan.WPAN_THREAD_ROUTER_TABLE)
            router_table = wpan_table_parser.parse_router_table_result(router_table)
            self.assertEqual(len(router_table), NUM_ROUTERS)
            for entry in router_table:
                verify(entry.rloc16 == r1_rloc or entry.is_link_established() or entry.next_hop != INVALID_ROUTER_ID)

        verify_within(check_r1_router_table, ROUTER_TABLE_WAIT_TIME)

    @testcase.test_method_decorator
    def test03_Transmit_Receive(self):
        # Send from the first router in the chain to the last one.
        # Send from the SED child of the last router to the SED child of the first
        # router.
        # Send from the FED child of the first router to the FED child of the last
        # router.
        class AddressType(enum.Enum):
            MLA = 0

        addresses = [
            (self.routers[0], self.routers[-1], AddressType.MLA, AddressType.MLA),
            (self.sed_children[-1], self.sed_children[0], AddressType.MLA, AddressType.MLA),
            (self.fed_children[0], self.fed_children[-1], AddressType.MLA, AddressType.MLA),
        ]

        timeout = 5
        delay = 1
        for i, (src, dst, src_address, dst_address) in enumerate(addresses):
            port = random.randint(10000 + i * 100, 10099 + i * 100)
            for msg_length in MSG_LENS:
                message = random_string(msg_length)
                src_address = src.ip6_mla
                dst_address = dst.ip6_mla

                dst.receive_udp_data(port, message, timeout)
                time.sleep(delay)
                src.send_udp_data(dst_address, port, message, src_address)

                time.sleep(timeout - delay)


if __name__ == "__main__":
    unittest.main()
