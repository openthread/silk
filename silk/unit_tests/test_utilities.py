# Copyright 2020 Google LLC
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

import os
import unittest

import silk.utils.signal as signal
from silk.unit_tests.test_utils import random_string
from silk.unit_tests.testcase import SilkTestCase
from silk.utils.decorator import ignore_attribute_error
from silk.utils.directorypath import DirectoryPath
from silk.utils.network import get_local_ip
from silk.utils.process import Process


class SilkUnitTest(SilkTestCase):
    """Silk unit tests for utility methods.
    """

    @staticmethod
    def test_decorator():
        """Test AttributeError ignoring decorator.
        """

        @ignore_attribute_error
        def function():
            raise AttributeError

        function()

    def test_directory_path(self):
        """Test get directory path method.
        """
        self.assertIn("silk/unit_tests", DirectoryPath.get_dir("unit_tests"))

    def test_get_local_ip(self):
        """Test get local IP method.
        """
        ip = get_local_ip()
        # if is IPv4
        if "." in ip:
            parts = ip.split(".")
            self.assertEqual(4, len(parts))
            for part in parts:
                self.assertTrue(0 <= int(part) <= 255)
                self.assertEqual(str(int(part)), part)
        # if is IPv6
        elif ":" in ip:
            parts = ip.split(":")
            for part in parts:
                if not part:
                    continue
                self.assertTrue(0 <= int(part, 16) <= 0xffff)
        else:
            self.fail("Not a valid IP address")

    def test_process(self):
        """Test process runner.
        """
        string = random_string(10)
        process = Process(f"echo '{string}'")
        self.assertEqual(string, process.get_process_result().rstrip())

    def test_signal(self):
        """Test signal publisher and subscriber.
        """

        class TestSubscriber(signal.Subscriber):
            """Subscriber for simple unit test.
            """

            def __init__(self, test_class: SilkTestCase, expect: str):
                """Initialize a test subscriber.
                """
                super().__init__()
                self.test_class = test_class
                self.expect = expect
                self.received = False

            def subscribe_handle(self, sender, **kwargs):
                """Checks for expected signal.
                """
                line = kwargs["line"]
                if line == self.expect:
                    self.received = True

        string = random_string(10)
        publisher = signal.Publisher()
        subscriber = TestSubscriber(self, string)
        subscriber.subscribe(publisher)
        publisher.emit(line=string)
        self.assertTrue(subscriber.received)


if __name__ == "__main__":
    unittest.main()
