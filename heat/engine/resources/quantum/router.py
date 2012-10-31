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
    properties_schema = {'name': {'Type': 'String'},
                        'admin_state_up': {'Type': 'Boolean',
                                      'Default': True},
    }

    def __init__(self, name, json_snippet, stack):
        super(Router, self).__init__(name, json_snippet, stack)

    def handle_create(self):
        props = dict((k, v) for k, v in self.properties.items()
            if v is not None)

        props.setdefault('name', self.name)

        router = self.quantum().create_router({'router': props})['router']
        self.instance_id_set(router['id'])

    def handle_update(self):
        return self.UPDATE_REPLACE

    def handle_delete(self):
        client = self.quantum()
        try:
            client.delete_router(self.instance_id)
        except:
            pass

    def FnGetRefId(self):
        return unicode(self.instance_id)

    def FnGetAtt(self, key):
        raise exception.InvalidTemplateAttribute(resource=self.name,
                                                 key=key)


class RouterInterface(resource.Resource):
    properties_schema = {'router_id': {'Type': 'String',
                                      'Required': True},
                        'subnet_id': {'Type': 'String',
                                      'Required': True},
    }

    def __init__(self, name, json_snippet, stack):
        super(RouterInterface, self).__init__(name, json_snippet, stack)

    def handle_create(self):
        router_id = self.properties.get('router_id')
        subnet_id = self.properties.get('subnet_id')
        self.quantum().add_interface_router(router_id,
            {'subnet_id': subnet_id})
        self.instance_id_set('%s:%s' % (router_id, subnet_id))

    def handle_update(self):
        return self.UPDATE_REPLACE

    def handle_delete(self):
        client = self.quantum()
        try:
            (router_id, subnet_id) = self.instance_id.split(':')
            client.remove_interface_router(router_id,
                {'subnet_id': subnet_id})
        except:
            pass

    def FnGetRefId(self):
        return unicode(self.instance_id)

    def FnGetAtt(self, key):
        raise exception.InvalidTemplateAttribute(resource=self.name,
                                                 key=key)


class RouterGateway(resource.Resource):
    properties_schema = {'router_id': {'Type': 'String',
                                      'Required': True},
                        'network_id': {'Type': 'String',
                                      'Required': True},
    }

    def __init__(self, name, json_snippet, stack):
        super(RouterGateway, self).__init__(name, json_snippet, stack)

    def handle_create(self):
        router_id = self.properties.get('router_id')
        network_id = self.properties.get('network_id')
        self.quantum().add_gateway_router(router_id,
            {'network_id': network_id})
        self.instance_id_set('%s:%s' % (router_id, network_id))

    def handle_update(self):
        return self.UPDATE_REPLACE

    def handle_delete(self):
        client = self.quantum()
        try:
            (router_id, network_id) = self.instance_id.split(':')
            client.remove_interface_router(router_id,
                {'network_id': network_id})
        except:
            pass

    def FnGetRefId(self):
        return unicode(self.instance_id)

    def FnGetAtt(self, key):
        raise exception.InvalidTemplateAttribute(resource=self.name,
                                                 key=key)
