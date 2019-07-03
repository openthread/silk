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
Implements publisher/subscriber classes for passing messages.
"""
import logging

import dispatch

from src.utils import decorator


class SignalLoggerAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter for adding extra logging to signal classes.
    """
    def process(self, msg, kwargs):
        """
        This will print out not only the standard Lattice logline, but also
        the subscriber that reported the log event and the source of the line
        (if available).
        """
        return "%s%s: %s" % (self.extra['source'], self.extra['classname'], msg), kwargs


class SignalLogger(object):
    """
    Convenient class for adding logging functionality only if a logger is set
    in the class.
    """

    @property
    def logger(self):
        """
        Returns the SignalLoggerAdapter instance. None if never set.
        """
        try:
            return self._logger
        except AttributeError:
            pass

    @logger.setter
    def logger(self, value):
        """
        Sets the logger by wrapping it with the SignalLoggerAdapter.
        """
        if not isinstance(value, logging.Logger):
            raise TypeError("value must be a Logger type")

        try:
            source = ("%s " % self.sourceName) if self.sourceName else ""
        except AttributeError:
            source = ""

        self._logger = SignalLoggerAdapter(value,
                                           {'source': source,
                                            'classname': self.__class__.__name__})

    @decorator.ignore_attribute_error
    def debug(self, msg, *args, **kwargs):
        """
        Log message at DEBUG level.
        """
        self.logger.debug(msg, *args, **kwargs)

    @decorator.ignore_attribute_error
    def info(self, msg, *args, **kwargs):
        """
        Log message at INFO level.
        """
        self.logger.info(msg, *args, **kwargs)

    @decorator.ignore_attribute_error
    def warn(self, msg, *args, **kwargs):
        """
        Alias of warning.
        """
        self.warning(msg, *args, **kwargs)

    @decorator.ignore_attribute_error
    def warning(self, msg, *args, **kwargs):
        """
        Log message at WARN level.
        """
        self.logger.warning(msg, *args, **kwargs)

    @decorator.ignore_attribute_error
    def error(self, msg, *args, **kwargs):
        """
        Log message at ERROR level.
        """
        self.logger.error(msg, *args, **kwargs)

    @decorator.ignore_attribute_error
    def critical(self, msg, *args, **kwargs):
        """
        Log message at CRITICAL level.
        """
        self.logger.critical(msg, *args, **kwargs)

    @decorator.ignore_attribute_error
    def fatal(self, msg, *args, **kwargs):
        """
        Log message at FATAL level.
        """
        self.logger.fatal(msg, *args, **kwargs)

    @decorator.ignore_attribute_error
    def exception(self, msg, *args, **kwargs):
        """
        Log message as exception.
        """
        self.logger.exception(msg, *args, **kwargs)


class Publisher(SignalLogger):
    """
    Base class for signaling Publisher.

    The base __init__ function setups the signaling object that a Subscriber
    can connect to.

    The child class
    """
    def __init__(self):
        """
        Setups signaling object.
        """
        super(Publisher, self).__init__()
        self._signal = dispatch.Signal()

    def subscribe(self, handle):
        """
        Subscribe a handle to this publisher.
        """
        self._signal.connect(handle)

    def unsubscribe(self, handle):
        """
        Unsubscribe a handle from this publisher.
        """
        self._signal.disconnect(handle)

    def emit(self, **kwargs):
        """
        Emits arguments to the subscribers.
        """
        self._signal.send(sender=self, **kwargs)


class Subscriber(SignalLogger):
    """
    Base class for signaling Subscriber.
    """
    def __init__(self, publisher=None, sourceName=None):
        """
        Creates a new subscriber for parsing logs.

        :param publisher:
            Publisher instance to subscribe to.
        :type publisher:
            Publisher

        :param sourceName:
            the source of the log lines. If provided, the source will be
            printed with each log.
        :type sourceName:
            string
        """
        super(Subscriber, self).__init__()

        self.publishers = []
        self.sourceName = sourceName

        if publisher:
            self.subscribe(publisher)

    def __del__(self):
        """
        Automatically unsubscribe from all publishers if the object is deleted.
        """
        self.unsubscribe()

    def subscribe(self, publisher):
        """
        Subscribe to a given publisher.
        """
        if not isinstance(publisher, Publisher):
            raise TypeError("publisher must be a type Publisher but was %s"
                            % type(publisher))

        publisher.subscribe(self.subscribeHandle)
        self.publishers.append(publisher)

    def unsubscribe(self, publisher=None):
        """
        Unsubscribe from the pubisher. If publisher argument is None (default),
        this function will unsubscribe from all publishers.
        """
        # Defaulting to an empty list here works around a race condition where
        # this object is destroyed via __del__ before __init__ was called.
        publishers = getattr(self, 'publishers', [])
        if publisher is None:
            for publisher in publishers:
                publisher.unsubscribe(self.subscribeHandle)
            self.publishers = []
        else:
            if publisher in publishers:
                publisher.unsubscribe(self.subscribeHandle)

    def subscribeHandle(self, sender, **kwargs):
        """
        Handler method that should be overwritten from the publisher.
        """
        pass
