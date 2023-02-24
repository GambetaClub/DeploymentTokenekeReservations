# Generated by Django 4.1.7 on 2023-02-24 20:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0004_alter_member_profile_pic'),
    ]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='member_n',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AlterField(
            model_name='member',
            name='profile_pic',
            field=models.ImageField(default='default.jpg', upload_to='profile_pics'),
        ),
    ]
