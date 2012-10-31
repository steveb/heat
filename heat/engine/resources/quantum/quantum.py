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


class QuantumResource(resource.Resource):

    def __init__(self, name, json_snippet, stack):
        super(QuantumResource, self).__init__(name, json_snippet, stack)

    def validate(self):
        '''
        Validate any of the provided params
        '''
        res = super(QuantumResource, self).validate()
        if res:
            return res

        if 'value_specs' in self.properties.keys():
            # make sure nothing in value_specs overwrites
            # anything in the main properties
            vs = self.properties.get('value_specs')
            banned_keys = set(['shared', 'tenant_id']).union(
                self.properties.keys())
            for k in banned_keys.intersection(vs.keys()):
                return '%s Not allowed in value_specs' % k

    def prepare_properties(self):
        # remove None values and value_specs
        props = dict((k, v) for k, v in self.properties.items()
            if v is not None and k != 'value_specs')

        if 'name' in self.properties.keys():
            props.setdefault('name', self.name)

        if 'value_specs' in self.properties.keys():
            props.update(self.properties.get('value_specs'))

        return props

    def handle_get_attributes(self, key, attributes, excluded=['id']):
        if key in excluded:
            raise exception.InvalidTemplateAttribute(resource=self.name,
                                                     key=key)
        if key in attributes.keys():
            value = attributes[key]
            return value

        raise exception.InvalidTemplateAttribute(resource=self.name,
                                                     key=key)

    def handle_update(self):
        return self.UPDATE_REPLACE

    def FnGetRefId(self):
        return unicode(self.instance_id)
