import django_stubs_ext
django_stubs_ext.monkeypatch()

from typing import Iterable
from django.db import models
import yfinance as yf
import datetime as dt
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("error")
from dataclasses import dataclass
from typing import Self

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
            if self.isin == "LU1834983477":
                  last_date = dt.date(2022,1,19)
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


    def get_perf(self, start_date, end_date=dt.datetime.today().date()):
        """
        Get Return between 2 dates
        """

        ini_nav = FinancialData.objects.filter(id_object=self, date=start_date, field="NAV", origin="Yahoo Finance").values_list("value", flat=True)
        end_nav = FinancialData.objects.filter(id_object=self, date=end_date, field="NAV", origin="Yahoo Finance").values_list("value", flat=True)
        
        ini_nav = list(ini_nav)[0]
        end_nav = list(end_nav)[0]

        return end_nav / ini_nav -1


class AccountOwner(models.Model):
    name = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.name


@dataclass
class PortfolioEntry:
    """
    Object for tracking an item of the portfolio inventory.

    Args:
        id_obj: FinancialObject on which a position is held
        nb: number of stocks in the portfolio
        pru: euro amount at which the stcck needs to be for the overall investment to be worth 0
    """
    fin_obj: "FinancialObject"
    nb: int
    pru: float

    @classmethod
    def from_order(cls, order: "Order") -> Self:
        """
        Create Portfolio Entry from an order
        """
        
        return cls(
            fin_obj = order.id_object, 
            nb = order.nb_items, 
            pru = (order.nb_items * order.price + order.total_fee)/order.nb_items
        )

    def update(self, order):
        """
        Update Portfolio Entry attributes with a new order.
        """
        if order.id_object.id == self.fin_obj.id:
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
    A list of PortfolioEntry. The class regroups useful methods to easily manipulate underlying FinancialObjects.
    """

    def __init__(self, portfolio_entries: list[PortfolioEntry]):
        """
        Preferred way to build one is from a list of PortfolioEntry
        """
        self.portfolio_entries = portfolio_entries

    @classmethod
    def from_orders(cls, orders):
        """
        Possible to build one from a bunch of orders
        """
        pass
    
    @classmethod
    def from_portfolio(cls, portfolio):
        """
        Possible to build one from a portfolio
        """
        pass

    @property
    def id_objects(self) -> list[str]:
        return [item.fin_obj.id for item in self.portfolio_entries]
    
    @property
    def fin_objs(self) -> list[FinancialObject]:
          return [item.fin_obj for item in self.portfolio_entries]
    
    @property
    def names(self) -> list[str]:
        return [item.fin_obj.name for item in self.portfolio_entries]

    @property
    def nbs (self) -> list[int]:
        return [item.nb for item in self.portfolio_entries]

    @property    
    def prus(self) -> list[float]:
          return [item.pru for item in self.portfolio_entries]

    @property
    def weights(self) -> dict[FinancialObject, float]:
        pass

    def to_df(self) -> pd.DataFrame:
        """
        Inventory to df with columns Id, Name, Number, PRU
        """
        rows = {i: [item.fin_obj.id, item.fin_obj.name, item.nb, item.pru] for i, item in enumerate(self.portfolio_entries)}
        return pd.DataFrame.from_dict(rows, orient='index', columns=["Id", "Name", "Number", "PRU"])

    def __len__(self) -> int:
        return len(self.portfolio_entries)


class Portfolio(models.Model):
    
    owner = models.ForeignKey(AccountOwner, on_delete=models.CASCADE)
    name = models.CharField(max_length=30, default="")

    ts_ret = None
    ts_val = None
    ts_cumul_ret = None

    def __str__(self):
        return f"{self.owner} - {self.name}"

    @property
    def orders(self) -> models.QuerySet["Order"]: 
        """
        Queries the order datatbase and returns all orders associated to Portfolio in date ascending order
        """
        return Order.objects.filter(portfolio=self.id).order_by("date")


    def inventory_df(self) -> pd.DataFrame:
          """
          Get current inventory in a dataframe, ordered by descending rows of weight
          """
          return self.get_inventory().to_df()


    def get_inventory(self, date=dt.datetime.today()) -> PortfolioInventory:
        """
        Given a date, return a list of Portfolio Entries with current inventory.
        """        
        all_orders = self.orders.filter(date__lte=date).order_by("date")
        
        curr_inventory: PortfolioInventory = []

        for order in all_orders:
            if curr_inventory and order.id_object.id in [entry.fin_obj.id for entry in curr_inventory]:
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

        most_recent_date = FinancialData.get_price_most_recent_date()
        
        inventory = self.get_inventory(most_recent_date)
        
        # Get NAV df
        qs = [FinancialData.objects\
                    .filter(id_object=obj, field="NAV", origin="Yahoo Finance", date=most_recent_date)\
                    .values_list("value", flat=True) for obj in inventory.fin_objs]
        
        # Evaluate Query set to only have lists
        qs = [list(q) for q in qs]

        # unlist
        prices = [x for xs in qs for x in xs]
        
        amounts = [price * nb for price, nb in zip(prices, inventory.nbs)]

        return {k: v/sum(amounts) for k,v in zip(inventory.names, amounts)}


    def get_TS(self) -> None:
        """
        Returns the time series of the portfolio since its inception
        """
        # Retrieve all orders
        all_order_dates = set([order.date for order in self.orders.all()])
        all_order_dates = sorted(all_order_dates, reverse=False)

        if len(all_order_dates) == 0:
            raise Exception("No order data.")

        # Add today so that the time series is computed until today
        all_order_dates.append(dt.datetime.today().date())

        ts = []
        ts_ret = []

        for i, order_date in enumerate(all_order_dates):
            if i == 0:
                continue

            start = all_order_dates[i-1]
            inventory = self.get_inventory(start)
            prices_df = YahooFinanceQuery.get_prices_from_inventory(fin_objs = inventory.fin_objs,
                                                                 from_date = start,
                                                                 until_date = order_date)

            # Make inventory a 2d numpy array
            inventory = np.array(inventory.nbs)
            
            ##### Return computation
            # Approximation: change in number of stocks only come into
            # effect at the end of the day when the order was placed.
            
            # Remove rows with NA, compute returns and remove first NA row
            prices_without_na = prices_df.dropna(axis=0, how="any")
            rets = prices_without_na.pct_change()[1:]

            # EUR amount in each stock is stock_price x nb_stock
            # Dimensions: (n_stocks, 1) = (n_dates -1, n_stocks) x (1, n_stocks)
            amount_per_stock = prices_without_na[:-1] * inventory
            

            # div because element-wise division
            weights = amount_per_stock.div(amount_per_stock.sum(axis=1), axis=0)
            
            # Keep rets date index
            ptf_ret = (rets * weights.set_index(rets.index)).sum(axis=1)        

            ts_ret.append(ptf_ret)

            ##### Portfolio TS computation
            # matrix multiplication
            if i == len(all_order_dates) -1:
                # last one
                ts.append(prices_without_na.dot(inventory))
            else:
                ts.append(prices_without_na.dot(inventory).iloc[:-1])
            

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

    def get_individual_returns(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Lines: All Financial Instruments that have been in the portfolio during the time frame
        Columns: Price contribution, Dividend contribution, Total contribution 
        """
        # Retrieve all Financial Instruments that have been in the portfolio during the time frame
        fin_ins = self.get_inventory(start_date).fin_objs
        subsequent_orders = Order.objects.filter(portfolio=self, date__gte=start_date, date__lte=end_date)
        fin_ins.extend([ord.id_object for ord in subsequent_orders])
        all_fin_instr = list(set(fin_ins))

        # Load Time Series during the time frame
        prices = YahooFinanceQuery.get_prices_from_inventory(fin_objs = all_fin_instr, from_date = start_date, until_date = end_date)        
        prices.index = pd.to_datetime(prices.index)
        divs = YahooFinanceQuery.get_divs_from_inventory(fin_objs = all_fin_instr, from_date = start_date, until_date = end_date)
        divs.index = pd.to_datetime(divs.index)

        available_start_date = prices.index[0]
        available_end_date = prices.index[-1]

        rets = dict()

        for fin in all_fin_instr:
            # quantity did not vary during time frame
            price_ret_tf = prices.loc[available_end_date][fin.name] / prices.loc[available_start_date][fin.name] - 1
            div_ret_tf = sum(divs[fin.name]) / prices[fin.name][available_start_date]
            total_ret_tf = price_ret_tf + div_ret_tf
            
            rets[fin.name] = [price_ret_tf, div_ret_tf, total_ret_tf]

        return pd.DataFrame.from_dict(rets, orient="index", columns=["Price", "Dividends", "Total"])

class YahooFinanceQuery:

    @staticmethod
    def get_prices_from_inventory(fin_objs: list[FinancialObject], from_date: dt.date, until_date: dt.date) -> pd.DataFrame:
        """
        Queries the database for prices, and returns dataframe (objs x dates)
        """
        if not all(isinstance(x, FinancialObject) for x in fin_objs):
              raise TypeError(f"Not a list of Financial Objects:{type(fin_objs[0])}")
        
        def query_price_from_db(obj: FinancialObject, from_date: dt.date, until_date: dt.date) -> pd.DataFrame:
            """
            Query the database for prices of a single financial object
            """
            df = pd.DataFrame(list(
                FinancialData.objects.filter(id_object=obj.id, field="NAV", date__gte=from_date, date__lte=until_date)
                .values("date", "value")))
            
            if df.empty:
                  raise ValueError(f"No data for {obj.name} (ISIN is {obj.isin}) between "
                                   f"{from_date} and {until_date}.")
            
            if obj.id == 255 and from_date == dt.date(2022, 3, 4):
                ess = df
                a=1
            
            df = df.set_index("date").squeeze().rename(obj.name)
            return df

        # Query prices
        # dfs = [pd.DataFrame(list(
        #         FinancialData.objects.filter(id_object=obj.id, field="NAV", origin="Yahoo Finance", date__gte=from_date, date__lte=until_date)
        #         .values("date", "value"))) for obj in fin_objs]

        # Adjust dfs to series with date index and relevant column names 
        # dfs = [df.set_index("date").squeeze().rename(fin_objs[i].name) for i,df in enumerate(dfs)]

        # To dataframe with ordered index dates
        dfs = [query_price_from_db(obj, from_date, until_date) for obj in fin_objs]
        prices = dfs[0].to_frame() if len(dfs) == 1 else pd.concat(dfs, axis=1, sort=True)

        # For some reason, datetime index unordered (later dates before earlier dates)
        # => messes up return calculation
        prices.sort_index(inplace=True)

        return prices
    
    @staticmethod
    def get_divs_from_inventory(fin_objs: list[FinancialObject], from_date: str, until_date: str) -> pd.DataFrame:

        if not all(isinstance(x, FinancialObject) for x in fin_objs):
              raise TypeError(f"Not a list of Financial Objects:{type(fin_objs[0])}")
        
        # Query prices
        dfs = [pd.DataFrame(list(
                FinancialData.objects.filter(
                      id_object=obj.id, field=FinancialData.TimeSeriesField.Dividends, origin="Yahoo Finance", date__gte=from_date, date__lte=until_date)
                .values("date", "value"))) for obj in fin_objs]

        # ISSUE IS HERE => PUT 0 WHEN NO DIVIDEND WAS PROVIDED
        # Adjust dfs to series with date index and relevant column names 
        for i, df in enumerate(dfs):
            if not df.empty:
                df = df.set_index("date")
                df = pd.Series(data=df.squeeze(), index=df.index, name=fin_objs[i].name) if df.shape == (1,1) else\
                     df.squeeze().rename(fin_objs[i].name)
            else:
                df = pd.Series(name=fin_objs[i].name)

            dfs[i] = df
        
        # To dataframe with ordered index dates
        divs = dfs[0].to_frame() if len(dfs) == 1 else pd.concat(dfs, axis=1, sort=True)
        divs.fillna(0, inplace=True)

        return divs
        


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
        PROVIDER = "Provider"

    class Meta:
        ordering = ["-date"]

    id_object = models.ForeignKey(FinancialObject, on_delete=models.CASCADE)
    date = models.DateField()
    field = models.CharField(max_length=15, choices=TimeSeriesField.choices)
    value = models.FloatField(default=0)
    origin = models.CharField(max_length=20, choices = DataOrigin.choices)

    def __str__(self):
        return f"object: {self.id_object}, date: {self.date}, value: {self.value}"
    
    @staticmethod          
    def get_price_most_recent_date() -> dt.date:
        """
        Get the second most recent date from price dates, in case all values were not updated to the most recent one
        """
        return sorted(FinancialData.objects.values_list("date", flat=True).distinct(), reverse=True)[1]