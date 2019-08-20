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

# wpantund properties

WPAN_STATE                                     = 'NCP:State'
WPAN_NAME                                      = 'Network:Name'
WPAN_PANID                                     = 'Network:PANID'
WPAN_XPANID                                    = 'Network:XPANID'
WPAN_KEY                                       = 'Network:Key'
WPAN_KEY_INDEX                                 = 'Network:KeyIndex'
WPAN_CHANNEL                                   = 'NCP:Channel'
WPAN_HW_ADDRESS                                = 'NCP:HardwareAddress'
WPAN_EXT_ADDRESS                               = 'NCP:ExtendedAddress'
WPAN_POLL_INTERVAL                             = 'NCP:SleepyPollInterval'
WPAN_NODE_TYPE                                 = 'Network:NodeType'
WPAN_ROLE                                      = 'Network:Role'
WPAN_PARTITION_ID                              = 'Network:PartitionId'
WPAN_IS_COMMISSIONED                           = 'Network:IsCommissioned'
WPAN_NCP_VERSION                               = 'NCP:Version'
WPAN_NCP_MCU_POWER_STATE                       = "NCP:MCUPowerState"
WPAN_NCP_MAC_ADDRESS                           = 'NCP:MACAddress'
WPAN_NETWORK_ALLOW_JOIN                        = 'com.nestlabs.internal:Network:AllowingJoin'
WPAN_NETWORK_PASSTHRU_PORT                     = 'com.nestlabs.internal:Network:PassthruPort'
WPAN_RCP_VERSION                               = "POSIXApp:RCPVersion"

WPAN_IP6_LINK_LOCAL_ADDRESS                    = "IPv6:LinkLocalAddress"
WPAN_IP6_MESH_LOCAL_ADDRESS                    = "IPv6:MeshLocalAddress"
WPAN_IP6_MESH_LOCAL_PREFIX                     = "IPv6:MeshLocalPrefix"
WPAN_IP6_ALL_ADDRESSES                         = "IPv6:AllAddresses"
WPAN_IP6_MULTICAST_ADDRESSES                   = "IPv6:MulticastAddresses"

WPAN_THREAD_RLOC16                             = "Thread:RLOC16"
WPAN_THREAD_ROUTER_ID                          = "Thread:RouterID"
WPAN_THREAD_LEADER_ADDRESS                     = "Thread:Leader:Address"
WPAN_THREAD_LEADER_ROUTER_ID                   = "Thread:Leader:RouterID"
WPAN_THREAD_LEADER_WEIGHT                      = "Thread:Leader:Weight"
WPAN_THREAD_LEADER_LOCAL_WEIGHT                = "Thread:Leader:LocalWeight"
WPAN_THREAD_LEADER_NETWORK_DATA                = "Thread:Leader:NetworkData"
WPAN_THREAD_STABLE_LEADER_NETWORK_DATA         = "Thread:Leader:StableNetworkData"
WPAN_THREAD_NETWORK_DATA                       = "Thread:NetworkData"
WPAN_THREAD_CHILD_TABLE                        = "Thread:ChildTable"
WPAN_THREAD_CHILD_TABLE_ASVALMAP               = "Thread:ChildTable:AsValMap"
WPAN_THREAD_CHILD_TABLE_ADDRESSES              = "Thread:ChildTable:Addresses"
WPAN_THREAD_NEIGHBOR_TABLE                     = "Thread:NeighborTable"
WPAN_THREAD_NEIGHBOR_TABLE_ASVALMAP            = "Thread:NeighborTable:AsValMap"
WPAN_THREAD_NEIGHBOR_TABLE_ERR_RATES           = "Thread:NeighborTable:ErrorRates"
WPAN_THREAD_NEIGHBOR_TABLE_ERR_RATES_AVVALMAP  = "Thread:NeighborTable:ErrorRates:AsValMap"
WPAN_THREAD_ROUTER_TABLE                       = "Thread:RouterTable"
WPAN_THREAD_ROUTER_TABLE_ASVALMAP              = "Thread:RouterTable:AsValMap"
WPAN_THREAD_CHILD_TIMEOUT                      = "Thread:ChildTimeout"
WPAN_THREAD_PARENT                             = "Thread:Parent"
WPAN_THREAD_PARENT_ASVALMAP                    = "Thread:Parent:AsValMap"
WPAN_THREAD_NETWORK_DATA_VERSION               = "Thread:NetworkDataVersion"
WPAN_THREAD_STABLE_NETWORK_DATA                = "Thread:StableNetworkData"
WPAN_THREAD_STABLE_NETWORK_DATA_VERSION        = "Thread:StableNetworkDataVersion"
WPAN_THREAD_PREFERRED_ROUTER_ID                = "Thread:PreferredRouterID"
WPAN_THREAD_COMMISSIONER_ENABLED               = "Thread:Commissioner:Enabled"
WPAN_THREAD_DEVICE_MODE                        = "Thread:DeviceMode"
WPAN_THREAD_OFF_MESH_ROUTES                    = "Thread:OffMeshRoutes"
WPAN_THREAD_ON_MESH_PREFIXES                   = "Thread:OnMeshPrefixes"
WPAN_THREAD_ROUTER_ROLE_ENABLED                = "Thread:RouterRole:Enabled"
WPAN_THREAD_CONFIG_FILTER_RLOC_ADDRESSES       = "Thread:Config:FilterRLOCAddresses"
WPAN_THREAD_ROUTER_UPGRADE_THRESHOLD           = "Thread:RouterUpgradeThreshold"
WPAN_THREAD_ROUTER_DOWNGRADE_THRESHOLD         = "Thread:RouterDowngradeThreshold"
WPAN_THREAD_ACTIVE_DATASET                     = "Thread:ActiveDataset"
WPAN_THREAD_ACTIVE_DATASET_ASVALMAP            = "Thread:ActiveDataset:AsValMap"
WPAN_THREAD_PENDING_DATASET                    = "Thread:PendingDataset"
WPAN_THREAD_PENDING_DATASET_ASVALMAP           = "Thread:PendingDataset:AsValMap"
WPAN_THREAD_ADDRESS_CACHE_TABLE                = "Thread:AddressCacheTable"
WPAN_THREAD_ADDRESS_CACHE_TABLE_ASVALMAP       = "Thread:AddressCacheTable:AsValMap"

WPAN_OT_LOG_LEVEL                              = "OpenThread:LogLevel"
WPAN_OT_STEERING_DATA_ADDRESS                  = "OpenThread:SteeringData:Address"
WPAN_OT_STEERING_DATA_SET_WHEN_JOINABLE        = "OpenThread:SteeringData:SetWhenJoinable"
WPAN_OT_MSG_BUFFER_COUNTERS                    = "OpenThread:MsgBufferCounters"
WPAN_OT_MSG_BUFFER_COUNTERS_AS_STRING          = "OpenThread:MsgBufferCounters:AsString"
WPAN_OT_DEBUG_TEST_ASSERT                      = "OpenThread:Debug:TestAssert"
WPAN_OT_DEBUG_TEST_WATCHDOG                    = "OpenThread:Debug:TestWatchdog"

WPAN_NCP_COUNTER_ALL_MAC                       = "NCP:Counter:AllMac"
WPAN_NCP_COUNTER_ALL_MAC_ASVALMAP              = "NCP:Counter:AllMac:AsValMap"
WPAN_NCP_RSSI                                  = "NCP:RSSI"
WPAN_NCP_STATE                                 = "NCP:State"
WPAN_NCP_COUNTER_TX_ERR_CCA                    = "NCP:Counter:TX_ERR_CCA"
WPAN_NCP_COUNTER_TX_IP_DROPPED                 = 'NCP:Counter:TX_IP_DROPPED'
WPAN_NCP_COUNTER_TX_PKT_ACKED                  = 'NCP:Counter:TX_PKT_ACKED'

WPAN_MAC_WHITELIST_ENABLED                     = "MAC:Whitelist:Enabled"
WPAN_MAC_WHITELIST_ENTRIES                     = "MAC:Whitelist:Entries"
WPAN_MAC_WHITELIST_ENTRIES_ASVALMAP            = "MAC:Whitelist:Entries:AsValMap"
WPAN_MAC_BLACKLIST_ENABLED                     = "MAC:Blacklist:Enabled"
WPAN_MAC_BLACKLIST_ENTRIES                     = "MAC:Blacklist:Entries"
WPAN_MAC_BLACKLIST_ENTRIES_ASVALMAP            = "MAC:Blacklist:Entries:AsValMap"

WPAN_CHILD_SUPERVISION_INTERVAL                = "ChildSupervision:Interval"
WPAN_CHILD_SUPERVISION_CHECK_TIMEOUT           = "ChildSupervision:CheckTimeout"

WPAN_JAM_DETECTION_STATUS                      = "JamDetection:Status"
WPAN_JAM_DETECTION_ENABLE                      = "JamDetection:Enable"
WPAN_JAM_DETECTION_RSSI_THRESHOLD              = "JamDetection:RssiThreshold"
WPAN_JAM_DETECTION_WINDOW                      = "JamDetection:Window"
WPAN_JAM_DETECTION_BUSY_PERIOD                 = "JamDetection:BusyPeriod"
WPAN_JAM_DETECTION_DEBUG_HISTORY_BITMAP        = "JamDetection:Debug:HistoryBitmap"

WPAN_CHANNEL_MONITOR_SAMPLE_INTERVAL           = "ChannelMonitor:SampleInterval"
WPAN_CHANNEL_MONITOR_RSSI_THRESHOLD            = "ChannelMonitor:RssiThreshold"
WPAN_CHANNEL_MONITOR_SAMPLE_WINDOW             = "ChannelMonitor:SampleWindow"
WPAN_CHANNEL_MONITOR_SAMPLE_COUNT              = "ChannelMonitor:SampleCount"
WPAN_CHANNEL_MONITOR_CHANNEL_QUALITY           = "ChannelMonitor:ChannelQuality"
WPAN_CHANNEL_MONITOR_CHANNEL_QUALITY_ASVALMAP  = "ChannelMonitor:ChannelQuality:AsValMap"

WPAN_CHANNEL_MANAGER_NEW_CHANNEL               = "ChannelManager:NewChannel"
WPAN_CHANNEL_MANAGER_DELAY                     = "ChannelManager:Delay"
WPAN_CHANNEL_MANAGER_CHANNEL_SELECT            = "ChannelManager:ChannelSelect"
WPAN_CHANNEL_MANAGER_AUTO_SELECT_ENABLED       = "ChannelManager:AutoSelect:Enabled"
WPAN_CHANNEL_MANAGER_AUTO_SELECT_INTERVAL      = "ChannelManager:AutoSelect:Interval"
WPAN_CHANNEL_MANAGER_SUPPORTED_CHANNEL_MASK    = "ChannelManager:SupportedChannelMask"
WPAN_CHANNEL_MANAGER_FAVORED_CHANNEL_MASK      = "ChannelManager:FavoredChannelMask"

#-------------------------------------------------------------------------------------------------------------------
# Valid state values

STATE_UNINITIALIZED                            =  '"uninitialized"'
STATE_FAULT                                    =  '"uninitialized:fault"'
STATE_UPGRADING                                =  '"uninitialized:upgrading"'
STATE_DEEP_SLEEP                               =  '"offline:deep-sleep"'
STATE_OFFLINE                                  =  '"offline"'
STATE_COMMISSIONED                             =  '"offline:commissioned"'
STATE_ASSOCIATING                              =  '"associating"'
STATE_CREDENTIALS_NEEDED                       =  '"associating:credentials-needed"'
STATE_ASSOCIATED                               =  '"associated"'
STATE_ISOLATED                                 =  '"associated:no-parent"'
STATE_NETWAKE_ASLEEP                           =  '"associated:netwake-asleep"'
STATE_NETWAKE_WAKING                           =  '"associated:netwake-waking"'

#-----------------------------------------------------------------------------------------------------------------------
# MCU Power state from `WPAN_NCP_MCU_POWER_STATE`

MCU_POWER_STATE_ON                             = '"on"'
MCU_POWER_STATE_LOW_POWER                      = '"low-power"'
MCU_POWER_STATE_OFF                            = '"off"'

#-----------------------------------------------------------------------------------------------------------------------
# Node types (from `WPAN_NODE_TYPE` property)

NODE_TYPE_UNKNOWN                              = '"unknown"'
NODE_TYPE_LEADER                               = '"leader"'
NODE_TYPE_ROUTER                               = '"router"'
NODE_TYPE_END_DEVICE                           = '"end-device"'
NODE_TYPE_SLEEPY_END_DEVICE                    = '"sleepy-end-device"'
NODE_TYPE_COMMISSIONER                         = '"commissioner"'
NODE_TYPE_NEST_LURKER                          = '"nl-lurker"'

#-----------------------------------------------------------------------------------------------------------------------
# Node types used by `Node.join()`

JOIN_TYPE_ROUTER                               = 'r'
JOIN_TYPE_END_DEVICE                           = 'e'
JOIN_TYPE_SLEEPY_END_DEVICE                    = 's'

#-----------------------------------------------------------------------------------------------------------------------
# Bit Flags for Thread Device Mode `WPAN_THREAD_DEVICE_MODE`

THREAD_MODE_FLAG_FULL_NETWORK_DATA   = (1 << 0)
THREAD_MODE_FLAG_FULL_THREAD_DEV     = (1 << 1)
THREAD_MODE_FLAG_SECURE_DATA_REQUEST = (1 << 2)
THREAD_MODE_FLAG_RX_ON_WHEN_IDLE     = (1 << 3)

#-----------------------------------------------------------------------------------------------------------------------