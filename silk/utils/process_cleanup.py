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

import subprocess
import logging

LOG_FILE = '/opt/openthread_test/results/ps_cleanup.log'


def ps_cleanup(usb_port='ALL', logname=LOG_FILE):

        logging.basicConfig(format='%(levelname)s:%(message)s', filename=logname, level=logging.DEBUG)

        logging.info('*'*30 + '  New logs  ' + '*'*30)

        output = subprocess.check_output('ps -ef | grep wpantund', shell=True)
        logging.info('#'*10 + 'wpantund and ttyACM process info after tearDownClass'  + '#'*10)
        logging.info(output)

        logging.info('#'*10 + 'Kill all wpantund processes if any ' +  '#'*10)
        for line in output.split('\n'):
            if 'sbin/wpantund' in line and (usb_port.upper() == 'ALL' or line.split()[-1] == usb_port):
                pid = line.split()[1]
                logging.info(pid)
                cmd = 'sudo kill -9 ' + pid
                logging.info(subprocess.check_output(cmd, shell=True))

        output = subprocess.check_output('ps -ef | grep ttyACM', shell=True)
        logging.info(output)


if __name__ == '__main__':
    ps_cleanup(LOG_FILE)
