from django.urls import path
from.views import *

#=-----------------------------------------------------=#
#   À DÉCOMMENTER QUAND LES VIEWS SERONT IMPLÉMENTÉS    
#=-----------------------------------------------------=#
urlpatterns = [
    path('', IndexView.as_view(), name="accueil"),

    path('product/search', ProductSearchView.as_view(), name="rechercher"),
    path('product/<int:pk>', ProductVisitView.as_view(), name="consulter"),
    path('category/<int:pk>', CategoryView.as_view(), name="categorie"),
    path('contactus', ContactUsView.as_view(), name="contacter"),
    path('aboutus', AboutUsView.as_view(), name="propos"),
    path('cart', CartView.as_view(), name="cart"),
    path('payment/', PaymentView.as_view(), name="payment"),
    path('payment/success/', PaymentSuccessView.as_view(), name="payment_success"),
    path('payment/cancel/', PaymentCancelView.as_view(), name="payment_cancel"),
    path('order/success/<int:order_id>/', OrderSuccessView.as_view(), name="succes_achat"),
    path('cart/update', UpdateCartView.as_view(), name="update_cart"),
    path('cart/remove/<int:product_id>', RemoveFromCartView.as_view(), name="remove_from_cart"),

]