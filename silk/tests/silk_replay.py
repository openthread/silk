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

import silk.hw.hw_resource as hw_resource


class SilkReplayer(object):
  """Replay topology changes and transmissions from a Silk log.

  Attributes:
    speed (float): speed ratio for the replay.
  """

  def __init__(self, argv=None):
    """Initialize a SilkReplayer.

    Args:
      argv (List[str], optional): command line arguments. Defaults to None.
    """
    args = self.parse_args(argv)
    self.verbosity = args.verbosity
    self.log_path = args.path
    self.speed = args.playback_speed

    hw_resource.global_instance(args.hw_conf_file)

  def parse_args(self, argv):
    """Parse arguments.

    Args:
      argv (List[str]): command line arguments.

    Returns:
      argparse.Namespace: parsed arguments attributes.
    """
    parser = argparse.ArgumentParser(description='Replay a Silk test log')
    parser.add_argument('-c', '--hwconfig', dest='hw_conf_file',
                        metavar='ConfFile',
                        help='Name the hardware config file')
    parser.add_argument('-v', '--verbose', '--verbosity', type=int,
                        default=1, choices=list(range(0, 3)),
                        dest='verbosity', metavar='X',
                        help='Verbosity level (0=quiet, 1=default, 2=verbose)')
    parser.add_argument('-s', '--otns', dest='otns_server',
                        metavar='OtnsServer',
                        help='OTNS server address')
    parser.add_argument('-p', '--speed', dest='playback_speed',
                        metavar='PlaybackSpeed',
                        help='Speed of log replay')
    parser.add_argument('path', nargs='+', metavar='P',
                        help='log file path')
    return parser.parse_args(argv[1:])
