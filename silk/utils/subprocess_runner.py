from __future__ import print_function
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

import re
import select
import subprocess
import threading
import traceback

from silk.utils import signal


class SubprocessRunner(signal.Publisher, threading.Thread):
    """A class which runs a command.

    :param command:
        command to run
    """

    def __init__(self, command):
        super(SubprocessRunner, self).__init__()

        self.command = command

        self.running = False
        self.daemon = True

    def start(self):
        """Start the subprocessrunner, this does not start process.
        """
        try:
            super(SubprocessRunner, self).start()
            self.running = True
        except Exception as e:
            traceback.print_exc()
            print("Error in SubprocessRunner start:", str(e))

    def stop(self, timeout=15):
        """End subprocessrunner.

        :param int timeout:
            the seconds to wait before force killing the process
        """
        if self.running:
            self.running = False
            # try joining for 15 seconds, else let the program tear down
            self.join(timeout)
            if self.is_alive():
                self.warn("SubprocessRunner join timed out")
                self.proc.kill()

    def run(self):
        """start the command.
        """

        # Added code to handle wpantund start in RCP mode
        # sudo /usr/local/sbin/wpantund -o Config:NCP:SocketPath "system:openthread/output/posix/x86_64-unknown-linux-
        # gnu/bin/ot-ncp /dev/ttyACM0 115200" -o Config:TUN:InterfaceName wpan0 -o Daemon:SyslogMask "all"

        command = re.findall(r"(?:\".*?\"|\S)+", self.command)

        command = " ".join(e for e in command)

        self.proc = subprocess.Popen(command, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        try:
            while self.running:
                for s in select.select([self.proc.stdout], [], [], 1)[0]:
                    line = s.readline().rstrip()
                    if line:
                        line = line.decode("utf-8")
                        self.emit(line=line)
        except Exception as e:
            traceback.print_exc()
            print("Error in SubprocessRunner run:", str(e))
        finally:
            self.running = False
            try:
                self.proc.terminate()
            except OSError:
                pass
