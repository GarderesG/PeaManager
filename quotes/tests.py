import pytest
from .models import AccountOwner, Order, Portfolio, PortfolioEntry, FinancialObject

# Testing inventory
class TestPortfolioEntry:

    @pytest.fixture()
    def input_account_owner(self):
        return AccountOwner(name="Testing Account Owner")

    @pytest.fixture()
    def input_portfolio(self, input_account_owner):
        return Portfolio(owner=input_account_owner, name="Portfolio Test")
    
    @pytest.fixture()
    def lvmh_object(self):
        return FinancialObject(id=1,
                               name="LVMH", 
                               category=FinancialObject.ObjectType.STOCK,
                               isin="FR",
                               ticker="MC.PA")

    @pytest.fixture()
    def input_order_lvmh_buy(self, input_portfolio, lvmh_object):
        return Order(date="2023-05-12",
                     portfolio=input_portfolio,
                     id_object=lvmh_object,
                     direction=Order.OrderDirection.BUY,
                     nb_items=2,
                     price=500,
                     total_fee=1
                     )
    
    @pytest.fixture()
    def input_order_lvmh_sell(self, input_portfolio, lvmh_object):
        return Order(date="2023-05-16",
                     portfolio=input_portfolio,
                     id_object=lvmh_object,
                     direction=Order.OrderDirection.SELL,
                     nb_items=2,
                     price=550,
                     total_fee=1.5
                     )

    def test_order_constructor(self, input_order_lvmh_buy, lvmh_object):
        ptflio_entry = PortfolioEntry.from_order(input_order_lvmh_buy)
        assert ptflio_entry.id_obj == lvmh_object, "id_obj is not right."
        assert ptflio_entry.nb == 2, "Stock number is not right."
        assert ptflio_entry.pru == 500.5, "PRU is not right."

    def test_order_constructor_2_orders(self, input_order_lvmh_buy, input_order_lvmh_sell, lvmh_object):
        ptflio_entry = PortfolioEntry.from_order(input_order_lvmh_buy)
        ptflio_entry.update(input_order_lvmh_sell)
        assert ptflio_entry.id_obj == lvmh_object, "id_obj is not right."
        assert ptflio_entry.nb == 0, "Stock number is not right."
        assert ptflio_entry.pru == 0, "PRU is not right."
