import django_stubs_ext
django_stubs_ext.monkeypatch()

from typing import Iterable
from django.db import models
import yfinance as yf
import datetime as dt
import pandas as pd
import numpy as np
import warnings
from dataclasses import dataclass
warnings.filterwarnings("error")

from typing import Self

@dataclass
class PortfolioEntry:
	"""
	Object for tracking an item of the portfolio inventory.

	Args:
		id: id_object code
		nb: number of stocks in the portfolio
		pru: euro amount at which the stcck needs to be for the overall investment to be worth 0
	"""
	id_obj: int
	nb: int
	pru: float

	@classmethod
	def from_order(cls, order) -> Self:
		"""
		Create Portfolio Entry from an order
		"""
		return PortfolioEntry(
			id_obj= order.id_object, 
			nb= order.nb_items, 
			pru= (order.nb_items * order.price + order.total_fee)/order.nb_items
		)

	def update(self, order):
		"""
		Update Portfolio Entry attributes with a new order.
		"""
		if order.id_object == self.id_obj:
			# We assume the order is on the same Financial Instrument as the PortfolioEntry
			
			if order.direction == Order.OrderDirection.BUY:
				# Update self.nb once pru has been calculated
				self.pru = (self.pru * self.nb + order.nb_items * order.price + order.total_fee)/(self.nb + order.nb_items)
				self.nb += order.nb_items
				
			else:
				if self.nb == order.nb_items:
					# Sell everything
					self.nb = 0
					self.pru = 0
				
				else:
					self.pru = (self.pru * self.nb - order.nb_items * order.price + order.total_fee)/ (self.nb - order.nb_items)
					self.nb -= order.nb_items


class PortfolioInventory:

	"""
	A list of PortfolioEntry. The class regroups useful methods to avoid always using list comprehensions.
	"""
	
	def __init__(self, portfolio_entries: list[PortfolioEntry]):
		self.portfolio_entries = portfolio_entries
		self.id_objects = self.id_objects()
		self.nb_objects = self.nbs()

	def id_objects(self) -> list[str]:
		return [item.id_obj for item in self.portfolio_entries]

	def nbs (self) -> list[int]:
		return [item.nb for item in self.portfolio_entries]
	
	def __len__(self) -> int:
		return len(self.portfolio_entries)
	
	# Iterate over the object
	def __iter__(self) -> Self:
		self.indx = 0
		return self

	def __next__(self):
		if self.indx < len(self):
			result = self.portfolio_entries[self.indx]
			self.indx += 1
			return result
		else:
			raise StopIteration


# Create your models here.
class AccountOwner(models.Model):
	name = models.CharField(max_length=30, unique=True)

	def __str__(self):
		return self.name


class Portfolio(models.Model):
	
	owner = models.ForeignKey(AccountOwner, on_delete=models.CASCADE)
	name = models.CharField(max_length=30, default="")
	orders: models.QuerySet["Order"]
	
	ts_ret = None
	ts_val = None
	ts_cumul_ret = None

	def __str__(self):
		return f"{self.owner} - {self.name}"


	def get_price_most_recent_date(self) -> dt.date:
		"""
		Get the second most recent date from price dates, in case all values were not updated to the most recent one
		"""
		return sorted(FinancialData.objects.values_list("date", flat=True).distinct(), reverse=True)[1]


	def get_inventory(self, date=dt.datetime.utcnow()) -> PortfolioInventory:
		"""
		Given a date, return a list of Portfolio Entries with current inventory.
		"""
		all_orders = Order.objects.filter(portfolio=self.id).filter(date__lte = date).order_by("date")
		all_orders = self.orders.all().filter(date__lte = date).order_by("date") ###
		
		curr_inventory: PortfolioInventory = []

		for order in all_orders:
			if curr_inventory and order.id_object in [entry.id_obj for entry in curr_inventory]:
				# Inventory not empty and Financial Instrument already in Portfolio
				
				for entry in curr_inventory:
					entry.update(order)

			else:
				curr_inventory.append(PortfolioEntry.from_order(order))

		return PortfolioInventory([entry for entry in curr_inventory if entry and entry.nb != 0])


	def get_weights(self) -> dict[str, float]:
		"""
		Returns dictionary {FinancialInstrument: weight} for most recent portfolio data
		"""

		most_recent_date = self.get_price_most_recent_date()
		
		inventory = self.get_inventory(most_recent_date)
		fin_instr_in_inventory = [entry.id_object for entry in inventory]
		
		# Get NAV df
		qs = [FinancialData.objects\
					.filter(id_object=obj, field="NAV", origin="Yahoo Finance", date=most_recent_date)\
					.values_list("value", flat=True) for obj in fin_instr_in_inventory]
		
		# Evaluate Query set to only have lists
		qs = [list(q) for q in qs]

		# unlist
		prices = [x for xs in qs for x in xs]
		
		amounts = [price * entry.nb for price, entry in zip(prices, inventory)]
		names = [entry.name for entry in inventory]

		return {k: v/sum(amounts) for k,v in zip(names, amounts)}


	def get_TS(self, date=dt.datetime.utcnow()) -> None:
		"""
		Returns the time series of the portfolio since its inception
		"""
		all_order_dates = set([order.date for order in Order.objects.filter(portfolio=self)])
		all_order_dates = sorted(all_order_dates, reverse=False)

		if len(all_order_dates) == 0:
			return pd.Series()

		# Add today so that the time series is computed until today
		all_order_dates.append(dt.datetime.utcnow().date())

		ts = []
		ts_ret = []

		for i, order_date in enumerate(all_order_dates):
			if i == 0:
				continue

			start = all_order_dates[i-1]

			# all dates prior to order_date (not included because there is a change in inventory)
			inventory = self.get_inventory(start) 

			# Query Prices
			dfs = [pd.DataFrame(list(
				FinancialData.objects.filter(id_object=obj, field="NAV", origin="Yahoo Finance", date__gte=start, date__lte=order_date)
				.values("date", "value"))) for obj in inventory.id_objects]

			# Adjust dfs to series with date index and relevant column names 
			dfs = [df.set_index("date").squeeze().rename(inventory.id_objects[i].name) for i,df in enumerate(dfs)]

			# To dataframe with ordered index dates
			prices = dfs[0].to_frame() if len(dfs) == 1 else pd.concat(dfs, axis=1, sort=True)

			# For some reason, datetime index unordered (later dates before earlier dates)
			# => messes up return calculation
			prices.sort_index(inplace=True)
			
			# Make inventory a 2d numpy array
			inventory = np.reshape(
				np.array(inventory.nb_objects),
				(len(inventory), 1))

			##### Return computation
			# Approximation: change in number of stocks only come into
			# effect at the end of the day when the order was placed.
			
			# Remove rows with NA, compute returns and remove first NA row
			prices_without_na = prices.dropna(axis=0, how="any")
			rets = prices_without_na.pct_change()[1:]

			# EUR amount in each stock is stock_price x nb_stock
			# Dimensions: (n_stocks, 1) = (n_dates -1, n_stocks) x (1, n_stocks)
			amount_per_stock = prices_without_na[:-1] * inventory.T

			# div because element-wise division
			weights = amount_per_stock.div(amount_per_stock.sum(axis=1), axis=0)

			# Keep rets date index
			ptf_ret = (rets * weights.set_index(rets.index)).sum(axis=1)		

			ts_ret.append(ptf_ret)

			##### Portfolio TS computation
			# matrix multiplication
			if i == len(all_order_dates) -1:
				# last one
				ts.append(prices.dot(inventory))
			else:
				ts.append(prices.dot(inventory).iloc[:-1])
			

		self.ts_ret = pd.concat(ts_ret, axis=0).squeeze()
		self.ts_val = pd.concat(ts, axis=0).squeeze()
		self.ts_cumul_ret = pd.concat([
			self.ts_ret.add(1), 
			pd.Series([1], index=[all_order_dates[0]])
			])
		self.ts_cumul_ret.sort_index(inplace=True)
		self.ts_cumul_ret = self.ts_cumul_ret.cumprod()
		
		self.ts_val.to_excel("TS_val.xlsx")
		self.ts_ret.to_excel("TS_ret.xlsx")


class FinancialObject(models.Model):
	
	class ObjectType(models.TextChoices):
		STOCK = "Stock"
		INDEX = "Index"
		ETF = "ETF"
		ETFShare = "ETFShare"

	name = models.CharField(max_length=100)
	category = models.CharField(max_length=10, choices=ObjectType.choices)
	isin = models.CharField(max_length=12)
	ticker = models.CharField(max_length=12, blank=True, null=True)

	def __str__(self):
		return f"{self.category} - {self.name}"

	def get_latest_available_nav(self):
		"""
		Queries FinancialData table to see until when data has been populated.
		"""
		
		if (FinancialData.objects.filter(id_object=self.id).exists()):
			return FinancialData.objects.filter(id_object=self.id).order_by("-date").first().date
		else:
			return None

	def update_nav_and_divs(self):
		"""
		Updates time series
		"""

		stock = yf.Ticker(self.ticker)
		data = []

		if self.get_latest_available_nav() == None:
			# Take everything from YF
			
			df = stock.history(period="max")
			prices: Iterable[tuple[pd.Timestamp, float]] = df["Close"].items() #type: ignore
			divs: Iterable[tuple[pd.Timestamp, float]] = df["Dividends"][df["Dividends"] != 0].items() #type: ignore

			for i, price in prices:
				new = FinancialData(id_object=self, date=i.date(), field="NAV", value=price, origin="Yahoo Finance")
				data.append(new)
			FinancialData.objects.bulk_create(data)
			
			data = []
			for i, div in divs:
				new = FinancialData(id_object=self, date=i.date(), field="Dividends", value=div, origin="Yahoo Finance")
				data.append(new)
			FinancialData.objects.bulk_create(data)

		else:
			last_date = self.get_latest_available_nav()
			df = stock.history(start=dt.datetime.combine(last_date, dt.time.min),
							   end=dt.datetime.now())

			if df.shape[0] == 0:
				# No data
				print(f"No data for {self.ticker}!")
				return 
			
			prices = list(df["Close"].items()) #type: ignore
			divs = list(df["Dividends"][df["Dividends"] != 0].items()) #type: ignore

			for i,price in prices:
				if i.date() == last_date:
					continue
				new = FinancialData(id_object=self, date=i.date(), field="NAV", value=price, origin="Yahoo Finance")
				data.append(new)

			FinancialData.objects.bulk_create(data)

			data = []
			for i, div in divs:
				if i.date() == last_date:
					continue
				new = FinancialData(id_object=self, date=i.date(), field="Dividends", value=div, origin="Yahoo Finance")
				data.append(new)
			FinancialData.objects.bulk_create(data)


	def get_perf(self, start_date, end_date=dt.datetime.utcnow().date()):
		"""
		Get Return between 2 dates
		"""

		ini_nav = FinancialData.objects.filter(id_object=self, date=start_date, field="NAV", origin="Yahoo Finance").values_list("value", flat=True)
		end_nav = FinancialData.objects.filter(id_object=self, date=end_date, field="NAV", origin="Yahoo Finance").values_list("value", flat=True)
		
		ini_nav = list(ini_nav)[0]
		end_nav = list(end_nav)[0]

		return end_nav / ini_nav -1

class Order(models.Model):

	class OrderDirection(models.TextChoices):
		BUY = "BUY"
		SELL = "SELL"

	date = models.DateField()
	portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="orders")
	id_object = models.ForeignKey(FinancialObject, on_delete=models.CASCADE)
	direction = models.CharField(max_length=4, choices=OrderDirection.choices)
	nb_items = models.IntegerField(default=1)
	price = models.FloatField(default=100)
	total_fee = models.FloatField(default=0)

	def __str__(self):
		return f"{self.portfolio.owner} | {self.date} | {self.id_object.name} ({self.nb_items})"


class FinancialData(models.Model):
	
	class TimeSeriesField(models.TextChoices):
		NAV = "NAV"
		Dividends = "Dividends"

	class DataOrigin(models.TextChoices):
		YF = "Yahoo Finance"

	class Meta:
		ordering = ["-date"]

	id_object = models.ForeignKey(FinancialObject, on_delete=models.CASCADE)
	date = models.DateField()
	field = models.CharField(max_length=15, choices=TimeSeriesField.choices)
	value = models.FloatField(default=0)
	origin = models.CharField(max_length=20, choices = DataOrigin.choices)