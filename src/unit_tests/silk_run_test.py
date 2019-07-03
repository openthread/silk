# Copyright 2019 Google LLC
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

from src.tests import silk_run
import os
import datetime

RESULT_LOG_PATH = '/opt/openthread_test/results/'+'silk_run_0502_A/'
CONFIG_PATH = '/opt/openthread_test/'

os.chdir('../tests')

timestamp = datetime.datetime.today().strftime("%m-%d-%H:%M")

run_log_path = RESULT_LOG_PATH + 'test_run_on_' + timestamp + '/'

argv = ['tests/silk_run.py', '-v2', '-c', CONFIG_PATH+'hwconfig.ini', '-d', run_log_path, 'ot_test*.py']

silk_run.SilkRunner(argv=argv)



