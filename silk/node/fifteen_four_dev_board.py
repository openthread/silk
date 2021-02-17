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

import datetime
import logging
import os
import re
import time
import traceback

from silk.config import wpan_constants as wpan
from silk.device.netns_base import create_link_pair
from silk.device.netns_base import NetnsController
from silk.device.netns_base import StandaloneNetworkNamespace
from silk.node.wpantund_base import role_is_thread
from silk.node.wpantund_base import WpantundWpanNode
from silk.postprocessing import ip as silk_ip
from silk.tools import wpan_table_parser
from silk.utils import signal, subprocess_runner
from silk.utils.directorypath import DirectoryPath
from silk.utils.jsonfile import JsonFile
from silk.utils.network import get_local_ip
from silk.utils.process import Process
import silk.config.defaults as defaults
import silk.hw.hw_module as hw_module
import silk.hw.hw_resource as hw_resource

LOG_PATH = "/opt/openthread_test/results/"
POSIX_PATH = "/opt/openthread_test/posix"
RETRY = 3


class WpantundMonitor(signal.Subscriber):
    """Class for logging wpantund output and reacting to state changes.
    """

    running = False
    crashed = False
    state = None
    logger = None

    framing_errors = 0

    state_regex = re.compile(r"State change: \"(?P<old_state>[.]+)\" -> \"(?P<new_state>[.]+)\"")

    def log_debug(self, line):
        if self.logger is not None:
            self.logger.debug(line)

    def subscribe_handle(self, sender, **kwargs):
        # Unconditionally log incoming line
        line = kwargs["line"]
        self.log_debug(line)

        # Check to see if there has been a state transition
        match = self.state_regex.search(line)
        if match is not None:
            self.state = match.group("new_state")

            if self.state == "uninitialized:fault":
                self.running = False

            return

        # Check if wpantund has crashed
        if "FATAL ERROR" in line:
            self.crashed = True
            self.running = False
            return

        if "Finished initializing NCP" in line:
            self.running = True

        if "Framing error" in line:
            self.framing_errors += 1


class FifteenFourDevBoardNode(WpantundWpanNode, NetnsController):
    """
    This class is meant to be used to control wpantund and wpanctl inside of
    network namespaces.
    All inheriting classes require sudo.
    """

    def __init__(self,
                 wpantund_verbose_debug=False,
                 sw_version=None,
                 virtual=False,
                 virtual_name="",
                 device=None,
                 device_path=None):
        self.logger = None
        self.wpantund_logger = None
        self.netns = None
        self.wpantund_process = None
        self.wpantund_monitor = None
        self.virtual_link_peer = None
        self.sw_version = sw_version
        self.virtual_eth_peer = "v-eth1"
        self.flash_result = False
        self.otns_manager = None

        self.wpantund_verbose_debug = wpantund_verbose_debug
        self.thread_mode = "NCP"
        if not virtual:
            local_ip = get_local_ip()

            try:
                cluster_list = JsonFile.get_json("clusters.conf")["clusters"]
                for cluster in cluster_list:
                    if cluster["ip"] == local_ip:
                        self.thread_mode = cluster["thread_mode"]
            except Exception as error:
                logging.info("Cannot load cluster.conf file." f" Running on NCP mode. Error: {error}")

        logging.debug("Thread Mode: {}".format(self.thread_mode))

        # TODO: Check what platform Silk is running on.
        # This will be addressed by issue ID #32.
        self.wpantund_start_time = 30

        if not virtual and os.geteuid() != 0:
            logging.error("ERROR: {0} requires 'sudo' access" % type(self).__name__)
            raise EnvironmentError

        # Acquire necessary hardware
        self.device = device
        self.device_path = device_path
        if self.device is None and self.device_path is None:
            if not virtual:
                self.get_device(sw_version=sw_version)
            else:
                self.get_unclaimed_device(virtual_name)
        super().__init__(self.device.name())

        self.log_info(f"Device interface: {self.device.interface_serial()}")
        if not virtual:
            self.log_info(f"Device Path: {self.device_path}")

            # Setup netns
            NetnsController.__init__(self, self.netns, self.device_path)

#################################
#   Logging functions
#################################

    def set_logger(self, parent_logger):
        self.logger = parent_logger.getChild(self.device.name())
        self.wpantund_logger = self.logger.getChild("wpantund")

        self.logger.setLevel(logging.DEBUG)
        self.wpantund_logger.setLevel(logging.DEBUG)

        if self.wpantund_monitor is not None:
            self.wpantund_monitor.logger = self.wpantund_logger

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

#################################
#   base_node functionality
#################################

    def set_up(self):
        """
        Set commissioning data to default state.
        Get the piece of hardware required for this test.
        Generate a fake MAC address to use for constructing addresses.
        Create a network namespace for this device.
        Start wpantund in the network namespace.
        """

        self.__stop_wpantund()

        self.log_debug(f"Device Interface Serial: {self.device.interface_serial()}")
        self.log_debug(f"Device Port: {self.device.port()}")

        try:
            self.__start_wpantund(self.thread_mode)
            time.sleep(5)

            self.wpanctl_async("setup", "getprop NCP:HardwareAddress", "[0-9a-fA-F]{16}", 1, self.wpan_mac_addr_label)
        except (RuntimeError, ValueError) as e:
            self.logger.critical(e.message)
            self.logger.debug(f"Cannot start wpantund on {self.netns}")

        NetnsController.__init__(self, self.netns, self.device_path)

        self.thread_interface = self.netns
        self.legacy_interface = self.netns + "-L"
        self.leave()

    def tear_down(self):
        """
        Stop wpantund in this network namespace.
        Stop all PIDs running in this network namespace.
        Free the hardware device resource.
        """
        if self.virtual_link_peer is not None:
            self.virtual_link_peer.tear_down()

        # Added leave to help avoiding NCP init issue
        self.leave()
        time.sleep(3)

        self.__stop_wpantund()
        if self.otns_manager is not None:
            self.otns_manager.remove_node(self)
        self.cleanup_netns()
        self.free_device()
        time.sleep(10)

#################################
#   wpan_node functionality
#################################

    def _get_addr(self, cmd):
        if role_is_thread(self.role):
            # Get the colon-separated thread prefix
            fabric_id = self.get_data("fabric-id")

            # Get the MAC that was generated earlier
            wpan_mac = self.wpan_mac_addr

            # Add the address
            self.add_ip6_addr(fabric_id, "0006", wpan_mac, self.thread_interface, self.ip6_thread_ula_label)

            # Get the link-local address
            wpanctl_command = "get IPv6:LinkLocalAddress"
            self.wpanctl_async("Wpanctl get", wpanctl_command, self._ip6_lla_regex, 1, self.ip6_lla_label)

            # Get the mesh-local address
            wpanctl_command = "get IPv6:MeshLocalAddress"
            self.wpanctl_async("Wpanctl get", wpanctl_command, self._ip6_mla_regex, 1, self.ip6_mla_label)

#################################
#   Handle wpantund and wpanctl
#################################

    def wpanctl_async(self, action, command, expect, timeout, field=None):
        """Queue a system call into wpanctl inside the network namespace.
        """
        wpanctl_command = defaults.WPANCTL_PATH + f" -I {self.netns} "
        wpanctl_command += command
        self.make_netns_call_async(wpanctl_command, expect, timeout, field)

    def wpanctl(self, action, command, timeout):
        """Make a system call into wpanctl inside the network namespace.
        Return the response
        """
        wpanctl_command = defaults.WPANCTL_PATH + f" -I {self.netns} "
        wpanctl_command += command
        output = self.make_netns_call(wpanctl_command, timeout)
        return output

    def __start_wpantund(self, thread_mode="NCP"):
        """Start wpantund inside a network namespace.
        """
        command = defaults.WPANTUND_PATH

        if thread_mode.upper() == "NCP":
            command += " -o Config:NCP:SocketPath %s " % self.device_path

        elif thread_mode.upper() == "RCP":

            _OT_NCP_FTD_POSIX_APP = POSIX_PATH + "/ot-ncp"

            ncp_socket_path = (f"system:{_OT_NCP_FTD_POSIX_APP}"
                               f" spinel+hdlc+uart://{self.device_path}?uart-baudrate=115200")

            command += f" -o Config:NCP:SocketPath \"{str(ncp_socket_path)}\""
            command += f" -o Config:TUN:InterfaceName {self.netns} "
            command += " -o Config:NCP:DriverName spinel "

        else:
            self.log_critical("Not supported Thread mode:{}".format(thread_mode))

        if self.wpantund_verbose_debug:
            command += "-o SyslogMask all "

        command += "-I %s" % self.netns

        command = self.construct_netns_command(command)

        self.log_info("Starting wpantund with command %s" % command)

        try:
            self.wpantund_process = subprocess_runner.SubprocessRunner(command)

        except Exception:
            print(traceback.format_exc())

        # Install signal listeners here
        self.wpantund_monitor = WpantundMonitor(publisher=self.wpantund_process)

        if self.otns_manager is not None:
            self.otns_manager.subscribe_to_node(self)

        if self.wpantund_logger is not None:
            self.wpantund_monitor.logger = self.wpantund_logger

        self.wpantund_process.start()

        start_time = time.time()
        while (time.time() - start_time) < self.wpantund_start_time:
            if self.wpantund_monitor.running:
                break
        else:
            self.log_error("wpantund failed to start.")
            self.__stop_wpantund()
            raise RuntimeError(f"Not able to start wpantund on {self.device.name()}")

    def __stop_wpantund(self):
        """
        Stop wpantund inside the network namespace.
        """
        self.log_info("Stopping wpantund")

        if self.wpantund_process is not None:
            self.wpantund_process.stop(1)

            if self.otns_manager is not None:
                self.otns_manager.unsubscribe_from_node(self)
        else:
            self.log_info("No wpantund process to stop")

    def configure_virtual_eth_peer(self, veth_name):
        netns_if = veth_name + "-netns-if"
        self.virtual_eth_peer = veth_name

        # Create network namespace virtual link
        output = create_link_pair(self.virtual_eth_peer, netns_if)

        # The command can complain if the link already exists.  Ignore it.
        if len(output) != 0:
            for line in output.splitlines():
                self.logger.debug(line)

        # Bring up the virtual interfaces in both network namespaces
        self.link_set(netns_if, self.virtual_eth_peer)

        return self.virtual_eth_peer

    def configure_external_route(self, route_data):
        if self.virtual_link_peer is None:
            # Create a netns to act as a peer to the border router
            self.virtual_link_peer = StandaloneNetworkNamespace("link_peer")

            if self.logger is not None:
                self.virtual_link_peer.set_logger(self.logger)

            router_if = "router-if"
            netns_if = "netns-if"

            # Create network namespace virtual link
            output = create_link_pair(router_if, netns_if)

            # The command can complain if the link already exists.  Ignore it.
            if len(output) != 0:
                for line in output.splitlines():
                    self.logger.debug(line)

            # Bring up the virtual interfaces in both network namespaces
            # self.link_set(router_if)
            # self.virtual_link_peer.link_set(netns_if)
            # TODO: check this link_set mapping later
            self.link_set(router_if, self.virtual_eth_peer)
            self.virtual_link_peer.link_set(netns_if, self.virtual_eth_peer)

            # Add addresses specified by the route_data
            self.add_ip6_addr(route_data.fabric_id, route_data.subnet, route_data.router_node_id, router_if,
                              "ip6_addr_border_router")

            self.virtual_link_peer.add_ip6_addr(route_data.fabric_id, route_data.subnet, route_data.peer_node_id,
                                                netns_if, "ip6_addr_border_router")

            # Enable forwarding on the border router
            self.enable_ipv6_forwarding()

            # Give the bare netns a route back to the Therad network
            self.virtual_link_peer.add_route(route_data.gateway_prefix, route_data.subnet_length,
                                             self.get_data("ip6_addr_border_router"), netns_if)

            return self.virtual_link_peer

    def query_association_state_delayed(self, delay, expected_association_state):
        # Allow a few seconds for the device to transition into the
        # associated state.
        self.make_system_call_async("reset", "sleep %s; echo done" % delay, "done", delay + 1)

        # Make sure that the DUT has transitioned into
        command = "getprop AssociationState"
        self.wpanctl_async("join", command, expected_association_state, 1)

    def get_device_name(self):
        return self.device.name()

    def image_flash_nrf52840(self, serial_number, fw_file, result_log_path=None):
        flash_rel = True
        shell_path = DirectoryPath.get_dir("shell")

        cmd = shell_path + f"nrfjprog.sh --erase-all {serial_number}"
        self.logger.debug(cmd)

        proc = Process(cmd=cmd)
        log = proc.get_process_result()
        ret = log

        if not self.__verify_image_flash(log):
            flash_rel = False

        time.sleep(2)

        cmd = shell_path + f"nrfjprog.sh --flash {fw_file} {serial_number}"
        self.logger.debug(cmd)

        proc = Process(cmd=cmd)
        log = proc.get_process_result()
        ret += log

        if not self.__verify_image_flash(log):
            flash_rel = False

        self.logger.debug(ret)
        if result_log_path:
            self.__write_to_log(result_log_path, "nrf52840_flash.log", ret)

        time.sleep(5)

        self.flash_result = flash_rel

        return flash_rel

    def image_flash_efr32(self, serial_number, fw_file, result_log_path=None):
        flash_rel = True
        shell_path = DirectoryPath.get_dir("shell")

        cmd = shell_path + "shell_flash_efr32.sh " + serial_number
        self.logger.debug(cmd)

        proc = Process(cmd=cmd)
        log = proc.get_process_result()

        if not self.__verify_image_flash(log):
            flash_rel = False

        self.logger.debug(log)
        if result_log_path:
            self.__write_to_log(result_log_path, "efr32_flash.log", log)

        time.sleep(5)

        self.flash_result = flash_rel

        return flash_rel

    def __verify_image_flash(self, log):
        for line in log.split("\n"):
            if line.startswith("Script processing completed"):
                return True
        return False

    def __write_to_log(self, file_path, filename, data):
        if not os.path.exists(file_path):
            os.mkdir(file_path)

        with open(os.path.join(file_path, filename), "w") as fn:
            fn.write(data)

    def firmware_update(self, fw_file):
        """
        1. Bring down wpantund and all other processes in the netns
        2. Upgrading firmware
        """
        self.log_info("Firmware file:{}".format(fw_file))

        def do_flash_nrf52840(delegates):
            date_string = datetime.datetime.now().strftime("%b%d%Y_%H_%M_%S")
            result_log_path = LOG_PATH + date_string

            jlink_serial_number = self.device.get_dut_serial()
            self.log_info(jlink_serial_number)

            return self.image_flash_nrf52840(jlink_serial_number, fw_file, result_log_path)

        def do_flash_efr32(delegates):
            date_string = datetime.datetime.now().strftime("%b%d%Y_%H_%M_%S")
            result_log_path = LOG_PATH + date_string

            jlink_serial_number = self.device.get_dut_serial()
            self.log_info(jlink_serial_number)

            return self.image_flash_efr32(jlink_serial_number, fw_file, result_log_path)

        for process in self.netns_pids():
            self.make_system_call_async("firmware-update", "kill -SIGINT %s" % process, None, 1)

        if "nrf52840" in fw_file:
            self.make_function_call_async(do_flash_nrf52840)
        elif "efr32" in fw_file:
            self.make_function_call_async(do_flash_efr32)
        else:
            self.log_critical("Silk does not support the image flashing for {}".format(fw_file))

    @property
    def framing_errors(self):
        return self.wpantund_monitor.framing_errors


#################################
#  Ipv6 methods
#################################

    def find_ip6_address_with_prefix(self, prefix):
        """Find an IPv6 address on node matching a given prefix.
        `prefix` should be an string containing the prefix.
        Returns a string containing the IPv6 address matching the prefix or
        empty string if no address found.
        """
        if len(prefix) > 2 and prefix[-1] == ":" and prefix[-2] == ":":
            prefix = prefix[:-1]
        all_addrs = wpan_table_parser.parse_list(self.get(wpan.WPAN_IP6_ALL_ADDRESSES))
        matched_addr = [addr for addr in all_addrs if addr.startswith(prefix)]
        return matched_addr[0] if len(matched_addr) >= 1 else ""

    def add_ip6_address_on_interface(self, address, prefix_len=64):
        """Adds an IPv6 interface on the network interface.
        `address` should be string containing the IPv6 address.
        `prefix_len` is an `int` specifying the prefix length.
        NOTE: this method uses linux `ip` command.
        """
        interface = self.thread_interface
        cmd = f"ip -6 address add {address}/{prefix_len} dev {interface}"
        result = self.make_netns_call(cmd, 15)

        return result

    def remove_ip6_address_on_interface(self, address, prefix_len=64):
        """Removes an IPv6 interface on the network interface.
        `address` should be string containing the IPv6 address.
        `prefix_len` is an `int` specifying the prefix length.
        NOTE: this method uses linux `ip` command.
        """
        interface = self.thread_interface
        cmd = f"ip -6 address del {address}/{prefix_len} dev {interface}"
        result = self.make_netns_call(cmd, 15)

        return result


class FifteenFourDevBoardThreadNode(FifteenFourDevBoardNode):
    """
    FifteenFourDevBoardNode with added Thread functionality.
    Inheriting classes require sudo
    """

    def data_poll(self):
        self.wpanctl_async("data-poll", "poll", "Polling parent node for IP traffic. . .", 2)

    def set_sleep_poll_interval(self, milliseconds):
        self.wpanctl_async("data-poll", "setprop SleepPollInterval %s" % milliseconds, "", 2)

    def config_gateway(self, prefix):
        output = ["Gateway configured", "Already"]
        search_str_output = "|".join(output)
        self.wpanctl_async("config-gateway", "config-gateway -d %s" % prefix, search_str_output, 1)

    def add_route1(self, prefix, subnet, mac, length):
        ip_addr = silk_ip.assemble(prefix, subnet, mac)
        self.wpanctl_async("add-route", "add-route {0} -l {1}".format(ip_addr, (length // 8)), "Route prefix added.",
                           5)


class ThreadDevBoard(FifteenFourDevBoardThreadNode):
    """
    Class for controlling a Dev Board running Thread
    Requires sudo
    """
    _hw_model = hw_module.HW_NRF52840

    def get_device(self, name=None, sw_version=None):
        """Find an unused dev board, or other hardware.
        """
        try:
            self.device = hw_resource.global_instance().get_hw_module(hw_module.HW_NRF52840,
                                                                      name=name,
                                                                      sw_version=sw_version)
            self.hwModel = hw_module.HW_NRF52840
        except Exception:
            try:
                self.device = hw_resource.global_instance().get_hw_module(hw_module.HW_EFR32,
                                                                          name=name,
                                                                          sw_version=sw_version)
                self.hwModel = hw_module.HW_EFR32
            except Exception as error:
                self.log_critical("Cannot find nRF52840 or efr32 Dev. board!! Error: %s" % error)

        self.device_path = self.device.port()

    def get_unclaimed_device(self, name: str):
        """Get an unclaimed device by name.

        Args:
        name (str): name of the device to create.
        """
        self.device = hw_resource.global_instance().find_hw_module_by_name(name)
        self.hwModel = hw_module.HW_GENERIC
