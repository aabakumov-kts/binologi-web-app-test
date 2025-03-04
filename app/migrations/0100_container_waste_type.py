# Generated by Django 2.2.13 on 2020-08-06 14:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_wastetype'),
        ('app', '0099_auto_20200806_1404'),
    ]

    state_operations = [
        migrations.AddField(
            model_name='container',
            name='waste_type',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='core.WasteType', verbose_name='waste type'),
            preserve_default=False,
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]
