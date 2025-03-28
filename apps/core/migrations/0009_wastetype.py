# Generated by Django 2.2.13 on 2020-08-06 14:06

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_sectors'),
        ('app', '0099_auto_20200806_1404'),
    ]

    state_operations = [
        migrations.CreateModel(
            name='WasteType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='title')),
                ('title_en', models.CharField(max_length=200, null=True, verbose_name='title')),
                ('title_ru', models.CharField(max_length=200, null=True, verbose_name='title')),
                ('code', models.CharField(db_index=True, max_length=8, null=True, verbose_name='waste code')),
                ('density', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0)])),
            ],
            options={
                'verbose_name': 'waste type',
                'verbose_name_plural': 'waste types',
            },
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]
