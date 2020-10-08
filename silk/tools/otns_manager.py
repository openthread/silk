# Copyright 2020 Google LLC
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
"""OTNS integration manager.

This class manages the communication between a Silk test case and the OTNS
dispatcher, for visualization purposes.
"""

from datetime import datetime
import enum
import logging
import math
import re
import socket
import struct
from typing import Dict, List, Tuple

import grpc
import pandas

from silk.hw.hw_module import HwModule
from silk.node.fifteen_four_dev_board import ThreadDevBoard
from silk.tools.pb import visualize_grpc_pb2
from silk.tools.pb import visualize_grpc_pb2_grpc
from silk.utils import signal
from silk.utils.network import get_local_ip

DATE_FORMAT = "%Y-%m-%d %H:%M:%S,%f"

GRPC_SERVER_PORT = 8999
SERVER_PORT = 9000


class RegexType(enum.Enum):
    """Regular expression collections.
    """
    START_WPANTUND_REQ = r"Starting wpantund .* ip netns exec"
    START_WPANTUND_RES = r"wpantund\[(\d+)\]: Starting wpantund"
    STOP_WPANTUND_REQ = r"sudo ip netns del"
    GET_EXTADDR_REQ = r"getprop -v NCP:ExtendedAddress"
    GET_EXTADDR_RES = r"\[stdout\] \[([A-Fa-f0-9]{16})\]"
    STATUS = r"wpantund\[(\d+)\]: NCP => .*\[OTNS\] ([\w\d]+=[A-Fa-f0-9,rsdn]+)"
    EXTADDR_STATUS = r"extaddr=([A-Fa-f0-9]{16})"
    ROLE_STATUS = r"role=([0-4])"
    CHILD_ADDED_STATUS = r"child_added=([A-Fa-f0-9]{16})"
    CHILD_REMOVED_STATUS = r"child_removed=([A-Fa-f0-9]{16})"
    ROUTER_ADDED_STATUS = r"router_added=([A-Fa-f0-9]{16})"
    ROUTER_REMOVED_STATUS = r"router_removed=([A-Fa-f0-9]{16})"
    NCP_VERSION = r"NCP is running \"(.*)\""


class EventType(enum.Enum):
    ALARM_FIRED = 0
    RADIO_RECEIVED = 1
    UART_WRITE = 2
    RADIO_SPINEL_WRITE = 3
    OTNS_STATUS_PUSH = 5
    DATA_MAX_SIZE = 1024


class RoleType(enum.Enum):
    DISABLED = 0
    DETACHED = 1
    CHILD = 2
    ROUTER = 3
    LEADER = 4


class GRpcClient:
    """gRPC client that interacts with OTNS server's gRPC services.

    Attributes:
        server_addr (str): address of the gRPC server.
        channel (grpc.Channel): gRPC channel.
        stub (VisualizeGrpcServiceStub): gRPC stub that references the visualization gRPC service.
        logger (Logger): logger for the client class.
    """

    def __init__(self, server_addr: str, logger: logging.Logger):
        """Initializes a gRPC client.

        Args:
            server_addr (str): the address of the gRPC server.
            logger (logging.Logger): logger for the class.
        """
        logger.debug(f"Starting gRPC client with address {server_addr}")
        self.server_addr = server_addr
        self.channel = grpc.insecure_channel(self.server_addr)
        self.stub = visualize_grpc_pb2_grpc.VisualizeGrpcServiceStub(self.channel)
        self.logger = logger

    def wait_for_channel_ready(self, timeout: int = 10):
        """Blocking method that waits for the gRPC channel to be ready.

        Args:
            timeout (int, optional): wait timeout. Defaults to 10.
        """
        grpc.channel_ready_future(self.channel).result(timeout=timeout)

    def _send_command(self, command: str):
        """Send a Command gRPC request.

        Args:
            command (str): command content.
        """
        self.logger.info(f"Sending cmd: {command}")
        response = self.stub.Command(visualize_grpc_pb2.CommandRequest(command=command))
        self.logger.info(f"Sent cmd: {command}, resp: {response}".rstrip("\n"))

    def set_title(self, title: str, x=0, y=20, font_size=20):
        """Send test title to OTNS.

        Args:
            title (str): test title.
            x (int): x position of title.
            y (int): y position of title.
            font_size (int): font size of title.
        """
        self._send_command(f"title \"{title}\" x {x} y {y} fs {font_size}")

    def set_speed(self, speed: float):
        """Send test replay speed to OTNS.

        Args:
            speed (float): test replay speed.
        """
        self._send_command(f"speed {speed}")

    def set_netinfo(self, version: str = None, commit: str = None):
        """Set OTNS netinfo.

        Args:
            version (str, optional): version string. Default to None.
            commit (str, optional): commit string. Default to None.
        """
        version_clause = f"version \"{version}\"" if version is not None else ""
        commit_clause = f"commit \"{commit}\"" if commit is not None else ""
        self._send_command(f"netinfo {version_clause} {commit_clause} real y")

    def add_node(self, x: int, y: int, node_id: int):
        """Sends an add node request.

        Args:
            x (int): x coordinate of the new node.
            y (int): y coordinate of the new node.
            node_id (int): node ID of the new node.
        """
        self._send_command(f"add router x {x} y {y} id {node_id}")

    def move_node(self, node_id: int, x: int, y: int):
        """Sends a move node request async.

        Args:
            node_id (int): node ID of the node to be moved.
            x (int): new x coordinate of the node.
            y (int): new y coordinate of the node.
        """
        self._send_command(f"move {node_id} {x} {y}")

    def delete_node(self, node_id: int):
        """Sends a delete node request.

    Args:
      node_id (int): node ID of the node to be deleted.
    """
        self._send_command(f"del {node_id}")


class Event:
    """Class that represents an event.

    Class represents a UDP message that OTNS interprets as an event.

    Attributes:
        delay (int): alarm delay in ns.
        event (EventType): type of the event.
        data (bytes): message data of the event.
        length (int): length of data.
    """

    def __init__(self, data: bytes, event: EventType, delay=0):
        """Initializes an event.

        Args:
            data (bytes): data bytes.
            event (EventType): type of the event.
            delay (int, optional): alarm delay in us. Defaults to 0 for non-alarm events.
        """
        self.delay = delay
        self.event = event.value
        self.data = data
        self.length = len(self.data)

    @staticmethod
    def status_event(message: str):
        """Creates a status event.

        Args:
            message (str): status event message string.

        Returns:
            Event: a status event object with the message encoded into bytes.
        """
        return Event(data=message.encode("ascii"), event=EventType.OTNS_STATUS_PUSH)

    @staticmethod
    def alarm_event(delay=1):
        """Creates an alarm event.

        Args:
            delay (int, optional): alarm delay in us. Defaults to 1.

        Returns:
            Event: an alarm event object with empty data.
        """
        return Event(data=b"", delay=delay, event=EventType.ALARM_FIRED)

    def to_bytes(self) -> bytes:
        """Convert the event to bytes, to be sent as a UDP message.

        The message format follows the OTNS event UDP format:
            <: little-endian, standard size, no alignment.
            Q: unsigned long long: 8 bytes. Corresponding to event's delay field in uint64_t.
            B: unsigned char: 1 byte. Corresponding to event's event field in uint8_t.
            H: unsigned short: 2 bytes. Corresponding to event's data length field in uint16_t.
        The data follows the header as defined above.

        Returns:
            bytes: converted message bytes.
        """
        return struct.pack("<QBH", self.delay, self.event, self.length) + self.data

    @staticmethod
    def from_bytes(event_bytes: bytes):
        """Unpack a UDP message into an Event object.

        Args:
            event_bytes (bytes): packed UDP message bytes.

        Returns:
            Event: a status event object with the message decoded from bytes.
        """
        delay, event, length = struct.unpack("<QBH", event_bytes[:11])
        data = event_bytes[11:]
        return Event(data, EventType(event), delay)

    @property
    def message(self) -> str:
        """Get the event message string.

        Returns:
            str: event message string.
        """
        return self.data.decode("ascii")


class OtnsNode(object):
    """Class that represents a Thread network node for OTNS integration.

    Attributes:
        node_id (int): ID of the node.
        dut_serial (str): DUT serial of the node.
        vis_x (int): visualization x coordinate.
        vis_y (int): visualization y coordinate.
        sock (socket): UDP socket to send message from.
        source_addr (str, int): UDP source address.
        dest_addr (str, int): UDP destination address.

        grpc_client (GRpcClient): gRPC client instance from the manager.
        logger (logging.Logger): logger for the node.
        node_on_otns (bool): if the node has been reported to OTNS.

        extaddr(int): extended address of the node in network.
        role(RoleType): role of the node in network.
        children (List[int]): extended addresses of children.
        neighbors (List[int]): extended addresses of neighbors.
    """

    def __init__(self, node_id: int, dut_serial: str, vis_x: int, vis_y: int, local_host: str, server_host: str,
                 server_port: int, grpc_client: GRpcClient, logger: logging.Logger):
        """Initialize a node.

        Args:
            node_id (int): ID of the node.
            dut_serial (str): DUT serial of the node.
            vis_x (int): visualization x coordinate.
            vis_y (int): visualization y coordinate.
            local_host (str): host address of this machine.
            server_host (str): host address of the OTNS dispatcher.
            server_port (int): port number of the OTNS dispatcher.
            grpc_client (GRpcClient): gRPC client instance from the manager.
            logger (logging.Logger): logger for the node.
        """
        assert node_id > 0

        self.node_id = node_id
        self.dut_serial = dut_serial

        self.logger = logger

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.source_addr = (local_host, server_port + node_id)
        self.dest_addr = (server_host, server_port)
        self.logger.debug("Node {:d} socket from {:s}:{:d} to {:s}:{:d}".format(self.node_id, self.source_addr[0],
                                                                                self.source_addr[1], self.dest_addr[0],
                                                                                self.dest_addr[1]))
        self.sock.bind(self.source_addr)

        self.vis_x = vis_x
        self.vis_y = vis_y
        self.grpc_client = grpc_client

        self.extaddr = node_id
        self.role = RoleType.DISABLED
        self.children = set()
        self.neighbors = set()

        self.node_on_otns = False

    def bind_socket(self):
        """Bind socket to the address.
        """
        self.sock.bind(self.source_addr)

    def close_socket(self):
        """Close the node's socket connection.
        """
        self.sock.close()

    def send_event(self, event_packet: bytes):
        """Send event bytes packet.

        Args:
            event_packet (bytes): packaged event content in bytes.
        """
        self.sock.sendto(event_packet, self.dest_addr)

    def send_extaddr_event(self):
        """Send extaddr event.
        """
        event = Event.status_event(f"extaddr={self.extaddr:016x}")
        self.logger.debug(f"Node {self.node_id} sending extaddr={self.extaddr:016x}")
        self.send_event(event.to_bytes())

    def send_dut_serial_event(self):
        """Send DUT serial event.
        """
        event = Event.status_event(f"dut_serial={self.dut_serial}")
        self.logger.debug(f"Node {self.node_id} sending dut_serial={self.dut_serial}")
        self.send_event(event.to_bytes())

    def send_role_event(self):
        """Send role event.
        """
        event = Event.status_event(f"role={self.role.value:1d}")
        self.logger.debug(f"Node {self.node_id} sending role={self.role.value:1d}")
        self.send_event(event.to_bytes())

    def send_child_added_event(self, child_addr: int):
        """Send child added event.

        Args:
            child_addr (str): extended address of the child that is added to this node.
        """
        event = Event.status_event(f"child_added={child_addr:016x}")
        self.send_event(event.to_bytes())

    def send_child_removed_event(self, child_addr: int):
        """Send child removed event.

        Args:
            child_addr (str): extended address of the child that is removed from this node.
        """
        event = Event.status_event(f"child_removed={child_addr:016x}")
        self.send_event(event.to_bytes())

    def send_router_added_event(self, router_addr: int):
        """Send router added event.

        Args:
            router_addr (str): extended address of the router that is added to  the neighbor list of this node.
        """
        event = Event.status_event(f"router_added={router_addr:016x}")
        self.send_event(event.to_bytes())

    def send_router_removed_event(self, router_addr: int):
        """Send router removed event.

        Args:
            router_addr (str): extended address of the router that is removed from the neighbor list of this node.
        """
        event = Event.status_event(f"router_removed={router_addr:016x}")
        self.send_event(event.to_bytes())

    def update_extaddr(self, extaddr: int):
        """Update the node's extended address.

        Args:
            extaddr (int): new extended address of the node.
        """
        if extaddr != self.extaddr:
            self.extaddr = extaddr
            self.send_extaddr_event()

    def update_role(self, role: RoleType):
        """Update the node's role.

        Args:
            role (RoleType): new role of the node.
        """
        if role != self.role:
            self.role = role
            self.send_role_event()

    def add_child(self, child_addr: int):
        """Add a node as a child of this node.

        Args:
            child_addr (int): extended address of the child to add.
        """
        if child_addr not in self.children:
            self.children.add(child_addr)
            self.send_child_added_event(child_addr)

    def remove_child(self, child_addr: int):
        """Remove a child node of this node.

        Args:
            child_addr (int): extended address of the child to remove.
        """
        if child_addr in self.children:
            self.children.remove(child_addr)
            self.send_child_removed_event(child_addr)

    def add_router(self, router_addr: int):
        """Add a router node as a neighbor of this node.

        Args:
            router_addr (int): extended address of the router to add.
        """
        if router_addr not in self.neighbors:
            self.neighbors.add(router_addr)
            self.send_router_added_event(router_addr)

    def remove_router(self, router_addr: int):
        """Remove a child node of this node.

        Args:
            router_addr (int): extended address of the router to remove.
        """
        if router_addr in self.neighbors:
            self.neighbors.remove(router_addr)
            self.send_router_removed_event(router_addr)

    def create_otns_node(self):
        """Call gRPC client to create a node on server for itself.
        """
        if self.node_on_otns:
            self.logger.debug(f"Node {self.node_id} already on OTNS while trying to create")
            return
        self.logger.debug(f"Adding node {self.node_id} to OTNS at ({self.vis_x},{self.vis_y})")
        self.grpc_client.add_node(self.vis_x, self.vis_y, self.node_id)
        self.send_extaddr_event()
        self.send_dut_serial_event()
        self.node_on_otns = True

    def delete_otns_node(self):
        """Call gRPC client to remove the node on server for itself.
        """
        if not self.node_on_otns:
            self.logger.debug(f"Node {self.node_id} not on OTNS while trying to delete")
            return
        self.logger.debug(f"Deleting node {self.node_id} on OTNS")
        self.grpc_client.delete_node(self.node_id)
        self.node_on_otns = False

    def update_otns_vis_position(self):
        """Call gRPC client to update the node's visualization position.
        """
        self.logger.debug(f"Moving node {self.node_id} to OTNS at ({self.vis_x},{self.vis_y})")
        self.grpc_client.move_node(self.node_id, self.vis_x, self.vis_y)

    def update_vis_position(self, x: int, y: int):
        if x != self.vis_x or y != self.vis_y:
            self.vis_x = x
            self.vis_y = y
            self.update_otns_vis_position()


class WpantundOtnsMonitor(signal.Subscriber):
    """OTNS log monitor for wpantund process logs.

    Attributes:
        node (OtnsNode): OTNS node instance that handles UDP messaging.
        otns_manager (OtnsManager): OTNS manager instance the monitor was created from.
    """

    def __init__(self, publisher: signal.Publisher, node: OtnsNode, otns_manager: "OtnsManager"):
        """Initialize a wpantund monitor.

        Args:
            publisher (signal.Publisher): wpantund process.
            node (OtnsNode): node the wpantund process is attached to.
            otns_manager (OtnsManager): the OTNS manager this monitor belongs to.
        """
        super().__init__(publisher)
        self.node = node
        self.otns_manager = otns_manager

    def process_log_line(self, line: str):
        """Process a single line of wpantund log.

        Args:
            line (str): line of log to process.
        """
        if self.otns_manager:
            self.otns_manager.update_status(self.node, line)

    def subscribe_handle(self, sender, **kwargs):
        """Handle messages from Publisher, a wpantund process.

        Args:
            sender (signal.Publisher): publisher of signal.
            **kwargs (str): published signal.
        """
        line = kwargs["line"]
        self.process_log_line(line)


class OtnsNodeSummary(object):
    """OTNS history summary for a node.

    Attributes:
        node_id (int): ID of the node.
        extaddr_history (List[Tuple[datetime, int]]): history of extaddr.
        role_history (List[Tuple[datetime, RoleType]]): history of the node's role.
        children_history (List[Tuple[datetime, bool, int]]): history of the node's children.
        neighbors_history (List[Tuple[datetime, bool, int]]): history of the node's neighbors.
    """

    def __init__(self, node_id: int):
        """Initialize a summary object for an OTNS node.

        Args:
            node_id (int): ID of the node.
        """
        self.node_id = node_id

        self.extaddr_history = []
        self.role_history = []
        self.children_history = []
        self.neighbors_history = []

    def extaddr_changed(self, extaddr: int, time=datetime.now()):
        """Add an entry to the node's extended address history.

        Args:
            extaddr (int): new extended address of node.
            time (datetime.datetime, optional): time of the change. Defaults to datetime.now().
        """
        if not self.extaddr_history or self.extaddr_history[-1][1] != extaddr:
            self.extaddr_history.append((time, extaddr))

    def role_changed(self, role: RoleType, time=datetime.now()):
        """Add an entry to the node's role history.

        Args:
            role (RoleType): new role of node.
            time (datetime.datetime, optional): time of the change. Defaults to datetime.now().
        """
        if not self.role_history or self.role_history[-1][1] != role:
            self.role_history.append((time, role))

    def child_changed(self, added: bool, child: int, time=datetime.now()):
        """Add an entry to the node's children history.

        Args:
            added (bool): True if the child is added; False if removed.
            child (int): extended address of the child.
            time (datetime.datetime, optional): time of the change. Defaults to datetime.now().
        """
        self.children_history.append((time, added, child))

    def neighbor_changed(self, added: bool, neighbor: int, time=datetime.now()):
        """Add an entry to the node's neighbors history.

        Args:
            added (bool): True if the neighbor is added; False if removed.
            neighbor (int): extended address of the neighbor.
            time (datetime.datetime, optional): time of the change. Defaults to datetime.now().
        """
        self.neighbors_history.append((time, added, neighbor))

    def format_extaddr_history(self) -> List[Tuple[datetime, str]]:
        """Format this summary's extaddr history and return the list.

        Returns:
            List[Tuple[datetime, str]]: list of extaddr history, in the format of a tuple containing
                the time of the event and the formatted string.
        """
        return [(time, f"extaddr {extaddr:016x}") for time, extaddr in self.extaddr_history]

    def format_role_history(self) -> List[Tuple[datetime, str]]:
        """Format this summary's role history and return the list.

        Returns:
            List[Tuple[datetime, str]]: list of role history, in the format of a tuple containing
                the time of the event and the formatted string.
        """
        return [(time, f"role {role.name}") for time, role in self.role_history]

    def format_children_history(self, extaddr_map: Dict[int, int]) -> List[Tuple[datetime, str]]:
        """Format this summary's children history and return the list.

        Args:
            extaddr_map (Dict[int, int]): table mapping extaddr to node ID.

        Returns:
            List[Tuple[datetime, str]]: list of children history, in the format of a tuple containing
                the time of the event and the formatted string.
        """
        history = []
        for time, added, child in self.children_history:
            action = "added" if added else "removed"
            if child in extaddr_map:
                child_repr = f"{action} child node {extaddr_map[child]:d}"
            else:
                child_repr = f"{action} child extaddr {child:016x}"
            history.append((time, f"{child_repr}"))
        return history

    def format_neighbors_history(self, extaddr_map: Dict[int, int]) -> List[Tuple[datetime, str]]:
        """Format this summary's neighbors history and return the list.

        Args:
            extaddr_map (Dict[int, int]): table mapping extaddr to node ID.

        Returns:
            List[Tuple[datetime, str]]: list of neighbors history, in the format of a tuple containing
                the time of the event and the formatted string.
        """
        history = []
        for time, added, neighbor in self.neighbors_history:
            action = "added" if added else "removed"
            if neighbor in extaddr_map:
                neighbor_repr = f"{action} neighbor node {extaddr_map[neighbor]}"
            else:
                neighbor_repr = f"{action} neighbor extaddr {neighbor:016x}"
            history.append((time, f"{neighbor_repr}"))
        return history

    def to_string(self, extaddr_map: Dict[int, int]) -> str:
        """Generate summary string.

        Args:
            extaddr_map (Dict[int, int]): table mapping extaddr to node ID.

        Returns:
            str: string representation of the summary.
        """
        lines = [f"OTNS Summary for node {self.node_id}"]

        if self.extaddr_history:
            lines.append("Extended address changes:")
            lines.extend([f"[{h[0].strftime(DATE_FORMAT)[:-3]}] {h[1]}" for h in self.format_extaddr_history()])

        if self.role_history:
            lines.append("Role changes:")
            lines.extend([f"[{h[0].strftime(DATE_FORMAT)[:-3]}] {h[1]}" for h in self.format_role_history()])

        if self.children_history:
            lines.append("Children changes:")
            lines.extend(
                [f"[{h[0].strftime(DATE_FORMAT)[:-3]}] {h[1]}" for h in self.format_children_history(extaddr_map)])

        if self.neighbors_history:
            lines.append("Neighbors changes:")
            lines.extend(
                [f"[{h[0].strftime(DATE_FORMAT)[:-3]}] {h[1]}" for h in self.format_neighbors_history(extaddr_map)])

        return "\n".join(lines)

    def to_log_list(self, extaddr_map: Dict[int, int]) -> List[Tuple[datetime, str]]:
        """Generate summary logs list.

        Args:
            extaddr_map (Dict[int, int]): table mapping extaddr to node ID.

        Returns:
            List[Tuple[datetime, str]]: list of node's history, in the format of a tuple containing the time
                of the event and the log-formatted string.
        """
        return (self.format_extaddr_history() + self.format_role_history() +
                self.format_children_history(extaddr_map) + self.format_neighbors_history(extaddr_map))


class OtnsNodeSummaryCollection(object):
    """A collection of OtnsNodeSummary that supports printing events ordered by time.

    Args:
        collection (List[OtnsNodeSummary]): list of OtnsNodeSummary.
    """

    def __init__(self, collection: List[OtnsNodeSummary]):
        self.collection = collection

    def to_string(self, extaddr_map: Dict[int, int]) -> str:
        """Generate summary string.

        Args:
            extaddr_map (Dict[int, int]): table mapping extaddr to node ID.

        Returns:
            str: string representation of the summary.
        """
        events = []
        for summary in self.collection:
            node_events = summary.to_log_list(extaddr_map)
            events.extend([(time, summary.node_id, string) for time, string in node_events])
        events.sort(key=lambda an_event: an_event[0])

        lines = ["OTNS Summary"]

        for event in events:
            lines.append(f"[{event[0].strftime(DATE_FORMAT)[:-3]}]" f" node {event[1]}: {event[2]}")

        return "\n".join(lines)

    def to_csv(self, extaddr_map: Dict[int, int]) -> pandas.DataFrame:
        """Generate summary string in CSV format.

        Args:
            extaddr_map (Dict[int, int]): table mapping extaddr to node ID.

        Returns:
            pandas.DataFrame: DataFrame of events.
        """
        events = []
        for summary in self.collection:
            node_events = summary.to_log_list(extaddr_map)
            events.extend([(time, summary.node_id, string) for time, string in node_events])
        events.sort(key=lambda an_event: an_event[0])

        node_ids = sorted(list(extaddr_map.values()))
        columns = [f"node{i:d}" for i in node_ids]
        columns.insert(0, "timestamp")

        for i, event in enumerate(events):
            events[i] = {"timestamp": event[0].strftime(DATE_FORMAT)[:-3], f"node{event[1]}": event[2]}

        return pandas.DataFrame(events, columns=columns)


class OtnsManager(object):
    """OTNS communication manager for a test case.

    Attributes:
        server_host (str): host address of OTNS dispatcher.
        grpc_client (GRpcClient): OTNS gRPC client.
        otns_node_map (Dict[ThreadDevBoard, OtnsNode]): map from device to OTNS node.
        otns_monitor_map (Dict[ThreadDevBoard, WpantundOtnsMonitor]): map from device to OTNS monitor.
        local_host (str): host of this local machine.
        logger (Logger): logger for the manager class.
        auto_layout (bool): if manager should auto layout node positions.
        max_node_count (int): the maximum number of nodes ever managed by this manager.
        node_summaries (Dict[int, OtnsNodeSummary]): map from node ID to OtnsNodeSummary instances.
    """

    def __init__(self, server_host: str, logger: logging.Logger):
        """Initialize an OTNS manager.

        Args:
            server_host (str): host address of OTNS dispatcher.
            logger (logging.Logger): logger for the manager.
        """
        self.server_host = server_host
        self.grpc_client = GRpcClient(server_addr=f"{server_host}:{GRPC_SERVER_PORT}",
                                      logger=logger.getChild("gRPCClient"))
        self.otns_node_map = {}
        self.otns_monitor_map = {}

        self.auto_layout = False
        self.max_node_count = 0
        self.node_summaries = {}

        self.local_host = get_local_ip()

        self.logger = logger
        self.logger.info(f"OTNS manager created, connect {self.local_host} to {server_host}.")

    def wait_for_grpc_channel_ready(self, timeout: int = 10):
        """Blocking method that waits for the gRPC channel to be ready.

        Args:
            timeout (int, optional): wait timeout. Defaults to 10.
        """
        self.grpc_client.wait_for_channel_ready(timeout)

    def set_test_title(self, title: str):
        """Set title of the test case.

        Args:
            title (str): title of the test case.
        """
        self.grpc_client.set_title(title)

    def set_replay_speed(self, speed: float):
        """Set speed of the replaying test log.

        Args:
            speed (float): speed of the replaying test log.
        """
        self.grpc_client.set_speed(speed)

    def add_device(self, device: HwModule) -> OtnsNode:
        """Add a hardware module to OTNS manager.

        Args:
            device (HwModule): hardware device to add.

        Returns:
            (OtnsNode): the OTNS node created from the device.
        """
        try:
            vis_x, vis_y = device.get_otns_vis_position()
        except ValueError:
            vis_x, vis_y = device.get_otns_vis_layout_center()
            self.auto_layout = True

        node_id = device.get_otns_vis_node_id()
        dut_serial = device.get_dut_serial()
        otns_node = OtnsNode(node_id=node_id,
                             dut_serial=dut_serial,
                             vis_x=vis_x,
                             vis_y=vis_y,
                             local_host=self.local_host,
                             server_host=self.server_host,
                             server_port=SERVER_PORT,
                             grpc_client=self.grpc_client,
                             logger=self.logger.getChild(f"OtnsNode{node_id}"))
        self.logger.debug(f"Adding new node {node_id} to OTNS")
        otns_node.create_otns_node()
        return otns_node

    def add_node(self, node: ThreadDevBoard):
        """Add a node to OTNS visualization.

        Args:
            node (ThreadDevBoard): node to add, with dev board properties.
        """
        assert isinstance(node.device, HwModule), "Adding non HwModule node to OTNS manager."

        if node not in self.otns_node_map:
            otns_node = self.add_device(node.device)
            node.otns_manager = self
            self.otns_node_map[node] = otns_node

            node_id = otns_node.node_id
            self.node_summaries[node_id] = OtnsNodeSummary(node_id)
        else:
            otns_node = self.otns_node_map[node]
            self.logger.debug(f"Adding existing node {otns_node.node_id} to OTNS")
            node.otns_manager = self
            self.otns_node_map[node].create_otns_node()

        self.max_node_count = max(self.max_node_count, len(self.otns_node_map))
        self.update_layout()

    def remove_node(self, node: ThreadDevBoard):
        """Remove a node from OTNS visualization.

        Args:
            node (ThreadDevBoard): node to remove, with dev board properties.
        """
        if node.otns_manager is self:
            node.otns_manager = None

            assert isinstance(node.device, HwModule), "Removing non HwModule node from OTNS manager."

            if node in self.otns_node_map:
                otns_node = self.otns_node_map[node]
                otns_node.close_socket()

                node_id = otns_node.node_id
                self.logger.debug(f"Removing node {node_id} from OTNS")
                otns_node.delete_otns_node()

                del self.otns_node_map[node]

                self.update_layout()

    def remove_all_nodes(self):
        """Remove all nodes from OTNS visualization.
        """
        nodes = list(self.otns_node_map.keys())
        for node in nodes:
            self.remove_node(node)

    def process_node_status(self, node: ThreadDevBoard, message: str, time=datetime.now()):
        """Manually process a ThreadDevBoard status message.

        Args:
            node (ThreadDevBoard): ThreadDevBoard node.
            message (str): status message.
            time (datetime, optional): time of the update. Defaults to datetime.now().
        """
        if node in self.otns_node_map:
            self.update_status(self.otns_node_map[node], message, time=time)

    def update_status(self, node: OtnsNode, message: str, time=datetime.now()):
        """Manually update node status with a status message.

        Args:
            node (OtnsNode): OTNS node.
            message (str): status message.
            time (datetime, optional): time of the update. Defaults to datetime.now().
        """
        status_match = re.search(RegexType.STATUS.value, message)
        if status_match:
            message = status_match.group(2)

            extaddr_match = re.search(RegexType.EXTADDR_STATUS.value, message)
            if extaddr_match:
                extaddr = int(extaddr_match.group(1), 16)
                node.update_extaddr(extaddr)
                self.node_summaries[node.node_id].extaddr_changed(extaddr, time)
                return

            role_match = re.search(RegexType.ROLE_STATUS.value, message)
            if role_match:
                role = RoleType(int(role_match.group(1)))
                node.update_role(role)
                self.node_summaries[node.node_id].role_changed(role, time)
                self.update_layout()

                if role in (RoleType.DISABLED, RoleType.DETACHED):
                    for child in list(node.neighbors):
                        node.remove_router(child)
                        for neighbor in self.otns_node_map.values():
                            if neighbor.extaddr == child:
                                neighbor.remove_router(node.extaddr)
                                break
                    for child in list(node.children):
                        node.remove_child(child)
                return

            child_added_match = re.search(RegexType.CHILD_ADDED_STATUS.value, message)
            if child_added_match:
                child = int(child_added_match.group(1), 16)
                node.add_child(child)
                self.node_summaries[node.node_id].child_changed(True, child, time)
                return

            child_removed_match = re.search(RegexType.CHILD_REMOVED_STATUS.value, message)
            if child_removed_match:
                child = int(child_removed_match.group(1), 16)
                node.remove_child(child)
                self.node_summaries[node.node_id].child_changed(False, child, time)
                return

            router_added_match = re.search(RegexType.ROUTER_ADDED_STATUS.value, message)
            if router_added_match:
                router = int(router_added_match.group(1), 16)
                node.add_router(router)
                self.node_summaries[node.node_id].neighbor_changed(True, router, time)
                return

            router_removed_match = re.search(RegexType.ROUTER_REMOVED_STATUS.value, message)
            if router_removed_match:
                router = int(router_removed_match.group(1), 16)
                node.remove_router(router)
                self.node_summaries[node.node_id].neighbor_changed(False, router, time)
                return

            event = Event.status_event(message)
            node.send_event(event.to_bytes())
            return

        get_extaddr_info_match = re.search(RegexType.GET_EXTADDR_RES.value, message)
        if get_extaddr_info_match:
            extaddr = get_extaddr_info_match.group(1)
            node.update_extaddr(int(extaddr, 16))
            return

        ncp_version_match = re.search(RegexType.NCP_VERSION.value, message)
        if ncp_version_match:
            ncp_version = ncp_version_match.group(1)
            self.grpc_client.set_netinfo(version=ncp_version)
            return

    def set_ncp_version(self, version: str):
        """Set NCP version for display on OTNS.

        Args:
            version (str): version string.
        """
        self.grpc_client.set_netinfo(version=version)

    def update_extaddr(self, node: ThreadDevBoard, extaddr: int, time=datetime.now()):
        """Report a node's extended address to OTNS manager.

        Args:
            node (ThreadDevBoard): node to update.
            extaddr (int): new extaddr to report.
            time (datetime.datetime, optional): time of the update. Defaults to datetime.now().
        """
        if node in self.otns_node_map:
            self.otns_node_map[node].update_extaddr(extaddr)
            node_id = self.otns_node_map[node].node_id

            if node_id in self.node_summaries:
                self.node_summaries[node_id].extaddr_changed(extaddr, time=time)

            self.update_layout()

    def subscribe_to_node(self, node: ThreadDevBoard):
        """Create a wpantund OTNS monitor and subscribe it to the node.

        Args:
            node (ThreadDevBoard): node to subscribe to.
        """
        if node in self.otns_node_map:
            self.logger.debug(f"Subscribing to node {self.otns_node_map[node].node_id}")
            wpantund_otns_monitor = WpantundOtnsMonitor(publisher=node.wpantund_process,
                                                        node=self.otns_node_map[node],
                                                        otns_manager=self)
            self.otns_monitor_map[node] = wpantund_otns_monitor

    def unsubscribe_from_node(self, node: ThreadDevBoard):
        """Remove the wpantund OTNS subscriber of the node.

        Args:
            node (ThreadDevBoard): node to unsubscribe from.
        """
        if node in self.otns_node_map and node in self.otns_monitor_map:
            self.logger.debug(f"Unsubscribing from node {self.otns_node_map[node].node_id}")
            self.otns_monitor_map[node].unsubscribe()
            self.otns_monitor_map[node].otns_manager = None
            del self.otns_monitor_map[node]

    def unsubscribe_from_all_nodes(self):
        """Unsubscribe the manager from all nodes.
        """
        self.logger.debug("Unsubscribing from all nodes")
        for subscriber in self.otns_monitor_map.values():
            subscriber.unsubscribe()
        self.otns_monitor_map.clear()

    def update_layout(self, use_two_layer=False):
        """Update layout of nodes in auto layout mode.

        Args:
            use_two_layer (bool, optional): if layout uses separate circles for routers and EDs. Defaults to False.
        """
        no_nodes = not self.otns_node_map or self.max_node_count == 0
        if not self.auto_layout or no_nodes:
            return

        self.logger.debug("Updating nodes layout")
        first_node = next(iter(self.otns_node_map))
        center_x, center_y = first_node.device.get_otns_vis_layout_center()
        radius = first_node.device.get_otns_vis_layout_radius()

        routers = set()
        others = set()

        for node in self.otns_node_map.values():
            if node.role == RoleType.ROUTER or node.role == RoleType.LEADER:
                routers.add(node)
            else:
                others.add(node)

        if not routers and not others:
            return

        if use_two_layer:
            router_list = list(routers)
            other_list = list(others)
            router_list.sort(key=lambda x: x.node_id)
            other_list.sort(key=lambda x: x.node_id)
            groups = [other_list, router_list]
        else:
            node_list = list(routers) + list(others)
            node_list.sort(key=lambda x: x.node_id)
            groups = [node_list]

        angle_step = math.radians(360 / self.max_node_count)
        for i, group in enumerate(groups):
            group_radius = radius / (i + 1)
            for node in group:
                angle = angle_step * node.node_id
                OtnsManager.layout_node(node, center_x, center_y, group_radius, angle)

    @staticmethod
    def layout_node(node: OtnsNode, center_x: int, center_y: int, radius: float, angle: float):
        """Update a single node's visualization position.

        Args:
            node (OtnsNode): node to update visualization.
            center_x (int): layout circle center x coordinate.
            center_y (int): layout circle center y coordinate.
            radius (float): layout circle radius.
            angle (float): angle of node on the circle.
        """
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        node.update_vis_position(int(x), int(y))
