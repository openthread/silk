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

"""Silk Test Log Replayer.

Enables replaying Silk log with OTNS enabled through OTNS visualization.
"""

import argparse
import logging
import sys

import silk.hw.hw_resource as hw_resource
from silk.hw.hw_resource import HardwareNotFoundError
import silk.node.fifteen_four_dev_board as ffdb
from silk.tools.otns_manager import OtnsManager

DATE_FORMAT = "%Y-%m-%d_%H.%M.%S"
LOG_LINE_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"


class SilkReplayer(object):
  """Replay topology changes and transmissions from a Silk log.

  Attributes:
    speed (float): speed ratio for the replay.
    verbosity (int): terminal log verbosity.
    input_path (str): input Silk log file path.
    logger (logging.Logger): logger for the replayer.

    devices (List[ThreadDevBoard]): hardware modules from hwconfig.ini file.
    otns_manager (OtnsManager): manager for OTNS communications.
  """

  def __init__(self, argv=None):
    """Initialize a Silk log replayer.

    Args:
      argv (List[str], optional): command line arguments. Defaults to None.
    """
    args = self.parse_args(argv)
    self.verbosity = args.verbosity
    self.input_path = args.path
    self.speed = args.playback_speed

    self.set_up_logger(args.result_path)

    hw_resource.global_instance(args.hw_conf_file)
    self.acquire_devices()

    self.otns_manager = OtnsManager(
        server_host=args.otns_server,
        logger=self.logger.getChild("otnsManager"))

  def set_up_logger(self, result_path: str):
    """Set up logger for the replayer.

    Args:
      result_path (str): output path of log.
    """
    self.logger = logging.getLogger("silk_replay")
    self.logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_LINE_FORMAT)

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
    parser.add_argument("-r", "--result_path", dest="result_path",
                        metavar="ResPath",
                        help="Set the path for run results")
    parser.add_argument("-c", "--hwconfig", dest="hw_conf_file",
                        metavar="ConfFile",
                        help="Name the hardware config file")
    parser.add_argument("-v", "--verbose", "--verbosity", type=int,
                        default=1, choices=list(range(0, 3)),
                        dest="verbosity", metavar="X",
                        help="Verbosity level (0=quiet, 1=default, 2=verbose)")
    parser.add_argument("-s", "--otns", dest="otns_server",
                        metavar="OtnsServer",
                        help="OTNS server address")
    parser.add_argument("-p", "--speed", dest="playback_speed",
                        metavar="PlaybackSpeed",
                        help="Speed of log replay")
    parser.add_argument("path", nargs="+", metavar="P",
                        help="log file path")
    return parser.parse_args(argv[1:])

  def acquire_devices(self):
    """Acquire devices from hwconfig.ini file.
    """
    while True:
      try:
        device = ffdb.ThreadDevBoard()
      except HardwareNotFoundError:
        break
      else:
        self.devices.append(device)

  def run(self):
    """Run the Silk log replayer.
    """
    with open(file=self.input_path, mode="r") as file:
      for line in file:
        print(line)

if __name__ == "__main__":
  SilkReplayer(argv=sys.argv)
