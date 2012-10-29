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


class FloatingIP(resource.Resource):
    properties_schema = {'floating_network_id': {'Type': 'String',
                                    'Required': True},
                        'value_specs': {'Type': 'Map'},
                        'port_id': {'Type': 'String'},
                        'fixed_ip_address': {'Type': 'String'},
    }

    def __init__(self, name, json_snippet, stack):
        super(FloatingIP, self).__init__(name, json_snippet, stack)


class FloatingIPAssociation(resource.Resource):
    properties_schema = {'floatingip_id': {'Type': 'String',
                                    'Required': True},
                        'port_id': {'Type': 'String',
                                    'Required': True},
    }

    def __init__(self, name, json_snippet, stack):
        super(FloatingIPAssociation, self).__init__(name, json_snippet, stack)
