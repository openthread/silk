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

import enum
import logging
import re
import socket
import struct

import grpc

from silk.hw.hw_module import HwModule
from silk.node.fifteen_four_dev_board import ThreadDevBoard
from silk.tools.pb import visualize_grpc_pb2
from silk.tools.pb import visualize_grpc_pb2_grpc
from silk.utils import signal

GRPC_SERVER_PORT = 8999
DISPATCHER_PORT = 9000


class RegexType(enum.Enum):
  START_WPANTUND_REQ = r"Starting wpantund .* ip netns exec (ttyACM\d+)"
  START_WPANTUND_RES = r"wpantund\[(\d+)\]: Starting wpantund"
  STOP_WPANTUND_REQ = r"sudo ip netns exec (ttyACM\d+) kill -SIGINT (\d+)"
  GET_EXTADDR_REQ = r"(ttyACM\d+) getprop -v NCP:ExtendedAddress"
  GET_EXTADDR_RES = r"\[stdout\] \[([A-Fa-f0-9]{16})\]"
  STATUS = r"wpantund\[(\d+)\]: NCP => .*\[OTNS\] ([\w\d]+=[A-Fa-f0-9,]+)"


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
    stub (VisualizeGrpcServiceStub): gRPC stub that references the
      visualization gRPC service.
    logger (Logger): logger for the client class.
  """

  def __init__(self, server_addr: str):
    """Initializes a gRPC client.

    Args:
      server_addr (str): the address of the gRPC server.
    """
    self.server_addr = server_addr
    self.channel = grpc.insecure_channel(self.server_addr)
    self.stub = visualize_grpc_pb2_grpc.VisualizeGrpcServiceStub(self.channel)
    self.logger = logging.getLogger("GRpcClient")

  def add_node(self, x: int, y: int, node_id: int):
    """Sends an add node request.

    Args:
      x (int): x coordinate of the new node.
      y (int): y coordinate of the new node.
      node_id (int): node ID of the new node.
    """
    mode = visualize_grpc_pb2.NodeMode(
        rx_on_when_idle=False,
        secure_data_requests=False,
        full_thread_device=True,
        full_network_data=False)
    response = self.stub.CtrlAddNode(
        visualize_grpc_pb2.AddNodeRequest(
            x=x, y=y, node_id=node_id, is_router=True, mode=mode))
    self.logger.info(
        "Added node {:d} at x={:d}, y={:d}, response: {})".format(
            node_id, x, y, response))

  def move_node(self, node_id: int, x: int, y: int):
    """Sends a move node request.

    Args:
      node_id (int): node ID of the node to be moved.
      x (int): new x coordinate of the node.
      y (int): new y coordianate of the node.
    """
    response = self.stub.CtrlMoveNodeTo(
        visualize_grpc_pb2.MoveNodeToRequest(node_id=node_id, x=x, y=y))
    self.logger.info(
        "Moved node ID={:d} to x={:d}, y={:d}, response: {}".format(
            node_id, x, y, response))

  def delete_node(self, node_id: int):
    """Sends a delete node request.

    Args:
      node_id (int): node ID of the node to be deleted.
    """
    response = self.stub.CtrlDeleteNode(
        visualize_grpc_pb2.DeleteNodeRequest(node_id=node_id))
    self.logger.info(
        "Deleted node ID={:d}, response: {}".format(node_id, response))


class Event:
  """Class that represents an event.

  Class represents a UDP message that OTNS interprets as an event.

  Attributes:
    delay (int): alarm delay in ns.
    event (EventType): type of the event.
    data (bytes): message data of the event.
    length (int): length of data.
  """

  def __init__(self, data: bytes, delay=0, event=EventType.OTNS_STATUS_PUSH):
    """Initializes an event.

    Args:
      data (bytes): data bytes.
      delay (int, optional): alarm delay in us. Defaults to 0
        for non-alarm events.
      event (EventType, optional): type of the event. Defaults to
        OTNS_STATUS_PUSH.
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
    return Event(data=message.encode("utf-8"))

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

    The message format follows the OTNS event UDP format.
    <: little-endian, standard size, no alignment.
    Q: unsigned long long: 8 bytes. Corresponding to event's
      delay field in uint64_t.
    B: unsigned char: 1 byte. Corresponding to event's event field in uint8_t.
    H: unsigned short: 2 bytes. Corresponding to event's data
      length field in uint16_t.
    The data follows the header as defined above.

    Returns:
      bytes: converted message bytes.
    """
    return struct.pack("<QBH", self.delay, self.event, self.length) + self.data


class OtnsNode(object):
  """Class that represents a Thread network node for the purpose of OTNS integration.

  Attributes:
    node_id (int): ID of the node.
    sock (socket): UDP socket to send message from.
    source_addr (str, int): UDP source address.
    dest_addr  (str, int): UDP destination address.
  """

  def __init__(self, node_id: int, dispatcher_host: str, dispatcher_port: int):
    """Initialize a node.

    Args:
      node_id (int): ID of the node.
      dispatcher_host (str): host address of the OTNS dispatcher.
      dispatcher_port (int): port number of the OTNS dispatcher.
    """
    assert node_id > 0

    self.node_id = node_id

    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.source_addr = ("", dispatcher_port + node_id)
    self.dest_addr = (dispatcher_host, dispatcher_port)
    self.sock.bind(self.source_addr)

  def close(self):
    """Close the node's socket connection.
    """
    self.sock.close()

  def send_event(self, event_packet: bytes):
    """Send event bytes packet.

    Args:
      event_packet (bytes): pacakged event content in bytes.
    """
    self.sock.sendto(event_packet, self.dest_addr)


class WpantundOtnsMonitor(signal.Subscriber):
  """OTNS log monitor for wpantund process logs.

  Attributes:
    node (OtnsNode): OTNS node instance that handles UDP messaging.
  """

  node = None

  def process_log_line(self, line: str):
    """Process a single line of wpantund log.

    Args:
        line (str): line of log to process.
    """
    status_match = re.search(RegexType.STATUS_RE.value, line)
    if status_match:
      message = status_match.group(2)

      if self.node is not None:
        event = Event.status_event(message)
        self.node.send_event(event.to_bytes())

  def subscribeHandle(self, sender, **kwargs):
    """Handle messages from Publisher, a wpantund process.

    Args:
      sender (singal.Publisher): publisher of signal.
      **kwargs (str): published signal.
    """
    line = kwargs["line"]
    self.process_log_line(line)


class OtnsManager(object):
  """OTNS communication manager for a test case.

  Attributes:
    dispatcher_host (str): host address of OTNS dispatcher.
    grpc_client (GRpcClient): OTNS gRPC client.
    otns_nodes (List[OtnsNode]): OTNS nodes managed my this manager.
    subscribers (List[signal.Subscriber]): wpatund process signal subscribers.
    logger (Logger): logger for the manager class.
  """

  def __init__(self, dispatcher_host: str):
    """Initialize an OTNS manager.

    Args:
      dispatcher_host (str): host address of OTNS dispatcher.
    """
    self.dispatcher_host = dispatcher_host
    self.grpc_client = GRpcClient(
        server_addr="{:s}:{:d}".format(dispatcher_host, GRPC_SERVER_PORT))
    self.otns_nodes = []
    self.subscribers = []

    self.logger = logging.getLogger("OTNSManager")

  def add_node(self, node: ThreadDevBoard):
    """Add a node to OTNS visualization.

    Args:
        node (ThreadDevBoard): node to add, with dev board properties.
    """
    if isinstance(node, HwModule):
      try:
        node_id = node.get_otns_vis_node_id()
        vis_x, vis_y = node.get_otns_vis_location()
        otns_node = OtnsNode(node_id, self.dispatcher_host, DISPATCHER_PORT)

        self.logger.debug("Adding node {:d} to OTNS".format(node_id))
        self.grpc_client.add_node(vis_x, vis_y, node_id)

        node.otns_manager = self
        self.otns_nodes.append(otns_node)
      except ValueError:
        self.logger.error("Failed to get node OTNS properties.")
    else:
      self.logger.error("Trying to add a non HwModule node to manager.")

  def remove_node(self, node: ThreadDevBoard):
    """Remove a node from OTNS visualization.

    Args:
        node (ThreadDevBoard): node to remove, with dev board properties.
    """
    if node.otns_manager is self:
      node.otns_manager = None

    if isinstance(node, HwModule):
      for otns_node in self.otns_nodes:
        try:
          target_node_id = node.get_otns_vis_node_id()
          if otns_node.node_id == target_node_id:
            node_id = otns_node.node_id
            self.logger.debug("Removing node {:d} from OTNS".format(node_id))
            self.grpc_client.delete_node(node_id)
            break
        except ValueError:
          self.logger.error("Failed to get node OTNS properties.")

  def subscribe_to_node(self, node: ThreadDevBoard):
    """Create a wpantund OTNS monitor and subscribe it to the node.

    Args:
        node (ThreadDevBoard): node to subscribe to.
    """
    wpantund_otns_monitor = WpantundOtnsMonitor(publisher=node.wpantund_process)
    wpantund_otns_monitor.node = node
    self.subscribers.append(wpantund_otns_monitor)

  def unsubscribe_from_node(self, node: ThreadDevBoard):
    """Remove the wpantund OTNS subscriber of the node.

    Args:
        node (ThreadDevBoard): node to unsubscribe from.
    """
    for i, subscriber in enumerate(self.subscribers):
      if node is subscriber.node:
        subscriber.unsubscribe()
        del self.subscribers[i]
        break
