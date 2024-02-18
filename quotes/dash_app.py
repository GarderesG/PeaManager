import dash
from dash import dcc, html
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from django_plotly_dash import DjangoDash
from quotes.models import Portfolio, FinancialData

import datetime as dt
import pandas as pd


## import data (to be fixed with internal Django mechanics)
portfolios = Portfolio.objects.all()

for ptf in portfolios:
    if ptf.ts_ret is None:
        ptf.get_TS()

user_colors = {
    "Guillaume": "darkorange",
    "Marie": "darkgreen",
    "Maman": "darkred"
}

portfolio = portfolios[0]
stocks = portfolio.get_inventory().id_objects
latest_date = min([FinancialData.objects.filter(id_object=stock).latest("date").date for stock in stocks])

# TO DO:
# 4. Graph should take more space on the window
# 5. Fill table with performance
# 6. A few benchmarks should be available for charting: MSCI France, CAC40, DAX, SP500, Nasdaq100, MSCI World, MSCI China
# 7. Background color could change between chart and table (cf. https://github.com/alfonsrv/crypto-tracker)

app = DjangoDash('Dashboard', 
                 #add_bootstrap_links=True,
                 external_stylesheets=["static/assets/buttons.css"]
                 )   # replaces dash.Dash

app.layout = html.Div(children=[
    # DB 
    dbc.Container([
        html.P(f"Most recent nav from Yahoo Finance is {latest_date.strftime('%d/%m/%Y')}", className="lead", style={"color": "white"}),

        html.Div([
            # Price / Return mode
            dbc.RadioItems(
                id="radio-chart-mode", 
                className="btn-group",
                inputClassName="btn-check",
                labelClassName="btn btn-outline-secondary",
                labelCheckedClassName="active",
                options=[
                        {"label": "Prices", "value": "Prices"},
                        {"label": "Returns", "value": "Returns"},
                    ],
                value="Returns",
            )], className="radio-group"),

            # Dates button (left) + DateRangePicker (right)
            html.Div([
                # Buttons for dates
                html.Div([
                    dbc.Button(id='btn-horizon-1m', children="1m", color="secondary"),
                    dbc.Button(id='btn-horizon-3m', children="3m", color="secondary"),
                    dbc.Button(id='btn-horizon-6m', children="6m", color="secondary"),
                    dbc.Button(id='btn-horizon-ytd', children="YTD", color="secondary"),
                    dbc.Button(id='btn-horizon-1y', children="1Y", color="secondary"),
                    dbc.Button(id='btn-horizon-3y', children="3Y", color="secondary"),
                    dbc.Button(id='btn-horizon-max', children="Max", color="secondary"),
                ], style={"float": "left"}),

                # DateRangePicker
                html.Div([
                    dmc.DateRangePicker(
                        id="date-range-picker",
                        minDate=dt.date(2020, 8, 5),
                        value=[dt.datetime.now().date(), dt.datetime.now().date() + dt.timedelta(days=5)],
                        style={"width": 300, "right":0, "display": "inline-block"},
                        styles={"color": 'white'}
                    ),
                ], style={"float": "right"}),
                ], 
                style={
                    "display": "flex",
                    "align-items": "flex-start",
                    "justify-content": "space-between"
                }
            ),

        # The Time Series chart
        dcc.Graph(id='graph-ts'),
    ], fluid=True)
    ], className="bg-dark")

##### CALLBACKS
# Price/Return callback
@app.callback(
    dash.dependencies.Output('graph-ts', 'figure'),
    dash.dependencies.Input('radio-chart-mode', 'value'),
    dash.dependencies.Input('btn-horizon-1m', 'n_clicks'),
    dash.dependencies.Input('btn-horizon-3m', 'n_clicks'),
    dash.dependencies.Input('btn-horizon-6m', 'n_clicks'),
    dash.dependencies.Input('btn-horizon-ytd', 'n_clicks'),
    dash.dependencies.Input('btn-horizon-1y', 'n_clicks'),
    dash.dependencies.Input('btn-horizon-3y', 'n_clicks'),
    dash.dependencies.Input('btn-horizon-max', 'n_clicks'),
    dash.dependencies.Input('date-range-picker', 'value')
)
def update_the_graph(chart_mode: str, btn_1m, btn_3m, btn_6m, btn_ytd, btn_1y, btn_3y, btn_max, date_range, callback_context):
    last_modif = None

    # Find the last item changed (either new time or new radio item)
    if len(callback_context.triggered):
        last_modif = callback_context.triggered[0]["prop_id"].split(".")[0]

    if last_modif in [None, "radio-chart-mode"]:
        # First callback or only Prices/returns modif: return right series on max time
        time_frame = 'max'

    elif last_modif == "date-range-picker":
        time_frame = "custom"
    
    else:
        # Change was on time frame
        # Find requested time frame
        time_frame = last_modif.split("-")[-1]

    chart = get_traces(portfolios=portfolios,
                       series_mode=chart_mode,
                       time_frame=time_frame,
                       custom_dates=date_range)

    return chart
         
def timeframe_to_limit_date(time_frame: str) -> dt.date:
    match time_frame:
        case "1m" | "3m" | "6m":
            nb_months = time_frame[0]
            start_datetime = dt.datetime.utcnow() - pd.tseries.offsets.DateOffset(months=int(nb_months))
            return start_datetime.date()

        case "ytd":
            return dt.datetime(dt.datetime.utcnow().year, 1, 1).date()

        case "1y" | "3y":
            nb_years = time_frame[0]
            start_datetime = dt.datetime.utcnow() - pd.tseries.offsets.DateOffset(years=int(nb_years)) 
            return start_datetime.date()

        case "max":
            return dt.date(2000, 1, 1)

def get_traces(portfolios: list[Portfolio], series_mode: str, time_frame: str, custom_dates: list[dt.datetime]) -> go.Figure:
    
    if not series_mode in ["Prices", "Returns"]:
        raise Exception("Series_mode parameter is not right: either prices or returns.")
    
    ts_mode = "ts_val" if series_mode == "Prices" else "ts_cumul_ret"

    # Get relevant series on the adequate time frame
    if time_frame == "custom":
        start, end = [dt.datetime.strptime(date, "%Y-%m-%d") for date in custom_dates]
        l_ts = [
            getattr(ptf, ts_mode)[(start.date() <= getattr(ptf, ts_mode).index) & (getattr(ptf, ts_mode).index <= end.date())]
            for ptf in portfolios]
    
    else:
        limit_date = timeframe_to_limit_date(time_frame)
        l_ts = [
            getattr(ptf, ts_mode)[getattr(ptf, ts_mode).index >= limit_date]
            for ptf in portfolios]

    l_traces = []

    for i, ts in enumerate(l_ts):
        chart = go.Scatter(
            x=list(ts.index),
            y=list((ts/ts.iloc[0]).values -1),
            name=portfolios[i].owner.name,
            line = {"color": user_colors[portfolios[i].owner.name], "width": 4}
        )
        l_traces.append(chart)
        
    fig = go.Figure(data=l_traces)
    
    # Customize the charting options
    if series_mode == "Returns":
        fig.update_layout(yaxis={
                            "side": "right", 
                            "tickformat": ".0%", 
                            "hoverformat": ".2%", 
                            "gridwidth": 1, 
                            "zerolinecolor": "lightgray", 
                            "tickfont": {"color": "white", "size": 14}
                            },
                        xaxis={
                            "dtick": "M1",
                            "tickformat": "%b\n%Y",
                            "hoverformat": "%d/%m/%Y",
                            "ticklabelmode": "period",
                            "showgrid": False, 
                            "tickfont": {"color": "white"},
                            "rangeslider": {"visible": True, "bgcolor": "darkgray"}
                            },
                        legend={
                            "orientation": "h",
                            "yanchor": "bottom",
                            "y": 1.02, 
                            "xanchor": "right", 
                            "x":1, 
                            "font": {"size": 18, "color": "white"}
                            }
                        )
        
    elif series_mode == "Prices":
        fig.update_layout(yaxis={
                            "side": "right", 
                            "tickformat": ",.0f", 
                            "hoverformat": ",.0f", 
                            "gridwidth": 1, 
                            "zerolinecolor": "lightgray", 
                            "tickfont": {"color": "white", "size": 14}
                            },
                        xaxis={
                            "dtick": "M1",
                            "tickformat": "%b\n%Y",
                            "hoverformat": "%d/%m/%Y",
                            "ticklabelmode": "period",
                            "showgrid": False, 
                            "tickfont": {"color": "white"},
                            "rangeslider": {"visible": True, "bgcolor": "darkgray"}
                            },
                        legend={
                            "orientation": "h",
                            "yanchor": "bottom",
                            "y": 1.02, 
                            "xanchor": "right", 
                            "x":1, 
                            "font": {"size": 18, "color": "white"}
                            }
                        )

    
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)')

    return fig


@app.callback(
    dash.dependencies.Output('date-range-picker', 'value'),
    dash.dependencies.Input('graph-ts', 'figure'),
    prevent_initial_call=True
)
def update_date_range_picker(fig: go.Figure):
    """
    Whenever the figure changes (i.e. whenever a button is pressed), adjust the values
    in the date picker.
    """
    min_dates = [fig["data"][i]["x"][0] for i in range(0, len(fig["data"]))]
    min_dates = [dt.datetime.strptime(date, "%Y-%m-%d") for date in min_dates]

    max_dates = [fig["data"][i]["x"][-1] for i in range(0, len(fig["data"]))]
    max_dates = [dt.datetime.strptime(date, "%Y-%m-%d") for date in max_dates]

    return (min(min_dates).date(), max(max_dates).date())