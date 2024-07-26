from plotly.graph_objs import YAxis
import datetime as dt
from django.shortcuts import render
from .models import Portfolio, Order, FinancialObject
from django.db.models import Q
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json

def home(request):
	
	portfolios = Portfolio.objects.all()

	context = {
		'portfolios': portfolios,
	} 

	return render(request, "home.html", context)


def about(request):
	return render(request, "about.html", {})


def portfolio(request, pk):
	"""
	For a given portfolio, provides the inventory and cumulative amount invested 
	"""
	# Send back a string to dash template in the context
	context = {
		"dash_context": {"pk": {"title": pk}}
			   }
	return render(request, "portfolio.html", context)


def instrument_comparison(request):
	
    return render(request, "instrument_comparison.html", {})


def databases(request):
	return render(request, "databases.html", {})