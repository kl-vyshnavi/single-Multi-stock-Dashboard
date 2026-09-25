import dash
from dash import dcc, html, Input, Output
import yfinance as yf
import plotly.graph_objs as go
from datetime import date
import pandas as pd
from functools import lru_cache


# Initialize app
app = dash.Dash(__name__)


# Layout
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
            debounce=True,
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
# YFINANCE DATA FUNCTION
# =========================================================

@lru_cache(maxsize=50)
def download_stock_data(symbol, start_date, end_date):

    try:

        data = yf.download(
            symbol,
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if data.empty:
            return None

        # -------------------------------------------------
        # Handle MultiIndex columns
        # -------------------------------------------------

        if isinstance(data.columns, pd.MultiIndex):

            # For a single ticker, extract the ticker level
            try:
                if symbol in data.columns.get_level_values(-1):

                    data = data.xs(
                        symbol,
                        axis=1,
                        level=-1
                    )

                else:
                    data.columns = data.columns.get_level_values(0)

            except Exception:

                data.columns = data.columns.get_level_values(0)

        # -------------------------------------------------
        # Reset index
        # -------------------------------------------------

        data = data.reset_index()

        # -------------------------------------------------
        # Make sure Date exists
        # -------------------------------------------------

        if 'Date' not in data.columns:

            if 'Datetime' in data.columns:
                data.rename(
                    columns={'Datetime': 'Date'},
                    inplace=True
                )
            else:
                return None

        data['Date'] = pd.to_datetime(
            data['Date']
        )

        data = data.sort_values(
            'Date'
        )

        # -------------------------------------------------
        # Make sure Close and Volume exist
        # -------------------------------------------------

        if 'Close' not in data.columns:
            return None

        if 'Volume' not in data.columns:
            return None

        # -------------------------------------------------
        # Convert Close
        # -------------------------------------------------

        data['Close'] = pd.to_numeric(
            data['Close'],
            errors='coerce'
        )

        data['Close'] = data['Close'].ffill()

        # -------------------------------------------------
        # Convert Volume
        # -------------------------------------------------

        data['Volume'] = pd.to_numeric(
            data['Volume'],
            errors='coerce'
        )

        data['Volume'] = data['Volume'].fillna(0)

        # -------------------------------------------------
        # 50-Day SMA
        # -------------------------------------------------

        data['SMA50'] = data['Close'].rolling(
            window=50,
            min_periods=1
        ).mean()

        return data

    except Exception as e:

        print(
            f"Error fetching {symbol}: {e}"
        )

        return None


# =========================================================
# CALLBACK
# =========================================================

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
def update_graph(
    stock_input,
    start_date,
    end_date
):

    # -----------------------------------------------------
    # Check stock input
    # -----------------------------------------------------

    if not stock_input:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            title="No symbols entered",
            template='plotly_dark',
            paper_bgcolor='#1f1f1f',
            plot_bgcolor='#1f1f1f',
            font=dict(color='white')
        )

        return empty_fig, empty_fig

    # -----------------------------------------------------
    # Convert input into symbols
    # -----------------------------------------------------

    symbols = [
        s.strip().upper()
        for s in stock_input.split(',')
        if s.strip()
    ]

    # -----------------------------------------------------
    # Create figures
    # -----------------------------------------------------

    price_fig = go.Figure()

    volume_fig = go.Figure()

    colors = [
        "red",
        "green",
        "#3E1E68"
    ]

    valid_symbol_found = False

    # -----------------------------------------------------
    # Process every stock
    # -----------------------------------------------------

    for i, sym in enumerate(symbols):

        data = download_stock_data(
            sym,
            start_date,
            end_date
        )

        # -------------------------------------------------
        # Check data
        # -------------------------------------------------

        if data is None or data.empty:

            print(
                f"No data for {sym}"
            )

            continue

        # -------------------------------------------------
        # Select color
        # -------------------------------------------------

        color = colors[
            i % len(colors)
        ]

        valid_symbol_found = True

        print(
            f"Fetched {sym}: {len(data)} rows"
        )

        # =================================================
        # PRICE LINE
        # =================================================

        price_fig.add_trace(
            go.Scatter(
                x=data['Date'],
                y=data['Close'],
                mode='lines+markers',
                name=f'{sym} Close',

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
        # SMA LINE
        # =================================================

        price_fig.add_trace(
            go.Scatter(
                x=data['Date'],
                y=data['SMA50'],
                mode='lines',

                line=dict(
                    color=color,
                    width=2,
                    dash='dash'
                ),

                name=f'{sym} 50-day SMA',

                hovertemplate=(
                    f"<b>Symbol:</b> {sym}<br>"
                    "<b>Date:</b> %{x|%Y-%m-%d}<br>"
                    "<b>50-day SMA:</b> %{y:.2f}"
                    "<extra></extra>"
                )
            )
        )

        # =================================================
        # VOLUME BARS
        # =================================================

        volume_fig.add_trace(
            go.Bar(
                x=data['Date'],
                y=data['Volume'],

                marker_color=color,

                name=f'{sym} Volume',

                hovertemplate=(
                    f"<b>Symbol:</b> {sym}<br>"
                    "<b>Date:</b> %{x|%Y-%m-%d}<br>"
                    "<b>Volume:</b> %{y:,}"
                    "<extra></extra>"
                )
            )
        )

    # -----------------------------------------------------
    # No valid data
    # -----------------------------------------------------

    if not valid_symbol_found:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            title="No valid data for the entered symbols",
            template='plotly_dark',
            paper_bgcolor='#1f1f1f',
            plot_bgcolor='#1f1f1f',
            font=dict(color='white')
        )

        return empty_fig, empty_fig

    # =====================================================
    # PRICE FIGURE
    # =====================================================

    price_fig.update_layout(
        title="Stock Price Comparison with 50-day SMA",

        xaxis_title="Date",

        yaxis_title="Price",

        template='plotly_dark',

        paper_bgcolor='#1f1f1f',

        plot_bgcolor='#1f1f1f',

        font=dict(
            color='white'
        ),

        hovermode='x unified'
    )

    # =====================================================
    # VOLUME FIGURE
    # =====================================================

    volume_fig.update_layout(
        title="Stock Volume Comparison",

        xaxis_title="Date",

        yaxis_title="Volume",

        barmode='group',

        template='plotly_dark',

        paper_bgcolor='#1f1f1f',

        plot_bgcolor='#1f1f1f',

        font=dict(
            color='white'
        ),

        hovermode='x unified'
    )

    return price_fig, volume_fig


# =========================================================
# GUNICORN SERVER
# =========================================================

server = app.server


# =========================================================
# RUN APP
# =========================================================

if __name__ == '__main__':
    app.run(debug=True)
