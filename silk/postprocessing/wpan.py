# -*- coding: utf-8 -*-
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
"""WPAN constants.
"""

import re

from silk.postprocessing import ip, util

WPAN_FORMAT_RTOS = "rtos"
WPAN_FORMAT_WPANTUND = "wpantund"

WPAN_DIRECTION_SENT = "^"
WPAN_DIRECTION_RCVD = "v"

WPAN_DIRECTION_MAP = {WPAN_DIRECTION_SENT: "Sent", WPAN_DIRECTION_RCVD: "Rcvd"}

WPAN_PACKET_LENGTH_DELTA = 16

NETWORK_STATE_NO_NETWORK = 0
NETWORK_STATE_SAVED = 1
NETWORK_STATE_JOINING = 2
NETWORK_STATE_ATTACHED = 3
NETWORK_STATE_ATTACHED_NO_PARENT = 4
NETWORK_STATE_ATTACHING = 5

WPAN_ADDRESS_LLA = "LLA"
WPAN_ADDRESS_MESH_LOCAL = "Mesh-Local"
WPAN_ADDRESS_WEAVE_LEGACY = "Weave Legacy"
WPAN_ADDRESS_WEAVE_THREAD = "Weave Thread"

WPAN_ADDRESS_WEAVE_SUBNET_MAP = {2: WPAN_ADDRESS_WEAVE_LEGACY, 6: WPAN_ADDRESS_WEAVE_THREAD}

WPAN_ADDRESS_TYPES = [WPAN_ADDRESS_LLA, WPAN_ADDRESS_MESH_LOCAL, WPAN_ADDRESS_WEAVE_LEGACY, WPAN_ADDRESS_WEAVE_THREAD]
"""
Regular Expressions go here.
"""
__WPAN_PACKET_HEADER_RTOS_REGEX = re.compile(r"(?P<direction>.*),? (len|l): ?(?P<length>\d+),"
                                             r" (f|m|management|typ): ?(\d+)(, st?:\d)?"
                                             r"(, cksum:0x(?P<checksum>%s+))?" % util.REGEX_HEX)
__WPAN_PACKET_HEADER_THCI_REGEX = re.compile(r"(?P<direction>.*) (pbuf_)?len: (?P<length>\d+),"
                                             r" (ot_len: (\d+), )?cksum:0x(?P<checksum>%s+)" % util.REGEX_HEX)

__WPAN_PACKET_HEADER_WPANTUND_REGEX = re.compile(r"\[(->)?NCP(->)?\] IPv6 len:(\d*)"
                                                 r" type:\d+(\(cksum (0x%s+)\))? \[\w*\]" % util.REGEX_HEX)
__WPAN_PACKET_FROM_TO_RTOS_REGEX = re.compile(r"\s?(FROM|TO):\s?(%s|%s)" %
                                              (ip.IPV6_REGEX, ip.IPV6_ALL_NODES_BROADCAST_SHORT))
__WPAN_PACKET_FROM_TO_WPANTUND_REGEX = re.compile(r"\s+(TO|FROM)\((LOCAL|REMOTE)\)"
                                                  r":\[(%s)\](:\d*)?" % ip.IPV6_REGEX)
__WPAN_PACKET_CHECKSUM_REGEX = re.compile(r"\s*(NEXTH:\d+, )?CKSUM:0X(%s+)" % util.REGEX_HEX)

__WPAN_PACKET_PAYLOAD_REGEX = re.compile(r"\s*↳\s*(%s+)" % util.REGEX_HEX)

WPAN_STATS_REGEX = re.compile(r"Stats ([A-Z_]*): ([\d]*)$")

__WPAN_VERSION_REGEX = re.compile(r"(\(wpan\))? (\w+) bin.mgmt.ver:(\d+),"
                                  r" stack.ver:([\d\.]+), build.ver:(\d+) \((.+)\)")

__WPAN_NETWORK_STATE_REGEX = re.compile(fr"CurrentNetwork id=([\w\-]*), ula=({ip.IPV6_REGEX}),"
                                        fr" xPanId=({util.REGEX_HEX}*), panId=({util.REGEX_HEX}*),"
                                        r" chan=(\d*), nodeType=\d, txPwr=(\-?\d*), status=(\d)?")
__WPAN_NETWORK_STATE_NEW_REGEX = re.compile(fr"CurrentNetwork id=([\w\-]*), xPanId=({util.REGEX_HEX}*),"
                                            fr" panId=({util.REGEX_HEX}*), chan=(\d*), nodeType=(\d*),"
                                            r" txPwr=(\-?\d*), old status=(\d), new status=(\d)(, reason=\d)?")
__WPAN_NETWORK_STATE_SHELL_REGEX = re.compile(r"Network status: '[\w_]+'\((\d+)\)")

__WPAN_MODULES = ["WPAN", "wpantund", "APPL", "THCI", "OTHR"]

__WPAN_NEW_ADDRESS_REGEX = re.compile(r"New (\w+) addr: (%s)([\s\(\)\w]+)?" % ip.IPV6_REGEX)
"""
OpenThread Regex
__OT_MODES: see openthread/src/cli/cli.cpp state options
__OT_VERSION_REGEX: OPENTHREAD/ga28078d; none; Jan 18 2017 04:08:34
"""
__OT_MODES = ["offline", "disabled", "detached", "child", "router", "leader"]
__OT_DEVICE_MODE_SHELL_REGEX = re.compile("(" + "|".join(__OT_MODES) + ")")
__OT_DEVICE_MODE_NEW_SHELL_REGEX = re.compile(r"Mode -> (?P<new_mode>.*)")
__OT_NETWORK_STATE_NEW_REGEX = re.compile(r"\d+ \(.*\) -> \d+ \((?P<new_state>.*)\)")
__OT_VERSION_REGEX = re.compile(r"(OPENTHREAD)/(.*); (.*); (.*)")

__OT_SEND_FAILURE_REGEX = re.compile(r"\[INFO\]\-+MAC\-+: Failed to send IPv6 UDP msg, len:(?P<length>\d+),"
                                     fr" chksum:(?P<checksum>{util.REGEX_HEX}+), to:(0x{util.REGEX_HEX}+),"
                                     r" sec:(\w+), error:(?P<error>\w+), prio:(?P<priority>\w+)")
