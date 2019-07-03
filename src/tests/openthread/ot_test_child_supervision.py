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
from src.tools.wpan_util import verify, verify_within
from src.utils import process_cleanup

import random
import unittest
import time
import os
import subprocess

CHILD_TIMEOUT = 6
CHILD_SUPERVISION_CHECK_TIMEOUT = 12
PARENT_SUPERVISION_INTERVAL = 10

hwr.global_instance()

class TestChildSupervision(testcase.TestCase):
    poll_interval = 500

    @classmethod
    def hardwareSelect(cls):
        cls.router = ffdb.ThreadDevBoard()
        cls.sed = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.router.set_logger(cls.logger)
        cls.sed.set_logger(cls.logger)

        cls.add_test_device(cls.router)
        cls.add_test_device(cls.sed)

        cls.router.set_up()
        cls.sed.set_up()

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

    def find_string_in_log_file(self):
        filename = os.path.join(self.current_output_directory, 'src.log')

        cmd = 'grep ' + '"' + self.child_supervision_msg + '" ' + filename
        ret = subprocess.check_output(cmd, shell=True)
        print ret   
        return verify(self.child_supervision_msg in ret)

    @testcase.test_method_decorator
    def test01_Pairing(self):
        self.router.form(self.network_data, "router")
        self.router.permit_join(3600)
        self.wait_for_completion(self.device_list)

        # self.logger.info(self.former.wpanctl("manual-status-check", "status", 2))
        self.logger.info(self.router.ip6_lla)
        self.logger.info(self.router.ip6_thread_ula)

        self.network_data.xpanid = self.router.xpanid
        self.network_data.panid = self.router.panid

        # QK TODO change sleepy to sleepy-end-device
        # self.joiner.join(self.network_data, "sleepy")
        self.sed.join(self.network_data, "sleepy-end-device")

        self.sed.set_sleep_poll_interval(self.poll_interval)
        self.wait_for_completion(self.device_list)

        self.sed.setprop(wpan.WPAN_THREAD_CHILD_TIMEOUT, str(CHILD_TIMEOUT))

        print self.sed.getprop(wpan.WPAN_THREAD_CHILD_TIMEOUT)

    @testcase.test_method_decorator
    def test02_GetWpanStatus(self):
        for _ in range(1):
            ret = self.router.wpanctl("get", "status", 2)
            print ret

            ret = self.router.wpanctl("get", "get Thread:NeighborTable", 2)
            print ret

            ret = self.router.wpanctl("get", "get Thread:ChildTable", 2)
            print ret

            ret = self.sed.wpanctl("get", "status", 2)
            print ret

            ret = self.sed.wpanctl("get", "get NCP:ExtendedAddress", 2)
            print 'Extended Address:{}'.format(ret)

            ret = self.sed.wpanctl("get", "get NCP:HardwareAddress", 2)
            print 'SED Hardware Address:{}'.format(ret)

            ret = self.sed.wpanctl("get", "get NCP:MACAddress", 2)
            print 'SED MAC Address:{}'.format(ret)

            time.sleep(5)

    @testcase.test_method_decorator
    def test03_PingRouterLLA(self):
        self.ping6(self.sed, self.router.ip6_lla, num_pings=10, allowed_errors=5, ping_size=200)

    @testcase.test_method_decorator
    def test04_settings(self):
        self.sed.setprop(wpan.WPAN_POLL_INTERVAL, str(self.poll_interval))
        interval = self.sed.getprop(wpan.WPAN_POLL_INTERVAL)
        print interval
        self.assertEqual(int(interval), self.poll_interval)

        self.sed.setprop(wpan.WPAN_THREAD_CHILD_TIMEOUT, str(CHILD_TIMEOUT))
        timeout = self.sed.getprop(wpan.WPAN_THREAD_CHILD_TIMEOUT)
        print timeout
        self.assertEqual(int(timeout), CHILD_TIMEOUT)

        self.sed.setprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, '0')
        child_supervision_timeout = self.sed.getprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT)
        print child_supervision_timeout
        self.assertEqual(int(child_supervision_timeout, 16), 0)

        self.router.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, '0')
        child_supervision_interval = self.router.getprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL)
        print child_supervision_interval
        self.assertEqual(int(child_supervision_interval, 16), 0)

    @testcase.test_method_decorator
    def test05_verify_childTable(self):
        childTable = self.router.wpanctl("get", "get Thread:ChildTable", 2)
        childTable = wpan_table_parser.parse_child_table_result(childTable)
        sed_ext_address = self.sed.wpanctl("get", "get NCP:ExtendedAddress", 2).split('=')[-1].strip()[1:-1]

        for e in childTable:
            if e.ext_address == sed_ext_address:
                break
        else:
            msg = 'Failed to find a child entry for extended address {} in table'.format(sed_ext_address)
            print msg

        self.assertEqual(int(e.rloc16, 16), int(self.sed.wpanctl("get", "get " +
                                                                 wpan.WPAN_THREAD_RLOC16, 2).split('=')[-1].strip(), 16))
        self.assertEqual(int(e.timeout, 0), CHILD_TIMEOUT)
        self.assertEqual(e.is_rx_on_when_idle(), False)
        self.assertEqual(e.is_ftd(), False)

    @testcase.test_method_decorator
    def test06_enable_whitelist(self):
        self.router.setprop(wpan.WPAN_MAC_WHITELIST_ENABLED, '1')

        print self.router.getprop(wpan.WPAN_MAC_WHITELIST_ENABLED)

        self.assertEqual(self.router.getprop(wpan.WPAN_MAC_WHITELIST_ENABLED), 'true')

        time.sleep(CHILD_TIMEOUT+3)

        childTable = self.router.wpanctl("get", "get Thread:ChildTable", 2)
        print 'Child Table:'
        print childTable
        childTable = wpan_table_parser.parse_child_table_result(childTable)
        sed_ext_address = self.sed.wpanctl("get", "get NCP:ExtendedAddress", 2).split('=')[-1].strip()[1:-1]

        print childTable

        for e in childTable:
            self.assertNotEqual(e.ext_address, sed_ext_address, 'SED MAC {} still still in Router ChildTable'.format(e.ext_address))

        # verify the sed is still associated since data polls are acked by radio driver) and
        # supervision check is disabled on the child
        self.assertTrue(wpan_table_parser.is_associated(self.sed), 'SED is not associated !!!')

    @testcase.test_method_decorator
    def test07_enable_supervision_on_child(self):
        # Enable supervision check on child and expect the child to
        # become detached after the check timeout

        self.sed.setprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT, str(CHILD_SUPERVISION_CHECK_TIMEOUT))
        self.assertEqual(int(self.sed.getprop(wpan.WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT), 16), int(CHILD_SUPERVISION_CHECK_TIMEOUT))

        time.sleep(CHILD_SUPERVISION_CHECK_TIMEOUT*3+1)

        self.assertTrue(wpan_table_parser.check_child_is_detached(self.sed), 'SED is still associated!!!')

    @testcase.test_method_decorator
    def test08_enable_supervision_on_parent(self):
        # Enable child supervision on parent and disable white-listing

        self.router.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))
        self.router.setprop(wpan.WPAN_MAC_WHITELIST_ENABLED, '0')

        # Wait for the child to attach back

        time.sleep(CHILD_SUPERVISION_CHECK_TIMEOUT*2)

        self.assertTrue(wpan_table_parser.is_associated(self.sed), 'SED is still not associated!!!')

        # MAC counters are used to verify the child supervision behavior.

        parent_unicast_tx_count = int(self.router.getprop("NCP:Counter:TX_PKT_UNICAST"), 0)

        time.sleep(PARENT_SUPERVISION_INTERVAL * 1.2)

        # To verify that the parent is indeed sending empty "supervision"
        # messages to its child, MAC counter for number of unicast tx is
        # used.

        print parent_unicast_tx_count
        print self.router.getprop("NCP:Counter:TX_PKT_UNICAST")

        self.assertGreaterEqual(int(self.router.getprop("NCP:Counter:TX_PKT_UNICAST"), 0), parent_unicast_tx_count+1)

        # Disable child supervision on parent
        self.router.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, '0')

        time.sleep(CHILD_SUPERVISION_CHECK_TIMEOUT*3)

        self.assertTrue(wpan_table_parser.is_associated(self.sed), 'SED is still not associated!!!')

    @testcase.test_method_decorator
    def test09_verify_supervision_message(self):

        self.router.setprop(wpan.WPAN_CHILD_SUPERVISION_INTERVAL, str(PARENT_SUPERVISION_INTERVAL))

        self.child_supervision_msg = 'Sending supervision message to child'
        result = verify_within(self.find_string_in_log_file, PARENT_SUPERVISION_INTERVAL*10)

        self.assertTrue(result, 'Cannot find the expected string:{} in log file !!!'.format(self.child_supervision_msg))


if __name__ == "__main__":
    unittest.main()
