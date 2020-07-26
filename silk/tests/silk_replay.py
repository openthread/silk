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

"""Silk Test Log Visualization Replayer.

Enables replaying Silk log with OTNS enabled through OTNS visualization.
"""

import argparse
import datetime
import enum
import logging
import os
import re
import sys
import time

import silk.hw.hw_resource as hw_resource
import silk.node.fifteen_four_dev_board as ffdb
from silk.tools.otns_manager import OtnsManager
from silk.tools.otns_manager import RegexType as OtnsRegexType

DATE_FORMAT = "%Y-%m-%d %H:%M:%S,%f"
LOG_LINE_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"


class RegexType(enum.Enum):
  """Regular expression collections.
  """
  # regex that matches the four components above as groups
  LOG_LINE = r"\[([\d\s,:-]+)\] \[([\w\d.-]+)\] \[(\w+)\] (.+)"
  SET_UP_CLASS = r"SET UP CLASS (\w+)"


class SilkReplayer(object):
  """Replay topology changes and transmissions from a Silk log.

  Attributes:
    speed (float): speed ratio for the replay. 2.0 means speeding up to 2x.
    verbosity (int): terminal log verbosity.
    input_path (str): input Silk log file path.
    logger (logging.Logger): logger for the replayer.

    device_names (Set[str]): name of hardware modules from hwconfig.ini file.
    device_name_map (Dict[str, ThreadDevBoard]): map from device name to
      ThreadDevBoard instance.
    otns_manager (OtnsManager): manager for OTNS communications.

    last_time (datetime.datetime): timestamp of the last line of log processed.
  """

  def __init__(self, argv=None):
    """Initialize a Silk log replayer.

    Args:
      argv (List[str], optional): command line arguments. Defaults to None.
    """
    args = self.parse_args(argv)
    self.verbosity = args.verbosity
    self.input_path = args.path
    self.speed = float(args.playback_speed)

    if args.results_dir is not None:
      self.set_up_logger(args.results_dir)
    else:
      self.set_up_logger(os.getcwd())
    self.acquire_devices(args.hw_conf_file)

    self.otns_manager = OtnsManager(
        server_host=args.otns_server,
        logger=self.logger.getChild("otnsManager"))

    self.last_time = None
    self.run()

  def set_up_logger(self, result_dir: str):
    """Set up logger for the replayer.

    Args:
      result_dir (str): output directory of log.
    """
    self.logger = logging.getLogger("silk_replay")
    self.logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_LINE_FORMAT)

    timestamp = datetime.datetime.today().strftime("%m-%d-%H:%M")
    result_path = result_dir + "/silk_replay_on_{}.log".format(timestamp)

    file_handler = logging.FileHandler(result_path, mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    if self.verbosity == 0:
      stream_level = logging.CRITICAL
    elif self.verbosity == 1:
      stream_level = logging.INFO
    else:
      stream_level = logging.DEBUG

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(stream_level)
    stream_handler.setFormatter(formatter)
    self.logger.addHandler(stream_handler)
    self.logger.addHandler(file_handler)

  def parse_args(self, argv):
    """Parse arguments.

    Args:
      argv (List[str]): command line arguments.

    Returns:
      argparse.Namespace: parsed arguments attributes.
    """
    parser = argparse.ArgumentParser(description="Replay a Silk test log")
    parser.add_argument("-r", "--results_dir", dest="results_dir",
                        metavar="ResPath",
                        help="Set the path for run results")
    parser.add_argument("-c", "--hwconfig", dest="hw_conf_file",
                        metavar="ConfFile",
                        default="/opt/openthread_test/hwconfig.ini",
                        help="Name the hardware config file")
    parser.add_argument("-v", "--verbose", "--verbosity", type=int,
                        default=1, choices=list(range(0, 3)),
                        dest="verbosity", metavar="X",
                        help="Verbosity level (0=quiet, 1=default, 2=verbose)")
    parser.add_argument("-s", "--otns", dest="otns_server",
                        metavar="OtnsServer",
                        default="localhost",
                        help="OTNS server address")
    parser.add_argument("-p", "--speed", dest="playback_speed",
                        type=float, default=1.0,
                        metavar="PlaybackSpeed",
                        help="Speed of log replay")
    parser.add_argument("path", metavar="P",
                        help="Log file path")
    return parser.parse_args(argv[1:])

  def acquire_devices(self, config_file: str):
    """Acquire devices from hwconfig.ini file.

    Args:
      config_file (str): path to hwconfig.ini file.
    """
    hw_resource.global_instance(config_file, virtual=True)
    hw_resource.global_instance().load_config()
    self.device_names = set(
        hw_resource.global_instance().get_hw_module_names())
    self.device_name_map = dict()
    self.logger.debug("Loaded devices %s", self.device_names)

  def execute_message(self, entity_name: str, message: str):
    """Execute the intended action represented by the message.

    Args:
      entity_name (str): name of the entity carrying out the action.
      message (str): message content of the action.
    """
    parts = entity_name.split(".")
    if len(parts) == 1 and parts[0] == "silk":
      set_up_class_match = re.match(RegexType.SET_UP_CLASS.value, message)
      if set_up_class_match:
        self.otns_manager.set_test_title(set_up_class_match.group(1))
    if len(parts) < 2 or parts[0] != "silk" or parts[1] == "otnsManager":
      return

    device_name = parts[1]
    if device_name not in self.device_names:
      return

    if device_name not in self.device_name_map:
      device = ffdb.ThreadDevBoard(virtual=True, virtual_name=device_name)
      self.device_name_map[device_name] = device
    else:
      device = self.device_name_map[device_name]

    start_match = re.match(OtnsRegexType.START_WPANTUND_RES.value, message)
    if start_match:
      self.otns_manager.add_node(device)
      return

    stop_match = re.match(OtnsRegexType.STOP_WPANTUND_REQ.value, message)
    if stop_match:
      self.otns_manager.remove_node(device)
      return

    extaddr_match = re.search(OtnsRegexType.GET_EXTADDR_RES.value, message)
    if extaddr_match:
      self.otns_manager.update_extaddr(device, int(extaddr_match.group(1), 16))
      return

    status_match = re.match(OtnsRegexType.STATUS.value, message)
    if status_match:
      self.otns_manager.process_node_status(device, message)

  def run(self):
    """Run the Silk log replayer.
    """
    with open(file=self.input_path, mode="r") as file:
      for line in file:
        line_match = re.search(RegexType.LOG_LINE.value, line)
        if line_match:
          timestamp = datetime.datetime.strptime(
              line_match.group(1), DATE_FORMAT)
          if not self.last_time:
            self.last_time = timestamp
          time_diff = timestamp - self.last_time
          delay = time_diff.total_seconds() / self.speed
          self.last_time = timestamp

          entity_name = line_match.group(2)
          message = line_match.group(4)

          # delay for the time difference between two log lines
          if delay > 0:
            time.sleep(delay)
          self.execute_message(entity_name, message)


if __name__ == "__main__":
  SilkReplayer(argv=sys.argv)
