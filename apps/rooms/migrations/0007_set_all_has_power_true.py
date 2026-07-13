from django.db import migrations


def set_has_power_true(apps, schema_editor):
    Room = apps.get_model('rooms', 'Room')
    Room.objects.update(has_power=True)


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0006_alter_room_image'),
    ]

    operations = [
        migrations.RunPython(set_has_power_true, reverse_code=migrations.RunPython.noop),
    ]
