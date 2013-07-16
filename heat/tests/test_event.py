# vim: tabstop=4 shiftwidth=4 softtabstop=4

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


import heat.db.api as db_api
from heat.engine import parser
from heat.engine import resource
from heat.engine import template
from heat.engine import event

from heat.tests.common import HeatTestCase
from heat.tests.utils import dummy_context
from heat.tests.utils import setup_dummy_db
from heat.tests import generic_resource as generic_rsrc


tmpl = {
    'Resources': {
        'EventTestResource': {
            'Type': 'ResourceWithRequiredProps',
            'Properties': {'Foo': 'goo'}
        }
    }
}


class EventTest(HeatTestCase):

    def setUp(self):
        super(EventTest, self).setUp()
        self.username = 'event_test_user'

        setup_dummy_db()
        self.ctx = dummy_context()

        self.m.ReplayAll()

        resource._register_class('ResourceWithRequiredProps',
                                 generic_rsrc.ResourceWithRequiredProps)

        self.stack = parser.Stack(self.ctx, 'event_load_test_stack',
                                  template.Template(tmpl))
        self.stack.store()

        self.resource = self.stack['EventTestResource']
        self.resource._store()
        self.addCleanup(db_api.stack_delete, self.ctx, self.stack.id)

    def test_load(self):
        self.resource.resource_id_set('resource_physical_id')

        e = event.Event(self.ctx, self.stack, self.resource,
                        'TEST', 'IN_PROGRESS', 'Testing',
                        'wibble', self.resource.properties)

        e.store()
        self.assertNotEqual(e.id, None)

        loaded_e = event.Event.load(self.ctx, e.id)

        self.assertEqual(self.stack.id, loaded_e.stack.id)
        self.assertEqual(self.resource.name, loaded_e.resource.name)
        self.assertEqual(self.resource.id, loaded_e.resource.id)
        self.assertEqual('wibble', loaded_e.physical_resource_id)
        self.assertEqual('TEST', loaded_e.action)
        self.assertEqual('IN_PROGRESS', loaded_e.status)
        self.assertEqual('Testing', loaded_e.reason)
        self.assertNotEqual(None, loaded_e.timestamp)
        self.assertEqual({'Foo': 'goo'}, loaded_e.resource_properties)

    def test_load_given_stack_event(self):
        self.resource.resource_id_set('resource_physical_id')

        e = event.Event(self.ctx, self.stack, self.resource,
                        'TEST', 'IN_PROGRESS', 'Testing',
                        'wibble', self.resource.properties)

        e.store()
        self.assertNotEqual(e.id, None)

        ev = db_api.event_get(self.ctx, e.id)

        loaded_e = event.Event.load(self.ctx, e.id, stack=self.stack, event=ev)

        self.assertEqual(self.stack.id, loaded_e.stack.id)
        self.assertEqual(self.resource.name, loaded_e.resource.name)
        self.assertEqual(self.resource.id, loaded_e.resource.id)
        self.assertEqual('wibble', loaded_e.physical_resource_id)
        self.assertEqual('TEST', loaded_e.action)
        self.assertEqual('IN_PROGRESS', loaded_e.status)
        self.assertEqual('Testing', loaded_e.reason)
        self.assertNotEqual(None, loaded_e.timestamp)
        self.assertEqual({'Foo': 'goo'}, loaded_e.resource_properties)

    def test_identifier(self):
        e = event.Event(self.ctx, self.stack, self.resource,
                        'TEST', 'IN_PROGRESS', 'Testing',
                        'wibble', self.resource.properties)

        eid = e.store()
        expected_identifier = {
            'stack_name': self.stack.name,
            'stack_id': self.stack.id,
            'tenant': self.ctx.tenant_id,
            'path': '/resources/EventTestResource/events/%s' % str(eid)
        }
        self.assertEqual(expected_identifier, e.identifier())

    def test_badprop(self):
        tmpl = {'Type': 'ResourceWithRequiredProps',
                'Properties': {'Foo': False}}
        rname = 'bad_resource'
        res = generic_rsrc.ResourceWithRequiredProps(rname, tmpl, self.stack)
        e = event.Event(self.ctx, self.stack, res,
                        'TEST', 'IN_PROGRESS', 'Testing',
                        'wibble', res.properties)
        self.assertTrue('Error' in e.resource_properties)
