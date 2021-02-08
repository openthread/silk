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
"""This module is used to execute the shell script.
"""

import os
import subprocess
import threading


class Process(object):

    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None

    def process_cmd(self):
        try:
            self.process = subprocess.Popen("exec " + self.cmd, bufsize=0, shell=True, stdout=subprocess.PIPE)
            return self.process
        except Exception:
            return None

    def process_cmd_asyc_end(self, key_word):
        self.stop_thread.set()
        stop_cmd = "ps -ef | grep '" + key_word + "' | grep -v grep | awk '{print $2}' | xargs kill"
        print(stop_cmd)
        os.popen(stop_cmd)

    def process_cmd_asyc(self):
        self.stop_thread = threading.Event()
        self.process = subprocess.Popen(self.cmd,
                                        bufsize=0,
                                        stdout=subprocess.PIPE,
                                        stdin=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        shell=True)
        print(self.process.pid)

        proc_thread = threading.Thread(target=self.read, args=(self.process,))
        proc_thread.start()

    def read(self, process):
        while not self.stop_thread.is_set():
            output = process.stdout.readline().decode("UTF-8")
            # TODO: should add the logic to record the log info here. This will be addressed by issue ID #33
            print(output.strip())
            if output == "" and self.process.poll() is not None:
                break

    def get_process(self):
        return self.process

    def get_process_result(self):
        self.process_cmd()
        return self.process.communicate()[0].decode("UTF-8")

    def get_process_list(self):
        self.process_cmd()
        res = self.process.communicate()[0].decode("UTF-8")
        return res if res is not None else ""

    def get_process_content(self):
        self.process_cmd()
        return self.process.check_out()

    @staticmethod
    def execute_command(cmd):
        process = subprocess.Popen("exec " + cmd, bufsize=0, shell=True, stdout=subprocess.PIPE)
        process.communicate()
