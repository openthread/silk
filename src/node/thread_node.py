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
Thread node profile
"""

import wpan_node
from base_node import not_implemented


class BorderRouterData(object):
    def __init__(self, fabric_id, subnet, subnet_length, gateway_prefix,
                 router_node_id, peer_node_id):
        self.fabric_id = fabric_id
        self.subnet = subnet
        self.subnet_length = subnet_length
        self.gateway_prefix = gateway_prefix
        self.router_node_id = router_node_id
        self.peer_node_id = peer_node_id

    def __str__(self):
        return_string = "Fabric ID: %s\n" % self.fabric_id
        return_string += "Subnet: %s\n" % self.subnet
        return_string += "Subnet Length: /%s\n" % self.subnet_length
        return_string += "Gateway Prefix: %s\n" % self.gateway_prefix
        return_string += "Router Node ID: %s\n" % self.router_node_id
        return_string += "Peer Node ID: %s" % self.peer_node_id


class ThreadNode(wpan_node.WpanNode):
    """
    Define the Thread node interface
    """
    def __init__(self, name='ThreadNode'):
        super(ThreadNode, self).__init__(name)

    @not_implemented
    def config_gateway(self):
        """TODO:"""
        pass

    @not_implemented
    def data_poll(self):
        """TODO:"""
        pass

    @not_implemented
    def set_sleep_poll_interval(self, milliseconds):
        """TODO:"""
        pass
