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
Watchable, an implementation of an object whose state can be watched
"""

import threading

from datetime import datetime

import deadline as silk_deadline


def is_watchable(object):
    return (isinstance(object, WatchableWithHistory) or
        isinstance(object, Watchable))


# An object whose state can be watched
class Watchable(object):
    # Constructor
    # @param value The initial value for this watchable
    # @param name The name for this watchable, for logging only
    # @Param logger A logger to invoke any logging operations
    def __init__(self, value, name = None, logger = None):
        self.value = value
        self.__lock = threading.Lock()
        self.__watchers = []
        self.__name = name
        self.__logger = logger

    def __get__(self, instance, owner):
        self.__lock.acquire()
        value = self.value
        self.__lock.release()

        return value

    def __set__(self, instance, value):
        modify = False

        self.__lock.acquire()

        modify = value != self.value
        if modify:
            self.value = value

        # Instruct watchers to poll again
        # even if values have not changed
        for watcher in self.__watchers:
            watcher.set()

        self.__lock.release()

        if modify and self.__logger:
            log = "%s modified" % str(self)
            self.__logger.debug(log)

        return value

    def __str__(self):
        return str(self.value)
    
    # Get the name
    # @returns The name
    @property
    def name(self):
        return self.__name;

    # Set the contained property
    # @param new_value The value to set
    def set(self, new_value):
        return self.__set__(None, new_value)

    # Get the contained property
    # @return The value of the contained property
    def get(self):
        return self.__get__(None, None)

    # Wait until the value of lambda_func(__property_object) == True
    # The below example will block until the underlying property becomes 5
    # watchable_object.watch(lambda x: x == 5)
    # @param lambda_func A function or callable that returns not None when the desired watch condition is Met
    # @param timeout Timeout in seconds. Specify None for no timeout
    # @return The result of the watch function. A None result implies a timeout
    def watch(self, lambda_func, timeout = None, must_update = False):
        retval = None

        deadline = silk_deadline.Deadline(timeout)

        updated = not must_update

        self.__lock.acquire()

        while True:

            if updated:
                # First check to see if the value is what we want
                #
                retval = lambda_func(self.value)
                if retval:
                    break

            # Otherwise, add ourselves to the wait list
            watch_event = threading.Event()
            self.__watchers.append(watch_event)

            self.__lock.release()
            wait_result = watch_event.wait(deadline.get_remaining_seconds())
            updated = True
            self.__lock.acquire()

            self.__watchers.remove(watch_event)

            # Bail if we timed out
            if wait_result is not True:
                break

        self.__lock.release()

        return retval

    # Wait until there is some update to the underlying variable. Useful for
    # cases where an asynchronous operation (i.e a command) is pending and we want to
    # wait until things are updated
    # @param timeout Timeout in seconds. Specify None for no timeout
    def watch_for_update(self, timeout = None):
        return self.watch(lambda v: True, must_update = True)


# A watchable state that also tracks history of the object changing
class WatchableWithHistory(object):
    # Constructor
    # @param initial_value The initial value of this watchable. Does not count towards history
    # @param name The name for this watchable, for logging only
    # @Param logger A logger to invoke any logging operations
    def __init__(self, initial_value = None, name = None, logger = None):
        self.__history = []
        self.__initial_value = initial_value
        self.__value = Watchable(None, name, logger)

    # Returns a string version of the watchable for debugging
    # @returns The debug string
    def debug_str(self):
        return "WatchableWithHistory: %s: %s" % (self.__value.name, self.__value)

    # Returns the string representation of the value
    # @returns The string representation of the value
    def __str__(self):
        return str(self.__value)

    def __update_value(self):
        if len(self.__history):
            [time, value] = self.__history[-1]
            self.__value.set(value)

    # Get the latest value
    def get(self):
        retval = None

        if len(self.__history):
            retval = self.__value.get()
        else:
            retval = self.__initial_value

        return retval

    # Get the history
    def get_history(self):
        return self.__history

    # Do an array-like get operation
    # @param index The index to look up
    def __getitem__(self, index):
        return self.__history[index]

    # Append a new value to this object
    # @param time The time
    # @param value The value
    def append(self, item):
        # Implicit check to ensure that this is a tuple
        [time, value] = item

        ret = self.__history.append(item)

        self.__update_value()

        return ret

    # Update the contained value
    # @param value the value
    def set(self, value):
        return self.append([datetime.now(), value])

    # Perform a watch. See the description of 'watch' above for Watchable
    # @param lambda_func A callable
    # @param timeout  Timeout in seconds
    # @return the result of the lambda function
    def watch(self, lambda_func, timeout = None):
        return self.__value.watch(lambda_func, timeout)

    # Perform a watch, for any change to this object. Useful
    # For waiting for a side effect to take place on a watchable
    # object after issuing a command
    def watch_for_update(self, timeout = None):
        return self.__value.watch_for_update(timeout)
