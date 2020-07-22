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

import datetime

from silk.tests import silk_replay

CONFIG_PATH = '/opt/openthread_test/'

LOG_PATH = '/opt/openthread_test/results/'

timestamp = datetime.datetime.today().strftime('%m-%d-%H:%M')

run_log_path = LOG_PATH + 'silk_replay_on_{}.log'.format(timestamp)

argv = [
    'tests/silk_replay.py',
    '-r', run_log_path,
    '-v2',
    '-c', CONFIG_PATH + 'hwconfig.ini',
    '-s', 'localhost',
    '-p', '20',
    LOG_PATH + 'silk.log'
]

silk_replay.SilkReplayer(argv=argv)
