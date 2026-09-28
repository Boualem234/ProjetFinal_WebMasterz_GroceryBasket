from django.urls import path

from .views import *

urlpatterns = [
    path('register/', PFRegistrationView.as_view(), name='inscription'),
    path('login/', PFLoginView.as_view(), name='connexion'),
    path('logout/', PFLogoutView.as_view(), name='deconnexion'),
    path('account/', PFClientDetailsView.as_view(), name="compte"),
    path('account/modifiy', PFClientChangeView.as_view(), name="modifier_compte"),
    path('account/password', PFPasswordChangeView.as_view(), name="modifier_mdp"),
    path('account/password/success', PFPasswordChangeSuccessView.as_view(), name="mdp_succes"),
]