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

import random

import silk.hw.hw_resource
from silk.config import wpan_constants as wpan
from silk.node import wpan_node


def role_is_thread(role):
    if not isinstance(role, int):
        role = getattr(wpan, "ROLES")[role]
    return role in [2, 3, 4]


class WpantundWpanNode(wpan_node.WpanNode):
    """
    This is the base class for controlling interactions with wpantund. This should provide a flexible overlay that
    can be ported to control Nordic, SiLabs dev boards, and any other dev board connected to a Linux machine
    with wpantund running in network name spaces and any other device that runs wpantund.

    This base class contains all the necessary hooks for calling into wpanctl to configure the NCP and query its
    state information.

    Requirements for inheriting classes:
    1) Must set the _hw_model attribute
    2) Must provide a wpanctl method and wpanctl_async method
    3) Must provide a _get_addr method
    4) Should fully implement the base_node and wpan_node functionality
    5) Must provide self.thread_interface and self.legacy_interface names

    See fifteen_four_dev_board.py for implementation examples of 2 and 3.
    """
    _hw_model = None
    _ip6_lla_regex = "fe80[a-fA-F0-9:]+"
    _ip6_mla_regex = "[fF][dD][a-fA-F0-9:]+"
    _ip6_legacy_ula_regex = "[fF][dD][a-fA-F0-9:]+"
    _ip6_thread_ula_regex = "[fF][dD][a-fA-F0-9:]+"
    _xpanid_regex = "0x[a-fA-F0-9]{16}"

    def wpanctl(self, command, *args, **kwargs):
        """Implemented by inheriting class.
        """
        pass

    def wpanctl_async(self, command, *args, **kwargs):
        """Implemented by inheriting class.
        """
        pass

    def free_device(self):
        """Free up hardware resources consumed by this class.
        """
        silk.hw.hw_resource.global_instance().free_hw_module(self.device)
        self.device = None
        self.device_path = None

    def clear_state(self):
        self.store_data(None, self.role_label)
        self.store_data(None, self.ip6_lla_label)
        self.store_data(None, self.ip6_mla_label)
        self.store_data(None, self.ip6_legacy_ula_label)
        self.store_data(None, self.ip6_thread_ula_label)
        self.store_data(None, self.ping6_sent_label)
        self.store_data(None, self.xpanid_label)
        self.store_data(None, "ping_loss")

    #################################
    #   base_node functionality
    #################################

    def set_up(self):
        pass

    def tear_down(self):
        pass

    def firmware_update(self, fw_file):
        pass

    def reset_thread_radio(self):
        """Perform an NCP soft reset.
        """
        self.wpanctl_async("reset", "reset", "Resetting NCP. . .", 5)
        self.make_system_call_async("reset", "sleep 4; echo done", "done", 20)

    def firmware_version(self):
        """Query the version of the Thread/ConnectIP stack running on the NCP.
        """

        return self.getprop("NCPVersion")

    #################################
    #   wpan_MAC Filter functionality
    #################################

    def allowlist_node(self, item):
        """Adds a given item (a node or mac address) to the allowlist of `self`
        and enables allowlisting on `self`.
        """
        if isinstance(item, str):
            self.add(wpan.WPAN_MAC_ALLOWLIST_ENTRIES, item)
        else:
            self.add(wpan.WPAN_MAC_ALLOWLIST_ENTRIES,
                     item.get(wpan.WPAN_EXT_ADDRESS)[1:-1])
        self.set(wpan.WPAN_MAC_ALLOWLIST_ENABLED, "1")

    def un_allowlist_node(self, item):
        """Removes a given item (a node or mac address) from the allowlist.
        """
        if isinstance(item, str):
            self.remove(wpan.WPAN_MAC_ALLOWLIST_ENTRIES, item)
        else:
            self.remove(wpan.WPAN_MAC_ALLOWLIST_ENTRIES,
                        item.get(wpan.WPAN_EXT_ADDRESS)[1:-1])

    #################################
    #   wpan_node functionality
    #################################

    def form(self, network, role, xpanid=None, panid=None, mesh_local_prefix=None, add_ip_addr=True):
        """
        Form the PAN specified by the arguments.
        Args:
            network (object): Stores network credentials {fabric_id, xpanid, psk, name, channel, panid}.
            role (str): role for the node.
            xpanid (str, optional): used to set specific xpanid. Defaults to None.
            panid (int, optional): used to set specific panid. Defaults to None.
            mesh_local_prefix (str, optional): used to set mesh local prefix. Defaults to None.
            add_ip_addr (boolean, optional): used to specify if ip addresses should be added by default
                                             on the nodes during setup process. Defaults to True.
        """

        self.store_data(network.fabric_id, "fabric-id")

        command = "setprop Network:Key --data %s" % network.psk

        self.wpanctl_async("form", command, None, 1)

        role = getattr(wpan, "ROLES")[role]
        self.store_data(role, self.role_label)

        command = "form {} -T {}".format(network.name, role)

        command += " -c {}".format(network.channel)

        if xpanid:
            command += " -x {}".format(xpanid)
        if panid:
            command += " -p {}".format(hex(panid))
        if mesh_local_prefix:
            command += " -M {}".format(mesh_local_prefix)

        self.wpanctl_async("form", command, "Successfully formed!", 60)

        self.__get_network_properties("form", network)

        if add_ip_addr:
            self._get_addr("form")

    def join(self, network, role, add_ip_addr=True):
        """Tell the NCP to join the PAN specified by the commissioning data.

        The Network Key should always be set prior to a join attempt.
        Args:
            network (object): Stores network credentials {fabric_id, xpanid, psk, name, channel, panid}.
            role (str): role for the node.
            add_ip_addr (boolean, optional): used to specify if ip addresses should be added by default
                                             on the nodes during setup process. Defaults to True.
        """

        self.store_data(network.fabric_id, "fabric-id")

        self.store_data(network.xpanid, self.xpanid_label)

        command = "setprop Network:Key --data %s" % network.psk

        self.wpanctl_async("join", command, None, 1)

        role = getattr(wpan, "ROLES")[role]
        self.store_data(role, self.role_label)

        join_command = "join %s -T %s -c %s -x %s -p 0x%x" % \
            (network.name, role, network.channel, network.xpanid, network.panid)

        self.wpanctl_async("join", join_command, "Successfully Joined!", 60)

        self.__get_network_properties("join", network)

        if add_ip_addr:
            self._get_addr("join")

    def provisional_join(self, network, role):
        """Perform an insecure join and then set the network key.
        """
        self.store_data(network.fabric_id, "fabric-id")

        self.store_data(network.xpanid, self.xpanid_label)

        role = getattr(wpan, "ROLES")[role]
        self.store_data(role, self.role_label)

        join_command = "join %s -T %s -c %s -x %s -p 0x%x" % \
            (network.name, role, network.channel, network.xpanid, network.panid)

        # Join to provisionally-joined state
        self.wpanctl_async("join", join_command,
                           r"Partial \(insecure\) join. Credentials needed. Update key to continue.", 30)

        command = "setprop Network:Key --data %s" % network.psk

        self.wpanctl_async("join", command, None, 1)

        self.query_association_state_delayed(5, "associated")

        self.__get_network_properties("join", network)

        self._get_addr("join")

    def join_node(self, network, role, should_set_key=True):
        """Join a network specified by another node based on should_set_key parameter.
           Perform an insecure join in case should_set_key=False.
        """
        self.store_data(network.fabric_id, "fabric-id")

        self.store_data(network.xpanid, self.xpanid_label)

        role = getattr(wpan, "ROLES")[role]
        self.store_data(role, self.role_label)

        join_command = "join %s -T %s -c %s -x %s -p 0x%x" % \
            (network.name, role, network.channel, network.xpanid, network.panid)

        if should_set_key:
            command = "setprop Network:Key --data %s" % network.psk
            self.wpanctl_async("join", command, None, 1)
            self.wpanctl_async("join", join_command, "Successfully Joined!", 60)

        else:
            self.wpanctl_async("join", join_command,
                               r"Partial \(insecure\) join. Credentials needed. Update key to continue.", 30)

        self._get_addr("join")

    def __get_network_properties(self, action, network):
        """Extract channel, PANID, XPANID, node type, and network key.
        """
        self.wpanctl_async(action, "getprop channel", " [0-9]{2}$", 20, self.channel_label)
        self.wpanctl_async(action, "getprop panid", "0x[0-9a-fA-F]{4}$", 20, self.panid_label)
        self.wpanctl_async(action, "getprop xpanid", "0x[a-fA-F0-9]{16}$", 20, self.xpanid_label)

        self.wpanctl_async(action, "get IPv6:LinkLocalAddress", self._ip6_lla_regex, 20, self.ip6_lla_label)
        self.wpanctl_async(action, "get IPv6:MeshLocalAddress", self._ip6_mla_regex, 20, self.ip6_mla_label)

        self.wpanctl_async(action, "getprop Network:Key", r"\[[0-9a-fA-F]{32}\]", 20, self.psk_label)

        self.wpanctl_async(action, "status", "AllowingJoin", 20)

    def leave(self):
        """Tell the NCP to leave its current PAN.
        """
        self.wpanctl_async("leave", "leave", "Leaving current WPAN. . .", 60)
        self.clear_state()

    def resume(self):
        """Tell the NCP to resume.
        """
        self.wpanctl_async("resume", "resume", "Resuming saved WPAN. . .", 10)

    def permit_join(self, period=None):
        """Tell the NCP to allow joining for period seconds.
        """
        if not period:
            period = 240
        self.wpanctl_async("permit-join", "setprop OpenThread:SteeringData:SetWhenJoinable true", "", 5)
        self.wpanctl_async("permit-join", "permit-join %s" % period, "Permitting Joining on the current WPAN", 10)

    def permit_join_new(self, duration_sec=None, port=None, udp=True, tcp=True):
        if not udp and not tcp:  # incorrect use!
            return ""
        traffic_type = ""
        if udp and not tcp:
            traffic_type = " --udp"
        if tcp and not udp:
            traffic_type = " --tcp"
        if port is not None and duration_sec is None:
            duration_sec = "240"

        return self.wpanctl(
            "permit-join", "permit-join" + (" {}".format(duration_sec) if duration_sec is not None else "") +
            (" {}".format(port) if port is not None else "") + traffic_type, 5)

    def perform_active_scan(self, channel=None):
        """Tell the NCP to scan for other networks.
        Return the list of other networks that have been seen.
        """
        self.wpanctl_async("scan", "scan", None, 20)

    def get_active_scan(self, channel=None):
        """Scan and Return list of other networks that have been seen.
        """
        if channel:
            output = self.wpanctl("scan", "scan -c {}".format(channel), 20)
        else:
            output = self.wpanctl("scan", "scan ", 20)
        print(output)
        return output

    def get_energy_scan(self, channel=None):
        if channel:
            output = self.wpanctl("scan", "scan -e -c {}".format(channel), 20)
        else:
            output = self.wpanctl("scan", "scan -e", 20)
        return output

    def get_discover_scan(self, channel=None, joiner_only=False, enable_filtering=False, panid_filter=None):
        cmd = "scan -d " + (" -c {}".format(channel) if channel else "") + (" -j" if joiner_only else "")
        cmd += (" -f" if enable_filtering else "") + (" -p {}".format(panid_filter) if panid_filter else "")
        return self.wpanctl("scan", cmd, 20)

    def config_gateway1(self, prefix, default_route=False, priority=None):
        return self.wpanctl(
            "config-gateway", "config-gateway " + prefix + (" -d" if default_route else "") +
            (" -P {}".format(priority) if priority is not None else ""), 20)

    def add_prefix(self,
                   prefix,
                   prefix_len=None,
                   priority=None,
                   stable=True,
                   on_mesh=False,
                   slaac=False,
                   dhcp=False,
                   configure=False,
                   default_route=False,
                   preferred=False):

        return self.wpanctl(
            "add-prefix", "add-prefix " + prefix + (" -l {}".format(prefix_len) if prefix_len is not None else "") +
            (" -P {}".format(priority) if priority is not None else "") + (" -s" if stable else "") +
            (" -f" if preferred else "") + (" -a" if slaac else "") + (" -d" if dhcp else "") +
            (" -c" if configure else "") + (" -r" if default_route else "") + (" -o" if on_mesh else ""), 20)

    def remove_prefix(self, prefix, prefix_len=None):
        return self.wpanctl(
            "remove-prefix",
            "remove-prefix " + prefix + (" -l {}".format(prefix_len) if prefix_len is not None else ""), 20)

    def add_route_using_prefix(self, route_prefix, prefix_len=None, priority=None, stable=True):
        """route priority [(>0 for high, 0 for medium, <0 for low)].
        """
        return self.wpanctl(
            "add-route",
            "add-route " + route_prefix + (" -l {}".format(prefix_len) if prefix_len is not None else "") +
            (" -p {}".format(priority) if priority is not None else "") + ("" if stable else " -n"), 20)

    def remove_route(self, route_prefix, prefix_len=None, priority=None, stable=True):
        """route priority [(>0 for high, 0 for medium, <0 for low)].
        """
        return self.wpanctl(
            "remove-route",
            "remove-route " + route_prefix + (" -l {}".format(prefix_len) if prefix_len is not None else "") +
            (" -p {}".format(priority) if priority is not None else ""), 20)

    #################################
    #   Calls into wpanctl for commissioning process in commissioner-joiner model
    #################################

    def commissioner_start(self):
        self.wpanctl_async("commissioner start", "commissioner start", "Commissioner started", 20)

    def commissioner_add_joiner(self, eui64, pskd, timeout="100"):
        cmd = "commissioner joiner-add {} {} {}".format(eui64, timeout, pskd)
        return self.wpanctl("commissioner add-joiner", cmd, 20)

    def commissioner_add_joiner_with_discerner(self, discerner_value, discerner_bit_len, pskd, timeout='100'):
        cmd = f"commissioner joiner-add-discerner {discerner_value} {discerner_bit_len} {timeout} {pskd}"
        return self.wpanctl("commissioner add joiner with discerner", cmd, 20)

    def joiner_join(self, pskd):
        return self.wpanctl("joiner-join", "joiner --join {}".format(pskd), 60)

    def joiner_attach(self):
        return self.wpanctl("joiner-attach", "joiner --attach", 20)

    #################################
    #   Calls into wpanctl for querying commissioning data
    #################################

    def setprop(self, key, value, data=False):
        """
        Make a call into wpanctl setprop to set the desired parameter.
        """
        if not data:
            output = self.wpanctl("setprop", "setprop %s %s" % (key, value), 2)
        else:
            output = self.wpanctl("setprop", "setprop %s --data %s" % (key, value), 2)
        return output

    def getprop(self, property_name):
        """
        Make a call into wpanctl getprop to query the desired parameter.
        """
        prop = self.wpanctl("getprop", "getprop %s" % property_name, 2)
        return prop.split("=")[1].strip() if "=" in prop else prop

    def get(self, prop_name, value_only=True):
        if value_only:
            output = self.wpanctl("getprop", "getprop -v %s" % prop_name, 2)
        else:
            output = self.wpanctl("getprop", "getprop  %s" % prop_name, 2)
        return output.strip()

    def set(self, prop_name, value, binary_data=False):
        return self._update_prop("set", prop_name, value, binary_data)

    def add(self, prop_name, value, binary_data=False):
        return self._update_prop("add", prop_name, value, binary_data)

    def remove(self, prop_name, value, binary_data=False):
        return self._update_prop("remove", prop_name, value, binary_data)

    def _update_prop(self, action, prop_name, value, binary_data):
        return self.wpanctl(action, action + " " + prop_name + " " + ("-d " if binary_data else "") + "-v " + value,
                            2)  # use -v to handle values starting with `-`.

    #################################
    #   Ping functionality
    #################################

    def ping6(self, ipv6_target, num_pings, payload_size=8, interface=None):
        """Perform ping6 to ipv6_target.

        Enable ping6_sent and ping6_received functionality.

        Make the ping call and store the % loss. Also store the number of pings sent.
        """

        command = "ping6"

        if interface == "legacy":
            command += " -I %s" % self.legacy_interface
        else:
            command += " -I %s" % self.thread_interface

        command += " %s -c %s -s %s -W 10" % (ipv6_target, num_pings, payload_size)

        search_string = r"(?P<%s>[\d]+) packets transmitted, (?P<%s>[\d]+) received" \
            % (self.ping6_sent_label, self.ping6_received_label)

        fields = [self.ping6_sent_label, self.ping6_received_label]

        self.make_netns_call_async(command, search_string, num_pings * 2 + 1, field=fields)

    def timed_ping6(self, ipv6_target, num_pings, payload_size=8, interface=None):
        """Perform ping6 to ipv6_target.

        Store the average ping time
        """

        command = "ping6"

        if interface == "legacy":
            command += " -I %s" % self.legacy_interface
        else:
            command += " -I %s" % self.thread_interface

        command += " %s -c %s -s %s -W 2" % (ipv6_target, num_pings, payload_size)

        search_string = r"rtt min/avg/max/mdev = \d+\.\d+/(?P<%s>\d+\.\d+)/\d+\.\d+/\d+\.\d+ ms" \
                % self.ping6_round_trip_time_label

        fields = [self.ping6_round_trip_time_label]

        self.make_netns_call_async(command, search_string, num_pings * 2 + 1, field=fields)

    #################################
    #   UDP functionality
    #################################

    def send_udp_data(self, target: str, port: int, message: str, source: str = None,
                      src_port: int = random.randint(11200, 11400), hop_limit: int = 64, timeout: float = 10):
        """Perform netcat command to send UDP message to ipv6_target via port.

        Args:
            target (str): target address.
            port (int): target port.
            message (str): message to send.
            source (str, optional): source address. Defaults to None.
            src_port (int, optional): source port. Defaults to random port between 11200 and 11400.
            hop_limit (int, optional): packet hop limit. Defaults to 64.
            timeout (float, optional): timeout for waiting for the async call output. Defaults to 10.
        """
        source_clause = f"-s {source}" if source else ""
        command = f"nc -6u -M {hop_limit} -p {src_port} {source_clause} {target} {port} <<< \"{message}\""
        self.make_netns_call(command, timeout)

    def receive_udp_data(self, port: int, message: str, timeout: int = 10):
        """Perform netcat command to receive expected UDP message from port.

        Args:
            port (int): target listening port.
            message (str): message to expect.
            timeout (int, optional): timeout for waiting for the async call output. Defaults to 10.
        """
        command = f"nc -6lu {port}"

        self.make_netns_call_async(command, message, timeout=timeout, exact_match=True)
