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

import logging


class SnifferNode(object):
    def __init__(self):
        self.logger = None
        self.device = None

    def set_up(self):
        self.logger.debug("Set Up failed. No sniffer present.")

    def tear_down(self):
        self.logger.debug("Tear Down failed. No sniffer present.")

    def set_logger(self, parent_logger):
        if self.device is not None:
            self.logger = parent_logger.getChild(self.device.name())
        else:
            self.logger = parent_logger.getChild("MissingSniffer")

        self.logger.setLevel(logging.DEBUG)

    def start(self, channel, output_path):
        self.logger.debug("Start failed. No sniffer present for channel %s." % channel)

    def restart(self):
        self.logger.debug("Restart failed. No sniffer present.")

    def stop(self):
        self.logger.debug("Stop failed. No sniffer present.")

    def get_stats(self):
        self.logger.debug("Get Stats failed. No sniffer present.")

    def wait_for_completion(self):
        pass
