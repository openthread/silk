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
import wpan_table_parser
import time
import inspect


def is_associated(device):
    return device.get(wpan.WPAN_STATE) == wpan.STATE_ASSOCIATED


class VerifyError(Exception):
    pass


_is_in_verify_within = False


def verify(condition):
    """Verifies that a `condition` is true, otherwise raises a VerifyError"""
    global _is_in_verify_within
    if not condition:
        calling_frame = inspect.currentframe().f_back
        error_message = 'verify() failed at line {} in "{}"'.format(calling_frame.f_lineno,
                                                                    calling_frame.f_code.co_filename)
        if not _is_in_verify_within:
            print error_message
        return False
    return True


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
        except VerifyError as e:
            if time.time() - start_time > wait_time:
                print 'Took too long to pass the condition ({}>{} sec)'.format(time.time() - start_time, wait_time)
                print e.message
                return False
        except:
            return False
        else:
            break
        if delay_time != 0:
            time.sleep(delay_time)
    _is_in_verify_within = old_is_in_verify_within
    return True


def verify_address(node_list, prefix):
    """
    This function verifies that all nodes in the `node_list` contain an IPv6 address with the given `prefix`.
    """
    for node in node_list:
        all_addrs = wpan_table_parser.parse_list(node.get(wpan.WPAN_IP6_ALL_ADDRESSES))
        verify(any([addr.startswith(prefix[:-1]) for addr in all_addrs]))


def verify_prefix(node_list, prefix, prefix_len=64, stable=True, priority='med', on_mesh=False, slaac=False, dhcp=False,
                  configure=False, default_route=False, preferred=True):
    """
    This function verifies that the `prefix` is present on all the nodes in the `node_list`.
    """
    for node in node_list:
        print node.get(wpan.WPAN_THREAD_ON_MESH_PREFIXES)
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
            print "Did not find prefix {} on node {}".format(prefix, node)
            exit(1)
