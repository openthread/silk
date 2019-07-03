#!/bin/bash
#
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

echo "Check if a new build is needed for Openthread"

date=`date +"%Y-%m-%d"`

echo 'current date:' $date

cd ~/openthread

output=$(git pull | grep "Already up to date")

if [[ $output == *"Already"* ]]; then

  echo "No code changes for Openthread........."

 else

  echo "Started to build Openthread for nrf52840..........."

  git clean -dfx
  echo "git clean done"

  ./bootstrap


  make -f examples/Makefile-nrf52840 TMF_PROXY=1 BORDER_ROUTER=1 COMMISSIONER=1 USB=1

  echo "Completed buildin, change to output/nrf52840/bin"
  cd output/nrf52840/bin/

  echo "Convert to hex file..."
  arm-none-eabi-objcopy -O ihex ot-ncp-ftd ot-ncp-ftd.hex

  echo "Copy to /opt/openthread_test/nrf52840_image folder"
  sudo cp ot-ncp-ftd.hex /opt/openthread_test/nrf52840_image/ot-ncp-ftd.hex
  sudo cp ot-ncp-ftd.hex /opt/openthread_test/nrf52840_image/ot-ncp-ftd_$date.hex

  echo "Done building new image for nrf52840 with latest Openthread code"
fi
