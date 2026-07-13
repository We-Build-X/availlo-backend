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
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='rooms', null=True)
    capacity = models.IntegerField(blank=True, null=True)
    has_power = models.BooleanField(default=False)
    image = CloudinaryField("image", blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)