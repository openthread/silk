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

import fcntl
import os
import Queue
import re
import select
import subprocess
import threading
import time

import message_item

from src.node.base_node import BaseNode


class MessageSystemCallItem(message_item.MessageItemBase):
    """Class to encapusulate a system call into the message queue
    """

    def __init__(self, action, cmd, expect, timeout, field, refresh=0):
        super(MessageSystemCallItem, self).__init__()

        self.action = action
        self.cmd = cmd
        self.expect = expect
        self.timeout = timeout
        self.field = field
        self.refresh = refresh

    def log_match_failure(self, response):
        self.parent.log_error("Worker failed to match expected output.")
        self.parent.log_error("Expected: \"%s\"" % self.expect)
        self.parent.log_error("Actual Output:")

        for line in response.splitlines():
            self.parent.log_error(line)

        self._delegates.set_error('{0} not found for cmd:{1}!'.format(
                                  self.expect, self.action))

    def log_response_failure(self):
        self.parent.log_error("Worker failed to execute command.")
        self.parent.log_error("Fork failed when trying to start subprocess.")
        self._delegates.set_error("Command \"%s\" not executed" % self.cmd)

    def store_groupdict_match(self, match):
        match_dict = match.groupdict()
        for key in self.field:
            self.parent.store_data(match_dict[key], key)

    def invoke(self, parent):
        """
        Consumer thread for serializing and asynchronously handling command
        inputs and expected returns.
        Make system calls using the _make_system_call method.
        """
        self.parent = parent

        if self.expect is None:
            self.expect = ""

        self.parent.log_debug("Dequeuing command \"%s\"" % self.cmd)

        response = None

        if self.cmd is not None:
            response = self.parent._make_system_call(self.action, self.cmd, self.timeout)
        if response is None:
            self.log_response_failure()
            return

        match = re.search(self.expect, response)

        if match is None:
            self.log_match_failure(response)
            return

        if type(self.field) is str:
            self.parent.store_data(match.group(), self.field)
        elif type(self.field) is list:
            self.store_groupdict_match(match)


class SystemCallManager(object):
    def __init__(self):
        self.__message_queue = Queue.Queue()
        self.__event_lock = threading.Lock()
        self.__worker_thread = threading.Thread(target=self.__worker_run, name="thread-" + self._name)
        self.__worker_thread.daemon = True
        self.__worker_thread.start()

    def make_system_call_async(self, action, command, expect, timeout, field=None):
        """
        Post a command, timeout, and expect value to a queue for the consumer
        thread.
        """
        self.log_info("Enqueuing command \"%s\"" % command)
        item = MessageSystemCallItem(action, command, expect, timeout, field)

        with self.__event_lock:
            self.set_all_clear(False)
            self.__message_queue.put_nowait(item)
            self.log_debug("Message enqueued")

    def make_function_call_async(self, function, *args):
        """
        Enqueue a Python function to be called on the worker thread
        """
        self.log_info("Enqueueing function %s with args %s" % (function, args))
        item = message_item.MessageCallableItem(function, args)

        with self.__event_lock:
            self.set_all_clear(False)
            self.__message_queue.put_nowait(item)
            self.log_debug("Message enqueued")

    def _make_system_call(self, action, command, timeout):
        """
        Generic method for making a system call with timeout
        """

        log_line = "Making system call for %s" % action
        self.log_debug(log_line)
        self.log_debug(command)
        try:
            proc = subprocess.Popen(command, shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        except:
            self.log_error("Failed to start subprocess.")
            self.log_error("\tCommand: %s" % command)
            return None

        flags = fcntl.fcntl(proc.stdout, fcntl.F_GETFL)
        fcntl.fcntl(proc.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        stdout = ""
        curr_line = ""

        t_start = time.time()

        while True:
            if proc.poll() == 0:
                break

            try:
                # Poll proc.stdout, no write list, no exception list, timeout=1s
                # If proc.stdout is closed, this will throw an exception
                # select.select is portable between OS X and Ubuntu.
                poll_list = select.select([proc.stdout], [], [], 1)

                # Check the length of the read list to see if there is new data
                if len(poll_list[0]) > 0:
                    curr_line += proc.stdout.read(1)
            except ValueError:
                break

            if len(curr_line) > 0 and curr_line[-1] == "\n" and not curr_line.isspace():
                self.log_debug("[stdout] %s" % (curr_line.rstrip()))
                stdout += curr_line
                curr_line = ""

            if time.time() - t_start > timeout:
                try:
                    proc.kill()
                except OSError:
                    pass

                break

        try:
            this_stdout = ""
            while True:
                try:
                    new_char = proc.stdout.read(1)
                    this_stdout += new_char
                    if not new_char:
                        break
                except:
                    break
            if this_stdout:
                this_stdout = curr_line + this_stdout
                for line in this_stdout.splitlines():
                    self.log_debug("[stdout] %s" % (line.rstrip()))
                stdout += this_stdout
        except ValueError:
            pass

        return stdout

    def __clear_message_queue(self):
        """Remove all pending messages in queue

        """
        try:
            while True:
                self.__message_queue.get_nowait()
        except Queue.Empty:
            pass

    def __set_error(self, msg):
        """Post error msg and clear message queue

        """
        self.log_error('set_error: {0}'.format(msg))
        self.post_error(msg)
        self.__clear_message_queue()

    def __worker_run(self):
        """
        Consumer thread for serializing and asynchronously handling command
        inputs and expected returns.
        Serialize requests to make system calls.
        Make system calls using the _make_system_call method.
        """
        response = ""
        while True:
            self.__event_lock.acquire()
            self.set_all_clear(self.__message_queue.empty())
            self.__event_lock.release()

            item = self.__message_queue.get()

            error_handler = lambda me, error_str: me.__set_error(error_str)

            delegates = message_item.MessageItemDelegates(self,
                                                          None,
                                                          None,
                                                          error_handler)

            item.set_delegates(delegates)

            item.invoke(self)


class TemporarySystemCallManager(SystemCallManager, BaseNode):
    """
    Class that can be used to make simple system calls with
    timeouts and logging functionality.
    """
    def __init__(self, name="TemporarySystemCallManager"):
        BaseNode.__init__(self, name)
        SystemCallManager.__init__(self)
