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

import unittest

from silk.unit_tests.testcase import SilkTestCase
from silk.unit_tests.mock_device import MockThreadDevBoard

class BasicTest(SilkTestCase):
  """Silk unit test case for OTNS.
  """
  def testAddDevice(self):
    ns = self.ns
    manager = self.manager

    device_1 = MockThreadDevBoard("device_1", 1)
    manager.add_node(device_1)
    ns.go(0.1)
    self.assertEqual(len(ns.nodes()), 1)

if __name__ == '__main__':
    unittest.main()
