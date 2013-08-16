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
from heat.engine import clients
from heat.engine import scheduler
from heat.engine.resources import nova_utils
from heat.engine import resource
from heat.openstack.common.gettextutils import _
from heat.openstack.common import log as logging

logger = logging.getLogger(__name__)


class Server(resource.Resource):

    block_mapping_schema = {
        'device_name': {
            'Type': 'String',
            'Required': True,
            'Description': _('A device name where the volume will be '
                             'attached in the system at /dev/device_name. '
                             'This value is typically vda')},
        'volume_id': {
            'Type': 'String',
            'Description': _('The ID of the volume to boot from. Only one of '
                             'volume_id or snapshot_id should be verified')},
        'snapshot_id': {
            'Type': 'String',
            'Description': _('The ID of the snapshot to create a volume from')},
        'volume_size': {
            'Type': 'String',
            'Description': _('The size of the volume, in GB. It is safe to '
                             'leave this blank and have the Compute service '
                             'infer the size')},
        'delete_on_termination': {
            'Type': 'Boolean',
            'Description': _('Indicate whether the volume should be deleted when '
                             'the instance is terminated')}
    }

    networks_schema = {
        'uuid': {
            'Type': 'String'},
        'fixed_ip': {
            'Type': 'String'},
        'port': {
            'Type': 'String'},
    }

    properties_schema = {
        'name': {
            'Type': 'String',
            'Description': _('Optional server name')},
        'image': {
            'Type': 'String',
            'Description': _('The ID or name of the image to boot with')},
        'block_device_mapping': {
            'Type': 'List',
            'Description': _('Block device mappings for this server.'),
            'Schema': {
                'Type': 'Map',
                'Schema': block_mapping_schema
            }
        },
        'flavor': {
            'Type': 'String',
            'Description': _('The ID or name of the flavor to boot onto'),
            'Required': True},
        'key_name': {
            'Type': 'String',
            'Description': _('Name of keypair to inject into the server')},
        'availability_zone': {
            'Type': 'String',
            'Description': _('Name of the availability zone for server '
                             'placement')},
        'security_groups': {
            'Type': 'List',
            'Description': _('List of security group names')},
        'networks': {
            'Type': 'List',
            'Description': _('An ordered list of nics to be '
                             'added to this server, with information about '
                             'connected networks, fixed ips, port etc'),
             'Schema': {
                 'Type': 'Map',
                 'Schema': networks_schema
            }
        },
        'os:scheduler_hints': {
            'Type': 'Map',
            'Description': _('Arbitrary key-value pairs specified by the '
                             'client to help boot an instance')},
        'metadata': {
            'Type': 'Map',
            'Description': _('Arbitrary key/value metadata to store for this '
                             'server. A maximum of five entries is allowed, '
                             'and both keys and values must be 255 characters '
                             'or less')},
        'user_data': {
            'Type': 'String',
            'Description': _('User data script to be executed by cloud-init')},
        'reservation_id': {
            'Type': 'String',
            'Description': _('A UUID for the set of servers being requested'),
            'Implemented': False},
        'config_drive': {
            'Type': 'String',
            'Description': _('value for config drive either boolean, or '
                             'volume-id'),
            'Implemented': False},
        'OS-DCF:diskConfig': {
            'Type': 'String',
            'Description': _('Control how the disk is partitioned when the '
                             'server is created'),
            'AllowedValues': ['AUTO', 'MANUAL']}
    }

    update_allowed_keys = ('Metadata', 'Properties')
    update_allowed_properties = ('flavor',)


    def __init__(self, name, json_snippet, stack):
        super(Server, self).__init__(name, json_snippet, stack)
        self.ipaddress = None
        self.mime_string = None

    def _set_ipaddress(self, networks):
        '''
        Read the server's IP address from a list of networks provided by Nova
        '''
        # Just record the first ipaddress
        for n in networks:
            if len(networks[n]) > 0:
                self.ipaddress = networks[n][0]
                break

    def get_mime_string(self, userdata):
        if not self.mime_string:
            self.mime_string = nova_utils.build_userdata(self, userdata)
        return self.mime_string

    def handle_create(self):
        security_groups = self.properties.get('security_groups', [])
        userdata = self.properties.get('user_data', '')
        flavor = self.properties['flavor']
        availability_zone = self.properties['availability_zone']

        key_name = self.properties['key_name']
        if key_name:
            # confirm keypair exists
            nova_utils.get_keypair(self.nova(), key_name)

        image = self.properties.get('image', None)
        if image:
            image = nova_utils.get_image_id(self.nova(), image)

        flavor_id = nova_utils.get_flavor_id(self.nova(), flavor)
        instance_meta = self.properties.get('metadata', None)
        scheduler_hints = self.properties.get('os:scheduler_hints', None)
        nics = self._build_nics(self.properties.get('networks', None))
        block_device_mapping = self._build_block_device_mapping(
            self.properties.get('block_device_mapping', None))
        reservation_id = self.properties.get('reservation_id', None)
        config_drive = self.properties.get('config_drive', None)
        disk_config = self.properties.get('OS-DCF:diskConfig', None)

        server = None
        try:
            server = self.nova().servers.create(
                name=self.physical_resource_name(),
                image=image,
                flavor=flavor_id,
                key_name=key_name,
                security_groups=security_groups,
                userdata=self.get_mime_string(userdata),
                meta=instance_meta,
                scheduler_hints=scheduler_hints,
                nics=nics,
                availability_zone=availability_zone,
                block_device_mapping=block_device_mapping,
                reservation_id=reservation_id,
                config_drive=config_drive,
                disk_config=disk_config)
        finally:
            # Avoid a race condition where the thread could be cancelled
            # before the ID is stored
            if server is not None:
                self.resource_id_set(server.id)

        return server

    def check_create_complete(self, server):

        if server.status != 'ACTIVE':
            server.get()

        # Some clouds append extra (STATUS) strings to the status
        short_server_status = server.status.split('(')[0]
        if short_server_status in nova_utils.deferred_server_statuses:
            return False
        elif server.status == 'ACTIVE':
            self._set_ipaddress(server.networks)
        elif server.status == 'ERROR':
            delete = scheduler.TaskRunner(nova_utils.delete_server, server)
            delete(wait_time=0.2)
            exc = exception.Error(_('Build of server %s failed.') %
                                  server.name)
            raise exc
        else:
            exc = exception.Error(_('%s instance[%s] status[%s]') %
                                  ('nova reported unexpected',
                                   self.name, server.status))
            raise exc

    @staticmethod
    def _build_nics(networks):
        if not networks:
            return None

        nics = []

        for net_data in networks:
            nic_info = {}
            if net_data.get('uuid'):
                nic_info['net-id'] = net_data['uuid']
            if net_data.get('fixed_ip'):
                nic_info['v4-fixed-ip'] = net_data['fixed_ip']
            if net_data.get('port'):
                nic_info['port-id'] = net_data['port']
            nics.append(nic_info)
        return nics

    def _resolve_attribute(self, name):
        pass

    def handle_update(self, json_snippet, tmpl_diff, prop_diff):
        if 'Metadata' in tmpl_diff:
            self.metadata = tmpl_diff['Metadata']
        if 'flavor' in prop_diff:
            flavor = prop_diff['flavor']
            flavor_id = nova_utils.get_flavor_id(self.nova(), flavor)
            server = self.nova().servers.get(self.resource_id)
            server.resize(flavor_id)
            scheduler.TaskRunner(nova_utils.check_resize, server, flavor)()

    def metadata_update(self, new_metadata=None):
        '''
        Refresh the metadata if new_metadata is None
        '''
        if new_metadata is None:
            self.metadata = self.parsed_template('Metadata')

    def validate(self):
        '''
        Validate any of the provided params
        '''
        res = super(Server, self).validate()
        if res:
            return res

        # check validity of key
        key_name = self.properties.get('key_name', None)
        if key_name:
            nova_utils.get_keypair(self.nova(), key_name)

        # make sure the image exists if specified.
        image = self.properties.get('image', None)
        if image:
            nova_utils.get_image_id(self.nova(), image)
        else:
            # TODO sbaker confirm block_device_mapping is populated
            # for boot-by-volume
            pass

    def handle_delete(self):
        '''
        Delete an instance, blocking until it is disposed by OpenStack
        '''
        if self.resource_id is None:
            return

        try:
            server = self.nova().servers.get(self.resource_id)
        except clients.novaclient.exceptions.NotFound:
            pass
        else:
            delete = scheduler.TaskRunner(nova_utils.delete_server, server)
            delete(wait_time=0.2)

        self.resource_id = None

    def handle_suspend(self):
        '''
        Suspend an instance - note we do not wait for the SUSPENDED state,
        this is polled for by check_suspend_complete in a similar way to the
        create logic so we can take advantage of coroutines
        '''
        if self.resource_id is None:
            raise exception.Error(_('Cannot suspend %s, resource_id not set') %
                                  self.name)

        try:
            server = self.nova().servers.get(self.resource_id)
        except clients.novaclient.exceptions.NotFound:
            raise exception.NotFound(_('Failed to find instance %s') %
                                     self.resource_id)
        else:
            logger.debug("suspending instance %s" % self.resource_id)
            # We want the server.suspend to happen after the volume
            # detachement has finished, so pass both tasks and the server
            suspend_runner = scheduler.TaskRunner(server.suspend)
            return server, suspend_runner

    def check_suspend_complete(self, cookie):
        server, suspend_runner = cookie

        if not suspend_runner.started():
            suspend_runner.start()

        if suspend_runner.done():
            if server.status == 'SUSPENDED':
                return True

            server.get()
            logger.debug("%s check_suspend_complete status = %s" %
                         (self.name, server.status))
            if server.status in list(nova_utils.deferred_server_statuses +
                                     ['ACTIVE']):
                return server.status == 'SUSPENDED'
            else:
                raise exception.Error(_(' nova reported unexpected '
                                        'instance[%(instance)s] '
                                        'status[%(status)s]') %
                                      {'instance': self.name,
                                       'status': server.status})
        else:
            suspend_runner.step()

    def handle_resume(self):
        '''
        Resume an instance - note we do not wait for the ACTIVE state,
        this is polled for by check_resume_complete in a similar way to the
        create logic so we can take advantage of coroutines
        '''
        if self.resource_id is None:
            raise exception.Error(_('Cannot resume %s, resource_id not set') %
                                  self.name)

        try:
            server = self.nova().servers.get(self.resource_id)
        except clients.novaclient.exceptions.NotFound:
            raise exception.NotFound(_('Failed to find instance %s') %
                                     self.resource_id)
        else:
            logger.debug("resuming instance %s" % self.resource_id)
            server.resume()
            return server, scheduler.TaskRunner(self._attach_volumes_task())

    def check_resume_complete(self, cookie):
        return self._check_active(cookie)

def resource_mapping():
    return {
        'OS::Nova::Server': Server,
    }
