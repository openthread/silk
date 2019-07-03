## Overview
Silk is a fully automated test platform for validating OpenThread function, feature and system performance with real 
devices. The initial supported device is Nordic nRF52840 Development board.

Silk runs on a Raspberry Pi or an ubuntu Linux PC. 
 
## Installation
Install libraries and dependencies:
``` shell
cd silk
./bootstrap.sh
``` 
Install and Build:
``` shell
sudo make install-cluster
``` 
## Configuration

### hwconfig.ini
Silk relies on configuration files to determine what devices that are connected to your computer are eligible to be 
used in tests. 

An example of hwconfig.ini is in src/tests folder.
 
The hardware model should be defined as 'nRF52840_OpenThread_Device' or 'NordicSniffer' in hwconfig.ini file.

``` shell
[Dev-8A7D]
HwModel: nRF52840_OpenThread_Device
HwRev: 1.0
InterfaceSerialNumber: E1A5012E8A7D
USBInterfaceNumber: 1
DutSerial: 683536778   

[Dev-6489]
HwModel: NordicSniffer
HwRev: 1.0
InterfaceSerialNumber: E992D833CBAF
USBInterfaceNumber: 1
DutSerial: 683906489
``` 

A tool called usbinfo is installed as part of Silk which can be used to find out the Interface Serial Number and Usb 
Interface Number. DutSerial is the SN number printed on the chip or displayed by usbinfo for J-Link product.   

### clusters.conf
Silk reads thread mode (NCP or RCP mode) from clusters.conf which should be added to /opt/openthread_test folder.

An example of clusters.conf is in src/config folder. 

## Run test

``` shell
usage: silk_run.py [-h] [-d ResPath] [-c ConfFile] [-v X] P [P ...]

Run a suite of Silk Tests
positional arguments:
  P                     test file search pattern
optional arguments:
  -h, --help            show this help message and exit
  -d ResPath, --results_dir ResPath
                        Set the directory path for test results
  -c ConfFile, --hwconfig ConfFile
                        Name the hardware config file
  -v X, --verbose X, --verbosity X
                        Set the verbosity level of the console (0=quiet,
                        1=default, 2=verbose)
```

There is an example of test run script silk_run_test.py under unit_tests folder.

## Build OpenThread image and wpantund

Please follow the link below.

https://codelabs.developers.google.com/codelabs/openthread-hardware/

Please note that the openthread image should have child-supervision, mac-filter and cert_log enabled.

### Build Openthread image from script build_nrf52840.sh

To build openthread image for testbed devices and sniffer you can make use of script build_nrf52840.sh present at 
silk/src/shell.

With build_nrf52840.sh an openthread image ot-ncp-ftd.hex will be created and copied to location /opt/openthread_test/
nrf52840_image/

To flash the build on testbed device attach usb cable to j-link port and replace chip serial number printed on the 
chip(e.g. 683906489).

```shell
cd silk/src/shell
./nrfjprog.sh --erase-all 683906489
./nrfjprog.sh --flash /opt/openthread_test/nrf52840_image/ot-ncp-ftd.hex 683906489
```
Note: On raspberry Pi JLink installed should be of the form JLink_Linux_XXX_arm.tgz and present at /opt/SEGGER. Create 
a symbolic link for JLink_Linux_XXX to "JLink". Make sure to run the command “sudo cp 99-jlink.rules /etc/udev/rules.d/”
given in README.txt of JLink and reboot the system.

## OpenThread Sniffer
nRF52840 can be used as a Thread Sniffer in Silk which can capture all 15.4 traffic in the specific wireless channel 
during test suite execution. The pcap file will be saved to the test result folder.

It is required that the OpenThread spinel-cli tools are installed.
``` shell
    $git clone https://github.com/openthread/pyspinel.git
    $cd pyspinel
    $sudo python setup.py develop
    $which sniffer.py (should show up in /usr/local/bin)

    You now have two options.
    Option 1: Add /usr/local/bin to your secure path
    Option 2: Create a symlink from a secure path location to the sniffer.py
              you found above
``` 
### Create image for sniffer
Recommend to flash the image for the Sniffer in a Linux PC. 
```shell
# Prepare firmware
make -f examples/Makefile-nrf52840 USB=1
arm-none-eabi-objcopy -O ihex output/nrf52840/bin/ot-rcp ot-rcp-nrf52840-115200.hex

# Flash to device
nrfjprog -f nrf52 --chiperase --reset --program ot-rcp-nrf52840-115200.hex chip-serial-number
nrfjprog -f nrf52 --pinresetenable chip-serial-number
nrfjprog -f nrf52 --reset chip-serial-number

# Disable MSD, this is very important
cd /opt/SEGGER/JLink_XXX).
./JLinkExe -SelectEmuBySN 683906489
msdddisable
exit
```
# Note
This is not an officially supported Google product.