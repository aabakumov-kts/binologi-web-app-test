from django.contrib.auth.models import User
from django.test import TestCase, Client

from apps.core.models import Sectors
from app.models import Country, City, Company, ContainerType, WasteType, Container


class ApiContainersTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name='foo_country')
        self.city = City.objects.create(country=self.country, title='foo_city')
        self.company = Company.objects.create(name='foo_company', country=self.country)
        self.sector = Sectors.objects.get(company=self.company)
        self.container_type = ContainerType.objects.create(title='foo_container_type')
        self.waste_type = WasteType.objects.create(title='foo_waste_type', density=0.1)
        superuser = User.objects.create(username='foo_user', is_staff=True, is_superuser=True)
        superuser.set_password('bar')
        superuser.save()
        self.client = Client()
        self.assertTrue(self.client.login(username='foo_user', password='bar'))

    def test_single_master_output(self):
        # ARRANGE
        container = self._create_container()
        # ACT
        response = self.client.get('/api/containers/')
        # ASSERT
        self.assertEqual(200, response.status_code)
        response_json = response.json()
        self.assertEqual(1, len(response_json['containers']))
        self.assertEqual(0, len(response_json['stations']))
        self.assertEqual(container.serial_number, response_json['containers'][0]['serial_number'])

    def test_master_with_satellite_output(self):
        # ARRANGE
        master_container = self._create_container()
        satellite_container = self._create_container(
            serial_number='bar_container', is_master=False, master_bin=master_container)
        # ACT
        response = self.client.get('/api/containers/')
        # ASSERT
        self.assertEqual(200, response.status_code)
        response_json = response.json()
        self.assertEqual(2, len(response_json['containers']))
        self.assertEqual(1, len(response_json['stations']))
        self.assertDictEqual({'x': 37, 'y': 55}, response_json['stations'][0]['location'])
        self.assertEqual(master_container.id, response_json['stations'][0]['master'])
        self.assertListEqual([satellite_container.id], response_json['stations'][0]['satellites'])

    def test_multiple_clusters_output(self):
        # ARRANGE
        master_container_one = self._create_container()
        satellite_container_one = self._create_container(
            serial_number='bar_container', is_master=False, master_bin=master_container_one)
        master_container_two = self._create_container(serial_number='baz_container', location='SRID=4326;POINT (20 60)')
        satellite_container_two = self._create_container(
            serial_number='qux_container', is_master=False, master_bin=master_container_two)
        # ACT
        response = self.client.get('/api/containers/')
        # ASSERT
        self.assertEqual(200, response.status_code)
        response_json = response.json()
        self.assertEqual(4, len(response_json['containers']))
        self.assertEqual(2, len(response_json['stations']))
        self.assertDictEqual({'x': 37, 'y': 55}, response_json['stations'][0]['location'])
        self.assertDictEqual({'x': 20, 'y': 60}, response_json['stations'][1]['location'])
        self.assertEqual(master_container_one.id, response_json['stations'][0]['master'])
        self.assertListEqual([satellite_container_one.id], response_json['stations'][0]['satellites'])
        self.assertEqual(master_container_two.id, response_json['stations'][1]['master'])
        self.assertListEqual([satellite_container_two.id], response_json['stations'][1]['satellites'])

    def _create_container(self, **kwargs):
        container_args = {
            'serial_number': 'foo_container',
            'phone_number': '-',
            'container_type': self.container_type,
            'is_master': True,
            'company': self.company, 'country': self.country,
            'city': self.city,
            'address': 'Foo Address',
            'sector': self.sector,
            'waste_type': self.waste_type,
            'location': 'SRID=4326;POINT (37 55)',
        }
        container_args.update(kwargs)
        return Container.objects.create(**container_args)
