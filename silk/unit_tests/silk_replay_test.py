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
"""Sample script to run SilkReplayer to replay a log.
"""

from silk.tests import silk_replay

CONFIG_PATH = "/opt/openthread_test/"
LOG_PATH = "/opt/openthread_test/results/"

argv = [
    "tests/silk_replay.py", "-r", LOG_PATH, "-v2", "-c", CONFIG_PATH + "hwconfig.ini", "-s", "localhost", "-p", "20",
    "/home/pi/Documents/silk.log"
]

silk_replay.SilkReplayer(argv=argv)
