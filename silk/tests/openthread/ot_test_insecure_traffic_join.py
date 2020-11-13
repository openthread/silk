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
"""Test insecure data transmission during joining.
"""

import random
import time
import unittest

import silk.hw.hw_resource as hwr
import silk.node.fifteen_four_dev_board as ffdb
import silk.tests.testcase as testcase
from silk.config import wpan_constants as wpan
from silk.node.wpan_node import WpanCredentials
from silk.tools.wpan_util import (verify, verify_within, is_associated)
from silk.unit_tests.test_utils import random_string
from silk.utils import process_cleanup

hwr.global_instance()
INSECURE_PORT = random.randint(10100, 10199)
SRC_PORT = random.randint(11000, 11500)
WAIT_TIME = 10  # in seconds


class TestInsecureTrafficJoin(testcase.TestCase):
    """Test description: Check insecure data transmission during joining.
    """

    @classmethod
    def hardware_select(cls: 'TestInsecureTrafficJoin'):
        cls.parent = ffdb.ThreadDevBoard()
        cls.router = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls: 'TestInsecureTrafficJoin'):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.add_test_device(cls.parent)
        cls.add_test_device(cls.router)

        for device in cls.device_list:
            device.set_logger(cls.logger)
            device.set_up()

        cls.network_data = WpanCredentials(network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
                                           psk="00112233445566778899aabbccdd{0:04x}".format(random.randint(0, 0xffff)),
                                           channel=random.randint(11, 25),
                                           fabric_id="{0:06x}dead".format(random.randint(0, 0xffffff)))

        cls.thread_sniffer_init(cls.network_data.channel)

    @classmethod
    @testcase.teardown_class_decorator
    def tearDownClass(cls: 'TestInsecureTrafficJoin'):
        for device in cls.device_list:
            device.tear_down()

    @testcase.setup_decorator
    def setUp(self):
        pass

    @testcase.teardown_decorator
    def tearDown(self):
        pass

    def transmit_receive_udp_message(self, src, dst, src_address, dst_address, port, src_port):
        timeout = 5
        delay = 1
        message = random_string(10)

        if src_address == src.ip6_lla:
            src_address = f"{src_address}%{src.netns}"

        dst.receive_udp_data(port, message, timeout)
        time.sleep(delay)
        src.send_udp_data(target=dst_address, port=port, message=message, source=src_address, src_port=src_port)
        time.sleep(timeout - delay)

    @testcase.test_method_decorator
    def test01_pairing(self):
        # allowlisting between parent (i.e. leader) and router
        self.parent.allowlist_node(self.router)
        self.router.allowlist_node(self.parent)

        self.parent.form(self.network_data, "router")
        self.parent.permit_join_new(duration_sec='100', port=INSECURE_PORT)
        self.wait_for_completion(self.device_list)

        self.assertEqual(self.parent.get(wpan.WPAN_NETWORK_ALLOW_JOIN), 'true')

        self.logger.info(self.parent.ip6_lla)
        self.logger.info(self.parent.ip6_thread_ula)

        self.network_data.xpanid = self.parent.xpanid
        self.network_data.panid = self.parent.panid

        # Join parent network from router without setting the key
        self.router.join_node(self.network_data, "router", should_set_key=False)
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_verify_router_joins_parent_network(self):
        self.assertEqual(self.router.getprop(wpan.WPAN_STATE), wpan.STATE_CREDENTIALS_NEEDED)
        self.assertEqual(self.router.getprop(wpan.WPAN_NAME), self.parent.getprop(wpan.WPAN_NAME))
        self.assertEqual(self.router.getprop(wpan.WPAN_XPANID), self.parent.getprop(wpan.WPAN_XPANID))
        self.assertEqual(self.router.getprop(wpan.WPAN_PANID), self.parent.getprop(wpan.WPAN_PANID))

    @testcase.test_method_decorator
    def test03_transmit_receive_insecure_traffic(self):
        # Send insecure traffic from router to parent using link-local IP address
        # for src/dst and insecure port number
        self.transmit_receive_udp_message(self.router, self.parent, self.router.ip6_lla, self.parent.ip6_lla,
                                          src_port=SRC_PORT, port=INSECURE_PORT)

        # Get the random src port number used by parent and ensure router allows
        # insecure rx traffic on that port
        self.router.permit_join_new(duration_sec='100', port=str(SRC_PORT))
        self.transmit_receive_udp_message(self.parent, self.router, self.parent.ip6_lla, self.router.ip6_lla,
                                          src_port=INSECURE_PORT, port=SRC_PORT)

    @testcase.test_method_decorator
    def test04_transmit_receive_secure_traffic(self):
        # Now router fully joins the network (set the network key), check all
        # secure traffic exchange between the nodes

        self.router.set(wpan.WPAN_KEY, self.parent.get(wpan.WPAN_KEY)[1:-1], binary_data=True)

        def check_router_is_associated():
            verify(is_associated(self.router))
        verify_within(check_router_is_associated, WAIT_TIME)

        self.parent.permit_join('0')
        self.transmit_receive_udp_message(self.router, self.parent, self.router.ip6_lla, self.parent.ip6_lla,
                                          src_port=SRC_PORT, port=INSECURE_PORT)

        self.router.permit_join('0')
        self.transmit_receive_udp_message(self.parent, self.router, self.parent.ip6_lla, self.router.ip6_lla,
                                          src_port=INSECURE_PORT, port=SRC_PORT)


if __name__ == "__main__":
    unittest.main()

