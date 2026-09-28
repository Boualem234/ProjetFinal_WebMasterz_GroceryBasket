from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView, LoginView, PasswordChangeDoneView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.views.generic.base import View
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .forms import *

from django.conf import settings
from django.core.mail import EmailMessage

from django.core.cache import cache

class PFRegistrationView(View):
    def get(self, request):
        user_form = PFClientForm()
        address_form = PFAddressForm()
        return render(request, 'register.html', {
            'user_form': user_form,
            'address_form': address_form
        })

    def post(self, request):
        context = {}

        user_form = PFClientForm(request.POST)
        address_form = PFAddressForm(request.POST)

        if user_form.is_valid() and address_form.is_valid():
            user = user_form.save()
            address = address_form.save(commit=False)
            address.client = user
            address.save()

            # Envoyer l'email de confirmation
            self.send_confirmation_email(user)

            return redirect('connexion')

        return render(request, 'register.html', {
            'user_form': user_form,
            'address_form': address_form
        })
    
    def send_confirmation_email(self, user):
        """Envoie l'email de confirmation d'inscription"""
        
        # Contexte pour le template email
        context = {
            'user': user,
            'contact_email': settings.DEFAULT_FROM_EMAIL,  # ou votre email de support
            'company_address': '123 Rue du Marché, Votre Ville, QC, G7H 1A1',
        }
        
        # Générer le contenu HTML de l'email
        html_message = render_to_string('emails/registration_confirmation.html', context)
        
        # Version texte brut (optionnel mais recommandé)
        plain_message = strip_tags(html_message)
        
        # Créer et envoyer l'email
        email = EmailMessage(
            subject='Bienvenue chez GROCERY BASKET',
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.content_subtype = 'html'  # Important pour envoyer en HTML
        
        try:
            email.send()
        except Exception as e:
            # Log l'erreur mais ne bloque pas l'inscription
            print(f"Erreur lors de l'envoi de l'email: {e}")


from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.core.cache import cache
from django.urls import reverse_lazy
from django.shortcuts import redirect

MAX_ATTEMPTS = 5
BLOCK_TIME = 300  # 5 minutes


class PFLoginView(LoginView):
    form_class = PFLoginForm
    template_name = "login.html"
    success_url = reverse_lazy("accueil")

    def post(self, request, *args, **kwargs):
        ip = self.get_client_ip()
        username = request.POST.get("username")

        cache_key = f"login_attempts_{ip}_{username}"
        attempts = cache.get(cache_key, 0)

        response = super().post(request, *args, **kwargs)

        #Connexion réussie → reset compteur
        if request.user.is_authenticated:
            cache.delete(cache_key)
            return response

        #Échec → incrément
        attempts += 1
        cache.set(
            cache_key,
            attempts,
            timeout=settings.BLOCK_TIME
        )

        # Message de blocage (UNE SEULE FOIS)
        if attempts == settings.MAX_ATTEMPTS:
            messages.error(
                request,
                "Trop de tentatives de connexion. Réessaie dans quelques minutes."
            )

        return response

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return self.request.META.get("REMOTE_ADDR")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ip = self.get_client_ip()
        username = self.request.POST.get("username", "")
        cache_key = f"login_attempts_{ip}_{username}"

        context["is_blocked"] = cache.get(cache_key, 0) >= settings.MAX_ATTEMPTS
        return context



class PFLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('accueil')

class PFClientDetailsView(LoginRequiredMixin, DetailView):
    template_name = "account_details.html"

    def get_object(self):
        return self.request.user

class PFClientChangeView(LoginRequiredMixin, View):
    template_name = "user_change.html"
    success_url = reverse_lazy("compte")

    def get(self, request):
        user = request.user

        client_form = PFClientChangeForm(instance=user, prefix="client")
        address_form = PFAddressChangeForm(
            instance=user.address if user.address else None,
            prefix="address"
        )

        return render(request, self.template_name, {
            "client_form": client_form,
            "address_form": address_form
        })

    def post(self, request):
        user = request.user

        client_form = PFClientChangeForm(request.POST, instance=user, prefix="client")
        address_form = PFAddressChangeForm(
            request.POST,
            instance=user.address if user.address else None,
            prefix="address"
        )

        if client_form.is_valid() and address_form.is_valid():
            client_form.save()

            address = address_form.save()
            if not user.address:
                user.address = address
                user.save(update_fields=["address"])

            return redirect(self.success_url)

        return render(request, self.template_name, {
            "client_form": client_form,
            "address_form": address_form
        })

    
class PFPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "password_change.html"
    success_url = reverse_lazy("mdp_succes")

class PFPasswordChangeSuccessView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "password_change_success.html"