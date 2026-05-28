from django.db import models

class Building(models.Model):
    name = models.CharField(max_length=100, blank=True) #(e.g., "New Engineering Building")
    code = models.CharField(max_length=10, unique=True) #(e.g., "NEB")

    def __str__(self):
        return self.name
    
class Room(models.Model):
    name = models.CharField(max_length=100,) #(e.g., "NEB 1")
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='rooms', null=True) # some building are standalone
    capacity = models.IntegerField(blank = True, null=True)

    def __str__(self):
        return self.name