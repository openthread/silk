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
Various time and timeout related utilties
"""

import datetime


# A class encapsulating tracking of a timeout
# Useful for cases where a timeout is passed in by the user and successive calls
# to blocking calls with timeouts need to be performed with timeout values adjusted
# according to the time remaining
class Deadline(object):
    # Constructor
    # @param timeout The timeout, in seconds. Specify None for an "infinite" timeout
    # @param start_now Whether to start tracking time passed now or wait until the first call
    def __init__(self, timeout = None, start_now = False):
        self.__timeout = None

        self.__start_time = None
        self.__end_time = None

        if timeout is not None:
            self.__timeout = datetime.timedelta(seconds = timeout)

        if start_now:
            self.__calculate_start_time()

    def __calculate_start_time(self):
        retval = self.__start_time is None
        if retval:
            self.__start_time = datetime.datetime.now()
            if self.__timeout is not None:
                self.__end_time = self.__start_time + self.__timeout

        return retval

    # Start tracking the time passed from now. Will throw a RuntimeError if tracking was already started
    def start(self):
        started = self.__calculate_start_time()
        if started == False:
            raise RuntimeError("Tracking already started")

    # Get the remaining time left, in seconds
    # @returns The time left in seconds
    def get_remaining_seconds(self):
        retval = None

        self.__calculate_start_time()

        if self.__end_time is not None:
            # Calculate how long it is until the deadline
            now = datetime.datetime.now()
            delta = self.__end_time - now
            retval = delta.total_seconds()
            if retval < 0:
                retval = 0

        return retval


# A class encapsulating tracking of the duration of an operation.
# Useful for cases where one wants to track how long something took.
class Duration(object):
    # Constructor
    # @param start_now Specify whether the start time should start now, or wait until explicitly invoked
    def __init__(self, start_now = False):
        self.__start_time = None

        if start_now:
            self.__calculate_start_time()

    def __calculate_start_time(self):
        retval = self.__start_time is None
        if retval:
            self.__start_time = datetime.datetime.now()
            print "Started", self.__start_time

        return retval

    # Return the start time
    # @returns the start time
    @property
    def start_time(self):
        return self.__start_time

    # Start the duration, if not already started
    def start(self):
        return self.__calculate_start_time()

    # Get the time since the start time
    # @returns The time in seconds
    def get_elapsed_seconds(self):
        retval = None

        self.__calculate_start_time()

        now = datetime.datetime.now()
        print "Now", now
        diff = now - self.start_time
        retval = diff.seconds

        return retval

