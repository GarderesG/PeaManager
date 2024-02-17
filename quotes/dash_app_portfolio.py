import dash
from dash import dcc, html
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from django_plotly_dash import DjangoDash
from quotes.models import Portfolio

import datetime as dt
import pandas as pd


"""
ONGLET OVERVIEW
Datatable avec le détail des positions de jour:
    - nombre de stocks
    - prix actuel
    - pru
    - dividendes reçus
    - return depuis achat en se fondant sur pru.

Un chart sur le côté avec la déviation de chaque stock par rapport aux poids cibles.

ONGLET ORDERS
Datatable avec l'ensemble des ordres + form pour rentrer de nouveaux ordres

ONGLET PERFORMANCE ANALYSIS [Creuser sur la gestion de portefeuille]
    - depuis le début de l'année
    - depuis le début du portefeuille

AUTRE MENU (pas lié au portefeuille)
    - voir la décomposition du return entre dividende et perf marché
    - voir historique du dividende 

AUTRE MENU
    - réfléchir à une possibilité de portefeuille modèle Buy and Hold [Futur]
"""


app = DjangoDash('Portfolio', add_bootstrap_links=True)   # replaces dash.Dash

app.layout = html.Div(children=[
    # DB 
    dbc.Container([
        html.Div(id='pk', title='0'),
        html.H1("Portfolio characteristics", style={"color": "white"}),
        html.Hr(className="my-2", style={"color": "white"}),
        html.P(f"The following tabs provide various tools to dive in the portfolio details.",
         className="lead", style={"color": "white"}),
        html.Div(id='db-price-date', className="lead", style={"color": "white"}),
        
        dcc.Tabs([
            dcc.Tab(label="Constituents", children=[
                
                html.Div(children=[
                    dbc.RadioItems(
                        id="weight-mode", 
                        value="Static",
                        class_name="btn-group",
                        inputClassName="btn-check",
                        labelClassName="btn btn-outline-secondary",
                        labelCheckedClassName="active",
                        options=[
                                {"label": "Static", "value": "Static"},
                                {"label": "Dynamic", "value": "Dynamic"},
                            ],
                        inline=True),
                
                    dmc.DatePicker(
                            id="date-picker",
                            label="Date",
                            minDate=dt.date(2020, 8, 5),
                            value=dt.datetime.now().date(),
                            style={"width": 330, "right":0, "display": "inline-block", "float": "right"},
                        )
                    ],
                    style={"display": "flex", "align-items": "flex-end", "justify-content": "space-between"}
                ),
                
                dcc.Graph(id='chart-weights')
                ],

                className="nav-item"),

            # See all previous orders, and add one if needed. 
            dcc.Tab(label="Orders", className="nav-item"),

            dcc.Tab(label="Monthly performance", children=[
                dcc.Graph(id='chart-monthly')
                ]),

            dcc.Tab(label="Constituent analyses", children=[
                html.Div(children=[
                    #Buttons
                    html.Div([
                        dbc.Button(id='btn-horizon-1m', children="1m", color="secondary"),
                        dbc.Button(id='btn-horizon-3m', children="3m", color="secondary"),
                        dbc.Button(id='btn-horizon-6m', children="6m", color="secondary"),
                        dbc.Button(id='btn-horizon-ytd', children="YTD", color="secondary"),
                        dbc.Button(id='btn-horizon-1y', children="1Y", color="secondary"),
                        dbc.Button(id='btn-horizon-3y', children="3Y", color="secondary"),
                        dbc.Button(id='btn-horizon-max', children="Max", color="secondary"),
                    ], 
                    style={"float": "left"}
                    ),
                
                    # DateRange Picker
                    dmc.DateRangePicker(
                        id="date-range-picker",
                        label="Date Range",
                        minDate=dt.date(2020, 8, 5),
                        value=[dt.datetime.now().date(), dt.datetime.now().date() + dt.timedelta(days=5)],
                        style={"width": 330, "right":0, "display": "inline-block", "float": "right"},
                    )],
                    style={"display": "flex", "align-items": "flex-end", "justify-content": "space-between"} 
                ),
            dcc.Graph(id="constituents")
            ]),

        ]), 

        ],
        fluid=True),
    ],
    className="bg-dark")


@app.callback(
    dash.dependencies.Output('chart-weights', 'figure'),
    dash.dependencies.Output('db-price-date', 'title'),
    dash.dependencies.Output('constituents', 'figure'),
    dash.dependencies.Output('date-picker', 'value'),
    dash.dependencies.Input('pk', 'title'),
    dash.dependencies.Input('weight-mode', "value")
    )
def do_callback(id_portfolio, weight_mode):
    
    ptf = Portfolio.objects.get(id=id_portfolio)
    latest_date = ptf.get_price_most_recent_date()

    # Update Chart weights
    if weight_mode == "Static":
        weights = pd.DataFrame.from_dict(ptf.get_weights(), orient="index", columns=["weights"])
        weights.sort_values(by="weights", ascending=False, inplace=True)

        fig = go.Figure(
            data = px.bar(weights, orientation="h"),
        )
        fig.update_layout(
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
    elif weight_mode == "Dynamic":
        pass


    # Update string with price db date
    string_date = f"Last update of the database loaded prices until {latest_date}"
    
    # Update Constituents
    inventory = ptf.get_inventory(latest_date)
    rets = [stock.get_perf(start_date=dt.date(dt.datetime.utcnow().year, 1, 2), end_date=latest_date) for stock in inventory.keys()]
    names = [stock.name for stock in inventory.keys()]

    fig_cons = go.Figure(
        data = px.bar(x=rets, y=names, orientation="h"),
    )
    fig_cons.update_layout(
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

    return fig, string_date, fig_cons, dt.datetime(2022, 10, 12)

# @app.callback(
#     dash.dependencies.Output('constituents', 'figure'),
#     dash.dependencies.Input('date-range-picker', 'value')
#     )
# def update_perf_date_picker(dates_selected):
#     start, end = [dt.datetime.strptime(date, "%Y-%m-%d") for date in dates_selected]
#     pass
