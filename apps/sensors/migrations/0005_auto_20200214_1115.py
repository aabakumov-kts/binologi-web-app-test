# Generated by Django 2.2.10 on 2020-02-14 11:15

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0004_auto_20200214_1013'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensor',
            name='range_to_bin_bottom',
            field=models.IntegerField(default=0, help_text='in millimeters (mm)'),
        ),
        migrations.CreateModel(
            name='Fullness',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ctime', models.DateTimeField(default=django.utils.timezone.now)),
                ('value', models.IntegerField(default=0)),
                ('actual', models.BooleanField(default=False, verbose_name='actual data')),
                ('sensor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fullness_table', to='sensors.Sensor', verbose_name='sensor')),
            ],
        ),
    ]
