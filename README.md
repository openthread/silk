## Overview
Silk is a fully automated test platform for validating OpenThread function, feature and system performance with real 
devices. This codebase is Python 3 compatible.
The initial supported device is Nordic nRF52840 Development board.

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

### `hwconfig.ini`
Silk relies on configuration files to determine what devices that are connected to your computer are eligible to be 
used in tests. 

An example of `hwconfig.ini` is in `silk/tests` folder.
 
The hardware model should be defined as 'Nrf52840' or 'NordicSniffer' in `hwconfig.ini` file. A cluster ID should be assigned
to the config file as well, providing an offset for node IDs for visualizing multiple clusters by the same OTNS service.
Attaching clusters with the same ID to the OTNS service could result in conflicts.

``` shell
[DEFAULT]
ClusterID: 0
LayoutCenter: 300, 300
LayoutRadius: 100

[Dev-8A7D]
HwModel: Nrf52840
HwRev: 1.0
InterfaceSerialNumber: E1A5012E8A7D
USBInterfaceNumber: 1
DutSerial: 683536778
OTNSVisPosition: 200, 200

[Dev-6489]
HwModel: NordicSniffer
HwRev: 1.0
InterfaceSerialNumber: E992D833CBAF
USBInterfaceNumber: 1
DutSerial: 683906489
``` 

A tool called usbinfo is installed as part of Silk which can be used to find out the Interface Serial Number and Usb 
Interface Number. DutSerial is the SN number printed on the chip or displayed by usbinfo for J-Link product.   

### `clusters.conf`
Silk reads thread mode (NCP or RCP mode) from `clusters.conf` which should be added to `/opt/openthread_test` folder.

An example of `clusters.conf` is in `silk/config` folder. 

## Run test

``` shell
usage: silk_run.py [-h] [-d ResPath] [-c ConfFile] [-v X] [-s OtnsServer] P [P ...]

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
  -s OtnsServer, --otns OtnsServer,
                        Set the OTNS server address to send OTNS messages to
```

There is an example of test run script `silk_run_test.py` under `unit_tests` folder.

### Using OTNS
[OpenThread Network Simulator](https://github.com/openthread/ot-ns) is a Thread network visualization and management tool.
Using this tool the topology and messages of a network in Silk's control could be visualized. Run the following to install OTNS.
Note that it requires Go which can be installed from https://golang.org/dl/, after which `$(go env GOPATH)/bin` should be added
to `$PATH`.

```shell
git clone https://github.com/openthread/ot-ns.git ./otns
cd otns
./script/install-deps
./script/install
```

Then follow these steps to use Silk with OTNS:

1. Configure `ClusterID` for the cluster. There are two ways to lay out nodes for the cluster:
   1. Specify `OTNSVisPosition` for each node in `hwconfig.ini`. Canvas is the same size in pixel as the
      monitor on which OTNS runs, so usually a 50px distance is clear enough.
   2. Specify `LayoutCenter` and `LayoutRadius` for the cluster in `hwconfig.ini` and not `OTNSVisPosition`. This will
      tell OTNS Manager to calculate each node's position dynamically based on their roles in the network.
   3. OTNS Manager will default to not using auto layout if all node's visualization positions have been set. Otherwise,
      it turns to auto layout.
2. Flash each board with the images compiled with OpenThread `OTNS=1` flag turned on.
3. Run OTNS in real mode using `otns -raw -real -ot-cli otns-silk-proxy`.
4. Run Silk with `silk_run.py`, supplying `-s OtnsServer` argument. If the server is running on the same machine, use `localhost`.

### Using Replayer
The `SilkReplayer` allows offline playback of Silk log file for visualization on OTNS platform. The playback speed can be controlled
via command line arguments. Usage:

``` shell
usage: silk_replay.py [-h] [-d ResPath] [-c ConfFile] [-v X] [-s OtnsServer] [-p PlaybackSpeed] P

Run a suite of Silk Tests
positional arguments:
  P                     Log file path
optional arguments:
  -h, --help            show this help message and exit
  -r ResPath, --results_dir ResPath
                        Set the path for run results. Defaults to current folder.
  -c ConfFile, --hwconfig ConfFile
                        Name the hardware config file. Defaults to `/opt/openthread_test/hwconfig.ini`.
  -v X, --verbose X, --verbosity X
                        Set the verbosity level of the console (0=quiet,
                        1=default, 2=verbose)
  -s OtnsServer, --otns OtnsServer,
                        Set the OTNS server address to send OTNS messages to. Defaults to `localhost`.
  -p PlaybackSpeed, --speed PlaybackSpeed,
                        Speed of log replay. e.g. 20 means speeding up to 20x. 1.0 by default.
```

There is an example of test run script `silk_replay_test.py` under `unit_tests` folder.

## Build Wpantund image

```shell
git clone https://github.com/openthread/wpantund.git
cd silk/silk/shell
./flash_wpantund.sh
```

## Build OpenThread image

```shell
git clone https://github.com/openthread/openthread.git
```

Please note that the openthread image should have child-supervision, mac-filter and log-output enabled (listed in detail in script `build_nrf52840.sh`).

### Testbed devices

To build openthread image for testbed devices and sniffer you can make use of script `build_nrf52840.sh`.

```shell
cd silk/silk/shell
./build_nrf52840.sh
```

To utilize OTNS, `OTNS=1` flag needs to be turned on when compiling the image.

With `build_nrf52840.sh` an openthread image `ot-ncp-ftd.hex` will be created and copied to location `/opt/openthread_test/nrf52840_image/`.

To flash the build on testbed device attach usb cable to j-link port and replace chip serial number printed on the 
chip(e.g. `683906489`).

```shell
cd silk/silk/shell
./nrfjprog.sh --erase-all 683906489
./nrfjprog.sh --flash /opt/openthread_test/nrf52840_image/ot-ncp-ftd.hex 683906489
```

Note: On raspberry Pi JLink installed should be of the form `JLink_Linux_XXX_arm.tgz` and present at `/opt/SEGGER`. Create 
a symbolic link for `JLink_Linux_XXX` to "JLink". Make sure to run the command `sudo cp 99-jlink.rules /etc/udev/rules.d/`
given in `README.txt` of JLink and reboot the system.
Example output of Jlink executable:

```shell
user@user:/opt/SEGGER$ ls -l
total 4
lrwxrwxrwx 1 root root   23 Sep 26  2018 JLink -> /opt/SEGGER/JLink_V634g
drwxr-xr-x 8 root root 4096 Aug 20 10:21 JLink_V634g
```

## OpenThread Sniffer
nRF52840 can be used as a Thread Sniffer in Silk which can capture all 15.4 traffic in the specific wireless channel 
during test suite execution. The pcap file will be saved to the test result folder.

It is required that the OpenThread spinel-cli tools are installed.

``` shell
git clone https://github.com/openthread/pyspinel.git
cd pyspinel
sudo python setup.py develop
which sniffer.py (should show up in /usr/local/bin)
``` 

You now have two options.

Option 1: Add `/usr/local/bin` to your secure path.

Option 2: Create a symlink from a secure path location to the `sniffer.py` you found above.

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
msddisable
exit
```

# Note
This is not an officially supported Google product.
