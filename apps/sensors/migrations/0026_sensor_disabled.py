# Generated by Django 2.2.17 on 2021-04-09 08:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0025_auto_20210319_0744'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensor',
            name='disabled',
            field=models.BooleanField(default=False, verbose_name='disabled'),
        ),
    ]
