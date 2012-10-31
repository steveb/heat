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


class FloatingIP(resource.Resource):
    properties_schema = {'floating_network_id': {'Type': 'String',
                                    'Required': True},
                        'value_specs': {'Type': 'Map'},
                        'port_id': {'Type': 'String'},
                        'fixed_ip_address': {'Type': 'String'},
    }

    def handle_create(self):
        props = dict((k, v) for k, v in self.properties.items()
            if v is not None and k != 'value_specs')

        value_specs = self.properties.get('value_specs')
        if value_specs is not None:
            props.update(value_specs)

        fip = self.quantum().create_floatingip({
            'floatingip': props})['floatingip']
        self.instance_id_set(fip['id'])

    def handle_update(self):
        return self.UPDATE_REPLACE

    def handle_delete(self):
        client = self.quantum()
        try:
            client.delete_floatingip(self.instance_id)
        except:
            pass

    def FnGetRefId(self):
        return unicode(self.instance_id)

    def FnGetAtt(self, key):
        raise exception.InvalidTemplateAttribute(resource=self.name,
                                                 key=key)


class FloatingIPAssociation(resource.Resource):
    properties_schema = {'floatingip_id': {'Type': 'String',
                                    'Required': True},
                        'port_id': {'Type': 'String',
                                    'Required': True},
                        'fixed_ip_address': {'Type': 'String'}
    }

    def __init__(self, name, json_snippet, stack):
        super(FloatingIPAssociation, self).__init__(name, json_snippet, stack)

    def handle_create(self):
        props = dict((k, v) for k, v in self.properties.items()
            if v is not None)

        floatingip_id = props.pop('floatingip_id')

        self.quantum().update_floatingip(floatingip_id, {
            'floatingip': props})['floatingip']
        self.instance_id_set('%s:%s' % (floatingip_id, props['port_id']))

    def handle_update(self):
        return self.UPDATE_REPLACE

    def handle_delete(self):
        client = self.quantum()
        try:
            (floatingip_id, port_id) = self.instance_id.split(':')
            client.update_floatingip(floatingip_id,
                {'floatingip': {'port_id': None}})
        except:
            pass

    def FnGetRefId(self):
        return unicode(self.instance_id)

    def FnGetAtt(self, key):
        raise exception.InvalidTemplateAttribute(resource=self.name,
                                                 key=key)
