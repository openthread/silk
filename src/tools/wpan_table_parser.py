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


import wpan_util
from src.config import wpan_constants as wpan

import re


def is_associated(sed):
    print sed.getprop(wpan.WPAN_STATE)
    return sed.getprop(wpan.WPAN_STATE) == wpan.STATE_ASSOCIATED


def check_child_is_detached(sed):
    return not is_associated(sed)


class ChildAddressEntry(object):
    """ This object encapsulates a child Address entry"""

    def __init__(self, text):

        # Example of expected text:
        #
        # `\t"9A456FEEC738F641, RLOC16:1402, IPv6Addrs:[fd74:5d77:b280:0:c7a2:c449:b097:147f]"`
        #
        # We get rid of the first two chars `\t"' and last char '"', split the rest using whitespace as separator.
        # Then remove any ',' at end of items in the list.
        items = [item[:-1] if item[-1] == ',' else item for item in text[2:-1].split()]

        # First item in the extended address
        self._ext_address = items[0]

        # Convert the rest into a dictionary by splitting using ':' as separator
        dict = {item.split(':', 1)[0]: item.split(':', 1)[1] for item in items[1:]}

        self._rloc16        = dict['RLOC16']
        self._ipv6_address       = dict['IPv6Addrs'] if 'IPv6Addrs' in dict else ''

    @property
    def ext_address(self):
        return self._ext_address

    @property
    def rloc16(self):
        return self._rloc16

    @property
    def ipv6_address(self):
        return self._ipv6_address

    def __repr__(self):
        return 'ChildEntry({})'.format(self.__dict__)


class ChildEntry(object):
    """ This object encapsulates a child entry"""

    def __init__(self, text):

        # Example of expected text:
        #
        # `\t"E24C5F67F4B8CBB9, RLOC16:d402, NetDataVer:175, LQIn:3, AveRssi:-20, LastRssi:-20, Timeout:120, Age:0, `
        # `RxOnIdle:no, FTD:no, SecDataReq:yes, FullNetData:yes"`
        #

        # We get rid of the first two chars `\t"' and last char '"', split the rest using whitespace as separator.
        # Then remove any ',' at end of items in the list.
        items = [item[:-1] if item[-1] == ',' else item for item in text[2:-1].split()]

        # First item in the extended address
        self._ext_address = items[0]

        # Convert the rest into a dictionary by splitting using ':' as separator
        dict = {item.split(':')[0]: item.split(':')[1] for item in items[1:]}

        self._rloc16        = dict['RLOC16']
        self._timeout       = dict['Timeout']
        self._rx_on_idle    = (dict['RxOnIdle'] == 'yes')
        self._ftd           = (dict['FTD'] == 'yes')
        self._sec_data_req  = (dict['SecDataReq'] == 'yes')
        self._full_net_data = (dict['FullNetData'] == 'yes')

    @property
    def ext_address(self):
        return self._ext_address

    @property
    def rloc16(self):
        return self._rloc16

    @property
    def timeout(self):
        return self._timeout

    def is_rx_on_when_idle(self):
        return self._rx_on_idle

    def is_ftd(self):
        return self._ftd

    def is_sec_data_req(self):
        return self._sec_data_req

    def is_full_net_data(self):
        return self._full_net_data

    def __repr__(self):
        return 'ChildEntry({})'.format(self.__dict__)


def parse_child_table_result(child_table_list):
    """ Parses child table list string and returns an array of `ChildEntry` objects"""
    items = child_table_list.split('\n')[1:-1]
    if items and ']' in items[-1]:
        items.pop()
    return [ChildEntry(item) for item in items]


def parse_child_table_address_result(child_table_list):
    """ Parses child table list string and returns an array of `ChildEntry` objects"""
    items = child_table_list.split('\n')[1:-1]
    if items and ']' in items[-1]:
        items.pop()
    return [ChildAddressEntry(item) for item in items]


class NeighborEntry(object):
    """ This object encapsulates a neighbor entry"""

    def __init__(self, text):

        # Example of expected text:
        #
        # `\t"5AC95ED4646D6565, RLOC16:9403, LQIn:3, AveRssi:-20, LastRssi:-20, Age:0, LinkFC:8, MleFC:0, IsChild:yes, '
        # 'RxOnIdle:no, FTD:no, SecDataReq:yes, FullNetData:yes"'
        #

        # We get rid of the first two chars `\t"' and last char '"', split the rest using whitespace as separator.
        # Then remove any ',' at end of items in the list.
        items = [item[:-1] if item[-1] == ',' else item for item in text[2:-1].split()]

        # First item in the extended address
        self._ext_address = items[0]

        # Convert the rest into a dictionary by splitting the text using ':' as separator
        dict = {item.split(':')[0]: item.split(':')[1] for item in items[1:]}

        self._rloc16     = dict['RLOC16']
        self._is_child   = (dict['IsChild'] == 'yes')
        self._rx_on_idle = (dict['RxOnIdle'] == 'yes')
        self._ftd        = (dict['FTD'] == 'yes')

    @property
    def ext_address(self):
        return self._ext_address

    @property
    def rloc16(self):
        return self._rloc16

    def is_rx_on_when_idle(self):
        return self._rx_on_idle

    def is_ftd(self):
        return self._ftd

    def is_child(self):
        return self._is_child

    def __repr__(self):
        return 'NeighborEntry({})'.format(self.__dict__)


def parse_neighbor_table_result(neighbor_table_list):
    """ Parses neighbor table list string and returns an array of `NeighborEntry` objects"""
    items = neighbor_table_list.split('\n')[1:-1]
    if items and ']' in items[-1]:
        items.pop()
    return [NeighborEntry(item) for item in items]


class RouterTableEntry(object):
    """ This object encapsulates a router table entry"""

    def __init__(self, text):

        # Example of expected text:
        #
        # `\t"8A970B3251810826, RLOC16:4000, RouterId:16, NextHop:43, PathCost:1, LQIn:3, LQOut:3, Age:3, LinkEst:yes"`
        #

        # We get rid of the first two chars `\t"' and last char '"', split the rest using whitespace as separator.
        # Then remove any ',' at end of items in the list.
        items = [item[:-1] if item[-1] ==',' else item for item in text[2:-1].split()]

        # First item in the extended address
        self._ext_address = items[0]

        # Convert the rest into a dictionary by splitting the text using ':' as separator
        dict = {item.split(':')[0] : item.split(':')[1] for item in items[1:]}

        self._rloc16    = int(dict['RLOC16'], 16)
        self._router_id = int(dict['RouterId'], 0)
        self._next_hop  = int(dict['NextHop'], 0)
        self._path_cost = int(dict['PathCost'], 0)
        self._age       = int(dict['Age'], 0)
        self._le        = (dict['LinkEst'] == 'yes')

    @property
    def ext_address(self):
        return self._ext_address

    @property
    def rloc16(self):
        return self._rloc16

    @property
    def router_id(self):
        return self._router_id

    @property
    def next_hop(self):
        return self._next_hop

    @property
    def path_cost(self):
        return self._path_cost

    def is_link_established(self):
        return self._le

    def __repr__(self):
        return 'RouterTableEntry({})'.format(self.__dict__)


def parse_router_table_result(router_table_list):
    """ Parses router table list string and returns an array of `RouterTableEntry` objects"""
    return [RouterTableEntry(item) for item in router_table_list.split('\n')[1:-1]]


class AddressCacheEntry(object):
    """ This object encapsulates an address cache entry"""

    def __init__(self, text):

        # Example of expected text:
        #
        # '\t"fd00:1234::d427:a1d9:6204:dbae -> 0x9c00, age:0"'
        #

        # We get rid of the first two chars `\t"' and last char '"', split the rest using whitespace as separator.
        # Then remove any ',' at end of items in the list.
        items = [item[:-1] if item[-1] ==',' else item for item in text[2:-1].split()]

        # First item in the extended address
        self._address = items[0]
        self._rloc16    = int(items[2], 16)

        # Convert the rest into a dictionary by splitting the text using ':' as separator
        dict = {item.split(':')[0] : item.split(':')[1] for item in items[3:]}

        self._age       = int(dict['age'], 0)

    @property
    def address(self):
        return self._address

    @property
    def rloc16(self):
        return self._rloc16

    @property
    def age(self):
        return self._age

    def __repr__(self):
        return 'AddressCacheEntry({})'.format(self.__dict__)


def parse_address_cache_table_result(addr_cache_table_list):
    """ Parses address cache table list string and returns an array of `AddressCacheEntry` objects"""
    return [AddressCacheEntry(item) for item in addr_cache_table_list.split('\n')[1:-1]]

# wpan scan parse


class ScanResult(object):
    """ This object encapsulates a scan result (active/discover/energy scan)"""

    TYPE_ACTIVE_SCAN     = 'active-scan'
    TYPE_DISCOVERY_SCAN  = 'discover-scan'
    TYPE_ENERGY_SCAN     = 'energy-scan'

    def __init__(self, result_text):

        items = [item.strip() for item in result_text.split('|')]

        if len(items) == 8:
            self._type         = ScanResult.TYPE_ACTIVE_SCAN
            self._index        = items[0]
            self._joinable     = (items[1] == 'YES')
            self._network_name = items[2][1:-1]
            self._panid        = items[3]
            self._channel      = items[4]
            self._xpanid       = items[5]
            self._ext_address  = items[6]
            self._rssi         = items[7]
        elif len(items) == 7:
            self._type         = ScanResult.TYPE_DISCOVERY_SCAN
            self._index        = items[0]
            self._network_name = items[1][1:-1]
            self._panid        = items[2]
            self._channel      = items[3]
            self._xpanid       = items[4]
            self._ext_address  = items[5]
            self._rssi         = items[6]
        elif len(items) == 2:
            self._type         = ScanResult.TYPE_ENERGY_SCAN
            self._channel      = items[0]
            self._rssi         = items[1]
        else:
            raise ValueError('"{}" does not seem to be a valid scan result string'.result_text)

    @property
    def type(self):
        return self._type

    @property
    def joinable(self):
        return self._joinable

    @property
    def network_name(self):
        return self._network_name

    @property
    def panid(self):
        return self._panid

    @property
    def channel(self):
        return self._channel

    @property
    def xpanid(self):
        return self._xpanid

    @property
    def ext_address(self):
        return self._ext_address

    @property
    def rssi(self):
        return self._rssi

    def __repr__(self):
        return 'ScanResult({})'.format(self.__dict__)


def parse_scan_result(scan_result):
    """
    Parses scan result string and returns an array of `ScanResult` objects
    scan result is a string like:
      | Joinable | NetworkName        | PAN ID | Ch | XPanID           | HWAddr           | RSSI
---+----------+--------------------+--------+----+------------------+------------------+------
 1 |       NO | "SILK-EDD6"      | 0xED69 | 11 | AFA702E6A80E008E | D266199DD2D5FD04 |  -31
 2 |       NO | "Silk-PAN-8ACE"    | 0x0CE2 | 11 | 647A2248881784BD | 6A54247406E3CA3C |  -56
 3 |       NO | "Silk-PAN-F926"    | 0x3DDA | 11 | E35BFBBBB014A4FF | EAD5AFC58F50D056 |  -49
    Exclude the last item '"' after split('\n')
    """
    print scan_result
    return [ScanResult(item) for item in scan_result.strip().split('\n')[2:]]  # skip first two lines which are table headers


def is_in_scan_result(node, scan_results):
    """Checks if node is in the scan results list
       `scan_result`s must be list of list of `ScanResult` object (see `parse_scan_result`).
    """
    joinable = (node.get(wpan.WPAN_NETWORK_ALLOW_JOIN).strip() == 'true')
    panid = node.get(wpan.WPAN_PANID)
    xpanid = node.get(wpan.WPAN_XPANID)[2:]
    name = node.get(wpan.WPAN_NAME)[1:-1]
    channel = node.get(wpan.WPAN_CHANNEL)
    ext_address = node.get(wpan.WPAN_EXT_ADDRESS)[1:-1]

    for scan_result in scan_results:

        for item in scan_result:

            if item.network_name == name:
                print [item.panid.strip() == panid.strip(),
                       item.xpanid.strip() == xpanid.strip(),
                       int(item.channel, 16) == int(channel, 16),
                       item.ext_address == ext_address,
                       (item.type == ScanResult.TYPE_DISCOVERY_SCAN) or (item.joinable == joinable)]

            if all([item.network_name == name,
                    item.panid.strip() == panid.strip(),
                    item.xpanid.strip() == xpanid.strip(),
                    int(item.channel, 16) == int(channel, 16),
                    item.ext_address == ext_address,
                    (item.type == ScanResult.TYPE_DISCOVERY_SCAN) or (item.joinable == joinable)]):
                return True

    return False


def parse_list(list_string):
    """
    Parses IPv6/prefix/route list string (output of wpanctl get for properties WPAN_IP6_ALL_ADDRESSES,
    IP6_MULTICAST_ADDRESSES, WPAN_THREAD_ON_MESH_PREFIXES, ...)
    Returns an array of strings each containing an IPv6/prefix/route entry.
    """
    # List string example (get(WPAN_IP6_ALL_ADDRESSES) output):
    #
    # '[\n
    # \t"fdf4:5632:4940:0:8798:8701:85d4:e2be     prefix_len:64   origin:ncp      valid:forever   preferred:forever"\n
    # \t"fe80::2092:9358:97ea:71c6                prefix_len:64   origin:ncp      valid:forever   preferred:forever"\n
    # ]'
    #
    # We split the lines ('\n' as separator) and skip the first and last lines which are '['  and ']'.
    # For each line, skip the first two characters (which are '\t"') and last character ('"'), then split the string
    # using whitespace as separator. The first entry is the IPv6 address.
    #
    return [line[2:-1].split()[0] for line in list_string.split('\n')[1:-1]]


class OnMeshPrefix(object):
    """ This object encapsulates an on-mesh prefix"""

    def __init__(self, text):

        # Example of expected text:
        #
        # '\t"fd00:abba:cafe::       prefix_len:64   origin:user     stable:yes flags:0x31'
        # ' [on-mesh:1 def-route:0 config:0 dhcp:0 slaac:1 pref:1 prio:med] rloc:0x0000"'

        m = re.match('\t"([0-9a-fA-F:]+)\s*prefix_len:(\d+)\s+origin:(\w*)\s+stable:(\w*).* \[' +
                    'on-mesh:(\d)\s+def-route:(\d)\s+config:(\d)\s+dhcp:(\d)\s+slaac:(\d)\s+pref:(\d)\s+prio:(\w*)\]' +
                    '\s+rloc:(0x[0-9a-fA-F]+)',
                     text)
        wpan_util.verify(m is not None)
        data = m.groups()

        self._prefix     = data[0]
        self._prefix_len = data[1]
        self._origin     = data[2]
        self._stable     = (data[3] == 'yes')
        self._on_mesh    = (data[4] == '1')
        self._def_route  = (data[5] == '1')
        self._config     = (data[6] == '1')
        self._dhcp       = (data[7] == '1')
        self._slaac      = (data[8] == '1')
        self._preferred  = (data[9] == '1')
        self._priority   = (data[10])
        self._rloc16     = (data[11])

    @property
    def prefix(self):
        return self._prefix

    @property
    def prefix_len(self):
        return self._prefix_len

    @property
    def origin(self):
        return self._origin

    @property
    def priority(self):
        return self._priority

    def is_stable(self):
        return self._stable

    def is_on_mesh(self):
        return self._on_mesh

    def is_def_route(self):
        return self._def_route

    def is_config(self):
        return self._config

    def is_dhcp(self):
        return self._dhcp

    def is_slaac(self):
        return self._slaac

    def is_preferred(self):
        return self._preferred

    def rloc16(self):
        return self._rloc16

    def __repr__(self):
        return 'OnMeshPrefix({})'.format(self.__dict__)


def parse_on_mesh_prefix_result(on_mesh_prefix_list):
    """ Parses on-mesh prefix list string and returns an array of `OnMeshPrefix` objects"""
    return [ OnMeshPrefix(item) for item in on_mesh_prefix_list.split('\n')[1:-1]]
