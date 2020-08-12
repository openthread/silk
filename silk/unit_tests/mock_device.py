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

import configparser
import random

from silk.hw.hw_module import HwModule
from silk.node.fifteen_four_dev_board import FifteenFourDevBoardNode, ThreadDevBoard

class MockHwModule(HwModule):
  """Mock HwModule for unit testing.
  """
  def __init__(self, name: str, node_id: int):
    """Initialize a mock HwModule.

    Args:
      name (str): name of the node.
      node_id (int): ID of the node.
    """
    super().__init__(name=name,
                     parser=configparser.ConfigParser(),
                     node_id=node_id,
                     port=f"/dev/tty{node_id}")
    self._model = "Mock"
    self._dut_serial = "683" + str(random.getrandbits(24))
    self._layout_center = 100, 100
    self._layout_radius = 100


class MockThreadDevBoard(ThreadDevBoard):
  """Mock ThreadDevBoard for unit testing.

  Attributes:
    _hwModel (str): device hardware model.
  """
  _hwModel = "Mock"

  def __init__(self, name: str, node_id: int):
    """Initialize a mock ThreadDevBoard.

    Args:
      name (str): name of the node.
      node_id (int): ID of the node.
    """
    mock_device = MockHwModule(name, node_id)
    FifteenFourDevBoardNode.__init__(self,
                                     virtual=True,
                                     device=mock_device,
                                     device_path=mock_device.port())
