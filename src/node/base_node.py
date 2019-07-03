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
Base class of node profiles
"""
import logging
import threading
import Queue

import src.tools.watchable as watchable


def not_implemented(f):
    def wrapper(self, *args):
        print "'%s.%s' not implemented" % (self.__class__.__name__, f.__name__)
    return wrapper


class BaseNode(object):
    """
    Base node superclass
    """
    _maxTimeout = 60 * 3

    def __init__(self, name='Node'):
        self._connected = False
        self._name = name
        self._error = Queue.Queue(1)
        self._all_clear = threading.Event()
        self._lock = threading.Lock()
        self.__store = dict()
        self.logger = logging.getLogger('SilkDefault')

    def __get_log_prefix(self):
        return "%s" % self._name

    def log_debug(self, log):
        """Helper to log debug events
        """
        line = "DBG: %s: %s" % (self.__get_log_prefix(), log)
        self.logger.debug(line)

    def log_info(self, log):
        """Helper to log info events
        """
        self.logger.info("%s: %s" % (self.__get_log_prefix(), log))

    def log_error(self, log):
        """Helper to log error events
        """
        self.logger.error("ERR: %s: %s" % (self.__get_log_prefix(), log))

    def in_error(self):
        """Returns true if error condition has been set
        """
        return not self._error.empty()

    def get_error(self):
        """Returns error message and clears error condition, if any

        Returns None if there is no error.
        """
        try:
            err_msg = self._error.get_nowait()
        except Queue.Empty:
            err_msg = None
        return err_msg

    def post_error(self, msg):
        """Posts the error msg if none exists.
        """
        self.logger.error('Posting error: {0}'.format(msg))
        try:
            self.log_error(msg)
            self._error.put_nowait(msg)
        except Queue.Full:
            print '{0}: Failed to post error {1}. Already has error'.format(
                self._name, msg)

    def set_all_clear(self, is_all_clear):
        """Update Event to the value of is_all_clear

        Args:
            is_all_clear (bool): Boolean value to assign Event.

        This method should only be called with the lock and only on three
        occasions:
            1: Initially at the start of the daemon (to set event)
            2: After a message is been processed (set if queue is empty)
            3: When a message has been queued (to clear event) 

        """

        self.log_debug("Setting all-clear to %s" % is_all_clear)

        if is_all_clear:
            self._all_clear.set()
        else:
            self._all_clear.clear()

    def wait_for_completion(self):
        """Block until all queued commands and responses have been received.
        """
        self._all_clear.wait(self._maxTimeout)
        if not self._all_clear.is_set():
            print 'Did not get an all-clear!'
        return self.get_error()

    def store_data(self, value, field):
        with self._lock:
            assigned = False

            print field, value
            if isinstance(value, str):
                value = value.strip()

            if field in self.__store:
                old_value = self.__store[field]
                if watchable.is_watchable(old_value):
                    old_value.set(value)
                    assigned = True

            if not assigned:
                self.__store[field] = value

    def clear_store(self):
        with self._lock:
            self.__store = {}

    def get_data(self, field, to_type=None, default=None):
        self._lock.acquire()
        value = self.__store.get(field, default)
        self._lock.release()

        # Convert to desired type
        if to_type is not None:
            try:
                if to_type == 'hex-int':
                    value = int(value, 16)
                else:
                    value = to_type(value)
            except ValueError:
                value = default

        return value

    """ Data labels and getters """

    @property
    def name(self):
        """ Name of the node """
        return self._name

    @property
    def ip6_lla_label(self):
        return 'ip6_lla'

    @property
    def ip6_lla(self):
        """ Link-Local Address """
        return self.get_data(self.ip6_lla_label)

    @property
    def ip6_mla_label(self):
        return 'ip6_mla'

    @property
    def ip6_mla(self):
        """ Mesh-Local Address """
        return self.get_data(self.ip6_mla_label)

    @property
    def ping6_sent_label(self):
        return 'ping6_sent'

    @property
    def ping6_sent(self):
        """ Number of ping6 packets sent in most recent ping6 command """
        return self.get_data(self.ping6_sent_label, int, default=0)

    @property
    def ping6_received_label(self):
        return 'ping6_received'

    @property
    def ping6_received(self):
        """ Number of ping6 packets received in most recent ping6 command """
        return self.get_data(self.ping6_received_label, int, default=0)

    @property
    def ping6_results_label(self):
        return 'ping6_results'

    def ping6_results_process(self):
        match_results = self.get_data(self.ping6_results_label)

        self.store_data(match_results.group(1), self.ping6_sent_label)
        self.store_data(match_results.group(2), self.ping6_received_label)

        return self.ping6_get_results(self)

    def ping6_get_results(self):
        return "%s / %s " % (self.ping6_received, self.ping6_sent)

    @property
    def ping6_round_trip_time_label(self):
        return "ping6_round_trip_time"

    @property
    def ping6_round_trip_time(self):
        """Average time to receive pings"""
        return self.get_data(self.ping6_round_trip_time_label, float, default=0)

    @not_implemented
    def set_up(self):
        """Perform all hardware and software set-up to ready the node.
        """
        pass

    @not_implemented
    def tear_down(self):
        """Perform post-test hardware and software actions.
        """
        pass

    def set_logger(self, parent_logger):
        """Set logger to a child from parent_logger
        """
        self.logger = parent_logger.getChild(self._name)
        self.logger.setLevel(logging.DEBUG)

    def ping6(self, ipv6_target, num_pings, payload_size=8, interface=None):
        """Perform ping6 to ipv6_target.

        Store results in ping6_sent and ping6_received
        """
        pass        

    @not_implemented
    def reset_thread_radio(self):
        """Reset the node's thread radio
        """
        pass

    @not_implemented
    def reset_host_cpu(self, reset_thread_radio=False):
        """Reset the node host (with or w/o radio)
        """
        pass

    @not_implemented
    def firmware_version(self):
        """
        Query node's firmware version.
        """
        return None

    @not_implemented
    def firmware_update(self, fw_file):
        """
        Update the node's firmware.
        """
        pass

    @not_implemented
    def clear_state(self):
        """
        Clear any persistent state in the node.
        """
        pass
