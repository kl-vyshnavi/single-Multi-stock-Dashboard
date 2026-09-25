import os
import requests
import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
from datetime import date
import pandas as pd


# ---------------------------------------------------------
# Initialize app
# ---------------------------------------------------------
app = dash.Dash(__name__)
server = app.server


# ---------------------------------------------------------
# Alpha Vantage API configuration
# ---------------------------------------------------------
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


# ---------------------------------------------------------
# Layout
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Function to get stock data from Alpha Vantage
# ---------------------------------------------------------
def get_stock_data(symbol):

    if not ALPHA_VANTAGE_API_KEY:
        print("ALPHA_VANTAGE_API_KEY is not configured.")
        return None

    try:

        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": ALPHA_VANTAGE_API_KEY
        }

        response = requests.get(
            ALPHA_VANTAGE_URL,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        result = response.json()

        # Check for API error
        if "Error Message" in result:
            print(f"Invalid symbol: {symbol}")
            return None

        # Check for API information/rate-limit message
        if "Information" in result:
            print(result["Information"])
            return None

        time_series = result.get("Time Series (Daily)")

        if not time_series:
            print(f"No data returned for {symbol}")
            return None

        # Convert JSON to DataFrame
        data = pd.DataFrame.from_dict(
            time_series,
            orient='index'
        )

        # Rename columns
        data = data.rename(columns={
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. volume": "Volume"
        })

        # Convert index to Date
        data.index = pd.to_datetime(data.index)

        data = data.reset_index()
        data = data.rename(columns={"index": "Date"})

        # Convert numeric columns
        data["Close"] = pd.to_numeric(
            data["Close"],
            errors="coerce"
        )

        data["Volume"] = pd.to_numeric(
            data["Volume"],
            errors="coerce"
        )

        # Sort by date
        data = data.sort_values("Date")

        # Remove missing values
        data = data.dropna(
            subset=["Close", "Volume"]
        )

        return data

    except Exception as e:

        print(f"Error fetching {symbol}: {e}")

        return None


# ---------------------------------------------------------
# Callback
# ---------------------------------------------------------
@app.callback(
    [
        Output('price-graph', 'figure'),
        Output('volume-graph', 'figure')
    ],

    [
        Input('stock-input', 'value'),
        Input('date-picker', 'start_date'),
        Input('date-picker', 'end_date')
    ]
)
def update_graph(stock_input, start_date, end_date):

    price_fig = go.Figure()
    volume_fig = go.Figure()

    colors = [
        "red",
        "green",
        "#3E1E68"
    ]

    valid_symbol_found = False

    # -----------------------------------------------------
    # Check stock input
    # -----------------------------------------------------
    if not stock_input:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            title="No symbols entered",
            template="plotly_dark",
            paper_bgcolor="#1f1f1f",
            plot_bgcolor="#1f1f1f",
            font=dict(color="white")
        )

        return empty_fig, empty_fig

    # Convert input to symbols
    symbols = [
        s.strip().upper()
        for s in stock_input.split(",")
        if s.strip()
    ]

    # -----------------------------------------------------
    # Process each stock
    # -----------------------------------------------------
    for i, sym in enumerate(symbols):

        data = get_stock_data(sym)

        if data is None or data.empty:
            print(f"No valid data for {sym}")
            continue

        try:

            # -------------------------------------------------
            # Filter according to selected date range
            # -------------------------------------------------
            data["Date"] = pd.to_datetime(data["Date"])

            if start_date:
                data = data[
                    data["Date"] >= pd.to_datetime(start_date)
                ]

            if end_date:
                data = data[
                    data["Date"] <= pd.to_datetime(end_date)
                ]

            if data.empty:
                print(
                    f"No data available for {sym} "
                    f"within selected date range."
                )
                continue

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

            color = colors[i % len(colors)]

            valid_symbol_found = True

            print(
                f"Fetched {sym}: "
                f"{len(data)} rows"
            )

            # -------------------------------------------------
            # Price line
            # -------------------------------------------------
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

            # -------------------------------------------------
            # SMA line
            # -------------------------------------------------
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

            # -------------------------------------------------
            # Volume bars
            # -------------------------------------------------
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

    # ---------------------------------------------------------
    # No valid stock
    # ---------------------------------------------------------
    if not valid_symbol_found:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            title="No valid data for the entered symbols",
            template="plotly_dark",
            paper_bgcolor="#1f1f1f",
            plot_bgcolor="#1f1f1f",
            font=dict(color="white")
        )

        return empty_fig, empty_fig

    # ---------------------------------------------------------
    # Price figure layout
    # ---------------------------------------------------------
    price_fig.update_layout(

        title="Stock Price Comparison with 50-day SMA",

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

    # ---------------------------------------------------------
    # Volume figure layout
    # ---------------------------------------------------------
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
