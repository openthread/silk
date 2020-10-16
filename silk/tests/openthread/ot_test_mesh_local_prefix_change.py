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
from silk.node.wpan_node import WpanCredentials
from silk.tools import wpan_table_parser
from silk.tools.wpan_util import verify, is_associated
from silk.utils import process_cleanup

hwr.global_instance()

ML_PREFIX_1 = 'fd00:1::'
ML_PREFIX_2 = 'fd00:2::'


class TestMeshLocalPrefixChange(testcase.TestCase):
    """
    Test description:

    This test covers the situation where a router attached to a parent with a different mesh-local prefix. It verifies
    that the attaching router adopts the parent's mesh-local prefix and the RLOC addresses on the router are correctly
    filtered (by wpantund).
    """

    @classmethod
    def hardware_select(cls):
        cls.router1 = ffdb.ThreadDevBoard()
        cls.router2 = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardware_select()

        cls.add_test_device(cls.router1)
        cls.add_test_device(cls.router2)

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
    def test01_form_network(self):
        # Form a network on router1
        self.router1.form(self.network_data, "router", mesh_local_prefix=ML_PREFIX_1)
        self.wait_for_completion(self.device_list)
        self.network_data.xpanid = self.router1.xpanid
        self.network_data.panid = self.router1.panid

        # On router2, form a network with same parameters but a different mesh-local prefix
        self.router2.form(self.network_data, "router", panid=self.router1.panid, xpanid=self.router1.xpanid,
                          mesh_local_prefix=ML_PREFIX_2)
        self.wait_for_completion(self.device_list)

    @testcase.test_method_decorator
    def test02_verify_router2_attaches_to_router1(self):
        # router2 is expected to attach to router1 and adopt the mesh-local prefix from router1
        verify(is_associated(self.router2))
        verify(self.router2.get(wpan.WPAN_IP6_MESH_LOCAL_PREFIX) == self.router1.get(wpan.WPAN_IP6_MESH_LOCAL_PREFIX))

        # Ensure that no ipv6 address starting with ML_PREFIX_2 i.e. fd00:2:: is seen
        verify(self.router2.find_ip6_address_with_prefix(ML_PREFIX_2) == "")

        # There are only 3 addresses on the router2 (link-local and mesh-local address obtained from
        # ML_PREFIX_1 i.e. fd00:1:: and ipv6 address added on the router2 interface) and that RLOC
        # address is correctly filtered (by wpantund).
        self.assertEqual(len(wpan_table_parser.parse_list(self.router2.get(wpan.WPAN_IP6_ALL_ADDRESSES))), 3)


if __name__ == "__main__":
    unittest.main()

