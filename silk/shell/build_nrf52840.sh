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

cd /home/pi/openthread
git reset --hard

output=$(git pull | grep "Already up to date")

if [[ $output == *"Already"* ]]; then

  echo "No code changes for Openthread........."

else

  echo "Started to build Openthread for nrf52840..........."

  git clean -dfx
  echo "git clean done"

  ./bootstrap

  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_LOG_LEVEL=OT_LOG_LEVEL_INFO"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_MLE_INFORM_PREVIOUS_PARENT_ON_REATTACH=1"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_COMMISSIONER_MAX_JOINER_ENTRIES=4"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_TMF_ADDRESS_CACHE_ENTRIES=16"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_TMF_ADDRESS_QUERY_MAX_RETRY_DELAY=120"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_TMF_ADDRESS_QUERY_TIMEOUT=6"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_TMF_ADDRESS_QUERY_INITIAL_RETRY_DELAY=4"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_TMF_ADDRESS_CACHE_MAX_SNOOP_ENTRIES=2"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_TMF_SNOOP_CACHE_ENTRY_TIMEOUT=10"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_CHANNEL_MANAGER_MINIMUM_DELAY=2"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_MLE_MAX_CHILDREN=32"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_MLE_IP_ADDRS_PER_CHILD=10"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_IP6_MAX_EXT_UCAST_ADDRS=8"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_IP6_MAX_EXT_MCAST_ADDRS=4"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_MAC_FILTER_SIZE=10"
  CPPFLAGS="${CPPFLAGS} -DOPENTHREAD_CONFIG_IP6_SLAAC_ENABLE=1"
  CPPFLAGS="${CPPFLAGS}" make -f examples/Makefile-nrf52840 \
    BORDER_ROUTER=1 \
    CHILD_SUPERVISION=1 \
    LOG_OUTPUT=APP \
    MAC_FILTER=1 \
    REFERENCE_DEVICE=1 \
    COMMISSIONER=1 \
    JOINER=1 \
    USB=1 \
    CHANNEL_MANAGER=1 \
    CHANNEL_MONITOR=1 \
    JAM_DETECTION=1 \
    OTNS=1

  echo "Completed building, change to output/nrf52840/bin"
  cd output/nrf52840/bin/

  echo "Convert to hex file..."
  arm-none-eabi-objcopy -O ihex ot-ncp-ftd ot-ncp-ftd.hex

  echo "Copy to /opt/openthread_test/nrf52840_image folder"
  sudo cp ot-ncp-ftd.hex /opt/openthread_test/nrf52840_image/ot-ncp-ftd.hex
  sudo cp ot-ncp-ftd.hex /opt/openthread_test/nrf52840_image/ot-ncp-ftd_$date.hex

  echo "Done building new image for nrf52840 with latest Openthread code"
fi
