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

"""
This module requires that the OpenThread spinel-cli tools are installed

    $git clone https://github.com/openthread/pyspinel.git
    $cd pyspinel
    $sudo python setup.py develop
    #$ which sniffer.py (should show up in /usr/local/bin)

    You now have two options

    $ sudo visudo

        Option 1: Add /usr/local/bin to your secure path
        Option 2: Create a symlink from a secure path location to the sniffer.py
                  you found above

This module makes subprocess calls out to sniffer.py to generate packet
captures.
"""
import os
import subprocess

import src.hw.hw_resource as hwr
from src.node.sniffer_base import SnifferNode

sniffer_py_path = None


class OpenThreadSniffer(SnifferNode):
    def __init__(self):
        self.logger = None
        self.sniffer_process = None
        self.output_path = None
        self.outfile = None
        self.channel = None

        self.fragment_count = 0

        global sniffer_py_path
        try:
            sniffer_py_path = subprocess.check_output(["which", "sniffer.py"]).strip()
        except:
            sniffer_py_path = '/usr/local/bin/sniffer.py'

        self.device = hwr.global_instance().get_hw_module(self._hwModel)

    def set_up(self):
        pass

    def tear_down(self):
        self.stop()
        hwr.global_instance().free_hw_module(self.device)

    def start(self, channel, output_path):
        self.channel = channel
        sniffer_args = [sniffer_py_path, "-c", str(channel), "-n 1", "--crc", "-b 115200", "--no-reset",
                        "-u", self.device.port()]

        self.output_path = os.path.join(output_path, "thread_channel_%s.pcap" % channel)
        self.outfile = open(self.output_path, "wb")
        self.sniffer_process = subprocess.Popen(sniffer_args, stdout = self.outfile)                 

    def restart(self):
        if self.sniffer_process is not None:
            return

        self.fragment_count += 1
        output_name = os.path.splitext(self.output_path)
        self.outfile = open(output_name[0] + "_fragment_{0}"
                            .format(self.fragment_count) + output_name[1], "wb")

        sniffer_args = [sniffer_py_path, "-c", str(self.channel), "-u", self.device.port()]
        self.sniffer_process = subprocess.Popen(sniffer_args, stdout = self.outfile)

    def stop(self):
        if self.sniffer_process is not None:
            self.sniffer_process.kill()

        if self.outfile is not None:
            self.outfile.close()

        self.sniffer_process = None
        self.outfile = None

    def get_stats(self):
        self.logger.debug("No stats for OpenThread.")


class NordicSniffer(OpenThreadSniffer):
    _hwModel = "NordicSniffer"

