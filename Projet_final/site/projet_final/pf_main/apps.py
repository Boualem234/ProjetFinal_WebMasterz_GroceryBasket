from django.apps import AppConfig


class PfMainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pf_main'
    verbose_name = "Boutique"

    def ready(self):
        import pf_main.signals
