# Generated by Django 2.2.16 on 2020-10-08 12:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_company_lang'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='featureflag',
            options={},
        ),
        migrations.AlterField(
            model_name='featureflag',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='features', to='core.Company'),
        ),
        migrations.AlterField(
            model_name='featureflag',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='featureflag',
            name='feature',
            field=models.CharField(choices=[('AIR_QUALITY', 'Air quality'), ('CHANGE_PASSWORD', 'Change password'), ('EFFICIENCY_MONITOR', 'Efficiency monitor')], max_length=128),
        ),
    ]
