# Generated by Django 2.2.17 on 2022-10-26 08:20

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0032_fullness_signal_amp'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sensorsettingsprofile',
            name='bin_tilt_angle',
        ),
        migrations.RemoveField(
            model_name='sensorsettingsprofile',
            name='measurement_profile',
        ),
        migrations.RemoveField(
            model_name='sensorsettingsprofile',
            name='measurement_range_max',
        ),
        migrations.RemoveField(
            model_name='sensorsettingsprofile',
            name='measurement_range_min',
        ),
        migrations.RemoveField(
            model_name='sensorsettingsprofile',
            name='measurement_samples',
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='accelerometer_delay',
            field=models.IntegerField(default=0, help_text='a111Delay', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(300)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='accelerometer_sensitivity',
            field=models.IntegerField(default=50, help_text='acelTh', validators=[django.core.validators.MinValueValidator(20), django.core.validators.MaxValueValidator(125)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='access_point_name',
            field=models.CharField(default='"IP","iot"', help_text='nbiot', max_length=64),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_approximation_profile',
            field=models.IntegerField(default=1, help_text='close_r_s_profile', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_distance_begin',
            field=models.FloatField(default=0.06, help_text='close_r_start', validators=[django.core.validators.MinValueValidator(-0.11), django.core.validators.MaxValueValidator(0.11)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_distance_length',
            field=models.FloatField(default=0.46, help_text='close_r_len', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(0.46)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_downsampling',
            field=models.IntegerField(default=1, help_text='close_r_downsampling', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(4)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_gain',
            field=models.FloatField(default=0.5, help_text='close_r_gain', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_noise_samples_number',
            field=models.IntegerField(default=30, help_text='close_r_sweep_bkgd', validators=[django.core.validators.MinValueValidator(10), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_noise_threshold',
            field=models.FloatField(default=0.25, help_text='close_r_threashold', validators=[django.core.validators.MinValueValidator(0.01), django.core.validators.MaxValueValidator(0.99)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_on_flag',
            field=models.IntegerField(default=0, help_text='close_r_meas_on', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_peaks_merge_distance',
            field=models.FloatField(default=0.005, help_text='close_r_peak_merge_lim', validators=[django.core.validators.MinValueValidator(0.001), django.core.validators.MaxValueValidator(0.46)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_peaks_sorting_method',
            field=models.IntegerField(default=1, help_text='close_r_peak_sorting', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(3)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='close_measurement_signal_samples_number',
            field=models.IntegerField(default=10, help_text='close_r_sweep_avr', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(50)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='current_orientation',
            field=models.IntegerField(default=0, help_text='orient', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(6)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='enabled_flag',
            field=models.IntegerField(default=1, help_text='onFlag', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_approximation_profile',
            field=models.IntegerField(default=4, help_text='far_r_s_profile', validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_distance_begin',
            field=models.FloatField(default=0.2, help_text='far_r_start', validators=[django.core.validators.MinValueValidator(0.05), django.core.validators.MaxValueValidator(4.5)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_distance_length',
            field=models.FloatField(default=2.5, help_text='far_r_len', validators=[django.core.validators.MinValueValidator(0.1), django.core.validators.MaxValueValidator(2.5)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_downsampling',
            field=models.IntegerField(default=2, help_text='far_r_downsampling', validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(4)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_gain',
            field=models.FloatField(default=0.7, help_text='far_r_gain', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_noise_samples_number',
            field=models.IntegerField(default=30, help_text='far_r_sweep_bkgd', validators=[django.core.validators.MinValueValidator(10), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_noise_threshold',
            field=models.FloatField(default=0.25, help_text='far_r_threashold', validators=[django.core.validators.MinValueValidator(0.01), django.core.validators.MaxValueValidator(0.99)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_on_flag',
            field=models.IntegerField(default=1, help_text='far_r_meas_on', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_peaks_merge_distance',
            field=models.FloatField(default=0.05, help_text='far_r_peak_merge_lim', validators=[django.core.validators.MinValueValidator(0.001), django.core.validators.MaxValueValidator(0.5)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_peaks_sorting_method',
            field=models.IntegerField(default=1, help_text='far_r_peak_sorting', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(3)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='far_measurement_signal_samples_number',
            field=models.IntegerField(default=10, help_text='far_r_sweep_avr', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(50)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='fill_alert_count',
            field=models.IntegerField(default=0, help_text='fillCount', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='fill_alert_interval',
            field=models.IntegerField(default=0, help_text='fillWakeup', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1440)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='fill_alert_range',
            field=models.IntegerField(default=200, help_text='fillAlert', validators=[django.core.validators.MinValueValidator(20), django.core.validators.MaxValueValidator(3500)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='fire_temp_gradient',
            field=models.IntegerField(default=1, help_text='gradient_temperature', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(20)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='first_turn_on_flag',
            field=models.IntegerField(default=0, help_text='on_init_modem', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='gps_in_every_connection',
            field=models.IntegerField(default=0, help_text='fGps', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='measurement_results_number',
            field=models.IntegerField(default=1, help_text='result_r_length', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_approximation_profile',
            field=models.IntegerField(default=2, help_text='mid_r_s_profile', validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_distance_begin',
            field=models.FloatField(default=0.2, help_text='mid_r_start', validators=[django.core.validators.MinValueValidator(0.05), django.core.validators.MaxValueValidator(2)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_distance_length',
            field=models.FloatField(default=1.25, help_text='mid_r_len', validators=[django.core.validators.MinValueValidator(0.1), django.core.validators.MaxValueValidator(1.25)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_downsampling',
            field=models.IntegerField(default=2, help_text='mid_r_downsampling', validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(4)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_gain',
            field=models.FloatField(default=0.7, help_text='mid_r_gain', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_noise_samples_number',
            field=models.IntegerField(default=30, help_text='mid_r_sweep_bkgd', validators=[django.core.validators.MinValueValidator(10), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_noise_threshold',
            field=models.FloatField(default=0.25, help_text='mid_r_threashold', validators=[django.core.validators.MinValueValidator(0.01), django.core.validators.MaxValueValidator(0.99)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_on_flag',
            field=models.IntegerField(default=1, help_text='mid_r_meas_on', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_peaks_merge_distance',
            field=models.FloatField(default=0.01, help_text='mid_r_peak_merge_lim', validators=[django.core.validators.MinValueValidator(0.001), django.core.validators.MaxValueValidator(0.5)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_peaks_sorting_method',
            field=models.IntegerField(default=1, help_text='mid_r_peak_sorting', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(3)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='mid_measurement_signal_samples_number',
            field=models.IntegerField(default=10, help_text='mid_r_sweep_avr', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(50)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='name',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='orientation_threshold',
            field=models.IntegerField(default=10, help_text='orientTh', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(125)]),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='updates_server_path',
            field=models.CharField(default='/firmware-updates/bfnew.bin', help_text='upPath', max_length=64),
        ),
        migrations.AddField(
            model_name='sensorsettingsprofile',
            name='updates_server_url',
            field=models.CharField(default='http://downloads.binology.com', help_text='upSer', max_length=64),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='connection_schedule_start',
            field=models.IntegerField(default=0, help_text='on_time', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(24)]),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='connection_schedule_stop',
            field=models.IntegerField(default=24, help_text='off_time', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(24)]),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='fire_min_temp',
            field=models.IntegerField(default=70, help_text='tempFire', validators=[django.core.validators.MinValueValidator(50), django.core.validators.MaxValueValidator(80)]),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='gps_timeout',
            field=models.IntegerField(default=180, help_text='tGps', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(300)]),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='gsm_timeout',
            field=models.IntegerField(default=30, help_text='tGsm', validators=[django.core.validators.MinValueValidator(20), django.core.validators.MaxValueValidator(600)]),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='login',
            field=models.CharField(help_text='serverLogin', max_length=32),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='measurement_interval',
            field=models.IntegerField(default=30, help_text='intConn', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(1440)]),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='message_send_retries',
            field=models.IntegerField(default=20, help_text='retry', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(300)]),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='password',
            field=models.CharField(help_text='serverPassword', max_length=32),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='server_host',
            field=models.CharField(help_text='serverHost', max_length=64),
        ),
        migrations.AlterField(
            model_name='sensorsettingsprofile',
            name='server_port',
            field=models.IntegerField(default=1883, help_text='serverPort', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)]),
        ),
    ]
