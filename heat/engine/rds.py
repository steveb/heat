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

import eventlet
import logging
import os

from heat.common import exception
from heat.engine.resources import Resource
from heat.engine.security_group import SecurityGroup
from heat.engine.instance import Instance

logger = logging.getLogger(__file__)


class DBSecurityGroup(SecurityGroup):
    properties_schema = {'GroupDescription': {'Type': 'String'},
                        'DBSecurityGroupIngress': {'Type': 'TuplesList',
                                    'Implemented': False}}

    def __init__(self, name, json_snippet, stack):
        super(DBSecurityGroup, self).__init__(name, json_snippet, stack)
        self.ipaddress = ''

    def create(self):
        """Allocate a floating IP for the current tenant."""
        if self.state != None:
            return
        self.state_set(self.CREATE_IN_PROGRESS)
        super(DBSecurityGroup, self).create()
        self.state_set(self.CREATE_COMPLETE)

    def validate(self):
        '''
        Validate the security group here
        '''
        return Resource.validate(self)

    def delete(self):
        if self.state == self.DELETE_IN_PROGRESS or \
           self.state == self.DELETE_COMPLETE:
            return

        self.state_set(self.DELETE_IN_PROGRESS)
        Resource.delete(self)
        self.state_set(self.DELETE_COMPLETE)


class DBInstance(Instance):
    properties_schema = {'ImageId': {'Type': 'String',
                                    'Required': True},
                         'InstanceType': {'Type': 'String',
                                    'Required': True},
                         'KeyName': {'Type': 'String',
                                     'Required': True},
                         'AvailabilityZone': {'Type': 'String',
                                              'Default': 'nova'},
                         'DisableApiTermination': {'Type': 'String',
                                                   'Implemented': False},
                         'KernelId': {'Type': 'String',
                                      'Implemented': False},
                         'Monitoring': {'Type': 'Boolean',
                                        'Implemented': False},
                         'PlacementGroupName': {'Type': 'String',
                                                'Implemented': False},
                         'PrivateIpAddress': {'Type': 'String',
                                              'Implemented': False},
                         'RamDiskId': {'Type': 'String',
                                       'Implemented': False},
                         'SecurityGroups': {'Type': 'TuplesList',
                                              'Implemented': False},
                         'SecurityGroupIds': {'Type': 'CommaDelimitedList',
                                              'Implemented': False},
                         'SourceDestCheck': {'Type': 'Boolean',
                                             'Implemented': False},
                         'SubnetId': {'Type': 'String',
                                       'Implemented': False},
                         'Tags': {'Type': 'CommaDelimitedList',
                                          'Implemented': False},
                         'Tenancy': {'Type': 'String',
                                     'AllowedValues': ['dedicated', 'default'],
                                     'Implemented': False},
                         'UserData': {'Type': 'String'},
                         'Volumes': {'Type': 'CommaDelimitedList',
                                     'Implemented': False},
                        'GroupDescription': {'Type': 'String'},
                        'Engine': {'Type': 'String'},
                        'DBName': {'Type': 'String'},
                        'DBInstanceClass': {'Type': 'Tuple'},
                        'AllocatedStorage': {'Type': 'Integer'},
                        'MasterUsername': {'Type': 'Tuple'},
                        'MasterUserPassword': {'Type': 'Tuple'},
                        'DBSecurityGroupIngress': {'Type': 'TuplesList',
                                    'Implemented': False},
                        'DBSecurityGroups': {'Type': 'TuplesList',
                                    'Implemented': False}}

    def __init__(self, name, json_snippet, stack):
        super(DBInstance, self).properties_schema.\
            update(self.properties_schema)
        super(DBInstance, self).__init__(name, json_snippet, stack)

    def FnGetAtt(self, key):
        res = None
        if key == 'Endpoint.Address':
            res = self.ipaddress
        elif key == 'AvailabilityZone':
            res = self.properties['AvailabilityZone']
        elif key == 'PublicIp':
            res = self.ipaddress
        elif key == 'PrivateDnsName':
            res = self.ipaddress
        else:
            raise exception.InvalidTemplateAttribute(resource=self.name,
                                                     key=key)
        logger.info('%s.GetAtt(%s) == %s' % (self.name, key, res))
        return unicode(res)
