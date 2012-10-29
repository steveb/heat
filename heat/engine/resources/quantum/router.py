# vim: tabstop=4 shiftwidth=4 softtabstop=4

#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from heat.common import exception
from heat.engine.resources import resource
from novaclient.exceptions import NotFound

from heat.openstack.common import log as logging

logger = logging.getLogger('heat.engine.quantum')


class Router(resource.Resource):
    properties_schema = {'name': {'Type': 'String',
                                    'Required': True},
                        'value_specs': {'Type': 'Map'},
                        'admin_state': {'Type': 'String',
                                      'AllowedValues': ['up', 'down'],
                                      'Default': 'up'},
    }

    def __init__(self, name, json_snippet, stack):
        super(Router, self).__init__(name, json_snippet, stack)


class RouterInterface(resource.Resource):
    properties_schema = {'router_id': {'Type': 'String',
                                      'Required': True},
                        'subnet_id': {'Type': 'String',
                                      'Required': True},
    }

    def __init__(self, name, json_snippet, stack):
        super(RouterInterface, self).__init__(name, json_snippet, stack)


class RouterGateway(resource.Resource):
    properties_schema = {'router_id': {'Type': 'String',
                                      'Required': True},
                        'external_network_id': {'Type': 'String',
                                      'Required': True},
    }

    def __init__(self, name, json_snippet, stack):
        super(RouterGateway, self).__init__(name, json_snippet, stack)
