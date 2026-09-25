import os
from functools import lru_cache

import dash
from dash import dcc, html, Input, Output
import requests
import plotly.graph_objs as go
from datetime import date
import pandas as pd


# =========================================================
# Initialize Dash App
# =========================================================

app = dash.Dash(__name__)

server = app.server


# =========================================================
# Twelve Data API Configuration
# =========================================================

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"


# =========================================================
# Layout
# =========================================================

app.layout = html.Div([

    html.H1(
        "Single/Multi-Stock Comparison Dashboard",
        style={
            'textAlign': 'center',
            'color': '#ffffff',
            'margin-bottom': '30px',
            'font-family': 'Arial'
        }
    ),

    html.Div([

        dcc.Input(
            id='stock-input',
            type='text',
            value='AAPL,MSFT',
            placeholder='Enter Stock Symbols separated by commas',
            style={
                'margin-right': '10px',
                'padding': '10px',
                'border-radius': '5px',
                'width': '300px',
                'border': '1px solid #696FC7',
                'backgroundColor': '#f0f0f0'
            }
        ),

        dcc.DatePickerRange(
            id='date-picker',
            start_date='2023-01-01',
            end_date=date.today().strftime("%Y-%m-%d"),
            style={
                'padding': '8px',
                'border': '1px solid #696FC7',
                'border-radius': '5px',
                'backgroundColor': '#f0f0f0'
            }
        )

    ],
    style={
        'textAlign': 'center',
        'margin-bottom': '20px'
    }),

    dcc.Graph(
        id='price-graph',
        style={
            'height': '400px',
            'margin': '20px'
        }
    ),

    dcc.Graph(
        id='volume-graph',
        style={
            'height': '400px',
            'margin': '20px'
        }
    )

],
style={
    'backgroundColor': '#1f1f1f',
    'color': 'white',
    'padding': '20px'
})


# =========================================================
# Get Stock Data from Twelve Data
# =========================================================

@lru_cache(maxsize=100)
def get_stock_data(symbol, start_date, end_date):

    if not TWELVE_DATA_API_KEY:

        print("ERROR: TWELVE_DATA_API_KEY is not configured.")

        return None

    try:

        params = {
            "symbol": symbol,
            "interval": "1day",
            "start_date": start_date,
            "end_date": end_date,
            "apikey": TWELVE_DATA_API_KEY
        }

        response = requests.get(
            TWELVE_DATA_URL,
            params=params,
            timeout=30
        )

        # Check HTTP status
        response.raise_for_status()

        result = response.json()

        # -------------------------------------------------
        # Check API error
        # -------------------------------------------------

        if "status" in result and result["status"] == "error":

            print(
                f"Twelve Data error for {symbol}: "
                f"{result.get('message', 'Unknown API error')}"
            )

            return None

        # -------------------------------------------------
        # Check for API message/error
        # -------------------------------------------------

        if "code" in result and "message" in result:

            print(
                f"Twelve Data error for {symbol}: "
                f"{result.get('message')}"
            )

            return None

        # -------------------------------------------------
        # Get values
        # -------------------------------------------------

        values = result.get("values")

        if not values:

            print(f"No data returned for {symbol}")

            return None

        # -------------------------------------------------
        # Convert JSON to DataFrame
        # -------------------------------------------------

        data = pd.DataFrame(values)

        # -------------------------------------------------
        # Rename columns
        # -------------------------------------------------

        data = data.rename(columns={
            "datetime": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        })

        # -------------------------------------------------
        # Convert data types
        # -------------------------------------------------

        data["Date"] = pd.to_datetime(
            data["Date"],
            errors="coerce"
        )

        data["Close"] = pd.to_numeric(
            data["Close"],
            errors="coerce"
        )

        data["Volume"] = pd.to_numeric(
            data["Volume"],
            errors="coerce"
        )

        # -------------------------------------------------
        # Remove invalid rows
        # -------------------------------------------------

        data = data.dropna(
            subset=[
                "Date",
                "Close"
            ]
        )

        # -------------------------------------------------
        # Sort oldest → newest
        # -------------------------------------------------

        data = data.sort_values(
            "Date"
        )

        data = data.reset_index(
            drop=True
        )

        if data.empty:

            print(
                f"No valid data available for {symbol}"
            )

            return None

        print(
            f"Fetched {symbol}: "
            f"{len(data)} rows"
        )

        return data

    except requests.exceptions.Timeout:

        print(
            f"Timeout while fetching {symbol}"
        )

        return None

    except requests.exceptions.RequestException as e:

        print(
            f"Network error while fetching {symbol}: {e}"
        )

        return None

    except Exception as e:

        print(
            f"Unexpected error while fetching {symbol}: {e}"
        )

        return None


# =========================================================
# Dash Callback
# =========================================================

@app.callback(
    [
        Output(
            'price-graph',
            'figure'
        ),

        Output(
            'volume-graph',
            'figure'
        )
    ],

    [
        Input(
            'stock-input',
            'value'
        ),

        Input(
            'date-picker',
            'start_date'
        ),

        Input(
            'date-picker',
            'end_date'
        )
    ]
)
def update_graph(
    stock_input,
    start_date,
    end_date
):

    # =====================================================
    # Create empty figures
    # =====================================================

    price_fig = go.Figure()

    volume_fig = go.Figure()

    colors = [
        "red",
        "green",
        "#3E1E68"
    ]

    valid_symbol_found = False

    # =====================================================
    # Check stock input
    # =====================================================

    if not stock_input:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            title="No symbols entered",
            template="plotly_dark",
            paper_bgcolor="#1f1f1f",
            plot_bgcolor="#1f1f1f",
            font=dict(
                color="white"
            )
        )

        return empty_fig, empty_fig

    # =====================================================
    # Convert input into symbols
    # =====================================================

    symbols = [
        s.strip().upper()
        for s in stock_input.split(",")
        if s.strip()
    ]

    # =====================================================
    # Make sure dates exist
    # =====================================================

    if not start_date:

        start_date = "2023-01-01"

    if not end_date:

        end_date = date.today().strftime(
            "%Y-%m-%d"
        )

    # =====================================================
    # Process every stock symbol
    # =====================================================

    for i, sym in enumerate(symbols):

        # -------------------------------------------------
        # Get data
        # -------------------------------------------------

        data = get_stock_data(
            sym,
            start_date,
            end_date
        )

        if data is None:

            print(
                f"No valid data for {sym}"
            )

            continue

        if data.empty:

            print(
                f"Empty data for {sym}"
            )

            continue

        try:

            # -------------------------------------------------
            # Ensure date range
            # -------------------------------------------------

            data["Date"] = pd.to_datetime(
                data["Date"]
            )

            data = data[
                (data["Date"] >= pd.to_datetime(start_date))
                &
                (data["Date"] <= pd.to_datetime(end_date))
            ]

            if data.empty:

                print(
                    f"No data for {sym} "
                    f"inside selected date range."
                )

                continue

            # -------------------------------------------------
            # Fill volume
            # -------------------------------------------------

            if "Volume" not in data.columns:

                data["Volume"] = 0

            data["Volume"] = pd.to_numeric(
                data["Volume"],
                errors="coerce"
            ).fillna(0)

            # -------------------------------------------------
            # Calculate 50-day SMA
            # -------------------------------------------------

            data["SMA50"] = (
                data["Close"]
                .rolling(
                    window=50,
                    min_periods=1
                )
                .mean()
            )

            # -------------------------------------------------
            # Select color
            # -------------------------------------------------

            color = colors[
                i % len(colors)
            ]

            valid_symbol_found = True

            # =================================================
            # PRICE GRAPH
            # =================================================

            price_fig.add_trace(
                go.Scatter(
                    x=data["Date"],

                    y=data["Close"],

                    mode="lines+markers",

                    name=f"{sym} Close",

                    line=dict(
                        color=color,
                        width=2
                    ),

                    hovertemplate=(
                        f"<b>Symbol:</b> {sym}<br>"
                        "<b>Date:</b> %{x|%Y-%m-%d}<br>"
                        "<b>Close Price:</b> %{y:.2f}"
                        "<extra></extra>"
                    )
                )
            )

            # =================================================
            # 50-DAY SMA
            # =================================================

            price_fig.add_trace(
                go.Scatter(
                    x=data["Date"],

                    y=data["SMA50"],

                    mode="lines",

                    line=dict(
                        color=color,
                        width=2,
                        dash="dash"
                    ),

                    name=f"{sym} 50-day SMA",

                    hovertemplate=(
                        f"<b>Symbol:</b> {sym}<br>"
                        "<b>Date:</b> %{x|%Y-%m-%d}<br>"
                        "<b>50-day SMA:</b> %{y:.2f}"
                        "<extra></extra>"
                    )
                )
            )

            # =================================================
            # VOLUME GRAPH
            # =================================================

            volume_fig.add_trace(
                go.Bar(
                    x=data["Date"],

                    y=data["Volume"],

                    marker_color=color,

                    name=f"{sym} Volume",

                    hovertemplate=(
                        f"<b>Symbol:</b> {sym}<br>"
                        "<b>Date:</b> %{x|%Y-%m-%d}<br>"
                        "<b>Volume:</b> %{y:,}"
                        "<extra></extra>"
                    )
                )
            )

        except Exception as e:

            print(
                f"Error processing {sym}: {e}"
            )

            continue

    # =====================================================
    # No valid data
    # =====================================================

    if not valid_symbol_found:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            title="No valid data for the entered symbols",

            template="plotly_dark",

            paper_bgcolor="#1f1f1f",

            plot_bgcolor="#1f1f1f",

            font=dict(
                color="white"
            )
        )

        return empty_fig, empty_fig

    # =====================================================
    # PRICE FIGURE LAYOUT
    # =====================================================

    price_fig.update_layout(

        title=(
            "Stock Price Comparison "
            "with 50-day SMA"
        ),

        xaxis_title="Date",

        yaxis_title="Price",

        template="plotly_dark",

        paper_bgcolor="#1f1f1f",

        plot_bgcolor="#1f1f1f",

        font=dict(
            color="white"
        ),

        hovermode="x unified"
    )

    # =====================================================
    # VOLUME FIGURE LAYOUT
    # =====================================================

    volume_fig.update_layout(

        title="Stock Volume Comparison",

        xaxis_title="Date",

        yaxis_title="Volume",

        barmode="group",

        template="plotly_dark",

        paper_bgcolor="#1f1f1f",

        plot_bgcolor="#1f1f1f",

        font=dict(
            color="white"
        ),

        hovermode="x unified"
    )

    return price_fig, volume_fig


# =========================================================
# Local Development
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
