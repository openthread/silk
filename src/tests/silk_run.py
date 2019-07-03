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

""" Silk Test Runner

Enables the discovery and running of Silk Tests from the command line.
"""

import argparse
import sys
import time
import unittest
import os

import src.hw.hw_resource as hw_resource
import src.tests.testcase
import logging


class Colors(object):
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    ENDC = '\033[0m'


RESULT_LOG_PATH = '/opt/openthread_test/results/'
CONFIG_PATH = '/opt/openthread_test/config/'


class SilkTestResult(unittest.TestResult):
    """ TestResult class to maintain and display silk results

    This class extends the base class to maintain order of tests run and to
    display the result in summary form.
    """

    testname_spacing = 64
    line_length = testname_spacing + 8
    result_pass = Colors.GREEN + "PASS" + Colors.ENDC
    result_fail = Colors.RED + "FAILED" + Colors.ENDC

    def __init__(self, verbosity, results_dir=None):
        unittest.TestResult.__init__(self)
        self.successes = []
        self.testlist = []
        self.startTime = time.time()
        self.current_testclass = None
        self.verbosity = verbosity

        if results_dir:
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
            logging.basicConfig(format='%(levelname)s:%(message)s', filename=results_dir+'/test_summary.log',
                                level=logging.DEBUG)
        else:
            logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

    def addSuccess(self, test): 
        unittest.TestResult.addSuccess(self, test)
        self.successes.append(test)
        if self.verbosity == 0:
            self.printTestResultLine(test, self.result_pass)

    def addFailure(self, test, err): 
        unittest.TestResult.addFailure(self, test, err)
        if self.verbosity == 0:
            self.printTestResultLine(test, self.result_fail)

    def stopTest(self, test):
        unittest.TestResult.stopTest(self, test)
        self.testlist.append(test)

    def printTestSummary(self):
        self.printTestErrors()
        self.printTestResults()
        self.printBanner('SUMMARY')
        end_time = time.time()
        self.printStatLine('Start time:', time.ctime(self.startTime))
        self.printStatLine('End time:', time.ctime(end_time))
        self.printStatLine('Execution time:', time.strftime('%H:%M:%S', time.gmtime(time.time() - self.startTime)))
        self.printStatLine('Tests skipped:', len(self.skipped))
        self.printStatLine('Tests errors:', len(self.errors))
        self.printStatLine('Tests run:', self.testsRun)
        self.printStatLine('Tests passed:', len(self.successes))
        self.printStatLine('Tests failed:', len(self.failures))

    def printStatLine(self, name, result):
        print '{0}{1}'.format(name.ljust(16), result)
        logging.info('{0}{1}'.format(name.ljust(16), result))

    def printTestResults(self):
        if self.verbosity > 0:
            self.printBanner('TEST RESULTS RECAP')
            self.current_testclass = None
            for t in self.testlist:
                self.printTestFailure(t)
                self.printTestSuccess(t)
            print "=" * self.line_length

    def printTestFailure(self, t):
        for f in self.failures:
            if f[0] == t:
                self.printTestResultLine(t, self.result_fail)

    def printTestSuccess(self, t):
        if t in self.successes:
            self.printTestResultLine(t, self.result_pass)

    def printTestResultLine(self, test, result):
        if self.testsRun == 1:
            self.printBanner('TEST RESULTS')
        if test.__class__ != self.current_testclass:
            self.current_testclass = test.__class__
            tc = test.__class__
            print '{0}.{1}'.format(tc.__module__, tc.__name__)
            logging.info('{0}.{1}'.format(tc.__module__, tc.__name__))

        print '    {0}{1}'.format(test._testMethodName.ljust(self.testname_spacing, '.'), result)
        logging.info('    {0}{1}'.format(test._testMethodName.ljust(self.testname_spacing, '.'), result))

    def printTestErrors(self):
        self.printBanner('HARDWARE TEST SET-UP ERRORS')
        for e in self.errors:
            print str(e[0])

    def printBanner(self, title):
        print '\n'
        print '=' * self.line_length
        logging.info('=' * self.line_length)
        print title.join([' ', ' ']).center(self.line_length, '=')
        logging.info(title.join([' ', ' ']).center(self.line_length, '='))
        print '=' * self.line_length
        logging.info('=' * self.line_length)


class SilkRunner(object):
    """ Discovers and runs tests from the command line
    """

    def __init__(self, argv=None):
        args = self.parseArgs(argv)
        self.verbosity = args.verbosity
        self.pattern = args.pattern
        self.results_dir = args.results_dir
        if args.results_dir is not None:
            print 'Setting results dir to {0}'.format(args.results_dir)
            src.tests.testcase.setOutputDirectory(args.results_dir)
        src.tests.testcase.setStreamVerbosity(self.verbosity)
        hw_resource.global_instance(args.hw_conf_file)

        self.discover()
        self.run()

    def parseArgs(self, argv):
        parser = argparse.ArgumentParser(
            description='Run a suite of Silk Tests')
        parser.add_argument('-d', '--results_dir', dest='results_dir',
            metavar='ResPath',
            help='Set the directory path for test results')
        parser.add_argument('-c', '--hwconfig', dest='hw_conf_file',
            metavar='ConfFile',
            help='Name the hardware config file')
        parser.add_argument('-v', '--verbose', '--verbosity', type=int,
            default=1, choices=range(0, 3), dest='verbosity', metavar='X',
            help='Set the verbosity level of the console (0=quiet, 1=default, 2=verbose)')
        parser.add_argument('pattern', nargs='+', metavar='P',
            help='test file search pattern')
        return parser.parse_args(argv[1:])

    def discover(self):
        self.test_suite = unittest.TestSuite()
        for p in self.pattern:
            self.test_suite.addTest(unittest.defaultTestLoader.discover('./', p))
        print 'Found {0} test cases.'.format(self.test_suite.countTestCases())

    def run(self):
        print 'Running tests...'
        tr = SilkTestResult(self.verbosity, self.results_dir)
        self.test_suite.run(tr)
        tr.printTestSummary()


if __name__ == "__main__":

    SilkRunner(argv=sys.argv)
