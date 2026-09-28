from django.conf import settings
from django.utils import timezone

from .models import Category, Product, Promotion


def demo_processor(request):
  # Fournit aux templates les catégories, produits récents et produits en promotion
  now = timezone.now()
  
  # Récupère les promotions actuellement actives (date_debut <= maintenant <= date_fin)
  active_promotions = Promotion.objects.filter(
    date_debut__lte=now,
    date_fin__gte=now
  )
  
  # Récupère les produits en promotion
  promotional_products = Product.objects.filter(
    promotions__in=active_promotions
  ).distinct().order_by('-id')[:12]
  
  # Calcule le nombre total d'articles dans le panier
  cart = request.session.get('cart', {})
  cart_count = sum(cart.values()) if cart else 0
  
  return {
    "SITE_LANGUAGES": settings.LANGUAGES,
    "all_categories": Category.objects.all(),
    "recent_products": Product.objects.order_by('-id')[:8],
    "promotional_products": promotional_products,
    "cart_count": cart_count,
  }
