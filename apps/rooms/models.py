from django.db import models
from django.utils.text import slugify
from cloudinary.models import CloudinaryField

class Building(models.Model):
    name = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Room(models.Model):
    name = models.CharField(max_length=100)
    full_name = models.CharField(max_length=255, default="NONE", blank=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='rooms', null=True)
    faculty = models.CharField(max_length=255, default="Engineering", blank=True)
    capacity = models.IntegerField(blank=True, null=True)
    has_power = models.BooleanField(default=False)
    image = CloudinaryField("image", blank=True, null=True)

    def __str__(self):
        return self.name

    def _generate_unique_slug(self):
        base = slugify(self.name) or "room"
        candidate, n = base, 2
        qs = Room.objects.exclude(pk=self.pk) if self.pk else Room.objects.all()
        while qs.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate

    def save(self, *args, **kwargs):
        # Regenerate the slug from the name on every save so renames update it.
        self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)