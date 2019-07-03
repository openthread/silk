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
Silk testcase class definition.

All Silk tests should inherit from this class.

"""
import collections
import json
import logging
import os
import sys
import time
import unittest

import src.config.defaults
import src.node.base_node
import src.node.openthread_sniffer as openthread_sniffer
import src.node.sniffer_base as sniffer_node
from src.hw.hw_resource import HardwareNotFound

import traceback

OUTPUT_DIRECTORY_KEY = "OUTPUT_DIRECTORY"
DATE_FORMAT = "%Y-%m-%d_%H.%M.%S"
LOG_LINE_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
SUITE_ID = "suite_id"
CASE_ID = "case_id"
PING_SENT = "pings_sent"
PING_RECEIVED = "pings_received"
PING_ROUND_TRIP_TIME = "ping_rtt"

__stream_verbosity = 1
__file_handler = None
__stream_handler = None


def setOutputDirectory(path):
    """ Set the output directory path for test results. """
    os.environ[OUTPUT_DIRECTORY_KEY] = path

def setStreamVerbosity(verbosity):
    """ Set the verbose level of console output

    0 = Minimal output (errors only)
    1 = Standard output (info)
    2 = Debug output
    """
    global __stream_verbosity
    __stream_verbosity = verbosity

def getSilkChildLogger(logger, device_name):
    """
    Silk nodes should take a logger object on instantiation.
    They should call this function with the logger and their own name to get a
    logger object into which they can publish their logs.
    """
    new_logger = logger.getChild(device_name)
    formatter = logging.Formatter(LOG_LINE_FORMAT)
    new_logger.setLevel(logging.DEBUG)

    return new_logger


def getFrameworkLogger(output_dest):
    """
    This function is only meant to be called by the setup_class_decorator.
    This creates a top-level silk logger and installs two handlers.  One
    handler writes ALL logs from children out to a file specified by the
    framework.  The other handler writes INFO level and above to the terminal.
    """
    global __file_handler
    global __stream_handler

    new_logger = logging.getLogger("silk")
    new_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_LINE_FORMAT)

    # Remove previous handler, if any
    if __file_handler is not None:
        new_logger.removeHandler(__file_handler)

    # Configure and install new file handler
    __file_handler = logging.FileHandler(output_dest, mode="w")
    __file_handler.setLevel(logging.DEBUG)
    __file_handler.setFormatter(formatter)

    if __stream_handler is not None:
        new_logger.removeHandler(__stream_handler)

    if __stream_verbosity == 0:
        stream_level = logging.CRITICAL
    elif __stream_verbosity == 1:
        stream_level = logging.INFO
    else:
        stream_level = logging.DEBUG

    __stream_handler = logging.StreamHandler()
    __stream_handler.setLevel(stream_level)
    __stream_handler.setFormatter(formatter)
    new_logger.addHandler(__stream_handler)
    new_logger.addHandler(__file_handler)

    return new_logger


def setup_decorator(func):
    """
    This decorator should be used as a wrapper for all setUp methods in
    src.

    When unittest calls setUp
    1. Store the test method name
    2. Log setUp class and method
    3. Call the user's setUp method
    4. Report if the setUp was successful
    """

    def wrapper(self, *args, **kwargs):
        # Get the method name
        self.current_test_method = self.__str__().split()[0]
        self.results[self.current_test_class][self.current_test_method] = {}
        self.results[self.current_test_class][self.current_test_method]["setUp"] = False
        self.results[self.current_test_class][self.current_test_method]["test"] = False
        self.results[self.current_test_class][self.current_test_method]["tearDown"] = False

        curr_case_id = self._testrail_dict_lookup(self.current_test_method)

        self.results[self.current_test_class][self.current_test_method][CASE_ID] = curr_case_id

        # Log the current test method
        self.logger.info("SET UP %s.%s" % (self.current_test_class,
                                           self.current_test_method))

        # Call the setUp function
        func(self)

        # Mark successful setup in the results dictionary
        self.results[self.current_test_class][self.current_test_method]["setUp"] = True

    return wrapper


def teardown_decorator(func):
    """
    Users should decorate their tearDown methods with this decorator.
    1. Mark the logs to indicate which tearDown method is running
    2. Run the client's tearDown
    3. Report a pass if tearDown was successful
    """
    def wrapper(self, *args, **kwargs):
        self.logger.info("TEAR DOWN %s.%s" % (self.current_test_class,
                                              self.current_test_method))

        self.wait_for_completion(self.device_list)
        func(self)

        # Mark successful setup in the results dictionary
        self.results[self.current_test_class][self.current_test_method]["tearDown"] = True

    return wrapper


def setup_class_decorator(func):
    """
    This decorator should be used as a wrapper for all setUpClass methods in
    src.

    When unittest calls setUpClass
    1. Get the user-specified environment variable or use default
    2. Get the test class name
    3. Create an output directory to store test results
    4. Create a top-level logger object and log the setUpClass class
    5. Create a result dictionary to store information as tests run
    6. Call the user's setUpClass method
    """
    def wrapper(*args, **kwargs):
        start_time_string = time.strftime(DATE_FORMAT)
        cls = args[0]

        cls.thread_sniffers.clear()

        if OUTPUT_DIRECTORY_KEY in os.environ:
            cls.top_output_directory = os.environ[OUTPUT_DIRECTORY_KEY]
        else:
            cls.top_output_directory = src.config.defaults.DEFAULT_LOG_OUTPUT_DIRECTORY

        # Set the test class name
        cls.current_test_class = cls.__name__

        # Create an output directory
        cls.current_output_directory = os.path.join(cls.top_output_directory,
                                                    start_time_string + "_" + cls.current_test_class)
        os.makedirs(cls.current_output_directory)

        # Create a new logger for the test framework
        silk_log_dest = os.path.join(cls.current_output_directory, "src.log")
        cls.logger = getFrameworkLogger(silk_log_dest)
        cls.logger.info("Log dest: %s" % cls.current_output_directory)
        cls.logger.info("SET UP CLASS %s" % cls.current_test_class)

        # Establish a results dictionary
        try:
            cls.results[cls.current_test_class] = collections.OrderedDict()
        except:
            cls.results = collections.OrderedDict()
            cls.results[cls.current_test_class] = collections.OrderedDict()

        curr_suite_id = cls._testrail_dict_lookup(SUITE_ID)

        cls.results[cls.current_test_class][SUITE_ID] = curr_suite_id

        # Call the user's setUpClass
        try:
            func(*args, **kwargs)

            # If the user's setUpClass call succeeded, try to Thread sniffers
            cls.thread_sniffer_start_all()
        except HardwareNotFound as e:
            cls.release_devices()
            raise

        except:
            stack = sys.exc_info()
            for call in traceback.format_tb(stack[2]):
                for line in call.rstrip().splitlines():
                    cls.logger.error(line)

            cls.logger.info("=====================================================================")
            cls.logger.info("==================== CHECK HARDWARE CONFIGURATION ===================")
            cls.logger.info("=====================================================================")
            cls.logger.info( ("%s" % cls.__name__).ljust(34,".") + "FAILED SETUPCLASS".rjust(34, "."))
            cls.logger.info("=====================================================================")
            cls.release_devices()
            raise

    return wrapper


def teardown_class_decorator(func):
    """
    Users should wrap their tearDownClass methods with this decorator.
    This will stamp the log with an indication that the tearDownClass method
    is running and will uninstall all log handlers used by this test.
    """
    def wrapper(*args, **kwargs):
        cls = args[0]
        cls.logger.info("TEAR DOWN CLASS %s" % cls.current_test_class)

        # Stop the Thread sniffer
        cls.thread_sniffer_tear_down_all()

        # Call the user teardown class function
        func(*args, **kwargs)

        # Print results summary
        cls.logger.info("=====================================================================")
        cls.logger.info("============================= SUMMARY ===============================")
        cls.logger.info("=====================================================================")
        for test_class in cls.results.keys():
            cls.logger.info(test_class)

            for test_case in cls.results[test_class]:
                if test_case == SUITE_ID:
                    continue

                test_case_name = test_case
                test_case_dict = cls.results[test_class][test_case_name]

                test_label = ("    %s" % test_case_name).ljust(34,".")

                if test_case_dict["setUp"] and test_case_dict["test"] and test_case_dict["tearDown"]:
                    cls.logger.info( test_label + "PASS".rjust(68-len(test_label), "."))
                elif not test_case_dict["setUp"]:
                    cls.logger.info( test_label + "FAILED SETUP".rjust(68-len(test_label), "."))
                elif not test_case_dict["tearDown"]:
                    cls.logger.info( test_label + "FAILED TEARDOWN".rjust(68-len(test_label), "."))
                else:
                    cls.logger.info( test_label + "FAILED TEST".rjust(68-len(test_label), "."))

        cls.logger.info("=====================================================================")

        # Remove the file and stream handler at the end of the test
        while len(cls.logger.handlers) > 0:
            cls.logger.removeHandler(cls.logger.handlers[0])

        output_file = open(os.path.join(cls.current_output_directory, "results.json"), "w")
        json.dump(cls.results, output_file, indent=4)
        output_file.close()

        cls.clear_test_devices()

    return wrapper


def test_method_decorator(func):
    """
    Users should use this decorator on all of their test methods
    1. Mark logs before test methods are called.
    2. Report if the test was successful
    """
    def wrapper(self, *args, **kwargs):

        self.add_test_device(None)
        self.wait_for_completion(self.device_list)
        self.logger.info("RUNNING TEST %s.%s" % (self.current_test_class,
                                                 self.current_test_method))

        try:
            func(self)
        except:
            stack = sys.exc_info()
            for call in traceback.format_tb(stack[2]):
                for line in call.rstrip().splitlines():
                    self.logger.error(line)
            self.logger.error(stack[1])

            raise

        self.results[self.current_test_class][self.current_test_method]["test"] = True

    return wrapper


class stress_test_decorator:
    def __init__(self, num_iterations, allowed_failures=0):
        self.num_iterations = num_iterations
        self.allowed_failures = allowed_failures

    def __call__(self, func):
        num_iterations = self.num_iterations
        allowed_failures = self.allowed_failures
        def wrapper(self, *args, **kwargs):
            self.add_test_device(None)
            self.wait_for_completion(self.device_list)
            self.logger.info("RUNNING TEST %s.%s" % (self.current_test_class,
                                                 self.current_test_method))

            pass_count = 0

            for ii in range(0, num_iterations, 1):
                self.logger.info("RUNNING TEST %s.%s (%s/%s)" % (self.current_test_class,
                                                                   self.current_test_method,
                                                                   ii+1, num_iterations))
                try:
                    func(self)
                    pass_count += 1
                except:
                    stack = sys.exc_info()
                    for call in traceback.format_tb(stack[2]):
                        for line in call.rstrip().splitlines():
                            self.logger.error(line)

            if pass_count < (num_iterations - allowed_failures):
                self.logger.error("Pass Rate: {0}/{1}".format(pass_count, num_iterations))
                self.fail("Pass Rate: {0}/{1}".format(pass_count, num_iterations))
            else:
                self.logger.info("Pass Rate: {0}/{1}".format(pass_count, num_iterations))
                self.results[self.current_test_class][self.current_test_method]["test"] = True

        return wrapper


class TestCase(unittest.TestCase):
    """
    Base class for all silk tests
    """

    thread_sniffers = {}

    def wait_for_completion(self, node_list):
        """
        Block until all nodes in node_list have completed their task queue.

        Signal test failure if any node in node_list returns an err_msg.
        """
        for n in node_list:
            err_msg = n.wait_for_completion()
            if err_msg is not None:
                self.fail(err_msg)

    def ping6(self, sender, target_addr, num_pings, ping_size=32,
              allowed_errors=0, num_expected=None, interface=None):
        if num_expected is None:
            num_expected = num_pings

        sender.ping6(target_addr, num_pings, ping_size, interface)
        self.wait_for_completion(self.device_list)

        self.results[self.current_test_class][self.current_test_method][PING_SENT] = sender.ping6_sent
        self.results[self.current_test_class][self.current_test_method][PING_RECEIVED] = sender.ping6_received

        self.logger.info("Pings sent: %s" % sender.ping6_sent)
        self.logger.info("Pings received: %s" % sender.ping6_received)
        self.assertEqual(sender.ping6_sent, num_pings)
        self.assertAlmostEqual(sender.ping6_received, num_expected,
                               delta=allowed_errors)

    def timed_ping6(self, sender, target_addr, num_pings, ping_size=32, interface=None):
        sender.timed_ping6(target_addr, num_pings, ping_size, interface)
        self.wait_for_completion(self.device_list)

        self.results[self.current_test_class][self.current_test_method][PING_ROUND_TRIP_TIME] = sender.ping6_round_trip_time

        self.logger.info("Ping RTT: %s" % sender.ping6_round_trip_time)

    def ping6_multi_dest(self, sender, target_addrs, num_pings, ping_size=32,
                         allowed_errors=0, num_expected=None, interface=None):
        """
        Sender pings all devices in target_addrs
        """
        if num_expected is None:
            num_expected = num_pings

        failed_device_count = 0

        for addr in target_addrs:
            sender.ping6(addr, num_pings, ping_size, interface)
            error = sender.wait_for_completion()

            if error is None:
                self.logger.info("Pings sent: %s" % sender.ping6_sent)
                self.logger.info("Pings received: %s" % sender.ping6_received)

            if sender.ping6_received < (num_expected - allowed_errors) or \
               sender.ping6_received > (num_expected + allowed_errors) or \
               error is not None:
                failed_device_count += 1

        self.assertEqual(failed_device_count, 0)

    def ping6_multi_source(self, senders, target_addr, num_pings, ping_size=32,
                           allowed_errors=0, num_expected=None, interface=None):
        """
        Multiple senders all ping6 the same target_addr
        """
        if num_expected is None:
            num_expected = num_pings

        failed_device_count = 0

        for sender in senders:
            sender.ping6(target_addr, num_pings, ping_size, interface)
            # Add a 2s delay to accommodate ping failure on Newman
            time.sleep(2)

        for sender in senders:
            error = sender.wait_for_completion()

            if error is not None:
                failed_device_count += 1
                continue

            elif sender.ping6_received < (num_expected - allowed_errors) or \
                 sender.ping6_received > (num_expected + allowed_errors):
                failed_device_count += 1

        self.assertEqual(failed_device_count, 0)

    @classmethod
    def get_thread_sniffer_from_type(cls, node_type):
        try:
            return node_type()
        except:
            traceback_message = traceback.format_exc()
            print traceback_message
            return None

    @classmethod
    def thread_sniffer_init(cls, channel):
        if channel in cls.thread_sniffers:
            return

        thread_sniffer_classes = [openthread_sniffer.NordicSniffer]

        new_sniffer = None
        for thread_sniffer_class in thread_sniffer_classes:
            new_sniffer = cls.get_thread_sniffer_from_type(thread_sniffer_class)

            if new_sniffer is not None:
                break

        if new_sniffer is None:
            cls.logger.debug("No more Thread sniffers for channel %s" % channel)
            new_sniffer = sniffer_node.SnifferNode()

        cls.thread_sniffers[channel] = new_sniffer
        cls.thread_sniffers[channel].set_logger(cls.logger)
        cls.thread_sniffers[channel].wait_for_completion()

    @classmethod
    def thread_sniffer_start_all(cls):
        for key in cls.thread_sniffers.keys():
            cls.thread_sniffer_start(key)

    @classmethod
    def thread_sniffer_stop_all(cls):
        for key in cls.thread_sniffer.keys():
            cls.thread_sniffer_stop(key)

    @classmethod
    def thread_sniffer_tear_down_all(cls):
        for key in cls.thread_sniffers.keys():
            cls.thread_sniffer_stop(key)
            cls.thread_sniffer_tear_down(key)

    @classmethod
    def thread_sniffer_start(cls, channel):
        if channel not in cls.thread_sniffers:
            return

        cls.logger.debug("Starting Thread sniffer on channel %s" % channel)
        cls.thread_sniffers[channel].start(channel=channel,
                                           output_path=cls.current_output_directory)
        cls.thread_sniffers[channel].wait_for_completion()

    @classmethod
    def thread_sniffer_stop(cls, channel):
        if channel not in cls.thread_sniffers:
            return

        cls.logger.debug("Stopping Thread sniffer on channel %s" % channel)
        cls.thread_sniffers[channel].stop()
        cls.thread_sniffers[channel].wait_for_completion()

    @classmethod
    def thread_sniffer_restart(cls, channel):
        if channel not in cls.thread_sniffers:
            return

        cls.thread_sniffers[channel].restart()
        cls.thread_sniffers[channel].wait_for_completion()

    @classmethod
    def thread_sniffer_get_stats(cls, channel):
        if channel not in cls.thread_sniffers:
            return

        cls.thread_sniffers[channel].get_stats()
        cls.thread_sniffers[channel].wait_for_completion()

    @classmethod
    def thread_sniffer_tear_down(cls, channel):
        if channel not in cls.thread_sniffers:
            return

        cls.thread_sniffers[channel].tear_down()
        cls.thread_sniffers[channel].wait_for_completion()

    @classmethod
    def add_test_device(cls, device):
        if not hasattr(cls, "device_list"):
            cls.device_list = []

        if device is not None:
            cls.device_list.append(device)

    @classmethod
    def clear_test_devices(cls):
        if hasattr(cls, "device_list"):
            while len(cls.device_list) > 0:
                cls.device_list.pop()

    @classmethod
    def release_devices(cls):
        # Release any claimed hardware
        for attr in dir(cls):
            d = getattr(cls, attr)
            if isinstance(d, src.node.base_node.BaseNode):
                d.tear_down()

    @classmethod
    def _testrail_dict_lookup(cls, test_element):
        """
        Return TestRail ID from TestRail dictionary key
        """
        return_id = None
        if hasattr(cls, "testrail_dict"):
            if test_element in cls.testrail_dict:
                return_id = cls.testrail_dict[test_element]

        return return_id
