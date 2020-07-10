#!/bin/bash
#
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


# Script to check build change in a repo and run tests with latest build

function run_test()
{
  REPO_NAME=$1
  CHECK_BUILD_CHANGE=$2
  source /home/pi/silk/silk/shell/$CHECK_BUILD_CHANGE

echo "******* exporting output variable's value depicting build change from $CHECK_BUILD_CHANGE *******"
echo $output
if [[ $output == *"Already"* ]]; then
  echo "No need to run tests as $REPO_NAME version is same"
else
    if [[ $REPO_NAME == "openthread" ]]; then
      echo "Flash the dev boards with latest ot build"
      cd /home/pi/silk/silk/shell
      echo "Getting serial number of dev boards from hwconfig.ini"
      cat /opt/openthread_test/hwconfig.ini |grep DutSerial|egrep -o [0-9]\{9\} >/opt/openthread_test/serial_num_list.txt
      for serial_num in $(cat /opt/openthread_test/serial_num_list.txt); do
          ./nrfjprog.sh --erase-all $serial_num
          ./nrfjprog.sh --flash /opt/openthread_test/nrf52840_image/ot-ncp-ftd.hex $serial_num
      done
    fi

    echo "Running OT test suite with latest $REPO_NAME version"
    DATE=`date +%b%m%Y_%H_%M_%S`
    LOG_FILE="/opt/openthread_test/results/$DATE"
    sudo python ../tests/silk_run.py -v2 -c /opt/openthread_test/hwconfig.ini -d $LOG_FILE/ P ot_test_*.py
    
fi
}

run_test wpantund flash_wpantund.sh
run_test openthread build_nrf52840.sh
