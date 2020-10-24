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

import inspect
import logging
import time

from silk.config import wpan_constants as wpan
from . import wpan_table_parser

logger = logging.getLogger(__name__)


def is_associated(device):
    return device.get(wpan.WPAN_STATE) == wpan.STATE_ASSOCIATED


class VerifyError(Exception):
    pass


_is_in_verify_within = False


def verify(condition):
    """Verifies that a `condition` is true, otherwise raises a VerifyError.
    """
    global _is_in_verify_within
    if not condition:
        calling_frame = inspect.currentframe().f_back
        error_message = "verify() failed at line {} in \"{}\"".format(calling_frame.f_lineno,
                                                                      calling_frame.f_code.co_filename)
        if not _is_in_verify_within:
            logger.error(error_message)
        raise VerifyError(error_message)


def verify_within(condition_checker_func, wait_time, delay_time=0.1):
    """Verifies that a given function `condition_checker_func` passes successfully within a given wait timeout.
        `wait_time` is maximum time waiting for condition_checker to pass (in seconds).
        `delay_time` specifies a delay interval added between failed attempts (in seconds).
    """
    global _is_in_verify_within
    start_time = time.time()
    old_is_in_verify_within = _is_in_verify_within
    _is_in_verify_within = True
    while True:
        try:
            condition_checker_func()
        except VerifyError:
            if time.time() - start_time > wait_time:
                logger.error("Took too long to pass the condition ({}>{} sec)".format(
                    time.time() - start_time, wait_time))
                raise
        except BaseException:
            raise
        else:
            break
        if delay_time != 0:
            time.sleep(delay_time)
    _is_in_verify_within = old_is_in_verify_within
    return True


def verify_address(node_list, prefix):
    """This function verifies that all nodes in the `node_list` contain an IPv6 address with the given `prefix`.
    """
    for node in node_list:
        all_addrs = wpan_table_parser.parse_list(node.get(wpan.WPAN_IP6_ALL_ADDRESSES))
        verify(any([addr.startswith(prefix[:-1]) for addr in all_addrs]))


def verify_no_address(node_list, prefix):
    """This function verifies that none of nodes in the `node_list` contain an IPv6 address with the given `prefix`.
    """
    for node in node_list:
        all_addrs = wpan_table_parser.parse_list(node.get(wpan.WPAN_IP6_ALL_ADDRESSES))
        verify(all([not addr.startswith(prefix[:-1]) for addr in all_addrs]))


def verify_prefix(node_list,
                  prefix,
                  prefix_len=64,
                  stable=True,
                  priority="med",
                  on_mesh=False,
                  slaac=False,
                  dhcp=False,
                  configure=False,
                  default_route=False,
                  preferred=True):
    """This function verifies that the `prefix` is present on all the nodes in the `node_list`.
    """
    for node in node_list:
        prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))
        for p in prefixes:
            if p.prefix == prefix:
                verify(int(p.prefix_len) == prefix_len)
                verify(p.is_stable() == stable)
                verify(p.is_on_mesh() == on_mesh)
                verify(p.is_def_route() == default_route)
                verify(p.is_slaac() == slaac)
                verify(p.is_dhcp() == dhcp)
                verify(p.is_config() == configure)
                verify(p.is_preferred() == preferred)
                verify(p.priority == priority)
                break
        else:
            raise VerifyError("Did not find prefix {} on node {}".format(prefix, node))


def verify_correct_prefix_among_similar_prefixes(node_list,
                                                 prefix,
                                                 prefix_len=64,
                                                 stable=True,
                                                 priority="med",
                                                 on_mesh=False,
                                                 slaac=False,
                                                 dhcp=False,
                                                 configure=False,
                                                 default_route=False,
                                                 preferred=False):
    """
    This function verifies that the `prefix` with specified flags is present on all nodes in the `node_list`
    by checking each and every prefix in the prefixes list till a match is found or the list is exhausted.
    Due to this the correct prefix can be found in cases where same prefix with different flags is added on the nodes.
    """
    for node in node_list:
        prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))
        for p in prefixes:
            if p.prefix == prefix:
                if (int(p.prefix_len) == prefix_len and p.is_stable() == stable and p.is_on_mesh() == on_mesh and
                        p.is_def_route() == default_route and p.is_slaac() == slaac and p.is_dhcp() == dhcp and
                        p.is_config() == configure and p.is_preferred() == preferred and p.priority == priority):
                    break
        else:
            raise VerifyError("Did not find prefix {} on node {}".format(prefix, node.name))


def verify_no_prefix(node_list, prefix):
    """This function verifies that the `prefix` is NOT present on any node in the `node_list`.
    """
    for node in node_list:
        prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))
        for p in prefixes:
            verify(not p.prefix == prefix)


def verify_prefix_with_rloc16(node_list,
                              prefix,
                              rloc16,
                              prefix_len=64,
                              stable=True,
                              priority="med",
                              on_mesh=False,
                              slaac=False,
                              dhcp=False,
                              configure=False,
                              default_route=False,
                              preferred=True):
    """
    This function verifies that the `prefix` is present on all the nodes in the `node_list`. It also verifies
        that the `prefix` is associated with the given `rloc16` (as an integer).
    """
    for node in node_list:
        prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))

        for p in prefixes:
            if p.prefix == prefix and p.origin == "ncp" and int(p.rloc16(), 0) == rloc16:
                verify(int(p.prefix_len) == prefix_len)
                verify(p.is_stable() == stable)
                verify(p.is_on_mesh() == on_mesh)
                verify(p.is_def_route() == default_route)
                verify(p.is_slaac() == slaac)
                verify(p.is_dhcp() == dhcp)
                verify(p.is_config() == configure)
                verify(p.is_preferred() == preferred)
                verify(p.priority == priority)
                break
        else:
            raise VerifyError("Did not find prefix {} on node {}".format(prefix, node.name))


def verify_no_prefix_with_rloc16(node_list, prefix, rloc16):
    """
    This function verifies that none of the nodes in `node_list` contains the on-mesh `prefix` associated with the
    given `rloc16`.
    """
    for node in node_list:
        prefixes = wpan_table_parser.parse_on_mesh_prefix_result(node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES))

        for p in prefixes:
            if p.prefix == prefix and p.origin == "ncp" and int(p.rloc16(), 0) == rloc16:
                raise VerifyError("Did find prefix {} with rloc16 {} on node {}".format(
                    prefix, hex(rloc16), node.name))


def check_neighbor_table(node, neighbors):
    """This function verifies that the neighbor table of a given `node` contains the node in the `neighbors` list.
    """
    neighbor_table = wpan_table_parser.parse_neighbor_table_result(node.get(wpan.WPAN_THREAD_NEIGHBOR_TABLE))
    for neighbor in neighbors:
        ext_addr = neighbor.get(wpan.WPAN_EXT_ADDRESS)[1:-1]
        for entry in neighbor_table:
            if entry.ext_address == ext_addr:
                break
        else:
            raise VerifyError("Failed to find a neighbor entry for extended address {} in table".format(ext_addr))


def check_parent_on_child_and_childtable_on_parent(parent, children):
    """Check parent on each child and on parent verify all children are present.
    """

    # Get parent's extended address
    parent_ext_addr = parent.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]

    # Verify parent on children
    for child in children:
        # get the extended address(it's length is always 16) of the parent from child
        thread_parent = child.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        verify(parent_ext_addr == thread_parent)
        logger.info("***** parent {} has extended address: {}, child {} selected parent: {} *****".format(
            parent.name, parent_ext_addr, child.name, thread_parent))

    # verify all children are present in selected parent's childtable
    child_table = parent.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
    child_table = wpan_table_parser.parse_child_table_result(child_table)
    verify(len(child_table) == len(children))

    counter = 0
    for i, child in enumerate(children):
        ext_addr = child.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]

        for entry in child_table:
            if entry.ext_address == ext_addr:
                verify(int(entry.rloc16, 16) == int(child.get(wpan.WPAN_THREAD_RLOC16), 16))
                verify(int(entry.timeout) == int(child.getprop(wpan.WPAN_THREAD_CHILD_TIMEOUT)))
                verify(child.get(wpan.WPAN_NODE_TYPE) == wpan.NODE_TYPE_SLEEPY_END_DEVICE)
                counter += 1

    missing_entry = len(children) - counter
    verify(missing_entry == 0)


def check_unselected_parent(parent, children):
    """Verify no children are attached to to this parent.
    """

    # Get unselected parent's extended address
    parent_ext_addr = parent.getprop(wpan.WPAN_EXT_ADDRESS)[1:-1]

    # Verify that no children are attached to this parent
    for child in children:
        # get the extended address(it's length is always 16) of the parent from child
        thread_parent = child.getprop(wpan.WPAN_THREAD_PARENT)[1:17]
        logger.info("*** unselected parent {} has extended address: {}, child {}'s parent: {} ***".format(
            parent.name, parent_ext_addr, child.name, thread_parent))
        verify(parent_ext_addr != thread_parent)

    child_table_on_unselected_parent = parent.wpanctl("get", "get " + wpan.WPAN_THREAD_CHILD_TABLE, 2)
    child_table_on_unselected_parent = wpan_table_parser.parse_child_table_result(child_table_on_unselected_parent)
    verify(len(child_table_on_unselected_parent) == 0)


def verify_channel(nodes, new_channel, wait_time=40):
    """
    This function checks the channel on a given list of `nodes` and verifies that all nodes
    switch to a given `new_channel` (as int) within certain `wait_time` (int and in seconds)
    """
    start_time = time.time()

    while not all([(new_channel == int(node.get(wpan.WPAN_CHANNEL), 0)) for node in nodes]):
        if time.time() - start_time > wait_time:
            print('Took too long to switch to channel {} ({}>{} sec)'.format(new_channel,
                                                                             time.time() - start_time, wait_time))
            exit(1)
        time.sleep(0.1)
