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

    ], style={
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

], style={
    'backgroundColor': '#1f1f1f',
    'color': 'white',
    'padding': '20px'
})


# =========================================================
# Helper Function - Empty/Error Figure
# =========================================================

def create_message_figure(message):

    fig = go.Figure()

    fig.update_layout(
        title=message,
        template='plotly_dark',
        paper_bgcolor='#1f1f1f',
        plot_bgcolor='#1f1f1f',
        font=dict(color='white'),
        xaxis=dict(
            visible=False
        ),
        yaxis=dict(
            visible=False
        )
    )

    return fig


# =========================================================
# Get Stock Data from Twelve Data
# =========================================================

@lru_cache(maxsize=100)
def get_stock_data(symbol, start_date, end_date):

    # ---------------------------------------------------------
    # Check API key
    # ---------------------------------------------------------

    if not TWELVE_DATA_API_KEY:

        return None, "ERROR: TWELVE_DATA_API_KEY is missing in Render."


    try:

        # -----------------------------------------------------
        # API parameters
        # -----------------------------------------------------

        params = {
            "symbol": symbol,
            "interval": "1day",
            "start_date": start_date,
            "end_date": end_date,
            "apikey": TWELVE_DATA_API_KEY
        }


        # -----------------------------------------------------
        # Send request
        # -----------------------------------------------------

        response = requests.get(
            TWELVE_DATA_URL,
            params=params,
            timeout=30
        )


        # -----------------------------------------------------
        # Print useful debugging information in Render logs
        # -----------------------------------------------------

        print("---------------------------------------------")
        print("Twelve Data request for:", symbol)
        print("HTTP status:", response.status_code)
        print("Response:", response.text[:1000])
        print("---------------------------------------------")


        # -----------------------------------------------------
        # Convert response to JSON
        # -----------------------------------------------------

        try:

            result = response.json()

        except ValueError:

            return None, (
                f"Twelve Data returned invalid JSON "
                f"(HTTP {response.status_code})."
            )


        # -----------------------------------------------------
        # Handle HTTP/API errors
        # -----------------------------------------------------

        if response.status_code != 200:

            error_code = result.get(
                "code",
                response.status_code
            )

            error_message = result.get(
                "message",
                "Unknown API error"
            )

            return None, (
                f"Twelve Data Error {error_code}: "
                f"{error_message}"
            )


        # -----------------------------------------------------
        # Handle API status error
        # -----------------------------------------------------

        if result.get("status") == "error":

            error_code = result.get(
                "code",
                "Unknown"
            )

            error_message = result.get(
                "message",
                "Unknown API error"
            )

            return None, (
                f"Twelve Data Error {error_code}: "
                f"{error_message}"
            )


        # -----------------------------------------------------
        # Handle response containing code + message
        # -----------------------------------------------------

        if "code" in result and "message" in result:

            return None, (
                f"Twelve Data Error "
                f"{result.get('code')}: "
                f"{result.get('message')}"
            )


        # -----------------------------------------------------
        # Extract values
        # -----------------------------------------------------

        values = result.get("values")


        if not values:

            return None, (
                f"No historical data returned for {symbol} "
                f"between {start_date} and {end_date}."
            )


        # -----------------------------------------------------
        # Convert to DataFrame
        # -----------------------------------------------------

        data = pd.DataFrame(values)


        # -----------------------------------------------------
        # Rename columns
        # -----------------------------------------------------

        data = data.rename(columns={
            "datetime": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        })


        # -----------------------------------------------------
        # Convert Date
        # -----------------------------------------------------

        data["Date"] = pd.to_datetime(
            data["Date"],
            errors="coerce"
        )


        # -----------------------------------------------------
        # Convert Close
        # -----------------------------------------------------

        data["Close"] = pd.to_numeric(
            data["Close"],
            errors="coerce"
        )


        # -----------------------------------------------------
        # Convert Volume
        # -----------------------------------------------------

        if "Volume" in data.columns:

            data["Volume"] = pd.to_numeric(
                data["Volume"],
                errors="coerce"
            )

        else:

            data["Volume"] = 0


        # -----------------------------------------------------
        # Remove invalid rows
        # -----------------------------------------------------

        data = data.dropna(
            subset=[
                "Date",
                "Close"
            ]
        )


        # -----------------------------------------------------
        # Sort by Date
        # -----------------------------------------------------

        data = data.sort_values(
            "Date"
        )


        data = data.reset_index(
            drop=True
        )


        # -----------------------------------------------------
        # Check final data
        # -----------------------------------------------------

        if data.empty:

            return None, (
                f"No usable data returned for {symbol}."
            )


        print(
            f"SUCCESS: {symbol} -> "
            f"{len(data)} rows received."
        )


        return data, None


    # =========================================================
    # Request Timeout
    # =========================================================

    except requests.exceptions.Timeout:

        return None, (
            f"Request timed out while fetching {symbol}."
        )


    # =========================================================
    # Connection Error
    # =========================================================

    except requests.exceptions.ConnectionError:

        return None, (
            f"Could not connect to Twelve Data "
            f"while fetching {symbol}."
        )


    # =========================================================
    # Other Request Error
    # =========================================================

    except requests.exceptions.RequestException as e:

        return None, (
            f"Request error for {symbol}: {str(e)}"
        )


    # =========================================================
    # Any Other Error
    # =========================================================

    except Exception as e:

        return None, (
            f"Unexpected error for {symbol}: {str(e)}"
        )


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
    # Create Figures
    # =====================================================

    price_fig = go.Figure()

    volume_fig = go.Figure()


    # =====================================================
    # Colors
    # =====================================================

    colors = [
        "red",
        "green",
        "#3E1E68"
    ]


    # =====================================================
    # Check Stock Input
    # =====================================================

    if not stock_input:

        empty_fig = create_message_figure(
            "No symbols entered"
        )

        return empty_fig, empty_fig


    # =====================================================
    # Convert Input into Symbols
    # =====================================================

    symbols = [
        s.strip().upper()
        for s in stock_input.split(",")
        if s.strip()
    ]


    # =====================================================
    # Default Dates
    # =====================================================

    if not start_date:

        start_date = "2023-01-01"


    if not end_date:

        end_date = date.today().strftime(
            "%Y-%m-%d"
        )


    # =====================================================
    # Track Valid Data
    # =====================================================

    valid_symbol_found = False

    errors = []


    # =====================================================
    # Process Every Stock
    # =====================================================

    for i, sym in enumerate(symbols):

        # -------------------------------------------------
        # Get Data
        # -------------------------------------------------

        data, error_message = get_stock_data(
            sym,
            start_date,
            end_date
        )


        # -------------------------------------------------
        # Handle Error
        # -------------------------------------------------

        if data is None:

            print(
                f"{sym}: {error_message}"
            )

            errors.append(
                f"{sym}: {error_message}"
            )

            continue


        try:

            # -------------------------------------------------
            # Make sure Date is datetime
            # -------------------------------------------------

            data["Date"] = pd.to_datetime(
                data["Date"]
            )


            # -------------------------------------------------
            # Filter Date Range
            # -------------------------------------------------

            data = data[
                (data["Date"] >= pd.to_datetime(start_date))
                &
                (data["Date"] <= pd.to_datetime(end_date))
            ]


            # -------------------------------------------------
            # Check Data
            # -------------------------------------------------

            if data.empty:

                errors.append(
                    f"{sym}: No trading data "
                    f"for selected dates."
                )

                continue


            # -------------------------------------------------
            # Calculate 50-Day SMA
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
            # Select Color
            # -------------------------------------------------

            color = colors[
                i % len(colors)
            ]


            valid_symbol_found = True


            print(
                f"Processing {sym}: "
                f"{len(data)} rows"
            )


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

            errors.append(
                f"{sym}: Error processing data - {str(e)}"
            )

            print(
                f"{sym}: Error processing data - {str(e)}"
            )


    # =====================================================
    # No Valid Data
    # =====================================================

    if not valid_symbol_found:

        if errors:

            error_text = "<br>".join(errors)

        else:

            error_text = (
                "No valid data for the entered symbols."
            )


        price_error = create_message_figure(
            error_text
        )

        volume_error = create_message_figure(
            error_text
        )

        return price_error, volume_error


    # =====================================================
    # Price Figure Layout
    # =====================================================

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


    # =====================================================
    # Volume Figure Layout
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


    # =====================================================
    # Return Graphs
    # =====================================================

    return price_fig, volume_fig


# =========================================================
# Run Application
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
