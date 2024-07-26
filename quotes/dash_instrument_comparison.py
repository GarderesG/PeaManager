import datetime as dt
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, dash_table
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from django.core.exceptions import ObjectDoesNotExist
from django_plotly_dash import DjangoDash
from quotes.models import Portfolio, FinancialData, FinancialObject, Order


app = DjangoDash('Comparisons', 
                 add_bootstrap_links=True,
                 external_stylesheets=["/static/assets/cards.css", dbc.themes.BOOTSTRAP])   # replaces dash.Dash

app.layout = html.Div([
    "Hello World!"])