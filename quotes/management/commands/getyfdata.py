from django.core.management.base import BaseCommand, CommandError
from quotes.models import FinancialObject, FinancialData, Portfolio

class Command(BaseCommand):
	help="Download from YF api all necessary data to get portfolio time series"

	def handle(self, *args, **options):

		# Step 1: get all Financial Objects currently declared in DB
		fin_objs = FinancialObject.objects.all()

		# Step 2: is first time or not?
		for fin_obj in fin_objs:
			print(fin_obj.name)
			fin_obj.update_nav_and_divs()




