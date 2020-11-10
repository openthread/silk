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
"""Test multicast traffic behavior is proper.
"""

import random
import time
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.unit_tests.test_utils import random_string
from silk.utils import process_cleanup

hwr.global_instance()

POLL_INTERVAL = 600

# Multicast addresses
LL_ALL_NODES = "ff02::1"
ML_ALL_NODES = "ff03::1"
ML_ALL_MLP_FWDER_NODES = "ff03::fc"

LL_ALL_ROUTERS = "ff02::2"
ML_ALL_ROUTERS = "ff03::2"
MCAST_ADDR = "ff03::114"
port = random.randint(10000, 10099)


class TestMulticastTraffic(testcase.TestCase):
    # Test description: Multicast traffic
    #
    # Network topology
    #
    #     r1 ---- r2 ---- r3 ---- r4
    #             |               |
    #             |               |
    #            fed             sed
    #
    # Test covers the following multicast traffic:
    #
    # - r2  =>> link-local all-nodes.   Expected to receive on [r1, r2, r3, fed].
    # - r3  =>> mesh-local all-nodes.   Expected to receive on [r1, r2, r3, r4, fed].
    # - r3  =>> link-local all-routers. Expected to receive on [r2, r3, r4].
    # - r3  =>> mesh-local all-routers. Expected to receive on all routers.
    # - r1  =>> link-local all-thread.  Expected to receive on [r1, r2].
    # - fed =>> mesh-local all-thread.  Expected to receive on all nodes.
    # - r1  =>> specific address (on r2 and sed). Expected to receive on [r2, sed].
    # - Check behavior with different multicast hop limit values (1-hop up to 4-hops).

    ml_all_thread_nodes_addr = None

    @classmethod
    def hardware_select(cls: 'TestMulticastTraffic'):
        cls.r1 = ffdb.ThreadDevBoard()
        cls.r2 = ffdb.ThreadDevBoard()
        cls.r3 = ffdb.ThreadDevBoard()
        cls.r4 = ffdb.ThreadDevBoard()
        cls.fed = ffdb.ThreadDevBoard()
        cls.sed = ffdb.ThreadDevBoard()
        cls.all_routers = [cls.r1, cls.r2, cls.r3, cls.r4]
        cls.all_nodes = cls.all_routers + [cls.fed, cls.sed]

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
    def tearDownClass(cls: 'TestMulticastTraffic'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def send_mcast(self,
            src_node,
            src_addr,
            mcast_addr,
            recving_nodes,
            non_recving_nodes=[],
            msg_len=30,
            mcast_hops=5,):
        """
        Send a multicast message with given `len` from `src_node` using `src_addr` to the multicast address `mcast_addr`.
        Verify that the message is received on all nodes in `recving_nodes` list and that it is not received on all
        nodes in `non_recving_nodes` list.
        """
        timeout = 10
        delay = 1

        message = random_string(msg_len)
        if src_addr == src_node.ip6_lla:
            src_addr = f"{src_addr}%{src_node.netns}"

        for receiver in recving_nodes:
            receiver.receive_udp_data(port, message, timeout)

        for listener in non_recving_nodes:
            listener.receive_udp_data(port, "", timeout)

        time.sleep(delay)

        src_node.send_udp_data(target=mcast_addr, port=port, message=message, source=src_addr,
                               hop_limit=mcast_hops)
        time.sleep(timeout - delay)

    @testcase.test_method_decorator
    def test01_pairing(self):
        for node1, node2 in [(self.r1, self.r2), (self.r2, self.r3), (self.r3, self.r4),
                             (self.r2, self.fed), (self.r4, self.sed)]:
            node1.allowlist_node(node2)
            node2.allowlist_node(node1)

        self.r1.form(self.network_data, "router")
        self.r1.permit_join(3600)
        self.wait_for_completion(self.device_list)

        self.logger.info(self.r1.ip6_lla)
        self.logger.info(self.r1.ip6_thread_ula)

        self.network_data.xpanid = self.r1.xpanid
        self.network_data.panid = self.r1.panid

        for node in [self.r2, self.r3, self.r4]:
            node.join(self.network_data, "router")
            self.wait_for_completion(self.device_list)

        self.fed.join(self.network_data, "end-node")
        self.wait_for_completion(self.device_list)

        self.sed.join(self.network_data, "sleepy-end-device")
        self.sed.set_sleep_poll_interval(POLL_INTERVAL)
        self.wait_for_completion(self.device_list)

        self.assertTrue(self.r1.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_LEADER)
        for node in [self.r2, self.r3, self.r4]:
            self.assertTrue(node.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_ROUTER)

        r2_ext_address = self.r2.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        fed_parent = self.fed.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(fed_parent == r2_ext_address)

        r4_ext_address = self.r4.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]
        sed_parent = self.sed.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        self.assertTrue(sed_parent == r4_ext_address)

    @testcase.test_method_decorator
    def test02_verify_multicast_all_nodes(self):
        #
        #    r1 ---- r2 ---- r3 ---- r4
        #            |               |
        #            |               |
        #           fed             sed

        # r2 =>> link-local all-nodes.
        self.send_mcast(self.r2, self.r2.ip6_lla, LL_ALL_NODES, [self.r1, self.r2, self.r3, self.fed],
                        [self.r4, self.sed])

        # ToDo: Add support for mesh local multicasts for nodes which are more than 1 hop away.
        # r3 =>> mesh-local all-nodes.
        # self.send_mcast(self.r3, self.r3.ip6_mla, ML_ALL_NODES, [self.r1, self.r2, self.r3, self.r4, self.fed])

    @testcase.test_method_decorator
    def test03_verify_multicast_all_routers(self):
        # r3 =>> link-local all-routers.
        self.send_mcast(self.r3, self.r3.ip6_lla, LL_ALL_ROUTERS, [self.r2, self.r3, self.r4],
                        [self.r1, self.fed, self.sed])

        # ToDo: Add support for mesh local multicasts for nodes which are more than 1 hop away.
        # r3 =>> mesh-local all-routers.
        # self.send_mcast(self.r3, self.r3.ip6_mla, ML_ALL_ROUTERS, self.all_routers, [self.sed])

    @testcase.test_method_decorator
    def test04_verify_multicast_all_thread_nodes(self):

        ml_prefix = self.r1.get(wpan.WPAN_IP6_MESH_LOCAL_PREFIX)[1:-1].split('/')[0]
        ll_all_thread_nodes_addr = 'ff32:40:' + ml_prefix + '1'
        ml_all_thread_nodes_addr = 'ff33:40:' + ml_prefix + '1'

        # r1 =>> link-local all-thread.
        self.send_mcast(self.r1, self.r1.ip6_lla, ll_all_thread_nodes_addr, [self.r1, self.r2],
                        [self.fed, self.r3, self.r4, self.sed])

    # ToDo: Add support for mesh local multicasts for nodes which are more than 1 hop away.

    #     # fed =>> mesh-local all-thread.
    #     # self.send_mcast(self.fed, self.fed.ip6_mla, ml_all_thread_nodes_addr, self.all_nodes)
    #
    #     TestMulticastTraffic.ml_all_thread_nodes_addr = ml_all_thread_nodes_addr

    # @testcase.test_method_decorator
    # def test05_verify_large_multicast_msg(self):
    #     # Send a large multicast message (requiring MAC level fragmentations)
    #
    #     self.send_mcast(self.r3, self.r3.ip6_mla, self.ml_all_thread_nodes_addr, self.all_nodes, msg_len=400)
    #
    # @testcase.test_method_decorator
    # def test06_verify_hop_limit_behavior(self):
    #
    #     # r1 =>> mesh-local all-thread (one hop)
    #     self.send_mcast(self.r1, self.r1.ip6_mla, self.ml_all_thread_nodes_addr, [self.r1, self.r2],
    #                     [self.fed, self.r3, self.r4, self.sed], mcast_hops=1)
    #
    #     # r1 =>> mesh-local all-thread (two hops)
    #     self.send_mcast(self.r1, self.r1.ip6_mla, self.ml_all_thread_nodes_addr, [self.r1, self.r2, self.fed, self.r3],
    #                     [self.r4, self.sed], mcast_hops=2)
    #
    #     # r1 =>> mesh-local all-thread (three hops)
    #     self.send_mcast(self.r1, self.r1.ip6_mla, self.ml_all_thread_nodes_addr,
    #                     [self.r1, self.r2, self.fed, self.r3, self.r4], [self.sed], mcast_hops=3)
    #
    #     # r1 =>> mesh-local all-thread (four hops)
    #     self.send_mcast(self.r1, self.r1.ip6_mla, self.ml_all_thread_nodes_addr,
    #                     [self.r1, self.r2, self.fed, self.r3, self.r4, self.sed], mcast_hops=4)

    # @testcase.test_method_decorator
    # def test07_verify_multicast_on_specific_address(self):
    #     # Subscribe to a specific multicast address on r2 and sed
    #     for node in [self.r2, self.sed]:
    #         node.add(wpan.WPAN_IP6_MULTICAST_ADDRESSES, MCAST_ADDR)
    #         self.wait_for_completion(self.device_list)
    #
    #     # r1 =>> specific address
    #     self.send_mcast(self.r1, self.r1.ip6_mla, MCAST_ADDR, [self.r2, self.sed],
    #                     [self.r1, self.r3, self.r4, self.fed])


if __name__ == "__main__":
    unittest.main()
