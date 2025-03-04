from django.db import migrations


def load_fixture(apps, schema_editor):
    pass


def unload_fixture(apps, schema_editor):
    pass


# This migration was used to automatically import sensors/error_types.xml fixture
# It ran into a maintenance issue and now is just a stub
# Operations should be removed upon squashing this migration
class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0003_batterylevel_error_errortype_sensordata_simbalance_temperature'),
    ]

    operations = [
        migrations.RunPython(load_fixture, reverse_code=unload_fixture),
    ]
