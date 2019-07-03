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

import logging
import os
import subprocess

from src.device.system_call_manager import SystemCallManager
from src.node.base_node import BaseNode
import src.postprocessing.ip as silk_ip


def createLinkPair(interface_1, interface_2):
    command = "sudo ip link add name %s " % interface_1
    command += "type veth peer name %s"   % interface_2

    print command

    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    return proc.communicate()[0]


class NetnsController(SystemCallManager):
    """
    This class contains methods for creating, destroying, and manipulating
    network namespaces.  It also provides methods for making systems calls in
    network namespaces.

    Network namespace manipulation requires sudo.  All inheriting classes must
    be run with sudo.

    Classes that inherit from NetnsController
    1) Must provide a self.device_path attribute. (This is used to roll a
       unique network namespace name.)
    2) Inheriting class must define the following logging methods
        a) log_debug(log_line)
        b) log_info(log_line)
        c) log_warning(log_line)
        d) log_error(log_line)
        e) log_critical(log_line)
    """

    _hwModel = None
    netns = None
    device_path = None

    def __init__(self):
        """
        Carve out a unique network namespace for this device instance.
        Initialize the necessary synchronization mechanisms for async
        operations.
        Startup the system call worker thread.
        """
        self.create_netns()

        SystemCallManager.__init__(self)

    def create_netns(self):
        """
        wpantund will run in a network namespace for these tests.
        This function should be called on instantiation to create a
        unique network namespace name.
        This function returns the network namepsace name.
        """
        self.log_info("Adding network namespace for %s" % self.device_path)

        self.netns = os.path.basename(self.device_path)
        command = "sudo ip netns add %s" % self.netns
        output = self._make_system_call("netns-add", command, 2)
        return self.netns

    def delete_netns(self):
        """
        Delete netns containing this Needle.
        """
        self.log_info("Deleting network namespace for %s" % self.device_path)

        command = "sudo ip netns del %s" % self.netns
        output = self._make_system_call("netns-del", command, 2)

    def netns_pids(self):
        """
        List all PIDs running in this Needle's netns
        """
        self.log_info("Getting PIDs for network namespace for %s" % self.device_path)

        command = "sudo ip netns pids %s" % self.netns
        output = self._make_system_call("netns-pids", command, 2).strip()
        return output.split('\n')

    def netns_killall(self):
        """
        Kill all PIDs in this netns.
        """
        self.log_info("Killing all processes in %s" % self.device_path)
        for pid in self.netns_pids():
            if len(pid.strip()) > 0:
                self.make_netns_call("kill -SIGINT %s" % pid)

    def cleanup_netns(self):
        """
        Kill all PIDs running in the netns.
        Delete the netns.
        """
        self.log_info("Cleaning up network namespace for %s" % self.device_path)
        self.netns_killall()
        self.delete_netns()

    def construct_netns_command(self, user_command):
        """
        Format a command so that it is called in this Needle's
        network namespace.
        """
        command = "sudo ip netns exec %s " % self.netns
        command += user_command
        return command

    def make_netns_call(self, command, timeout=10):
        """
        Take a standard system call (eg: ifconfig, ping, etc.).
        Format the command so that it will be called in this network namespace.
        Make the system call with a timeout.
        """
        command = self.construct_netns_command(command)
        return self._make_system_call("netns-exec", command, timeout)

    def make_netns_call_async(self, command, expect, timeout, field=None):
        """
        Take a standard system call (eg: ifconfig, ping, etc.).
        Format the command so that it will be called in this network namespace.
        Make the system call with a timeout.
        """
        command = self.construct_netns_command(command)
        return self.make_system_call_async("netns-exec", command, expect, timeout, field)

    def link_set(self, interface_name, virtual_eth_peer):
        """
        Assign a network namespace link endpoint to this network namespace.
        Bring up the new interface.
        """
        command = "ip link set %s netns %s" % (interface_name, self.netns)
        self._make_system_call("link-set", command, 1)

        command = "ifconfig %s up" % interface_name
        self.make_netns_call(command, 1)

        command = "ip link set %s up" % virtual_eth_peer
        self._make_system_call("link-set", command, 1)

    def add_ip6_addr(self, prefix, subnet, mac, interface, interface_label):
        """
        Construct a new IP with the specified prefix, subnet, and MAC.
        Store the IP address that was generated.
        Make a call to add the newly formed address to the appropriate
        interface.
        """
        new_ip = silk_ip.assemble(prefix, subnet, mac)
        command = "ip addr add %s/64 dev %s" % (new_ip, interface)
        self.store_data(new_ip, interface_label)
        self.make_netns_call_async(command, "", 1)
        self.make_netns_call_async("ifconfig", "", 1)

    def set_default_route(self, default_interface=None):
        if default_interface is None:
            default_interface = self.thread_interface
        command = "ip -6 route add default dev %s" % default_interface
        self.make_netns_call_async(command, "", 1)

    def enable_ipv6_forwarding(self):
        command = "sysctl -w net.ipv6.confcx.all.forwarding=1"
        self.make_netns_call_async(command, "", 1, None)

    def disable_ipv6_forwarding(self):
        command = "sysctl -w net.ipv6.confcx.all.forwarding=0"
        self.make_netns_call_async(command, "", 1, None)

    def add_route(self, dest, dest_subnet_length, via_addr, interface_name):
        command = "ip -6 route add %s/%s via %s dev %s" % (dest, dest_subnet_length,
                                                           via_addr, interface_name)
        self.make_netns_call_async(command, "", 1, None)


class StandaloneNetworkNamespace(NetnsController, BaseNode):
    """
    Class to control a standalone network namespace that is not associated
    with a development board.
    """
    def __init__(self, netns_name):
        self.device_path = os.path.join("/dev", netns_name)
        BaseNode.__init__(self, netns_name)
        NetnsController.__init__(self)

    def tear_down(self):
        self.cleanup_netns()

#################################
#   Logging functions
#################################
    def set_logger(self, parent_logger):
        self.logger = parent_logger.getChild(self.netns)

        self.logger.setLevel(logging.DEBUG)

    def log_debug(self, log_line):
        if self.logger is not None:
            self.logger.debug(log_line)

    def log_info(self, log_line):
        if self.logger is not None:
            self.logger.info(log_line)

    def log_warning(self, log_line):
        if self.logger is not None:
            self.logger.warning(log_line)

    def log_error(self, log_line):
        if self.logger is not None:
            self.logger.error(log_line)

    def log_critical(self, log_line):
        if self.logger is not None:
            self.logger.critical(log_line)
