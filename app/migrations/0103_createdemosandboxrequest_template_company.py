# Generated by Django 2.2.16 on 2020-10-08 12:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_auto_20201008_1233'),
        ('app', '0102_auto_20201008_1233'),
    ]

    operations = [
        migrations.AddField(
            model_name='createdemosandboxrequest',
            name='template_company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Company'),
        ),
    ]
