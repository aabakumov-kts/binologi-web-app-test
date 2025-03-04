# Generated by Django 2.2.17 on 2021-09-15 06:42

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0104_auto_20201013_1233'),
        ('trashbins', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrashbinPilot',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('app.container',),
        ),
        migrations.CreateModel(
            name='TrashReceiverStatistic',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ctime', models.DateTimeField(default=django.utils.timezone.now)),
                ('open_count', models.IntegerField(default=0)),
                ('actual', models.BooleanField(default=False, verbose_name='actual data')),
                ('trashbin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trash_recv_stats', to='app.Container')),
            ],
            options={
                'ordering': ('ctime',),
            },
        ),
    ]
