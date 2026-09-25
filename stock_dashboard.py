import dash
from dash import dcc, html, Input, Output
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd
from datetime import date
from functools import lru_cache


# =========================================================
# DASH APP
# =========================================================

app = dash.Dash(__name__)

app.title = "Single/Multi-Stock Comparison Dashboard"


# =========================================================
# LAYOUT
# =========================================================

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
            style={
                "textAlign": "center"
            }
        ),

        html.Div(
            [

                # Stock input
                dcc.Input(
                    id="stock-input",
                    type="text",
                    value="AAPL,MSFT",
                    placeholder="Enter stock symbols",
                    debounce=True,
                    style={
                        "width": "300px",
                        "padding": "10px",
                        "marginRight": "10px"
                    }
                ),

                # Date picker
                dcc.DatePickerRange(
                    id="date-picker",
                    start_date="2023-01-01",
                    end_date=date.today(),
                    display_format="DD/MM/YYYY"
                )

            ],
            style={
                "textAlign": "center",
                "marginBottom": "20px"
            }
        ),

        # Price graph
        dcc.Graph(
            id="price-graph"
        ),

        # Volume graph
        dcc.Graph(
            id="volume-graph"
        )
    ]
)


# =========================================================
# DOWNLOAD STOCK DATA
# =========================================================

@lru_cache(maxsize=50)
def get_stock_data(symbol, start_date, end_date):

    try:

        data = yf.download(
            symbol,
            start=start_date,
            end=end_date,
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if data.empty:
            return None, f"No data found for {symbol}"

        # -------------------------------------------------
        # Handle yfinance MultiIndex columns
        # -------------------------------------------------

        if isinstance(data.columns, pd.MultiIndex):

            try:
                data = data.xs(
                    symbol,
                    axis=1,
                    level=1
                )
            except Exception:

                data.columns = data.columns.get_level_values(0)

        # -------------------------------------------------
        # Make sure required columns exist
        # -------------------------------------------------

        required_columns = [
            "Close",
            "Volume"
        ]

        for column in required_columns:

            if column not in data.columns:
                return None, f"{column} data unavailable for {symbol}"

        return data, None

    except Exception as e:

        return None, f"Error downloading {symbol}: {str(e)}"


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

    # =====================================================
    # EMPTY INPUT
    # =====================================================

    if not stock_input:

        empty_price = go.Figure()

        empty_price.update_layout(
            template="plotly_dark",
            title="Please enter a stock symbol"
        )

        empty_volume = go.Figure()

        empty_volume.update_layout(
            template="plotly_dark",
            title="Please enter a stock symbol"
        )

        return empty_price, empty_volume


    # =====================================================
    # PROCESS STOCK SYMBOLS
    # =====================================================

    symbols = [
        symbol.strip().upper()
        for symbol in stock_input.split(",")
        if symbol.strip()
    ]


    # =====================================================
    # CREATE FIGURES
    # =====================================================

    price_fig = go.Figure()

    volume_fig = go.Figure()

    errors = []


    # =====================================================
    # DOWNLOAD EACH STOCK
    # =====================================================

    for symbol in symbols:

        data, error = get_stock_data(
            symbol,
            start_date,
            end_date
        )

        # -------------------------------------------------
        # Error handling
        # -------------------------------------------------

        if error:

            errors.append(
                f"{symbol}: {error}"
            )

            continue


        # =================================================
        # CLOSE PRICE
        # =================================================

        close = data["Close"]

        # Convert Series safely
        if isinstance(close, pd.DataFrame):

            close = close.iloc[:, 0]

        close = pd.to_numeric(
            close,
            errors="coerce"
        )


        # =================================================
        # VOLUME
        # =================================================

        volume = data["Volume"]

        if isinstance(volume, pd.DataFrame):

            volume = volume.iloc[:, 0]

        volume = pd.to_numeric(
            volume,
            errors="coerce"
        )


        # =================================================
        # 50-DAY SMA
        # =================================================

        sma_50 = close.rolling(
            window=50
        ).mean()


        # =================================================
        # PRICE GRAPH
        # =================================================

        price_fig.add_trace(
            go.Scatter(
                x=data.index,
                y=close,
                mode="lines",
                name=f"{symbol} Close"
            )
        )


        # =================================================
        # SMA GRAPH
        # =================================================

        price_fig.add_trace(
            go.Scatter(
                x=data.index,
                y=sma_50,
                mode="lines",
                name=f"{symbol} 50-day SMA"
            )
        )


        # =================================================
        # VOLUME GRAPH
        # =================================================

        volume_fig.add_trace(
            go.Bar(
                x=data.index,
                y=volume,
                name=symbol
            )
        )


    # =====================================================
    # PRICE GRAPH LAYOUT
    # =====================================================

    price_fig.update_layout(
        template="plotly_dark",
        title="Stock Price Comparison with 50-day SMA",
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode="x unified"
    )


    # =====================================================
    # VOLUME GRAPH LAYOUT
    # =====================================================

    volume_fig.update_layout(
        template="plotly_dark",
        title="Stock Volume Comparison",
        xaxis_title="Date",
        yaxis_title="Volume",
        hovermode="x unified"
    )


    # =====================================================
    # DISPLAY ERRORS WITHOUT EXPOSING ANYTHING
    # =====================================================

    if errors:

        error_message = " | ".join(errors)

        price_fig.add_annotation(
            text=error_message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.95,
            showarrow=False,
            font=dict(size=14)
        )

        volume_fig.add_annotation(
            text=error_message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.95,
            showarrow=False,
            font=dict(size=14)
        )


    return price_fig, volume_fig


# =========================================================
# GUNICORN SERVER
# =========================================================

server = app.server


# =========================================================
# LOCAL DEVELOPMENT
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
