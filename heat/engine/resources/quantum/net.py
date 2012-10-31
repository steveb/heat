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

from heat.openstack.common import log as logging

logger = logging.getLogger('heat.engine.quantum')


class Net(resource.Resource):
    properties_schema = {'name': {'Type': 'String'},
                        'value_specs': {'Type': 'Map'},
                        'admin_state_up': {'Default': True},
    }

    def __init__(self, name, json_snippet, stack):
        super(Net, self).__init__(name, json_snippet, stack)

    def handle_create(self):
        props = dict((k, v) for k, v in self.properties.items()
            if v is not None and k != 'value_specs')

        props.setdefault('name', self.name)
        value_specs = self.properties.get('value_specs')
        if value_specs is not None:
            props.update(value_specs)

        net = self.quantum().create_network({'network': props})['network']
        self.instance_id_set(net['id'])

    def handle_update(self):
        return self.UPDATE_REPLACE

    def handle_delete(self):
        client = self.quantum()
        try:
            client.delete_network(self.instance_id)
        except:
            pass

    def FnGetRefId(self):
        return unicode(self.instance_id)

    def FnGetAtt(self, key):
        raise exception.InvalidTemplateAttribute(resource=self.name,
                                                 key=key)
