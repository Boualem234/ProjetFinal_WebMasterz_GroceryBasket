from django.contrib.auth.models import AbstractUser
from django.db import models

#Modèle personnalisé de User de Django adapté à nos besoins
class Client(AbstractUser):

    address = models.ForeignKey(
        'Address',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='habitants'
    )



#Modèle pour les adresses des clients
class Address(models.Model):
    street_name = models.CharField(max_length=255, null=False, blank=False)
    number = models.CharField(max_length=10, null=False, blank=False)
    city = models.CharField(max_length=100, null=False, blank=False)
    postal_code = models.CharField(max_length=20, null=False, blank=False)

    def __str__(self):
        return f"{self.number} {self.street_name}, {self.city}, {self.postal_code}"
    
    class Meta:
        ordering = ('city', 'street_name')
        verbose_name = "Adresse"
        verbose_name_plural = "Adresses"