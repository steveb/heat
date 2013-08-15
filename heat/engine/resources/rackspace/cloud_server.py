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

import tempfile

import json
import paramiko
from Crypto.PublicKey import RSA
import novaclient.exceptions as novaexception

from heat.common import exception
from heat.openstack.common import log as logging
from heat.engine import scheduler
from heat.engine.resources import instance
from heat.engine.resources import nova_utils
from heat.engine.resources.rackspace import rackspace_resource
from heat.db.sqlalchemy import api as db_api

logger = logging.getLogger(__name__)


class CloudServer(instance.Instance):
    """Resource for Rackspace Cloud Servers."""

    properties_schema = {'flavor': {'Type': 'String', 'Required': True},
                         'image': {'Type': 'String', 'Required': True},
                         'user_data': {'Type': 'String'},
                         'key_name': {'Type': 'String'},
                         'Volumes': {'Type': 'List'},
                         'name': {'Type': 'String'}}

    attributes_schema = {'PrivateDnsName': ('Private DNS name of the specified'
                                            ' instance.'),
                         'PublicDnsName': ('Public DNS name of the specified '
                                           'instance.'),
                         'PrivateIp': ('Private IP address of the specified '
                                       'instance.'),
                         'PublicIp': ('Public IP address of the specified '
                                      'instance.')}

    base_script = """#!/bin/bash

# Install cloud-init and heat-cfntools
%s
# Create data source for cloud-init
mkdir -p /var/lib/cloud/seed/nocloud-net
mv /tmp/userdata /var/lib/cloud/seed/nocloud-net/user-data
touch /var/lib/cloud/seed/nocloud-net/meta-data
chmod 600 /var/lib/cloud/seed/nocloud-net/*

# Run cloud-init & cfn-init
cloud-init start || cloud-init init
bash -x /var/lib/cloud/data/cfn-userdata > /root/cfn-userdata.log 2>&1
"""

    # - Ubuntu 12.04: Verified working
    ubuntu_script = base_script % """\
apt-get update
apt-get install -y cloud-init python-boto python-pip gcc python-dev
pip install heat-cfntools
cfn-create-aws-symlinks --source /usr/local/bin
"""

    # - Fedora 17: Verified working
    # - Fedora 18: Not working.  selinux needs to be in "Permissive"
    #   mode for cloud-init to work.  It's disabled by default in the
    #   Rackspace Cloud Servers image.  To enable selinux, a reboot is
    #   required.
    # - Fedora 19: Verified working
    fedora_script = base_script % """\
yum install -y cloud-init python-boto python-pip gcc python-devel
pip-python install heat-cfntools
cfn-create-aws-symlinks
"""

    # - Centos 6.4: Verified working
    centos_script = base_script % """\
rpm -ivh http://mirror.rackspace.com/epel/6/i386/epel-release-6-8.noarch.rpm
yum install -y cloud-init python-boto python-pip gcc python-devel \
  python-argparse
pip-python install heat-cfntools
"""

    # - RHEL 6.4: Verified working
    rhel_script = base_script % """\
rpm -ivh http://mirror.rackspace.com/epel/6/i386/epel-release-6-8.noarch.rpm
# The RPM DB stays locked for a few secs
while fuser /var/lib/rpm/*; do sleep 1; done
yum install -y cloud-init python-boto python-pip gcc python-devel \
  python-argparse
pip-python install heat-cfntools
cfn-create-aws-symlinks
"""

    # - Debian 7: Not working (heat-cfntools patch submitted)
    # TODO(jason): Test with Debian 7 as soon as heat-cfntools patch
    # is in https://review.openstack.org/#/c/38822/
    debian_script = base_script % """\
echo "deb http://mirror.rackspace.com/debian wheezy-backports main" >> \
  /etc/apt/sources.list
apt-get update
apt-get -t wheezy-backports install -y cloud-init
apt-get install -y python-pip gcc python-dev
pip install heat-cfntools
"""

    # - Arch 2013.6: Not working (deps not in default package repos)
    # TODO(jason): Install cloud-init & other deps from third-party repos
    arch_script = base_script % """\
pacman -S --noconfirm python-pip gcc
"""

    # - Gentoo 13.2: Not working (deps not in default package repos)
    # TODO(jason): Install cloud-init & other deps from third-party repos
    gentoo_script = base_script % """\
emerge cloud-init python-boto python-pip gcc python-devel
"""

    # - OpenSUSE 12.3: Not working (deps not in default package repos)
    # TODO(jason): Install cloud-init & other deps from third-party repos
    opensuse_script = base_script % """\
zypper --non-interactive rm patterns-openSUSE-minimal_base-conflicts
zypper --non-interactive in cloud-init python-boto python-pip gcc python-devel
"""

    # List of supported Linux distros and their corresponding config scripts
    image_scripts = {'arch': None,
                     'centos': centos_script,
                     'debian': None,
                     'fedora': fedora_script,
                     'gentoo': None,
                     'opensuse': None,
                     'rhel': rhel_script,
                     'ubuntu': ubuntu_script}

    # Template keys supported for handle_update.  Properties not
    # listed here trigger an UpdateReplace
    update_allowed_keys = ('Metadata', 'Properties')
    update_allowed_properties = ('flavor', 'name')

    def __init__(self, name, json_snippet, stack):
        super(CloudServer, self).__init__(name, json_snippet, stack)
        self._private_key = None
        self._server = None
        self._distro = None
        self._public_ip = None
        self._private_ip = None
        self.rs = rackspace_resource.RackspaceResource(name,
                                                       json_snippet,
                                                       stack)

    def physical_resource_name(self):
        name = self.properties.get('name')
        if name:
            return name

        return super(CloudServer, self).physical_resource_name()

    def nova(self):
        return self.rs.nova()  # Override the Instance method

    def cinder(self):
        return self.rs.cinder()

    @property
    def server(self):
        """Get the Cloud Server object."""
        if not self._server:
            logger.debug("Calling nova().servers.get()")
            self._server = self.nova().servers.get(self.resource_id)
        return self._server

    @property
    def distro(self):
        """Get the Linux distribution for this server."""
        if not self._distro:
            logger.debug("Calling nova().images.get()")
            image = self.nova().images.get(self.properties['image'])
            self._distro = image.metadata['os_distro']
        return self._distro

    @property
    def script(self):
        """Get the config script for the Cloud Server image."""
        return self.image_scripts[self.distro]

    @property
    def flavors(self):
        """Get the flavors from the API."""
        logger.debug("Calling nova().flavors.list()")
        return [flavor.id for flavor in self.nova().flavors.list()]

    @property
    def private_key(self):
        """Return the private SSH key for the resource."""
        if self._private_key:
            return self._private_key
        if self.id is not None:
            private_key = db_api.resource_data_get(self, 'private_key')
            if not private_key:
                return None
            self._private_key = private_key
            return private_key

    @private_key.setter
    def private_key(self, private_key):
        """Save the resource's private SSH key to the database."""
        self._private_key = private_key
        if self.id is not None:
            db_api.resource_data_set(self, 'private_key', private_key, True)

    def _get_ip(self, ip_type):
        """Return the IP of the Cloud Server."""
        if ip_type in self.server.addresses:
            for ip in self.server.addresses[ip_type]:
                if ip['version'] == 4:
                    return ip['addr']

        raise exception.Error("Could not determine the %s IP of %s." %
                              (ip_type, self.properties['image']))

    @property
    def public_ip(self):
        """Return the public IP of the Cloud Server."""
        if not self._public_ip:
            self._public_ip = self._get_ip('public')
        return self._public_ip

    @property
    def private_ip(self):
        """Return the private IP of the Cloud Server."""
        if not self._private_ip:
            self._private_ip = self._get_ip('private')
        return self._private_ip

    @property
    def has_userdata(self):
        if self.properties['user_data'] or self.metadata != {}:
            return True
        else:
            return False

    def validate(self):
        """Validate user parameters."""
        if self.properties['flavor'] not in self.flavors:
            return {'Error': "flavor not found."}

        # It's okay if there's no script, as long as user_data and
        # metadata are empty
        if not self.script and self.has_userdata:
            return {'Error': "user_data/metadata are not supported with %s." %
                    self.properties['image']}

    def _run_ssh_command(self, command):
        """Run a shell command on the Cloud Server via SSH."""
        with tempfile.NamedTemporaryFile() as private_key_file:
            private_key_file.write(self.private_key)
            private_key_file.seek(0)
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
            ssh.connect(self.public_ip,
                        username="root",
                        key_filename=private_key_file.name)
            stdin, stdout, stderr = ssh.exec_command(command)
            logger.debug(stdout.read())
            logger.debug(stderr.read())

    def _sftp_files(self, files):
        """Transfer files to the Cloud Server via SFTP."""
        with tempfile.NamedTemporaryFile() as private_key_file:
            private_key_file.write(self.private_key)
            private_key_file.seek(0)
            pkey = paramiko.RSAKey.from_private_key_file(private_key_file.name)
            transport = paramiko.Transport((self.public_ip, 22))
            transport.connect(hostkey=None, username="root", pkey=pkey)
            sftp = paramiko.SFTPClient.from_transport(transport)
            for remote_file in files:
                sftp_file = sftp.open(remote_file['path'], 'w')
                sftp_file.write(remote_file['data'])
                sftp_file.close()

    def handle_create(self):
        """Create a Rackspace Cloud Servers container.

        Rackspace Cloud Servers does not have the metadata service
        running, so we have to transfer the user-data file to the
        server and then trigger cloud-init.
        """
        # Retrieve server creation parameters from properties
        flavor = self.properties['flavor']

        # Generate SSH public/private keypair
        if self._private_key is not None:
            rsa = RSA.importKey(self._private_key)
        else:
            rsa = RSA.generate(1024)
        self.private_key = rsa.exportKey()
        public_keys = [rsa.publickey().exportKey('OpenSSH')]
        if self.properties.get('key_name'):
            key_name = self.properties['key_name']
            public_keys.append(nova_utils.get_keypair(self.nova(),
                                                      key_name).public_key)
        personality_files = {
            "/root/.ssh/authorized_keys": '\n'.join(public_keys)}

        # Create server
        client = self.nova().servers
        logger.debug("Calling nova().servers.create()")
        server = client.create(self.physical_resource_name(),
                               self.properties['image'],
                               flavor,
                               files=personality_files)

        # Save resource ID to db
        self.resource_id_set(server.id)

        return server, scheduler.TaskRunner(self._attach_volumes_task())

    def _attach_volumes_task(self):
        tasks = (scheduler.TaskRunner(self._attach_volume, volume_id, device)
                 for volume_id, device in self.volumes())
        return scheduler.PollingTaskGroup(tasks)

    def _attach_volume(self, volume_id, device):
        logger.debug("Calling nova().volumes.create_server_volume()")
        self.nova().volumes.create_server_volume(self.server.id,
                                                 volume_id,
                                                 device or None)
        yield
        volume = self.cinder().get(volume_id)
        while volume.status in ('available', 'attaching'):
            yield
            volume.get()

        if volume.status != 'in-use':
            raise exception.Error(volume.status)

    def _detach_volumes_task(self):
        tasks = (scheduler.TaskRunner(self._detach_volume, volume_id)
                 for volume_id, device in self.volumes())
        return scheduler.PollingTaskGroup(tasks)

    def _detach_volume(self, volume_id):
        volume = self.cinder().get(volume_id)
        volume.detach()
        yield
        while volume.status in ('in-use', 'detaching'):
            yield
            volume.get()

        if volume.status != 'available':
            raise exception.Error(volume.status)

    def check_create_complete(self, cookie):
        """Check if server creation is complete and handle server configs."""
        if not self._check_active(cookie):
            return False

        if self.has_userdata:
            # Create heat-script and userdata files on server
            raw_userdata = self.properties['user_data'] or ''
            userdata = nova_utils.build_userdata(self, raw_userdata)

            files = [{'path': "/tmp/userdata", 'data': userdata},
                     {'path': "/root/heat-script.sh", 'data': self.script}]
            self._sftp_files(files)

            # Connect via SSH and run script
            cmd = "bash -ex /root/heat-script.sh > /root/heat-script.log 2>&1"
            self._run_ssh_command(cmd)

        return True

    # TODO(jason): Make this consistent with Instance and inherit
    def _delete_server(self, server):
        """Return a coroutine that deletes the Cloud Server."""
        server.delete()
        while True:
            yield
            try:
                server.get()
                if server.status == "DELETED":
                    break
                elif server.status == "ERROR":
                    raise exception.Error("Deletion of server %s failed." %
                                          server.name)
            except novaexception.NotFound:
                break

    def handle_update(self, json_snippet, tmpl_diff, prop_diff):
        """Try to update a Cloud Server's parameters.

        If the Cloud Server's Metadata or flavor changed, update the
        Cloud Server.  If any other parameters changed, re-create the
        Cloud Server with the new parameters.
        """
        if 'Metadata' in tmpl_diff:
            self.metadata = json_snippet['Metadata']
            metadata_string = json.dumps(self.metadata)

            files = [{'path': "/var/cache/heat-cfntools/last_metadata",
                      'data': metadata_string}]
            self._sftp_files(files)

            command = "bash -x /var/lib/cloud/data/cfn-userdata > " + \
                      "/root/cfn-userdata.log 2>&1"
            self._run_ssh_command(command)

        if 'flavor' in prop_diff:
            self.flavor = json_snippet['Properties']['flavor']
            self.server.resize(self.flavor)
            resize = scheduler.TaskRunner(nova_utils.check_resize,
                                          self.server,
                                          self.flavor)
            resize(wait_time=1.0)

        # If name is the only update, fail update
        if prop_diff.keys() == ['name'] and \
           tmpl_diff.keys() == ['Properties']:
            raise exception.NotSupported(feature="Cloud Server rename")
        # Other updates were successful, so don't cause update to fail
        elif 'name' in prop_diff:
            logger.info("Cloud Server rename not supported.")

        return True

    def _resolve_attribute(self, key):
        """Return the method that provides a given template attribute."""
        attribute_function = {'PublicIp': self.public_ip,
                              'PrivateIp': self.private_ip,
                              'PublicDnsName': self.public_ip,
                              'PrivateDnsName': self.public_ip}
        if key not in attribute_function:
            raise exception.InvalidTemplateAttribute(resource=self.name,
                                                     key=key)
        function = attribute_function[key]
        logger.info('%s._resolve_attribute(%s) == %s'
                    % (self.name, key, function))
        return unicode(function)


# pyrax module is required to work with Rackspace cloud server provider.
# If it is not installed, don't register cloud server provider
def resource_mapping():
    if rackspace_resource.PYRAX_INSTALLED:
        return {'Rackspace::Cloud::Server': CloudServer}
    else:
        return {}
