from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect


from  .models import *


#Modèle Admin pour les promotions
@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    ordering = ['-date_debut', 'name']
    readonly_fields = ('product_list', 'is_active_display')
    list_display = ('name', 'value', 'format', 'date_debut', 'date_fin', 'is_active_display', 'product_list')
    filter_horizontal = ('products',)

    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ En vigueur</span>')
        return format_html('<span style="color: gray;">✗ Inactive</span>')
    
    is_active_display.short_description = "Statut"
    is_active_display.admin_order_field = 'date_debut' 

    def product_list(self, obj):
        """Affiche la liste des produits liés avec image + lien"""
        if not obj.pk:
            return "-"

        products = obj.products.all()
        if not products:
            return _("Aucun produit")

        return format_html_join(
            mark_safe("<br>"),
            """
            <div style="display:flex; align-items:center; gap:10px;">
                <img src="{}" style="max-height:50px; border-radius:5px;" />
                <a href="{}" style="font-weight:600;">{}</a>
            </div>
            """,
            (
                (
                    # Première image (comme CategoryAdmin)
                    (
                        p.images.first().url.url 
                        if p.images.first() and p.images.first().url 
                        else ""
                    ),
                    # Lien admin automatique
                    reverse(f"admin:{p._meta.app_label}_{p._meta.model_name}_change", args=[p.pk]),
                    # Nom du produit
                    p.name,
                )
                for p in products
            )
        )

    product_list.short_description = "Produits liés"



    

#Modèle Admin pour les produits
class ProductImageInline(admin.TabularInline):
    model = Image
    extra = 1
    fields = ('url', 'image_preview', 'position')
    readonly_fields = ('image_preview',)
    ordering = ('position',)
    
    def image_preview(self, obj):
        """Affiche un aperçu de l'image."""
        if obj.url:
            return format_html('<img src="{}" style="max-height:100px; border-radius:5px;" />', obj.url.url)
        return "Aucune image"
    
    image_preview.short_description = "Aperçu"
    
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('get_main_image', 'name', 'category', 'price', 'stock')
    list_editable = ('stock',)
    list_filter = ('category',)
    search_fields = ('name', 'description', 'category__name')
    inlines = [ProductImageInline]
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('name', 'category', 'description')
        }),
        ('Prix et stock', {
            'fields': ('price', 'stock')
        })
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['category'].required = True
        return form
    
    def get_main_image(self, obj):
        main_image = obj.images.filter(position=1).first()
        if main_image:
            return format_html('<img src="{}" width="50" height="50" />', main_image.url.url)
        return "No image"
    get_main_image.short_description = 'Image'

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }

    
class ImageFormSet(BaseInlineFormSet):
    """FormSet personnalisé pour valider la présence d'au moins une image."""
    
    def clean(self):
        super().clean()
        
        # Compter les images valides (non supprimées)
        valid_images = 0
        for form in self.forms:
            if form.cleaned_data.get('url') and not form.cleaned_data.get('DELETE', False):
                valid_images += 1
        
        if valid_images == 0:
            raise ValidationError("Chaque catégorie doit avoir au moins une image.")


#Modèles Admin pour les catégories
class ImageInline(admin.StackedInline):
    model = Image
    extra = 1
    max_num = 1  # Limite à 1 image maximum
    fields = ("url", "image_preview")
    readonly_fields = ("image_preview",)
    formset = ImageFormSet
    
    def image_preview(self, obj):
        """Affiche un aperçu de l'image en édition."""
        if obj.url:
            return format_html('<img src="{}" style="max-height:150px; border-radius:5px;" />', obj.url.url)
        return "Aucune image"
    
    image_preview.short_description = "Aperçu"
    
    def get_queryset(self, request):
        """Filtre pour afficher que les images liées à la catégorie (category, pas product)"""
        qs = super().get_queryset(request)
        return qs.filter(category__isnull=False, product__isnull=True)
    
    def get_extra(self, request, obj=None, **kwargs):
        """Masque le formulaire vide si une image existe déjà."""
        if obj is not None and obj.images.filter(product__isnull=True).exists():
            return 0
        return 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "image_preview", "product_count")
    search_fields = ("name",)
    inlines = [ImageInline]
    
    def image_preview(self, obj):
        """Affiche la première image liée à la catégorie dans la liste."""
        first_image = obj.images.first()
        if first_image and first_image.url:
            return format_html(
                '<img src="{}" style="max-height:50px; border-radius:5px;" />',
                first_image.url.url
            )
        return "Aucune image"
    
    image_preview.short_description = "Image"
    
    def product_count(self, obj):
        """Affiche le nombre de produits liés à cette catégorie."""
        return obj.products.count()
    
    product_count.short_description = "Nb. produits"
    
    def has_delete_permission(self, request, obj=None):
        """Empêche la suppression si la catégorie est liée à des produits."""
        if obj and obj.products.exists():
            return False
        return super().has_delete_permission(request, obj)
    
    def delete_view(self, request, object_id, extra_context=None):
        """Affiche un message d'erreur si tentative de suppression d'une catégorie liée."""
        obj = self.get_object(request, object_id)
        if obj and obj.products.exists():
            self.message_user(
                request,
                f"Impossible de supprimer la catégorie '{obj.name}' : elle est liée à {obj.products.count()} produit(s).",
                level='error'
            )
            return HttpResponseRedirect(request.path.replace('/delete/', '/change/'))
        return super().delete_view(request, object_id, extra_context)