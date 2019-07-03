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
import src.hw.hw_resource as hwr
import src.tests.testcase as testcase
from src.utils import process_cleanup

import random
import unittest
import time

hwr.global_instance()

all_gettable_props = [
    wpan.WPAN_STATE,
    wpan.WPAN_NAME,
    wpan.WPAN_PANID,
    wpan.WPAN_XPANID,
    wpan.WPAN_KEY,
    wpan.WPAN_CHANNEL,
    wpan.WPAN_HW_ADDRESS,
    wpan.WPAN_EXT_ADDRESS,
    wpan.WPAN_POLL_INTERVAL,
    wpan.WPAN_NODE_TYPE,
    wpan.WPAN_ROLE,
    wpan.WPAN_PARTITION_ID,
    wpan.WPAN_NCP_VERSION,
    wpan.WPAN_NCP_MAC_ADDRESS,
    wpan.WPAN_NCP_COUNTER_TX_ERR_CCA,
    wpan.WPAN_NCP_COUNTER_TX_IP_DROPPED,
    wpan.WPAN_NCP_COUNTER_TX_PKT_ACKED,
    wpan.WPAN_IS_COMMISSIONED,
 #   wpan.WPAN_NCP_MCU_POWER_STATE,
    wpan.WPAN_NETWORK_ALLOW_JOIN,
    wpan.WPAN_NETWORK_PASSTHRU_PORT,
    wpan.WPAN_IP6_LINK_LOCAL_ADDRESS,
    wpan.WPAN_IP6_MESH_LOCAL_ADDRESS,
    wpan.WPAN_IP6_MESH_LOCAL_PREFIX,
    wpan.WPAN_IP6_ALL_ADDRESSES,
    wpan.WPAN_IP6_MULTICAST_ADDRESSES,
    wpan.WPAN_THREAD_RLOC16,
    wpan.WPAN_THREAD_ROUTER_ID,
    wpan.WPAN_THREAD_CHILD_TABLE,
    wpan.WPAN_THREAD_CHILD_TABLE_ASVALMAP,
    wpan.WPAN_THREAD_CHILD_TABLE_ADDRESSES,
    wpan.WPAN_THREAD_NEIGHBOR_TABLE,
    wpan.WPAN_THREAD_NEIGHBOR_TABLE_ASVALMAP,
    wpan.WPAN_THREAD_NEIGHBOR_TABLE_ERR_RATES,
    wpan.WPAN_THREAD_ROUTER_TABLE,
    wpan.WPAN_THREAD_ROUTER_TABLE_ASVALMAP,
    wpan.WPAN_THREAD_CHILD_TIMEOUT,
    wpan.WPAN_THREAD_NETWORK_DATA_VERSION,
    wpan.WPAN_THREAD_STABLE_NETWORK_DATA,
    wpan.WPAN_THREAD_STABLE_NETWORK_DATA_VERSION,
    wpan.WPAN_THREAD_DEVICE_MODE,
    wpan.WPAN_THREAD_OFF_MESH_ROUTES,
    wpan.WPAN_THREAD_ON_MESH_PREFIXES,
    wpan.WPAN_THREAD_ROUTER_ROLE_ENABLED,
    wpan.WPAN_THREAD_CONFIG_FILTER_RLOC_ADDRESSES,
    wpan.WPAN_THREAD_ROUTER_UPGRADE_THRESHOLD,
    wpan.WPAN_THREAD_ROUTER_DOWNGRADE_THRESHOLD,
    wpan.WPAN_THREAD_ACTIVE_DATASET,
    wpan.WPAN_THREAD_ACTIVE_DATASET_ASVALMAP,
    wpan.WPAN_THREAD_PENDING_DATASET,
    wpan.WPAN_THREAD_PENDING_DATASET_ASVALMAP,
    wpan.WPAN_OT_LOG_LEVEL,
    wpan.WPAN_OT_STEERING_DATA_ADDRESS,
    wpan.WPAN_OT_STEERING_DATA_SET_WHEN_JOINABLE,
    wpan.WPAN_OT_MSG_BUFFER_COUNTERS,
    wpan.WPAN_OT_MSG_BUFFER_COUNTERS_AS_STRING,
    wpan.WPAN_NCP_COUNTER_ALL_MAC,
    wpan.WPAN_NCP_COUNTER_ALL_MAC_ASVALMAP,
    wpan.WPAN_NCP_RSSI,
    wpan.WPAN_NCP_STATE,
    wpan.WPAN_MAC_WHITELIST_ENABLED,
    wpan.WPAN_MAC_WHITELIST_ENTRIES,
    wpan.WPAN_MAC_WHITELIST_ENTRIES_ASVALMAP,
    wpan.WPAN_MAC_BLACKLIST_ENABLED,
    wpan.WPAN_MAC_BLACKLIST_ENTRIES,
    wpan.WPAN_MAC_BLACKLIST_ENTRIES_ASVALMAP,
    wpan.WPAN_JAM_DETECTION_STATUS,
    wpan.WPAN_JAM_DETECTION_ENABLE,
    wpan.WPAN_JAM_DETECTION_RSSI_THRESHOLD,
    wpan.WPAN_JAM_DETECTION_WINDOW,
    wpan.WPAN_JAM_DETECTION_BUSY_PERIOD,
    wpan.WPAN_JAM_DETECTION_DEBUG_HISTORY_BITMAP,
    wpan.WPAN_CHANNEL_MONITOR_SAMPLE_INTERVAL,
    wpan.WPAN_CHANNEL_MONITOR_RSSI_THRESHOLD,
    wpan.WPAN_CHANNEL_MONITOR_SAMPLE_WINDOW,
    wpan.WPAN_CHANNEL_MONITOR_SAMPLE_COUNT,
    wpan.WPAN_CHANNEL_MONITOR_CHANNEL_QUALITY,
    wpan.WPAN_CHANNEL_MONITOR_CHANNEL_QUALITY_ASVALMAP,
    wpan.WPAN_CHANNEL_MANAGER_NEW_CHANNEL,
    wpan.WPAN_CHANNEL_MANAGER_DELAY,
    wpan.WPAN_CHANNEL_MANAGER_CHANNEL_SELECT,
    wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED,
    wpan.WPAN_CHANNEL_MANAGER_AUTO_SELECT_INTERVAL,
    wpan.WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK,
    wpan.WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK,
    wpan.WPAN_THREAD_LEADER_ADDRESS,
    wpan.WPAN_THREAD_LEADER_ROUTER_ID,
    wpan.WPAN_THREAD_LEADER_WEIGHT,
    wpan.WPAN_THREAD_LEADER_LOCAL_WEIGHT,
    wpan.WPAN_THREAD_LEADER_NETWORK_DATA,
    wpan.WPAN_THREAD_STABLE_LEADER_NETWORK_DATA
]


class TestWpanGetSet(testcase.TestCase):

    @classmethod
    def hardwareSelect(cls):
        cls.router = ffdb.ThreadDevBoard()

    @classmethod
    @testcase.setup_class_decorator
    def setUpClass(cls):
        # Check and clean up wpantund process if any left over
        process_cleanup.ps_cleanup()

        cls.hardwareSelect()

        cls.add_test_device(cls.router)

        for d in cls.device_list:
            d.set_logger(cls.logger)
            d.set_up()

        cls.network_data = WpanCredentials(
            network_name="SILK-{0:04X}".format(random.randint(0, 0xffff)),
            psk="00112233445566778899AAbbCCdd{0:04x}".format(random.randint(0, 0xffff)),
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
    def test01_NCP_State(self):
        self.assertEqual(self.router.getprop(wpan.WPAN_STATE), wpan.STATE_OFFLINE)

    @testcase.test_method_decorator
    def test02_Set_Props(self):

        self.router.setprop(wpan.WPAN_NAME, self.network_data.name)

        self.assertEqual(self.router.getprop(wpan.WPAN_NAME), '"'+self.network_data.name+'"')

        self.router.setprop(wpan.WPAN_NAME, 'a')
        self.assertEqual(self.router.getprop(wpan.WPAN_NAME), '"a"')

        self.router.setprop(wpan.WPAN_PANID, '0xABBA')
        self.assertEqual(self.router.getprop(wpan.WPAN_PANID), '0xABBA')

        self.router.setprop(wpan.WPAN_XPANID, '1020031510006016')
        self.assertEqual(self.router.getprop(wpan.WPAN_XPANID), '0x1020031510006016')

        self.router.setprop(wpan.WPAN_KEY, self.network_data.psk, data=True)
        self.assertEqual(self.router.getprop(wpan.WPAN_KEY), '['+self.network_data.psk.upper()+']')

        self.router.setprop(wpan.WPAN_MAC_WHITELIST_ENABLED, '1')
        self.assertEqual(self.router.getprop(wpan.WPAN_MAC_WHITELIST_ENABLED), 'true')

        self.router.setprop(wpan.WPAN_MAC_WHITELIST_ENABLED, '0')
        self.assertEqual(self.router.getprop(wpan.WPAN_MAC_WHITELIST_ENABLED), 'false')

        self.router.setprop(wpan.WPAN_MAC_WHITELIST_ENABLED, 'true')
        self.assertEqual(self.router.getprop(wpan.WPAN_MAC_WHITELIST_ENABLED), 'true')

        self.router.setprop(wpan.WPAN_THREAD_ROUTER_UPGRADE_THRESHOLD, '100')
        self.assertEqual(int(self.router.getprop(wpan.WPAN_THREAD_ROUTER_UPGRADE_THRESHOLD), 0), 100)

        self.router.setprop(wpan.WPAN_THREAD_ROUTER_DOWNGRADE_THRESHOLD, '40')
        self.assertEqual(int(self.router.getprop(wpan.WPAN_THREAD_ROUTER_DOWNGRADE_THRESHOLD), 0), 40)

    @testcase.test_method_decorator
    def test03_Get_Props(self):
        self.router.form(self.network_data, "router")
        self.wait_for_completion(self.device_list)

        for prop in all_gettable_props:
            value = self.router.get(prop)
            print value

            self.assertFalse('Property Not Found' in value, 'Property: {} was not found !!!'.format(prop))

            self.assertFalse('Error' in value, 'Getting property {} comes with error !!!! '.format(prop))


if __name__ == "__main__":
    unittest.main()
