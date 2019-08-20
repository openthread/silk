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
message_item.py

This module provides a base class for message items processed by the embedded shell and system call manager
"""


class MessageItemDelegates:

    # Constructor
    # @param instance Instance object for all of the callables
    # @param expect_handler An callable for handling expect calls
    # @param send_handler A callable for hanlding for send calls
    # @param error_handler A callable for handling errors
    def __init__(self, instance, expect_handler, send_handler, error_handler):
        self.instance = instance
        self.expect_handler = expect_handler
        self.send_handler = send_handler
        self.error_handler = error_handler

    # Perform an expect
    # See arguments in envision.Envision
    def expect(self, expect_list, timeout = None):
        return self.expect_handler(self.instance, expect_list, timeout)

    # Perform a send
    # See arguments in envision.Envision
    def send(self, command, echo=True):
        return self.send_handler(self.instance, command, echo)

    # Report an error
    # @param error_str The error string
    def set_error(self, error_str):
        return self.error_handler(self.instance, error_str)


class MessageItemBase(object):
    """
    Base class used to encapsulate message/work objects handled by EmbeddedShell's message queue
    """

    def __init__(self):
        self._delegates = None
        pass

    # Set the delegates
    # @param delegates Some delegates
    def set_delegates(self, delegates):
        self._delegates = delegates

    def invoke(self, parent):
        """ Invoke the action to be taken. 
            Return true if the worker thread should exit.
        """
        raise NotImplementedError()


class MessageCallableItem(MessageItemBase):
    """ 
    Class to encapusulate a command/expect message into the message
    queue.
    
    callable_ must be a method that returns true when action is complete. 
    Must not return false indefinitely.
    """
    def __init__(self, callable_, args):
        super(MessageCallableItem, self).__init__()
        self.__callable = callable_
        self.__args = args

    def __call(self):
        """ Invoke the underlying callable
        """
        args = self.__args + (self._delegates,)
        satisfied = self.__callable(*args)
        return satisfied

    def invoke(self, parent):
        """ Invoke the action repeatedly via callable method until the callable returns true.
            Return true if the worker thread should exit.
        """
        should_exit = False

        while not parent.in_error() and not self.__call():
            pass

        return should_exit


class MessageExitItem(MessageItemBase):
    """Class to encapsulate a worker thread exit message into the message queue
    """

    def __init__(self):
        super(MessageExitItem, self).__init__()

    def invoke(self, parent):
        should_exit = True

        return should_exit
