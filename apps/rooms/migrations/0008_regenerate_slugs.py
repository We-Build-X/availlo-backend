from django.db import migrations
from django.utils.text import slugify


def regenerate_slugs(apps, schema_editor):
    Room = apps.get_model('rooms', 'Room')
    for room in Room.objects.all():
        new_slug = slugify(room.name)
        if room.slug != new_slug:
            room.slug = new_slug
            room.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0007_set_all_has_power_true'),
    ]

    operations = [
        migrations.RunPython(regenerate_slugs, reverse_code=migrations.RunPython.noop),
    ]
