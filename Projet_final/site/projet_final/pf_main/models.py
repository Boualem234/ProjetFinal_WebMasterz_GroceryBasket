from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta

from pf_auth.models import Client


# ------------------------------
# Modèle pour les produits
# ------------------------------
class Product(models.Model):
    name = models.CharField(max_length=50, verbose_name="Nom")
    stock = models.PositiveIntegerField(default=0, verbose_name="Stock")
    description = models.CharField(max_length=300, verbose_name="Description", null=True, blank=True)
    price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(1)],
        verbose_name="Prix du produit"
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name="Catégorie",
        null=False,
        blank=False,
        default=None
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name', )
        verbose_name = "Produit"
        verbose_name_plural = "Produits"


# ------------------------------
# Modèle pour les promotions associées aux produits
# ------------------------------
def default_date_debut():
    return timezone.now() + timedelta(days=1)

def default_date_fin():
    return timezone.now() + timedelta(days=8)


class Promotion(models.Model):
    TYPE_CHOICES = [
        ('pourcentage', 'Pourcentage'),
        ('monetaire', 'Monétaire'),
    ]
    
    name = models.CharField(max_length=50, verbose_name="Nom")
    format = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='pourcentage',
        verbose_name="Format"
    )
    value = models.PositiveIntegerField(
        verbose_name="Valeur",
        validators=[MinValueValidator(0)],
        help_text="Doit être ≤ 100 si format = pourcentage"
    )
    date_debut = models.DateTimeField(
        verbose_name="Date de début",
        default=default_date_debut
    )
    date_fin = models.DateTimeField(
        verbose_name="Date de fin",
        default=default_date_fin
    )

    products = models.ManyToManyField(
        'Product',
        related_name='promotions',
        verbose_name="Produit"
    )

    @property
    def is_active(self):
        now = timezone.now()
        return self.date_debut <= now <= self.date_fin

    def __str__(self):
        return f"{self.name} ({self.format})"

    class Meta:
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(format='monetaire') |
                    (models.Q(format='pourcentage') & models.Q(value__lte=100))
                ),
                name='promotion_value_constraint'
            ),
            models.CheckConstraint(
                check=models.Q(date_fin__gte=models.F('date_debut')),
                name='promotion_date_constraint'
            )
        ]


# ------------------------------
# Modèle pour les catégories de produits
# ------------------------------
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"


# ------------------------------
# Modèle pour les images
# ------------------------------
class Image(models.Model):
    url = models.ImageField(upload_to='images/', verbose_name="Image")
    position = models.PositiveIntegerField(verbose_name="Position", default=1)
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        related_name='images',
        null=True,
        blank=True
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='images',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Image {self.id} - {self.url}"

    class Meta:
        ordering = ['position']
        verbose_name = "Image"
        verbose_name_plural = "Images"


# ------------------------------
# Modèle pour les commandes
# ------------------------------
class Order(models.Model):
    date = models.DateTimeField(auto_now_add=True, verbose_name="Date de commande")
    order_serial = models.CharField(max_length=20, unique=True, verbose_name="Numéro de commande")
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    is_paid = models.BooleanField(default=False, verbose_name="Payé")

    def __str__(self):
        return f"Commande {self.order_serial} - {self.date.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        ordering = ['date']
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"


# ----------------------------------------------------------------------------------------------------------------------------
# Modèle de liaison pour les produits et les promotions, car un produit peu avoir plusieurs promotions, et inversement
# ----------------------------------------------------------------------------------------------------------------------------
class ProductOrder(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product_qty = models.IntegerField(null=False,blank=False)
