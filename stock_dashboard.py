import os
from functools import lru_cache
from datetime import date

import dash
from dash import dcc, html, Input, Output
import requests
import pandas as pd
import plotly.graph_objs as go


# =========================================================
# ALPHA VANTAGE API
# =========================================================

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


# =========================================================
# APP
# =========================================================

app = dash.Dash(__name__)

app.title = "Single/Multi-Stock Comparison Dashboard"

app.layout = html.Div(
    style={
        "backgroundColor": "#1f1f1f",
        "minHeight": "100vh",
        "padding": "20px",
        "color": "white"
    },
    children=[

        html.H1(
            "Single/Multi-Stock Comparison Dashboard",
            style={"textAlign": "center"}
        ),

        html.Div(
            [
                dcc.Input(
                    id="stock-input",
                    type="text",
                    value="AAPL,MSFT",
                    placeholder="Enter stock symbols, e.g. AAPL,MSFT",
                    debounce=True,
                    style={
                        "width": "300px",
                        "padding": "10px",
                        "marginRight": "10px"
                    }
                ),

                dcc.DatePickerRange(
                    id="date-picker",
                    start_date="2023-01-01",
                    end_date=date.today(),
                    display_format="DD/MM/YYYY",
                    style={"marginRight": "10px"}
                ),
            ],
            style={
                "textAlign": "center",
                "marginBottom": "20px"
            }
        ),

        dcc.Graph(id="price-graph"),

        dcc.Graph(id="volume-graph")
    ]
)


# =========================================================
# GET STOCK DATA FROM ALPHA VANTAGE
# =========================================================

@lru_cache(maxsize=50)
def get_stock_data(symbol):

    if not ALPHA_VANTAGE_API_KEY:
        return None, "ALPHA_VANTAGE_API_KEY is not configured."

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": ALPHA_VANTAGE_API_KEY
    }

    try:

        response = requests.get(
            ALPHA_VANTAGE_URL,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        # ---------------------------------------------
        # API ERROR
        # ---------------------------------------------

        if "Error Message" in data:
            return None, data["Error Message"]

        if "Note" in data:
            return None, data["Note"]

        if "Information" in data:
            return None, data["Information"]

        # ---------------------------------------------
        # FIND TIME SERIES
        # ---------------------------------------------

        time_series = data.get("Time Series (Daily)")

        if not time_series:
            return None, "No daily stock data returned by Alpha Vantage."

        # ---------------------------------------------
        # CONVERT TO DATAFRAME
        # ---------------------------------------------

        df = pd.DataFrame.from_dict(
            time_series,
            orient="index"
        )

        df.index = pd.to_datetime(df.index)

        df = df.rename(
            columns={
                "1. open": "Open",
                "2. high": "High",
                "3. low": "Low",
                "4. close": "Close",
                "5. volume": "Volume"
            }
        )

        df = df.apply(pd.to_numeric)

        df = df.sort_index()

        return df, None

    except requests.exceptions.RequestException as e:

        return None, f"Network error: {str(e)}"

    except Exception as e:

        return None, f"Error processing {symbol}: {str(e)}"


# =========================================================
# CALLBACK
# =========================================================

@app.callback(
    [
        Output("price-graph", "figure"),
        Output("volume-graph", "figure")
    ],
    [
        Input("stock-input", "value"),
        Input("date-picker", "start_date"),
        Input("date-picker", "end_date")
    ]
)
def update_graphs(stock_input, start_date, end_date):

    # ---------------------------------------------
    # EMPTY INPUT
    # ---------------------------------------------

    if not stock_input:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            template="plotly_dark",
            title="Please enter a stock symbol"
        )

        return empty_fig, empty_fig

    # ---------------------------------------------
    # STOCK SYMBOLS
    # ---------------------------------------------

    symbols = [
        symbol.strip().upper()
        for symbol in stock_input.split(",")
        if symbol.strip()
    ]

    price_fig = go.Figure()
    volume_fig = go.Figure()

    errors = []

    # ---------------------------------------------
    # PROCESS EACH STOCK
    # ---------------------------------------------

    for symbol in symbols:

        df, error = get_stock_data(symbol)

        if error:

            errors.append(f"{symbol}: {error}")
            continue

        if df is None or df.empty:

            errors.append(f"{symbol}: No data available.")
            continue

        # -----------------------------------------
        # DATE FILTER
        # -----------------------------------------

        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        df = df[
            (df.index >= start) &
            (df.index <= end)
        ].copy()

        if df.empty:

            errors.append(
                f"{symbol}: No data available for the selected dates. "
                "The free Alpha Vantage plan currently provides the latest "
                "100 daily records."
            )

            continue

        # -----------------------------------------
        # 50-DAY SMA
        # -----------------------------------------

        df["SMA_50"] = df["Close"].rolling(
            window=50
        ).mean()

        # -----------------------------------------
        # PRICE GRAPH
        # -----------------------------------------

        price_fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"],
                mode="lines",
                name=f"{symbol} Close"
            )
        )

        price_fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_50"],
                mode="lines",
                name=f"{symbol} 50-day SMA"
            )
        )

        # -----------------------------------------
        # VOLUME GRAPH
        # -----------------------------------------

        volume_fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name=symbol
            )
        )

    # =================================================
    # PRICE FIGURE
    # =================================================

    price_fig.update_layout(
        template="plotly_dark",
        title="Stock Price Comparison with 50-day SMA",
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode="x unified"
    )

    # =================================================
    # VOLUME FIGURE
    # =================================================

    volume_fig.update_layout(
        template="plotly_dark",
        title="Stock Volume Comparison",
        xaxis_title="Date",
        yaxis_title="Volume",
        hovermode="x unified"
    )

    # =================================================
    # SHOW ERRORS
    # =================================================

    if errors:

        error_text = " | ".join(errors)

        price_fig.update_layout(
            title=f"Stock Price Comparison with 50-day SMA — {error_text}"
        )

        volume_fig.update_layout(
            title=f"Stock Volume Comparison — {error_text}"
        )

    return price_fig, volume_fig


# =========================================================
# GUNICORN SERVER
# =========================================================

server = app.server


# =========================================================
# LOCAL RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
