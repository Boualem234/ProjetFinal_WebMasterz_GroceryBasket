from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from paypal.standard.ipn.signals import valid_ipn_received
from paypal.standard.models import ST_PP_COMPLETED
from decimal import Decimal
import os
import logging

from .models import Image, Order, ProductOrder, Product

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Image)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Supprime l'ancienne image du disque lors de la modification
    d'une instance Image si l'image a changé.
    """
    if not instance.pk:
        return False
    
    try:
        old_file = sender.objects.get(pk=instance.pk).url
    except sender.DoesNotExist:
        return False
    
    new_file = instance.url
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


@receiver(post_delete, sender=Image)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Supprime le fichier image du disque lors de la suppression
    d'une instance Image.
    """
    if instance.url and os.path.isfile(instance.url.path):
        os.remove(instance.url.path)


# Signal receiver pour PayPal IPN - MAJ de l'inventaire uniquement après confirmation de paiement
@receiver(valid_ipn_received)
def payment_notification(sender, **kwargs):
    ipn_obj = sender
    
    # verif que le paiement est complété
    if ipn_obj.payment_status == ST_PP_COMPLETED:
        try:
            order_id = int(ipn_obj.custom)
            order = Order.objects.get(id=order_id)
            
            # verif que le montant correspond
            expected_total = Decimal(ipn_obj.mc_gross)
            
            with transaction.atomic():
                order_items = ProductOrder.objects.filter(order=order).select_related('product')
                
                # MAJ du stock
                for item in order_items:
                    product = Product.objects.select_for_update().get(id=item.product.id)
                    
                    if product.stock >= item.product_qty:
                        product.stock -= item.product_qty
                        product.save()
                        logger.info(f"Stock mis à jour pour {product.name}: -{item.product_qty} (nouveau stock: {product.stock})")
                    else:
                        logger.warning(f"Stock insuffisant pour {product.name} lors de la confirmation PayPal")
                
                # Marquer la commande comme payée
                order.is_paid = True
                order.save()
                                
                logger.info(f"Commande {order.order_serial} confirmée et stock mis à jour via IPN PayPal")
                
                # Envoyer l'email de confirmation
                send_payment_confirmation_email(order)
                
        except (ValueError, Order.DoesNotExist) as e:
            logger.error(f"Erreur lors du traitement IPN PayPal: {e}")
    else:
        # Paiement échoué ou refusé
        logger.warning(f"IPN reçu avec statut non-complété: {ipn_obj.payment_status}")
        try:
            order_id = int(ipn_obj.custom)
            order = Order.objects.get(id=order_id)
            send_payment_failure_email(order, ipn_obj.payment_status)
        except (ValueError, Order.DoesNotExist):
            pass


def send_payment_confirmation_email(order):
    try:
        from .views import get_best_promotion
        
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

        context = {
            'order': order,
            'items': items_data,
            'subtotal': subtotal,
            'tps': tps,
            'tvq': tvq,
            'taxes': taxes,
            'total': total,
            'user': order.client,
        }
        
        html_message = render_to_string('emails/succes-commande-email.html', context)
        
        email = EmailMessage(
            subject='Confirmation de votre commande',
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.client.email],
        )
        email.content_subtype = 'html'
        email.send()
        
        logger.info(f"Email de confirmation envoyé pour la commande {order.order_serial}")
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email de confirmation: {e}")


def send_payment_failure_email(order, payment_status):
    try:
        context = {
            'order': order,
            'user': order.client,
            'payment_status': payment_status,
        }
        
        html_message = render_to_string('emails/echec-paiement-email.html', context)
        
        email = EmailMessage(
            subject='Problème avec votre paiement',
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.client.email],
        )
        email.content_subtype = 'html'
        email.send()
        
        logger.info(f"Email d'échec de paiement envoyé pour la commande {order.order_serial}")
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email d'échec: {e}")
