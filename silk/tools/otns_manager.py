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
SERVER_PORT = 9000


class RegexType(enum.Enum):
  START_WPANTUND_REQ = r"Starting wpantund .* ip netns exec"
  START_WPANTUND_RES = r"wpantund\[(\d+)\]: Starting wpantund"
  STOP_WPANTUND_REQ = r"sudo ip netns del"
  GET_EXTADDR_REQ = r"getprop -v NCP:ExtendedAddress"
  GET_EXTADDR_RES = r"\[stdout\] \[([A-Fa-f0-9]{16})\]"
  STATUS = r"wpantund\[(\d+)\]: NCP => .*\[OTNS\] ([\w\d]+=[A-Fa-f0-9,]+)"
  EXTADDR_STATUS = r"extaddr=([A-Fa-f0-9]{16})"


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

  def __init__(self, server_addr: str, logger: logging.Logger):
    """Initializes a gRPC client.

    Args:
      server_addr (str): the address of the gRPC server.
      logger (logging.Logger): logger for the class.
    """
    logger.debug("Starting gRPC client with address {:s}".format(server_addr))
    self.server_addr = server_addr
    self.channel = grpc.insecure_channel(self.server_addr)
    self.stub = visualize_grpc_pb2_grpc.VisualizeGrpcServiceStub(self.channel)
    self.logger = logger

  def set_title(self, title: str, x=0, y=20, font_size=20):
    """Send test title to OTNS.

    Args:
      title (str): test title.
      x (int): x position of title.
      y (int): y position of title.
      font_size (int): font size of title.
    """
    response = self.stub.CtrlSetTitle(
        visualize_grpc_pb2.SetTitleEvent(
            title=title, x=x, y=y, font_size=font_size))
    self.logger.info("Sent title {:s}, response: {}".format(title, response))

  def add_node(self, x: int, y: int, node_id: int, ftd=True,
               rx_on_when_idle=True):
    """Sends an add node request.

    Args:
      x (int): x coordinate of the new node.
      y (int): y coordinate of the new node.
      node_id (int): node ID of the new node.
      ftd (bool): if the node is a full Thread device.
      rx_on_when_idle (bool): if rx is on when device is idle.
    """
    mode = visualize_grpc_pb2.NodeMode(
        rx_on_when_idle=rx_on_when_idle,
        secure_data_requests=False,
        full_thread_device=ftd,
        full_network_data=False)
    is_router = ftd and rx_on_when_idle

    response = self.stub.CtrlAddNode(
        visualize_grpc_pb2.AddNodeRequest(
            x=x, y=y, is_router=is_router, mode=mode, node_id=node_id))
    self.logger.info(
        ("Added node {:d} at x={:d}, y={:d}, sleepy: {}, FTD: {}, "
         "response: {}").format(
             node_id, x, y, not rx_on_when_idle, ftd, response))

  def move_node(self, node_id: int, x: int, y: int):
    """Sends a move node request async.

    Args:
      node_id (int): node ID of the node to be moved.
      x (int): new x coordinate of the node.
      y (int): new y coordianate of the node.
    """
    def handle_response(request_future):
      response = request_future.result()
      self.logger.info(
          "Moved node ID={:d} to x={:d}, y={:d}, response: {}".format(
              node_id, x, y, response))

    request_future = self.stub.CtrlMoveNodeTo.future(
        visualize_grpc_pb2.MoveNodeToRequest(node_id=node_id, x=x, y=y))
    request_future.add_done_callback(handle_response)

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

  def __init__(self, data: bytes, event: EventType, delay=0):
    """Initializes an event.

    Args:
      data (bytes): data bytes.
      event (EventType): type of the event.
      delay (int, optional): alarm delay in us. Defaults to 0
        for non-alarm events.
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
    return Event(data=message.encode("ascii"),
                 event=EventType.OTNS_STATUS_PUSH)

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
    vis_x (int): visualization x coordinate.
    vis_y (int): visualization y coordinate.
    sock (socket): UDP socket to send message from.
    source_addr (str, int): UDP source address.
    dest_addr (str, int): UDP destination address.

    extaddr(int): extended address of the node in network.
    rx_on_when_idle (bool): if device is receiving when idling.
    full_thread_device (bool): if device is a full Thread device.

    grpc_client (GRpcClient): gRPC client instance from the manager.
    logger (logging.Logger): logger for the node.
    node_on_otns (bool): if the node has been reported to OTNS.
  """

  def __init__(self, node_id: int, vis_x: int, vis_y: int,
               local_host: str, server_host: str, server_port: int,
               rx_on_when_idle: bool, full_thread_device: bool,
               grpc_client: GRpcClient, logger: logging.Logger):
    """Initialize a node.

    Args:
      node_id (int): ID of the node.
      vis_x (int): visualization x coordinate.
      vis_y (int): visualization y coordinate.
      local_host (str): host address of this machine.
      server_host (str): host address of the OTNS dispatcher.
      server_port (int): port number of the OTNS dispatcher.
      rx_on_when_idle (bool): if device is receiving when idling.
      full_thread_device (bool): if device is a full Thread device.
      grpc_client (GRpcClient): gRPC client instance from the manager.
      logger (logging.Logger): logger for the node.
    """
    assert node_id > 0

    self.node_id = node_id
    self.logger = logger

    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.source_addr = (local_host, server_port + node_id)
    self.dest_addr = (server_host, server_port)
    self.logger.debug(
        "Node {:d} socket from {:s}:{:d} to {:s}:{:d}".format(
            self.node_id,
            self.source_addr[0],
            self.source_addr[1],
            self.dest_addr[0],
            self.dest_addr[1]))
    self.sock.bind(self.source_addr)

    self.vis_x = vis_x
    self.vis_y = vis_y
    self.grpc_client = grpc_client

    self.extaddr = node_id
    self.rx_on_when_idle = rx_on_when_idle
    self.full_thread_device = full_thread_device

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
      event_packet (bytes): pacakged event content in bytes.
    """
    self.sock.sendto(event_packet, self.dest_addr)

  def send_extaddr_event(self):
    """Send extaddr event.
    """
    event = Event.status_event("extaddr={:016x}".format(self.extaddr))
    self.logger.debug(
        "Node {:d} sending extaddr={:016x}".format(self.node_id, self.extaddr))
    self.send_event(event.to_bytes())

  def update_extaddr(self, extaddr: int):
    """Update the node's extended address.

    Args:
        extaddr (int): new extended address of the node.
    """
    if extaddr != self.extaddr:
      self.extaddr = extaddr
      self.send_extaddr_event()

  def create_otns_node(self):
    """Call gRPC client to create a node on server for itself.
    """
    if self.node_on_otns:
      self.logger.debug("Node {:d} already on OTNS while trying to create")
      return
    self.logger.debug(
        "Adding node {:d} to OTNS at ({:d},{:d})".format(
            self.node_id, self.vis_x, self.vis_y))
    self.grpc_client.add_node(self.vis_x, self.vis_y, self.node_id,
                              ftd=self.full_thread_device,
                              rx_on_when_idle=self.rx_on_when_idle)
    self.send_extaddr_event()
    self.node_on_otns = True

  def delete_otns_node(self):
    """Call gRPC client to remove the node on server for itself.
    """
    if not self.node_on_otns:
      self.logger.debug("Node {:d} not on OTNS while trying to delete")
      return
    self.logger.debug(
        "Deleting node {:d} on OTNS ".format(self.node_id))
    self.grpc_client.delete_node(self.node_id)
    self.node_on_otns = False

  def update_vis_position(self):
    """Call gRPC client to update the node's visualization position.
    """
    self.logger.debug(
        "moving node {:d} to OTNS at ({:d},{:d})".format(
            self.node_id, self.vis_x, self.vis_y))
    self.grpc_client.move_node(self.vis_x, self.vis_y, self.node_id)


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
    status_match = re.search(RegexType.STATUS.value, line)
    if status_match:
      message = status_match.group(2)

      if self.node is not None:
        extaddr_match = re.search(RegexType.EXTADDR_STATUS.value, message)
        if extaddr_match:
          self.node.update_extaddr(int(extaddr_match.group(1), 16))
        else:
          event = Event.status_event(message)
          self.node.send_event(event.to_bytes())

    get_extaddr_info_match = re.search(RegexType.GET_EXTADDR_RES.value, line)
    if get_extaddr_info_match:
      extaddr = get_extaddr_info_match.group(1)
      if self.node is not None:
        self.node.update_extaddr(int(extaddr, 16))

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
    server_host (str): host address of OTNS dispatcher.
    grpc_client (GRpcClient): OTNS gRPC client.
    otns_node_map (Dict[ThreadDevBoard, OtnsNode]): map from device to
      OTNS node.
    otns_monitor_map (Dict[ThreadDevBoard, WpantundOtnsMonitor]): map from
      device to OTNS monitor.
    local_host (str): host of this local machine.
    logger (Logger): logger for the manager class.
  """

  def __init__(self, server_host: str, logger: logging.Logger):
    """Initialize an OTNS manager.

    Args:
      server_host (str): host address of OTNS dispatcher.
      logger (logging.Logger): logger for the manager.
    """
    self.server_host = server_host
    self.grpc_client = GRpcClient(
        server_addr="{:s}:{:d}".format(server_host, GRPC_SERVER_PORT),
        logger=logger.getChild("gRPCClient"))
    self.otns_node_map = {}
    self.otns_monitor_map = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))
    self.local_host = sock.getsockname()[0]

    self.logger = logger
    self.logger.info(
        "OTNS manager created, connecting from {:s} to {:s}.".format(
            self.local_host, server_host))

  def set_test_title(self, title: str):
    """Set title of the test case.

    Args:
        title (str): title of the test case.
    """
    self.grpc_client.set_title(title)

  def add_node(self, node: ThreadDevBoard):
    """Add a node to OTNS visualization.

    Args:
      node (ThreadDevBoard): node to add, with dev board properties.
    """
    assert isinstance(node.device, HwModule), (
        "Adding non HwModule node to OTNS manager.")

    try:
      if node not in self.otns_node_map:
        node_id = node.device.get_otns_vis_node_id()
        vis_x, vis_y = node.device.get_otns_vis_position()
        otns_node = OtnsNode(
            node_id=node_id,
            vis_x=vis_x,
            vis_y=vis_y,
            local_host=self.local_host,
            server_host=self.server_host,
            server_port=SERVER_PORT,
            rx_on_when_idle=node.rx_on_when_idle,
            full_thread_device=node.full_thread_device,
            grpc_client=self.grpc_client,
            logger=self.logger.getChild("OtnsNode{:d}".format(node_id)))

        self.logger.debug("Adding new node {:d} to OTNS".format(node_id))
        otns_node.create_otns_node()
        node.otns_manager = self
        self.otns_node_map[node] = otns_node
      else:
        self.logger.debug("Adding existing node {:d} to OTNS".format(node_id))
        node.otns_manager = self
        self.otns_node_map[node].create_otns_node()
    except ValueError as e:
      self.logger.error("Failed to get node OTNS properties.", str(e))

  def remove_node(self, node: ThreadDevBoard):
    """Remove a node from OTNS visualization.

    Args:
      node (ThreadDevBoard): node to remove, with dev board properties.
    """
    if node.otns_manager is self:
      node.otns_manager = None

      assert isinstance(node.device, HwModule), (
          "Removing non HwModule node from OTNS manager.")

      if node in self.otns_node_map:
        otns_node = self.otns_node_map[node]
        otns_node.close_socket()

        node_id = otns_node.node_id
        self.logger.debug("Removing node {:d} from OTNS".format(node_id))
        otns_node.delete_otns_node()

        del self.otns_node_map[node]

  def update_extaddr(self, node: ThreadDevBoard, extaddr: int):
    """Report a node's extended address to OTNS manager.

    Args:
        node (ThreadDevBoard): node to update.
        extaddr (int): new extaddr to report.
    """
    if node in self.otns_node_map:
      self.otns_node_map[node].update_extaddr(extaddr)

  def subscribe_to_node(self, node: ThreadDevBoard):
    """Create a wpantund OTNS monitor and subscribe it to the node.

    Args:
      node (ThreadDevBoard): node to subscribe to.
    """
    if node in self.otns_node_map:
      self.logger.debug(
          "Subscribing to node {:d}".format(self.otns_node_map[node].node_id))
      wpantund_otns_monitor = WpantundOtnsMonitor(
          publisher=node.wpantund_process)
      wpantund_otns_monitor.node = self.otns_node_map[node]
      self.otns_monitor_map[node] = wpantund_otns_monitor

  def unsubscribe_from_node(self, node: ThreadDevBoard):
    """Remove the wpantund OTNS subscriber of the node.

    Args:
      node (ThreadDevBoard): node to unsubscribe from.
    """
    if node in self.otns_node_map and node in self.otns_monitor_map:
      self.logger.debug(
          "Unsubscribing from node {:d}".format(
              self.otns_node_map[node].node_id))
      self.otns_monitor_map[node].unsubscribe()
      del self.otns_monitor_map[node]

  def unsubscribe_from_all_nodes(self):
    """Unsubscribe the manager from all nodes.
    """
    self.logger.debug("Unsubscribing from all nodes")
    for subscriber in self.otns_monitor_map.values():
      subscriber.unsubscribe()
    self.otns_monitor_map.clear()
