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

import logging
import time
import tracemalloc
import unittest

from otns.cli import OTNS
from silk.tools.otns_manager import OtnsManager

LOG_LINE_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"

class SilkTestCase(unittest.TestCase):
  """Silk unit test base case.
  """
  @classmethod
  def setUpClass(cls) -> None:
    tracemalloc.start()
    logging.basicConfig(level=logging.DEBUG, format=LOG_LINE_FORMAT)

  def setUp(self) -> None:
    """Test method set up.
    """
    self.ns = OTNS(otns_args=[
        "-raw", "-real",
        "-ot-cli", "otns-silk-proxy",
        "-listen", ":9000",
        "-log", "debug"])
    # wait for OTNS gRPC server to start
    time.sleep(0.5)
    self.manager = OtnsManager("localhost", logging.Logger("OTNS Manager"))

  def tearDown(self) -> None:
    """Test method tear down.
    """
    self.manager.unsubscribe_from_all_nodes()
    self.manager.remove_all_nodes()
    self.ns.close()
