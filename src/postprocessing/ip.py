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

import re
import string
import src.postprocessing.util
import ipaddress

from src.postprocessing import hwaddr as mp_hwaddr

# e.g fd26:644d:c77f:0002:1ab4:3000:002d:d2c0
IPV6_REGEX_CHUNK = "%s{1,4}" % src.postprocessing.util.REGEX_HEX
IPV6_REGEX = "(%s:?:){1,7}(%s)" % (IPV6_REGEX_CHUNK, IPV6_REGEX_CHUNK)

IPV6_ALL_NODES_BROADCAST = "FF02:0000:0000:0000:0000:0000:0000:0001"
IPV6_ALL_NODES_BROADCAST_SHORT = "FF02::1"

IPV6_CROSS_IGNORE_DESTS = [
    "FF02:0000:0000:0000:0000:0000:0000:0002"
]


def ipv6_address_reformat(addr):
    ret = ipaddress.ip_address(unicode(addr)).exploded
    ret = str(ret).upper()

    return ret


def ipv6_address_get_prefix(addr):
    ret = None

    if len(addr) == 39:
        ret = addr[:15]

    return ret


def ipv6_address_get_iid(addr):
    ret = None

    if len(addr) == 39:
        ret = addr[20:]

    return ret


def ipv6_address_get_subnet(addr):
    ret = None

    if len(addr) == 39:
        ret = addr[15:19]

    return ret


def lla_to_hwaddr(lla):
    hwaddr = None

    iid = ipv6_address_get_iid(lla)
    if iid:
        hwaddr = mp_hwaddr.hwaddr_from_iid(iid)

    return hwaddr


def ipv6_assemble(prefix, subnet, iid):
    """
    Build an IPv6 address string

    prefix must be a string containing a 48-bit hex value
    subnet must be a string containing a 16-bit hex value
    mac_addr must be a string containing a 64-bit hex value

    The 57th LSB (the UL bit) will be set in the address

    """

    prefix = prefix.replace(':', '')
    iid = iid.replace(':', '')
    
    if len(prefix) != 12:
        raise ValueError("prefix must be length 12, %u given" % len(prefix))
    
    if len(subnet) != 4:
        raise ValueError("subnet must be length 4, %u given" % len(subnet))

    if len(iid) != 16:
        #QK TODO
        print 'iid={}'.format(iid)
        raise ValueError("iid must be length 16, %u given" % len(iid))

    lower64 = int(iid, 16) | ( 1 << 57 )

    addr = [prefix, subnet, "%016x" % lower64]
    # clean up input strings
    addr = [x.strip().replace('0x','') for x in addr]
    addr = [x.replace(':','') for x in addr]

    # Join and Insert ':'s
    addr = string.join(addr, '')
    addr = string.join(re.findall(r"[0-9A-Fa-f]{4}", addr),':')

    return addr


def assemble(fabric_id, subnet, iid):
    prefix = 'fd' + fabric_id
    return ipv6_assemble(prefix, subnet, iid)
