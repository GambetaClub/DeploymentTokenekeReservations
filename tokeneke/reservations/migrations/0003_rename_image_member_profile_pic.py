# Generated by Django 4.1.7 on 2023-02-24 20:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0002_member_image'),
    ]

    operations = [
        migrations.RenameField(
            model_name='member',
            old_name='image',
            new_name='profile_pic',
        ),
    ]
