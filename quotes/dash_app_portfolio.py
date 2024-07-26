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

from quotes.forms import OrderForm


"""
ONGLET OVERVIEW
Datatable avec le détail des positions de jour:
    - nombre de stocks
    - prix actuel
    - pru
    - dividendes reçus
    - return depuis achat en se fondant sur pru.

Un chart sur le côté avec la déviation de chaque stock par rapport aux poids cibles.

AUTRE MENU (pas lié au portefeuille)
    - voir la décomposition du return entre dividende et perf marché
    - voir historique du dividende 

AUTRE MENU
    - réfléchir à une possibilité de portefeuille modèle Buy and Hold [Futur]
"""

class Colors:
    dark = "#212529"
    card_dark = "#2d2d2d"

def order_tab_layout():

    portfolios = Portfolio.objects.all()
    financial_objects = FinancialObject.objects.all()

    # Create options for the select boxes
    portfolio_options = [{'label': str(p), 'value': p.id} for p in portfolios]
    financial_object_options = [{'label': str(o), 'value': o.id} for o in financial_objects]
    direction_options = [{'label': 'Buy', 'value': Order.OrderDirection.BUY}, {'label': 'Sell', 'value': Order.OrderDirection.SELL}]

    dropdown_style = {"background-color": Colors.card_dark, "color": "black"}
    input_style = {"background-color": Colors.card_dark, "color": "white"}

    return html.Div(children=[
        
        dbc.Row([
            dbc.Col(dbc.Label('Portfolio'), width=2),
            dbc.Col(dcc.Dropdown(id='portfolio', options=portfolio_options, style=dropdown_style), width=10)
        ]),

        dbc.Row([
            dbc.Col(dbc.Label('Financial Object'), width=2),
            dbc.Col(dcc.Dropdown(id='id_object', options=financial_object_options, style=dropdown_style), width=10)
        ]),

        dbc.Row([
            dbc.Col(dbc.Label('Date'), width=2),
            dbc.Col(dcc.Input(id='date', type='date', style=input_style), width=10)
        ]),

        dbc.Row([
            dbc.Col(dbc.Label('Direction'), width=2),
            dbc.Col(dcc.Dropdown(id='direction', options=direction_options, style=dropdown_style), width=10)
        ]),

        dbc.Row([
            dbc.Col(dbc.Label('Number of Items'), width=2),
            dbc.Col(dcc.Input(id='nb_items', type='number', style=input_style), width=10)
        ]),

        dbc.Row([
            dbc.Col(dbc.Label('Price'), width=2),
            dbc.Col(dcc.Input(id='price', type='number', style=input_style), width=10)
        ]),

        dbc.Row([
            dbc.Col(dbc.Label('Total Fee'), width=2),
            dbc.Col(dcc.Input(id='total_fee', type='number', style=input_style), width=10)
        ]),

        dbc.Row([
            dbc.Col(dbc.Button('Submit', id='submit-btn', color='primary', n_clicks=0))
        ]),
    ], style={'color': 'white'})

def get_order_history(id_portfolio):
    portfolio = Portfolio.objects.get(id=id_portfolio)
    orders = Order.objects.filter(portfolio=portfolio).order_by('-date')

    dt_columns = [
            {'name': 'Date', 'id': 'date'},
            {'name': 'Instrument Name', 'id': 'id_object'},
            {'name': 'Direction', 'id': 'direction'},
            {'name': 'Number of Items', 'id': 'nb_items'},
            {'name': 'Price', 'id': 'price'},
            {'name': 'Total Fee', 'id': 'total_fee'},
        ] 

    #display in a dash_table all orders in database associated with portfolio
    return dash_table.DataTable(
        id='order-table',
        columns=dt_columns,
        data=[
            {'date': o.date, 'id_object': o.id_object.name, 'direction': o.direction, 'nb_items': o.nb_items, 'price': o.price, 'total_fee': o.total_fee} 
            for o in orders
            ],
        style_as_list_view=True,
        style_cell={'backgroundColor': '#2d2d2d', 'color': 'white', "textAlign": "center", 'font-family': 'sans-serif', "lineHeight": "24px"},
        style_header={'fontWeight': 'bold', 'border': 'none'},
        filter_action='native',
        sort_action='native',
        page_size=10,
    )

def get_order_card_body(id_portfolio):
    """
    This function returns the table of previous orders, and a button to add a new one.
    """
    table = get_order_history(id_portfolio)
    button = dbc.Button("Add a new order", id="btn-add-order", color="primary")
    modal = dbc.Modal(
        [
            dbc.ModalHeader("Add a new order", style={"background-color": "#343a40", "color": "white"}),
            dbc.ModalBody(order_tab_layout(), style={"background-color": "#343a40", "color": "white"}),
            dbc.ModalFooter(
                dbc.Button("Close", id="btn-close-modal", className="ml-auto", n_clicks=0),
                style={"background-color": "#343a40", "color": "white"}
            ),
        ],
        id="modal",
        size="lg",
        is_open=False
    )
    return [table, button, modal]

def get_individual_returns(id_portfolio):

    date_range = dmc.Group(
        spacing="xl",
        children=[
            dmc.DatePicker(
                id="indiv-ret-start-date",
                label="Start Date",
                className="label-class text-white",

            ),
            dmc.DatePicker(
                id="indiv-ret-end-date",
                label="End Date",
                maxDate=dt.datetime.now().date()
            ),
        ], 
    )
    
    div_id = html.Div(title=f"{id_portfolio}", id="ptf", hidden=True)

    contrib_graph = dcc.Graph(id='contrib-graph', style={"display": "none"})

    return html.Div(children=[date_range, contrib_graph, div_id])

def performance_overview(id_portfolio):
    ptf = Portfolio.objects.get(id=id_portfolio)
    latest_date = FinancialData.get_price_most_recent_date()

    df = ptf.inventory_df()
    
    df["Amount Paid"] = df["PRU"] * df["Number"]

    prices = [FinancialData.objects
              .filter(id_object=id, field="NAV", origin="Yahoo Finance", date=latest_date)
              .values_list("value", flat=True).first() for id in df["Id"].tolist()]
    
    df["Current Value"] = np.multiply(df["Number"], np.array(prices))
    df.sort_values(by="Current Value", ascending=False, inplace=True)

    df["+/- Value"] = df["Current Value"] - df["Amount Paid"]
    
    df["Weight"] = df["Current Value"]/df["Current Value"].sum()
    df["Weight"] = df["Weight"].map('{:,.1%}'.format)
    
    # Formatting
    numeric_cols = ["PRU", "Amount Paid", "Current Value", "+/- Value"]
    df[numeric_cols] = df[numeric_cols].map('{:,.2f}'.format)
    del df["Id"]

    header_style = {"background-color": "#2d2d2d", "color": "white"}
    row_style = {"color": "white", "background-color": "#2d2d2d"}
    
    table_header = [
        html.Thead(html.Tr([html.Th(col, style=header_style) for col in df.columns]))
    ]
    
    rows = []
    for item in df.to_dict(orient="records"):
        rows.append(
            html.Tr([html.Td(item[col], style=row_style) for col in df.columns])
        )
    table_body = [html.Tbody(rows)]
    table = dbc.Table(table_header + table_body, 
                      hover=True, 
                      color="dark",
                      style={"text-align": "center", "border": "none"},
                      id="tb",
                      className="custom-table"
                     )
    
    return table

app = DjangoDash('Portfolio', 
                 add_bootstrap_links=True,
                 external_stylesheets=["/static/assets/cards.css", dbc.themes.BOOTSTRAP])   # replaces dash.Dash

app.layout = html.Div(children=[
    dbc.Container([
        html.Div(id='pk', title="na"),
        html.H1("Portfolio characteristics", style={"color": "white"}),
        html.Hr(className="my-2", style={"color": "white"}),
        html.P(f"The following tabs provide various tools to dive in the portfolio details.",
         className="lead", style={"color": "white"}),
        html.Div(id='db-price-date', className="lead", style={"color": "white"}),
        
        # Cards with performance and custom css for style
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Current Portfolio Value"), 
                    dbc.CardBody(id="card-ptf-value")
                ], class_name="card-darken"),
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("+/- Values"),
                    dbc.CardBody(id="card-ptf-pnl")
                ], class_name="card-darken"),
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Last Updated"),
                    dbc.CardBody(id="card-last-updated")
                ], class_name="card-darken"),
            ),
        ], id="row-card-override"),

        dbc.Card([
            dbc.CardHeader(
                dbc.Tabs([
                    dbc.Tab(label="Overview", tab_id="overview"),
                    dbc.Tab(label="Order History", tab_id="orders"),
                    dbc.Tab(label="Constituent Analysis", tab_id="constituent"),
                ], 
                id="tabs", 
                active_tab="overview", 
                style={"border": "none", "align-items": "center", "text-transform": "uppercase", "font-size": "14px",
                        "font-weight": "bold", "color": "darkgray"}
                ),
            ),
            dbc.CardBody(id="essai")
            ], 
            id="card-tabs", 
            style={"border-radius": "15px", "background-color": "#2d2d2d"}
        ),        
        ],
        fluid=True),
    ],
    className="bg-dark",
    style={"background": "#2d2d2d"})


## Callbacks
@app.callback(
    dash.dependencies.Output('essai', 'children'),
    dash.dependencies.Input('tabs', 'active_tab'),
    dash.dependencies.State('pk', 'title')
)
def display_tab_in_cardbody(active_tab, pk):
    """
    Display the content of the active tab in the card body.
    """
    print(active_tab)
    if active_tab == "overview":
        return performance_overview(pk)
    
    elif active_tab == "orders":
        return get_order_card_body(pk)
    
    elif active_tab == "constituent":
        return get_individual_returns(pk)

@app.callback(
    dash.dependencies.Output("modal", "is_open"),
    [dash.dependencies.Input("btn-add-order", "n_clicks"),
     dash.dependencies.Input("btn-close-modal", "n_clicks")],
    [dash.dependencies.State("modal", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    """
    Toggle modal with the button to add a new order.
    """
    if n1 or n2:
        return not is_open
    return is_open


@app.callback(
    dash.dependencies.Output('submit-btn', 'n_clicks'),
    [dash.dependencies.Input('portfolio', 'value'),
     dash.dependencies.Input('id_object', 'value'),
     dash.dependencies.Input('date', 'value'),
     dash.dependencies.Input('direction', 'value'),
     dash.dependencies.Input('nb_items', 'value'),
     dash.dependencies.Input('price', 'value'),
     dash.dependencies.Input('total_fee', 'value'),
     dash.dependencies.Input('submit-btn', 'n_clicks')]
)
def submit_form(portfolio_id, id_object_id, date, direction, nb_items, price, total_fee, n_clicks):
    """
    Callback to submit a new order in the Orders tab.
    """
    if n_clicks > 0:
        try:
            portfolio = Portfolio.objects.get(id=portfolio_id)
            id_object = FinancialObject.objects.get(id=id_object_id)
        except ObjectDoesNotExist:
            return 'Invalid portfolio or financial object ID'

        form = OrderForm({
            'portfolio': portfolio,
            'id_object': id_object,
            'date': date,
            'direction': direction,
            'nb_items': nb_items,
            'price': price,
            'total_fee': total_fee,
        })
        if form.is_valid():
            form.save()

@app.callback(
    dash.dependencies.Output('contrib-graph', 'figure'),
    dash.dependencies.Output('contrib-graph', 'style'),
    dash.dependencies.Input('indiv-ret-start-date', 'value'),
    dash.dependencies.Input('indiv-ret-end-date', 'value'),
    dash.dependencies.State('ptf', 'title')
)
def update_graph(start_date, end_date, id_portfolio):
    if start_date and end_date:
        ptf = Portfolio.objects.get(id=id_portfolio)
        contributions = ptf.get_individual_returns(start_date, end_date)

        # Create a figure from the contributions
        figure = go.Figure(
            data=[go.Bar(x=contributions["Total"], y=contributions.index, orientation="h")]
            )

        figure.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font={"color": "white", "size": 14},
            xaxis={
                "title": "weights",
                "categoryorder": "category ascending",
                "tickformat": ".0%", 
                "hoverformat": ".1%",
            },
            
            yaxis={
                "title": "Instrument",
            },

            showlegend=False
            )
        
        return figure, {"display": "block"}
    return go.Figure(data=[]), {"display": "none"}


@app.callback(
    dash.dependencies.Output('card-ptf-value', 'children'),
    dash.dependencies.Output('card-ptf-pnl', 'children'),
    dash.dependencies.Output('card-last-updated', 'children'),
    dash.dependencies.Input('pk', 'title'),
)
def update_cards(id_portfolio: int):
    """
    Callback to update the 3 cards with the portfolio value, pnl and last updated date at the
    top of the page.
    """
    ptf = Portfolio.objects.get(id=id_portfolio)
    latest_date = FinancialData.get_price_most_recent_date()
    inventory = ptf.get_inventory(latest_date)

    if ptf.ts_val is None:
        ptf.get_TS()

    # Portfolio Value
    ptf_value = ptf.ts_val[latest_date]
    
    # Portfolio PnL
    pnl = ptf_value - np.dot(inventory.nbs, inventory.prus) 

    return f"{ptf_value:,.2f}€", f"{pnl:,.2f}€", latest_date

