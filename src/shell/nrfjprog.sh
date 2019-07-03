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

read -d '' USAGE <<- EOF
nrfprog.sh
This is a loose shell port of the nrfjprog.exe program distributed by Nordic,
which relies on JLinkExe to interface with the JLink hardware.
usage:
nrfjprog.sh <action> [hexfile]
where action is one of
  --reset
  --pin-reset
  --erase-all
  --flash
  --flash-softdevice
  --rtt
  --gdbserver
  --list
EOF

GREEN="\033[32m"
RESET="\033[0m"
STATUS_COLOR=$GREEN

TOOLCHAIN_PREFIX=arm-none-eabi
# assume the tools are on the system path
TOOLCHAIN_PATH=
JLINK_OPTIONS="-device nRF52 -if swd -speed 1000"

HEX=$2

JLINK="sudo /opt/SEGGER/JLink/JLinkExe $JLINK_OPTIONS"
JLINKGDBSERVER="JLinkGDBServer $JLINK_OPTIONS"
GDB_PORT=2331

# the script commands come from Makefile.posix, distributed with
# nrf51-pure-gcc. I've made some changes to use hexfiles instead of binfiles

TMPSCRIPT=/tmp/tmp_$$.jlink
if [ "$1" = "--reset" ]; then
    echo ""
    echo -e "${STATUS_COLOR}resetting...${RESET}"
    echo ""
    echo "usb" $2 > $TMPSCRIPT
    echo "r" > $TMPSCRIPT
    echo "g" >> $TMPSCRIPT
    echo "exit" >> $TMPSCRIPT
    $JLINK $TMPSCRIPT
    rm $TMPSCRIPT
elif [ "$1" = "--pin-reset" ]; then
    echo ""
    echo -e "${STATUS_COLOR}resetting with pin...${RESET}"
    echo ""
    echo "w4 40000544 1" > $TMPSCRIPT
    echo "r" >> $TMPSCRIPT
    echo "exit" >> $TMPSCRIPT
    $JLINK $TMPSCRIPT
    rm $TMPSCRIPT
elif [ "$1" = "--erase-all" ]; then
    echo ""
    echo -e "${STATUS_COLOR}perfoming full erase...${RESET}"
    echo ""
    echo "usb" $2 >> $TMPSCRIPT
    echo "h" >> $TMPSCRIPT
    echo "w4 4001e504 2" >> $TMPSCRIPT
    echo "w4 4001e50c 1" >> $TMPSCRIPT
    echo "sleep 100" >> $TMPSCRIPT
    echo "r" >> $TMPSCRIPT
    echo "exit" >> $TMPSCRIPT
    $JLINK $TMPSCRIPT
    rm $TMPSCRIPT
elif [ "$1" = "--flash" ]; then
    echo ""
    echo -e "${STATUS_COLOR}flashing ${HEX}...${RESET}"
    echo ""
    echo "r" >> $TMPSCRIPT
    echo "h" >> $TMPSCRIPT
    echo "usb" $3 > $TMPSCRIPT
    echo "loadfile $HEX" >> $TMPSCRIPT
    echo "r" >> $TMPSCRIPT
    echo "g" >> $TMPSCRIPT
    echo "exit" >> $TMPSCRIPT
    $JLINK $TMPSCRIPT
    rm $TMPSCRIPT
elif [ "$1" = "--flash-softdevice" ]; then
    echo ""
    echo -e "${STATUS_COLOR}flashing softdevice ${HEX}...${RESET}"
    echo ""
    # Halt, write to NVMC to enable erase, do erase all, wait for completion. reset
    echo "h"  > $TMPSCRIPT
    echo "w4 4001e504 2" >> $TMPSCRIPT
    echo "w4 4001e50c 1" >> $TMPSCRIPT
    echo "sleep 100" >> $TMPSCRIPT
    echo "r" >> $TMPSCRIPT
    # Halt, write to NVMC to enable write. Write mainpart, write UICR. Assumes device is erased.
    echo "h" >> $TMPSCRIPT
    echo "w4 4001e504 1" >> $TMPSCRIPT
    echo "usb" $3 > $TMPSCRIPT
    echo "loadfile $HEX" >> $TMPSCRIPT
    echo "r" >> $TMPSCRIPT
    echo "g" >> $TMPSCRIPT
    echo "exit" >> $TMPSCRIPT
    $JLINK $TMPSCRIPT
    rm $TMPSCRIPT
elif [ "$1" = "--rtt" ]; then
    # trap the SIGINT signal so we can clean up if the user CTRL-C's out of the
    # RTT client
    trap ctrl_c INT
    function ctrl_c() {
        return
    }
    echo -e "${STATUS_COLOR}Starting RTT Server...${RESET}"
    JLinkExe -device nrf52 -if swd -speed 1000 &
    JLINK_PID=$!
    sleep 1
    echo -e "\n${STATUS_COLOR}Connecting to RTT Server...${RESET}"
    #telnet localhost 19021
    JLinkRTTClient
    echo -e "\n${STATUS_COLOR}Killing RTT server ($JLINK_PID)...${RESET}"
    kill $JLINK_PID
elif [ "$1" = "--gdbserver" ]; then
    $JLINKGDBSERVER -port $GDB_PORT
elif [ "$1" = "--list" ]; then
    echo "ShowEmuList" > $TMPSCRIPT
    echo "exit" >> $TMPSCRIPT
    $JLINK $TMPSCRIPT | grep 68 | cut -d ' ' -f 6 | cut -c1-9
    rm $TMPSCRIPT
else
    echo "$USAGE"
fi