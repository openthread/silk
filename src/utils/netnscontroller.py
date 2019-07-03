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

import os
import subprocess
from src.utils.process import Process
from src.postprocessing import ip as silk_ip


def createLinkPair(interface_1, interface_2):
    command = "sudo ip link add name %s " % interface_1
    command += "type veth peer name %s"   % interface_2

    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    return proc.communicate()[0]


class NetnsController(object):
    """
    This class contains methods for creating, destroying, and manipulating
    network namespaces.  It also provides methods for making systems calls in
    network namespaces.

    Network namespace manipulation requires sudo.  All inheriting classes must
    be run with sudo.

    Classes that inherit from NetnsController
    1) Must provide a self.device_path attribute. (This is used to roll a
       unique network namespace name.)
    """

    def __init__(self, device_path):
        """
        Carve out a unique network namespace for this device instance.
        Initialize the necessary synchronization mechanisms for async
        operations.
        Startup the system call worker thread.
        """
        self.netns = None
        self.device_path = device_path
        self.create_netns()

    @staticmethod
    def create_netns(serial_number):
        """
        wpantund will run in a network namespace for these tests.
        This function should be called on instantiation to create a
        unique network namespace name.
        This function returns the network namepsace name.
        """
        print("Adding network namespace for %s" % serial_number)
        command = "sudo ip netns add %s" % serial_number
        proc = Process(cmd=command)
        proc.process_cmd_asyc()

    @staticmethod
    def delete_netns(serial_number):
        """
        Delete netns containing this Needle.
        """
        # self.log_info("Deleting network namespace for %s" % self.device_path)

        command = "sudo ip netns del %s" % serial_number
        proc = Process(cmd=command)
        print(command)
        proc.get_process_result()

    @staticmethod
    def netns_killall():
        """
        Kill all netns.
        """
        command = 'sudo ip -all netns del'
        proc=Process(cmd=command)
        proc.get_process_result()

    @staticmethod
    def cleanup_netns():
        """
        Kill all PIDs running in the netns.
        Delete the netns.
        """
        # self.log_info("Cleaning up network namespace for %s" % self.device_path)
        command = 'sudo ip -all netns del'
        proc=Process(cmd=command)
        proc.get_process_result()

    @staticmethod
    def construct_netns_command(serial_number, user_command):
        """
        Format a command so that it is called in this Needle's
        network namespace.
        """
        command = "sudo ip netns exec %s " % serial_number
        command += user_command
        return command

    @staticmethod
    def get_ipv6_addr_list(netns, interface_name):
        """
        Get the ipv6 address from the specified net ns and network interface name
        """
        command = "sudo ip netns exec %s " % netns
        command += "ifconfig %s | grep inet6 | awk -F ' ' '{print $2}'" % interface_name
        proc = Process(cmd=command)
        return proc.get_process_result().split()

    def link_set(self, interface_name):
        """
        Assign a network namespace link endpoint to this network namespace.
        Bring up the new interface.
        """
        command = "ip link set %s netns %s" % (interface_name, self.netns)
        self.make_system_call_async("link-set", command, "", 1, None)

        command = "ifconfig %s up" % interface_name
        Process.execute_command(cmd=command)

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


if __name__ == '__main__':
    netns = os.path.join("/dev", 'ttyACM0')
    netns_controller = NetnsController(netns)
    netns_controller.construct_netns_command('wpantund -o Config:NCP:SocketPath /dev/ttyACM0 -o Config:TUN:InterfaceName wpan0 -o Daemon:SyslogMask "a')

    netns1 = os.path.join("/dev", 'ttyACM1')
    netns_controller1 = NetnsController(netns1)
    netns_controller1.construct_netns_command('wpantund -o Config:NCP:SocketPath /dev/ttyACM1 -o Config:TUN:InterfaceName wpan1 -o Daemon:SyslogMask "a')


