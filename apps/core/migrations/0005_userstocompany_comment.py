# Generated by Django 2.2.10 on 2020-03-18 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_companysubscription_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='userstocompany',
            name='comment',
            field=models.CharField(blank=True, max_length=150, verbose_name='comment'),
        ),
    ]
