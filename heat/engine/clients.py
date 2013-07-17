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

from oslo.config import cfg

from heat.openstack.common import importutils
from heat.openstack.common import log as logging

logger = logging.getLogger(__name__)


from heat.common import heat_keystoneclient as hkc
from novaclient import client as novaclient
try:
    from swiftclient import client as swiftclient
except ImportError:
    swiftclient = None
    logger.info('swiftclient not available')
try:
    from quantumclient.v2_0 import client as quantumclient
except ImportError:
    quantumclient = None
    logger.info('quantumclient not available')
try:
    from cinderclient import client as cinderclient
except ImportError:
    cinderclient = None
    logger.info('cinderclient not available')


cloud_opts = [
    cfg.StrOpt('cloud_backend',
               default=None,
               help="Cloud module to use as a backend. Defaults to OpenStack.")
]
cfg.CONF.register_opts(cloud_opts)


class OpenStackClients(object):
    '''
    Convenience class to create and cache client instances.
    '''

    def __init__(self, context):
        self.context = context
        self._nova = {}
        self._keystone = None
        self._swift = None
        self._quantum = None
        self._cinder = None

    def keystone(self):
        if self._keystone:
            return self._keystone

        self._keystone = hkc.KeystoneClient(self.context)
        return self._keystone

    def url_for(self, **kwargs):
        return self.keystone().url_for(**kwargs)

    def nova(self, service_type='compute'):
        if service_type in self._nova:
            return self._nova[service_type]

        con = self.context
        if con.auth_token is None:
            logger.error("Nova connection failed, no auth_token!")
            return None

        args = {
            'project_id': con.tenant,
            'auth_url': con.auth_url,
            'service_type': service_type,
            'username': None,
            'api_key': None
        }

        client = novaclient.Client(1.1, **args)

        management_url = self.url_for(service_type=service_type)
        client.client.auth_token = con.auth_token
        client.client.management_url = management_url

        self._nova[service_type] = client
        return client

    def swift(self):
        if swiftclient is None:
            return None
        if self._swift:
            return self._swift

        con = self.context
        if con.auth_token is None:
            logger.error("Swift connection failed, no auth_token!")
            return None

        args = {
            'auth_version': '2.0',
            'tenant_name': con.tenant,
            'user': con.username,
            'key': None,
            'authurl': None,
            'preauthtoken': con.auth_token,
            'preauthurl': self.url_for(service_type='object-store')
        }
        self._swift = swiftclient.Connection(**args)
        return self._swift

    def quantum(self):
        if quantumclient is None:
            return None
        if self._quantum:
            return self._quantum

        con = self.context
        if con.auth_token is None:
            logger.error("Quantum connection failed, no auth_token!")
            return None

        args = {
            'auth_url': con.auth_url,
            'service_type': 'network',
            'token': con.auth_token,
            'endpoint_url': self.url_for(service_type='network')
        }

        self._quantum = quantumclient.Client(**args)

        return self._quantum

    def cinder(self):
        if cinderclient is None:
            return self.nova('volume')
        if self._cinder:
            return self._cinder

        con = self.context
        if con.auth_token is None:
            logger.error("Cinder connection failed, no auth_token!")
            return None

        args = {
            'service_type': 'volume',
            'auth_url': con.auth_url,
            'project_id': con.tenant,
            'username': None,
            'api_key': None
        }

        self._cinder = cinderclient.Client('1', **args)
        management_url = self.url_for(service_type='volume')
        self._cinder.client.auth_token = con.auth_token
        self._cinder.client.management_url = management_url

        return self._cinder

if cfg.CONF.cloud_backend:
    cloud_backend_module = importutils.import_module(cfg.CONF.cloud_backend)
    Clients = cloud_backend_module.Clients
else:
    Clients = OpenStackClients

logger.debug('Using backend %s' % Clients)
