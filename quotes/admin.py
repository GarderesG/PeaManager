from django.contrib import admin
from django.apps import apps
from .models import AccountOwner, Portfolio, FinancialObject, Order, FinancialData
# Register your models here.

admin.site.register(AccountOwner)
admin.site.register(Portfolio)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ["date", "portfolio", "id_object", "direction", "nb_items", "price", "total_fee"]
	list_filter = ["date", "portfolio", "id_object", "nb_items"]
	search_fields = ["date", "portfolio", "id_object"]
	date_hierarchy = "date"
	ordering = ["-date"]

@admin.register(FinancialObject)
class FinancialObjectAdmin(admin.ModelAdmin):
	list_display = ["id", "name", "category", "isin", "ticker"]
	list_filter = ["name", "category", "isin", "ticker"]
	search_fields = ["name", "category", "isin", "ticker"]
	ordering = ["id"]

@admin.register(FinancialData)
class FinancialDataAdmin(admin.ModelAdmin):
	list_display = ["id_object", "date", "field", "value", "origin"]
	list_filter = ["id_object", "date", "field"]
	search_fields = ["id_object", "date", "field"]
	ordering = ["id"]