# Imports Django Core
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.dispatch import receiver
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone

# Imports Django Email
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Imports PayPal
from paypal.standard.forms import PayPalPaymentsForm
from paypal.standard.models import ST_PP_COMPLETED
from paypal.standard.ipn.signals import valid_ipn_received

# Imports du projet
from .models import Product, Promotion, Category, Order, ProductOrder

# Imports Python standard
from decimal import Decimal
import uuid
import logging
import datetime

# Configuration du logger
logger = logging.getLogger(__name__)

def get_best_promotion(product):
    now = timezone.now()
    active_promotions = product.promotions.filter(
        date_debut__lte=now,
        date_fin__gte=now
    )
    
    if not active_promotions.exists():
        return None, None, None
    
    best_price = product.price
    best_promo = None
    best_discount_percentage = None
    
    for promo in active_promotions:
        if promo.format == 'pourcentage':
            discounted = product.price * (Decimal('1') - Decimal(str(promo.value)) / Decimal('100'))
            discount_pct = promo.value
        elif promo.format == 'monetaire':
            discounted = max(Decimal('0'), product.price - Decimal(str(promo.value)))
            discount_pct = round(((product.price - discounted) / product.price) * 100) if product.price else 0
        else:
            continue
        
        # Si ce prix est meilleur (plus bas), on le garde
        if discounted < best_price:
            best_price = discounted
            best_promo = promo
            best_discount_percentage = discount_pct
    
    # Si aucune promotion n'améliore le prix, retourner None
    if best_promo is None:
        return None, None, None
    
    return best_promo, best_price, best_discount_percentage

class IndexView(View):
    def get(self, request):
        all_products = Product.objects.all()
        
        # recent products 
        recent_products_raw = all_products.order_by('-id')[:8]
          # featured products (products with highest stock or different logic)
        featured_products_raw = all_products.order_by('-stock')[:8]
        
        # promotional products
        now = timezone.now()
        promotional_products_raw = Product.objects.filter(
            promotions__date_debut__lte=now,
            promotions__date_fin__gte=now
        ).distinct()[:8]
        
        # If not enough promotional products, fill with random products
        if promotional_products_raw.count() < 8:
            remaining_count = 8 - promotional_products_raw.count()
            extra_products = all_products.exclude(
                id__in=promotional_products_raw.values_list('id', flat=True)
            ).order_by('?')[:remaining_count]
            promotional_products_raw = list(promotional_products_raw) + list(extra_products)
        
        # calculate promotions
        def prepare_products_with_promo(products):
            products_with_promo = []
            for product in products:
                best_promo, discounted_price, discount_percentage = get_best_promotion(product)
                has_promotion = best_promo is not None

                products_with_promo.append({
                    'product': product,
                    'has_promotion': has_promotion,
                    'discounted_price': discounted_price,
                    'discount_percentage': discount_percentage,
                })
            return products_with_promo
        
        # Get all categories for the category slider
        all_categories = Category.objects.all()
        
        context = {
            'recent_products_with_promo': prepare_products_with_promo(recent_products_raw),
            'featured_products_with_promo': prepare_products_with_promo(featured_products_raw),
            'promotional_products_with_promo': prepare_products_with_promo(promotional_products_raw),
            'all_categories': all_categories,
        }
        return render(request, 'accueil.html', context)
    

class ProductVisitView(View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        
        # get the best promotion for this product
        best_promo, discounted_price, discount_percentage = get_best_promotion(product)
        has_promotion = best_promo is not None
        
        # get related products from the same category
        related_products_raw = Product.objects.filter(
            category=product.category
        ).exclude(pk=product.pk)[:4]  # Limit to 4 related products
        
        related_products_with_promo = []
        for related_product in related_products_raw:
            rel_promo, rel_discounted_price, rel_discount_percentage = get_best_promotion(related_product)
            related_products_with_promo.append({
                'product': related_product,
                'has_promotion': rel_promo is not None,
                'discounted_price': rel_discounted_price,
                'discount_percentage': rel_discount_percentage,
            })
        
        context = {
            'product': product,
            'discounted_price': discounted_price,
            'discount_percentage': discount_percentage,
            'has_promotion': has_promotion,
            'related_products_with_promo': related_products_with_promo,
        }
        
        return render(request, 'consulter.html', context)
    
class ContactUsView(View):

    def get(self, request):
        return render(request, 'contact.html')

    def post(self, request):
        context = {}

        firstname = request.POST.get('firstname')
        lastname = request.POST.get('lastname')
        email = request.POST.get('email')
        message = request.POST.get('message')

        subject = f"Nouveau message de {firstname} {lastname}"

        if firstname and lastname and email and message:
            try:
                mail = EmailMessage(
                    subject=subject,
                    body=message,
                    from_email=settings.EMAIL_HOST_USER,   
                    to=[settings.EMAIL_HOST_USER],        
                    reply_to=[email],                     
                )
                mail.send()
                context['result'] = 'Le courriel a bien été envoyé !'

            except Exception as e:
                context['result'] = f'Une erreur est survenue : {e}'
        else:
            context['result'] = 'Tous les champs sont requis'

        return render(request, 'contact.html', context)
    
class AboutUsView(View):
    def get(self, request):
        return render(request, 'propos.html')

class CartView(View):
    def get(self, request):
        # Récupérer le panier de la session
        cart = request.session.get('cart', {})
        
        cart_items = []
        subtotal = Decimal('0')
        
        # Construire la liste des items du panier avec les infos produit
        for product_id, quantity in cart.items():
            try:
                product = Product.objects.get(pk=product_id)
                
                # Obtenir le meilleur prix (avec promotion si applicable)
                best_promo, discounted_price, discount_percentage = get_best_promotion(product)
                
                # Utiliser le prix promotionnel si disponible, sinon le prix normal
                unit_price = discounted_price if discounted_price else product.price
                item_total = unit_price * quantity
                
                cart_items.append({
                    'product': product,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'item_total': item_total,
                    'has_promotion': best_promo is not None,
                    'discount_percentage': discount_percentage,
                })
                
                subtotal += item_total
                
            except Product.DoesNotExist:
                continue
        
        # Calcul des taxes canadiennes (Québec)
        tps = subtotal * Decimal('0.05')  # TPS 5%
        tvq = subtotal * Decimal('0.09975')  # TVQ 9.975%
        total = subtotal + tps + tvq
        
        context = {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'tps': tps,
            'tvq': tvq,
            'total': total,
            'cart_count': sum(cart.values()),
        }
        
        return render(request, 'cart.html', context)
    
    def post(self, request):
        # Gérer l'ajout au panier
        if 'add' in request.POST:
            product_id = request.POST.get('add')
            quantity = int(request.POST.get('quantity', 1))
            
            try:
                product = Product.objects.get(pk=product_id)
                
                # Initialiser le panier si nécessaire
                cart = request.session.get('cart', {})
                
                # Ajouter ou mettre à jour la quantité
                current_qty = cart.get(product_id, 0)
                new_qty = current_qty + quantity
                
                # Vérifier le stock
                if new_qty <= product.stock:
                    cart[product_id] = new_qty
                    request.session['cart'] = cart
                    request.session.modified = True
                else:
                    # Stock insuffisant -> on met le maximum disponible
                    cart[product_id] = product.stock
                    request.session['cart'] = cart
                    request.session.modified = True
                    
            except Product.DoesNotExist:
                pass
        
        return redirect('cart')
    
class CategoryView(View):
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        products = Product.objects.filter(category=category)

        products_with_promo = []
        for product in products:
            best_promo, discounted_price, discount_percentage = get_best_promotion(product)
            has_promotion = best_promo is not None

            products_with_promo.append({
                'product': product,
                'has_promotion': has_promotion,
                'discounted_price': discounted_price,
                'discount_percentage': discount_percentage,
            })

        context = {
            'category': category,
            'products_with_promo': products_with_promo,
        }

        return render(request, 'categorie.html', context)
    

class ProductSearchView(View):
    def get(self, request):
        query = request.GET.get("q", "")
        category_id = request.GET.get("category_id", "")
        promo_only = request.GET.get("promo") == "1"
        page_number = request.GET.get('page', 1)
        products = Product.objects.all()

        # Recherche textuelle
        if query:
            products = products.filter(name__icontains=query)

        # Filtre Catégorie
        if category_id:
            products = products.filter(category_id=category_id)

        # Filtrer uniquement les produits en promotion
        if promo_only:
            now = timezone.now()
            products = products.filter(
                promotions__date_debut__lte=now,
                promotions__date_fin__gte=now
            ).distinct()

        # Pagination - 12 produits par page
        paginator = Paginator(products, 12)
        try:
            products_page = paginator.page(page_number)
        except PageNotAnInteger:
            products_page = paginator.page(1)
        except EmptyPage:
            products_page = paginator.page(paginator.num_pages)

        # Préparer les données promotionnelles
        products_with_promo = []
        for product in products_page:
            best_promo, discounted_price, discount_percentage = get_best_promotion(product)
            has_promotion = best_promo is not None

            products_with_promo.append({
                "product": product,
                "has_promotion": has_promotion,
                "discounted_price": discounted_price,
                "discount_percentage": discount_percentage,
            })

        context = {
            "query": query,
            "selected_category": category_id,
            "promo_only": promo_only,
            "categories": Category.objects.all(),
            "products_with_promo": products_with_promo,
            "page_obj": products_page,
        }

        return render(request, "rechercher.html", context)


class PaymentView(LoginRequiredMixin, View):
    login_url = '/client/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        cart = request.session.get('cart', {})
        
        if not cart:
            messages.warning(request, "Votre panier est vide.")
            return redirect('cart')
        
        # vérification et réservation du stock avec verrouillage
        cart_items = []
        subtotal = Decimal('0')
        stock_issues = []
        
        with transaction.atomic():
            for product_id, quantity in cart.items():
                try:
                    product = Product.objects.select_for_update().get(id=product_id)
                    
                    # Vérifier le stock dispo
                    if product.stock < quantity:
                        stock_issues.append({
                            'product': product,
                            'requested': quantity,
                            'available': product.stock
                        })
                        continue
                    
                    # Calculer le prix avec promotion
                    best_promo, discounted_price, discount_percentage = get_best_promotion(product)
                    
                    if best_promo:
                        item_price = discounted_price
                    else:
                        item_price = product.price
                    
                    item_total = item_price * quantity
                    subtotal += item_total
                    
                    cart_items.append({
                        'product': product,
                        'quantity': quantity,
                        'price': item_price,
                        'total': item_total,
                        'promo': best_promo,
                        'discount_percentage': discount_percentage
                    })
                    
                except Product.DoesNotExist:
                    continue
            
            if stock_issues:
                for issue in stock_issues:
                    messages.error(
                        request,
                        f"Stock insuffisant pour {issue['product'].name}: "
                        f"{issue['available']} disponible(s), {issue['requested']} demandé(s)"
                    )
                # Transaction annulée
                return redirect('cart')
            
            if not cart_items:
                messages.error(request, "Aucun produit valide dans votre panier.")
                return redirect('cart')
            
            tps = subtotal * Decimal('0.05')
            tvq = subtotal * Decimal('0.09975')
            taxes = tps + tvq
            total = subtotal + taxes
            
            # Créer la commande en attente
            user = request.user
            order_serial = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            order = Order.objects.create(order_serial=order_serial, client=user)
            
            # Sauvegarder les produits de la commande
            for item in cart_items:
                ProductOrder.objects.create(
                    order=order,
                    product=item['product'],
                    product_qty=item['quantity']
                )
        
        # Stocker dans la session
        request.session['pending_order_id'] = order.id
        request.session['order_total'] = str(total)
        request.session.modified = True
        
        # Préparer les items détaillés pour PayPal
        paypal_dict = {
            "cmd": "_cart",
            "upload": "1", 
            "business": settings.PAYPAL_RECEIVER_EMAIL,
            "currency_code": "CAD",
            "notify_url": request.build_absolute_uri(reverse('paypal-ipn')),
            "return": request.build_absolute_uri(reverse('payment_success')),
            "cancel_return": request.build_absolute_uri(reverse('payment_cancel')),
            "custom": str(order.id),
            "invoice": order_serial,
            "no_shipping": "1",
            "charset": "utf-8",
        }
        
        for idx, item in enumerate(cart_items, 1):
            # Nom du produit
            paypal_dict[f'item_name_{idx}'] = item['product'].name[:127]
            
            # Prix unitaire
            paypal_dict[f'amount_{idx}'] = str(item['price'].quantize(Decimal('0.01')))
            
            # Quantité
            paypal_dict[f'quantity_{idx}'] = item['quantity']
            
            # Numéro de produit
            paypal_dict[f'item_number_{idx}'] = str(item['product'].id)
            
            # URL de l'image du produit pour l'afficher dans PayPal
            if item['product'].images.exists():
                image_url = request.build_absolute_uri(item['product'].images.first().url.url)
                paypal_dict[f'image_url_{idx}'] = image_url
        
        # Ajouter les taxes
        paypal_dict['tax_cart'] = str(taxes.quantize(Decimal('0.01')))
                
        form = PayPalPaymentsForm(initial=paypal_dict)
        
        context = {
            "form": form,
            "order": order,
            "cart_items": cart_items,
            "subtotal": subtotal,
            "tps": tps,
            "tvq": tvq,
            "taxes": taxes,
            "total": total,
        }
        
        return render(request, "paiement.html", context)
    
class UpdateCartView(View):    
    def post(self, request):
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 0))
        
        cart = request.session.get('cart', {})
        
        if quantity > 0:
            try:
                product = Product.objects.get(pk=product_id)
                # Vérifier le stock
                if quantity <= product.stock:
                    cart[product_id] = quantity
                else:
                    cart[product_id] = product.stock
            except Product.DoesNotExist:
                pass
        else:
            # Si quantité = 0, supprimer l'item
            if product_id in cart:
                del cart[product_id]
        
        request.session['cart'] = cart
        request.session.modified = True
        
        return redirect('cart')


class RemoveFromCartView(View):    
    def get(self, request, product_id):
        cart = request.session.get('cart', {})
        
        if str(product_id) in cart:
            del cart[str(product_id)]
            request.session['cart'] = cart
            request.session.modified = True
        
        return redirect('cart')




class PaymentSuccessView(View):
    def get(self, request):
        order_id = request.session.get('pending_order_id')
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                
                # Vérifier si le paiement a été confirmé
                if order.is_paid:
                    # Rediriger vers la page de succès finale
                    return redirect('order_success', order_id=order.id)
                else:
                    # Paiement en attente de confirmation PayPal
                    context = {
                        'order': order,
                        'message': 'Votre paiement est en cours de traitement par PayPal...'
                    }
                    return render(request, 'payment-processing.html', context)
                    
            except Order.DoesNotExist:
                messages.error(request, "Commande introuvable.")
                return redirect('accueil')
        
        messages.info(request, "Aucune commande en attente.")
        return redirect('accueil')


class PaymentCancelView(View):
    def get(self, request):
        order_id = request.session.get('pending_order_id')
        order_serial = None
        
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order_serial = order.order_serial
                # Supprimer la commande annulée
                order.delete()
                
                # Nettoyer la session
                del request.session['pending_order_id']
                if 'order_total' in request.session:
                    del request.session['order_total']
                request.session.modified = True
                
                logger.info(f"Commande {order_serial} annulée par l'utilisateur")
            except Order.DoesNotExist:
                pass
        
        context = {'order_serial': order_serial}
        return render(request, 'payment-cancelled.html', context)


class OrderSuccessView(View):
    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            order_items = ProductOrder.objects.filter(order=order).select_related('product')
            
            subtotal = Decimal('0')
            items_data = []
            
            for item in order_items:
                product = item.product
                best_promo, discounted_price, discount_percentage = get_best_promotion(product)
                
                if best_promo:
                    item_price = discounted_price
                else:
                    item_price = product.price
                
                item_total = item_price * item.product_qty
                subtotal += item_total
                
                items_data.append({
                    'product': product,
                    'quantity': item.product_qty,
                    'price': item_price,
                    'total': item_total,
                    'promo': best_promo,
                    'discount_percentage': discount_percentage
                })
            
            tps = subtotal * Decimal('0.05')
            tvq = subtotal * Decimal('0.09975')
            taxes = tps + tvq
            total = subtotal + taxes
            
            # Nettoyer la session
            if 'pending_order_id' in request.session:
                del request.session['pending_order_id']
            if 'order_total' in request.session:
                del request.session['order_total']
            if 'cart' in request.session:
                del request.session['cart']
            request.session.modified = True

            # L'email est envoyé automatiquement par le signal IPN PayPal

            context = {
                'order': order,
                'items': items_data,
                'subtotal': subtotal,
                'tps': tps,
                'tvq': tvq,
                'taxes': taxes,
                'total': total,
            }
            
            return render(request, 'succes-achat.html', context)
            
        except Order.DoesNotExist:
            messages.error(request, "Commande introuvable.")
            return redirect('accueil')
