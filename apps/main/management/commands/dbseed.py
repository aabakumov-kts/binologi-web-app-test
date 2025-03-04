import logging
import pytz
import random
import uuid

from datetime import date, timedelta, datetime
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.translation import override as current_language_override
from faker import Faker

from apps.core.helpers import format_random_location
from apps.core.models import Company, UsersToCompany, Country, City, WasteType
from apps.sensors.models import (
    Sensor, CompanySensorsLicense, SensorSettingsProfile, ContainerType as SensorContainerType, Sectors,
    DEFAULT_SENSOR_LOCATION, SensorOnboardRequest,
)
from app.models import Container, ContainerType as TrashbinContainerType
from app.tasks import generate_report_data_for_bins, generate_report_data_for_sensors
from apps.trashbins.models import CompanyTrashbinsLicense


class Command(BaseCommand):
    help = 'Seeds the database with sample data useful to get started'

    def handle(self, *args, **options):
        faker = Faker()
        user_model = get_user_model()
        default_password = '123'
        logging.getLogger('app_main').disabled = True  # This logger is noisy during reporting data parsing

        self.stdout.write('Creating super user...')
        user_model.objects.create_superuser('super', None, default_password, first_name='Super', last_name='User')

        self.stdout.write('Creating auxiliary data...')
        with current_language_override('en'):
            unknown_country = Country.objects.create(name='Unknown')
            unknown_city = City.objects.create(country=unknown_country, title='Unknown')
        sensor_settings_profile = SensorSettingsProfile.objects.create()

        self.stdout.write('Creating sample company...')
        company = Company.objects.create(name=faker.company())
        company_default_sector = Sectors.objects.filter(company=company).first()

        self.stdout.write('Creating company users...')
        admin_user = user_model.objects.create_user(
            'admin', None, default_password, first_name=faker.first_name(), last_name=faker.last_name())
        UsersToCompany.objects.create(user=admin_user, company=company, role=UsersToCompany.ADMIN_ROLE)
        op_user = user_model.objects.create_user(
            'operator', None, default_password, first_name=faker.first_name(), last_name=faker.last_name())
        UsersToCompany.objects.create(user=op_user, company=company, role=UsersToCompany.OPERATOR_ROLE)
        driver_user = user_model.objects.create_user(
            'driver', None, default_password, first_name=faker.first_name(), last_name=faker.last_name())
        UsersToCompany.objects.create(user=driver_user, company=company, role=UsersToCompany.DRIVER_ROLE)

        def create_trashbin(container_type, waste_type, location, **kwargs):
            trashbin = Container.objects.create(
                serial_number=str(uuid.uuid4()),  # To just ensure there won't be collisions
                phone_number=faker.phone_number(),
                container_type=container_type,
                company=company,
                country=unknown_country,
                city=unknown_city,
                address=faker.address(),
                sector=company_default_sector,
                waste_type=waste_type,
                location=location,
                **kwargs
            )
            prefix = 'BBO120-CISP' if trashbin.is_master else 'BBO120-CESP'
            trashbin.serial_number = f"{prefix}{trashbin.id:05d}"
            trashbin.save()
            return trashbin

        self.stdout.write('Creating company containers...')
        create_trashbin(
            TrashbinContainerType.objects.get(pk=3),  # FLMS, TC, IoT-module
            WasteType.objects.get(pk=1),  # Mix
            format_random_location(DEFAULT_SENSOR_LOCATION),
        )
        dual_station_location = format_random_location(DEFAULT_SENSOR_LOCATION)
        dual_station_master = create_trashbin(
            TrashbinContainerType.objects.get(pk=3),  # FLMS, TC, IoT-module
            WasteType.objects.get(pk=1),  # Mix
            dual_station_location,
        )
        create_trashbin(
            TrashbinContainerType.objects.get(pk=1),  # FLMS only
            WasteType.objects.get(pk=10),  # Raw Garbage - type #1
            dual_station_location,
            is_master=False,
            master_bin=dual_station_master,
        )
        triple_station_location = format_random_location(DEFAULT_SENSOR_LOCATION)
        triple_station_master = create_trashbin(
            TrashbinContainerType.objects.get(pk=3),  # FLMS, TC, IoT-module
            WasteType.objects.get(pk=1),  # Mix
            triple_station_location,
        )
        for i in range(2):
            waste_type_pk = 10 if i == 0 else 11  # Raw Garbage - type #1 or type #2
            create_trashbin(
                TrashbinContainerType.objects.get(pk=1),  # FLMS only
                WasteType.objects.get(pk=waste_type_pk),
                triple_station_location,
                is_master=False,
                master_bin=triple_station_master,
            )

        self.stdout.write('Creating company sensors...')
        sensors_count = 5
        for _ in range(sensors_count):
            hardware_identity = str(uuid.uuid4())
            sensor = Sensor.objects.create(
                settings_profile=sensor_settings_profile,
                serial_number=hardware_identity,  # To just ensure there won't be collisions
                hardware_identity=hardware_identity,
                phone_number=faker.numerify(''.join(('#' for _ in range(15)))),
                container_type=random.choice(SensorContainerType.objects.all()),
                company=company,
                country=unknown_country,
                city=unknown_city,
                address=faker.address(),
                sector=company_default_sector,
                waste_type=random.choice(WasteType.objects.all()),
                location=format_random_location(DEFAULT_SENSOR_LOCATION),
                mount_type=Sensor.HORIZONTAL_MOUNT_TYPE if random.choice([True, False]) else Sensor.VERTICAL_MOUNT_TYPE,
            )
            sensor.serial_number =\
                f"BWS{SensorOnboardRequest.install_types_to_sn[SensorOnboardRequest.FRONT_INSTALL_TYPE]}" \
                f"{SensorOnboardRequest.network_types_to_sn[SensorOnboardRequest.NETWORK_TYPE_NB_IOT]}-{sensor.id:08d}"
            sensor.save()

        self.stdout.write('Creating company licenses...')
        license_period = 365
        CompanySensorsLicense.objects.create(
            company=company, end=date.today() + timedelta(days=license_period),
            usage_balance=sensors_count * license_period, description=f'Seeded license for company {company.name}')
        CompanyTrashbinsLicense.objects.create(
            company=company, end=date.today() + timedelta(days=license_period),
            description=f'Seeded license for company {company.name}')

        self.stdout.write('Creating sample reporting data...')
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        days_to_generate_range = range(14)
        record_generation_interval = 43200  # Twice a day in seconds
        for day in reversed(days_to_generate_range):
            day_timestamp = utc_now - timedelta(days=day)
            generate_report_data_for_bins(
                Container.objects.filter(company=company), day_timestamp, record_generation_interval)
            generate_report_data_for_sensors(
                Sensor.objects.filter(company=company), day_timestamp, record_generation_interval)

        self.stdout.write('✅ Seed data created successfully!')
