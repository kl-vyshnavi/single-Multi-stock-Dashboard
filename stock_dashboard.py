import dash
from dash import dcc, html, Input, Output
import yfinance as yf
import plotly.graph_objs as go
from datetime import date
import pandas as pd

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
        'display': 'flex',
        'justifyContent': 'center',
        'alignItems': 'center',
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

    symbols = [
        s.strip().upper()
        for s in stock_input.split(',')
        if s.strip()
    ]

    price_fig = go.Figure()
    volume_fig = go.Figure()

    colors = ["red", "green", "#3E1E68"]

    valid_symbol_found = False

    if not symbols:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="No symbols entered"
        )
        return empty_fig, empty_fig

    for i, sym in enumerate(symbols):

        try:
            print(f"Fetching data for {sym}")
            print(f"Start date: {start_date}")
            print(f"End date: {end_date}")

            # Download stock data
            data = yf.download(
                sym,
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=False,
                progress=False
            )

            print(f"Downloaded {sym}: {data.shape}")
            print(f"Columns for {sym}: {data.columns}")

            if data.empty:
                print(f"No data returned for {sym}")
                continue

            # --------------------------------------------------
            # Handle different yfinance column structures
            # --------------------------------------------------

            if isinstance(data.columns, pd.MultiIndex):

                # Case 1:
                # Columns look like:
                # Close, AAPL
                # Volume, AAPL
                if 'Close' in data.columns.get_level_values(0):

                    close_data = data['Close']
                    volume_data = data['Volume']

                    if isinstance(close_data, pd.DataFrame):
                        close_data = close_data.iloc[:, 0]

                    if isinstance(volume_data, pd.DataFrame):
                        volume_data = volume_data.iloc[:, 0]

                # Case 2:
                # Columns look like:
                # AAPL, Close
                # AAPL, Volume
                else:

                    close_data = data[sym]['Close']
                    volume_data = data[sym]['Volume']

            else:

                # Normal single-level columns
                close_data = data['Close']
                volume_data = data['Volume']

            # Reset index
            data = data.reset_index()

            # Make sure Date is datetime
            data['Date'] = pd.to_datetime(data['Date'])

            # Create clean dataframe
            clean_data = pd.DataFrame({
                'Date': data['Date'],
                'Close': pd.to_numeric(
                    close_data.values,
                    errors='coerce'
                ),
                'Volume': pd.to_numeric(
                    volume_data.values,
                    errors='coerce'
                )
            })

            # Remove missing close prices
            clean_data = clean_data.dropna(
                subset=['Close']
            )

            # Fill missing volume values
            clean_data['Volume'] = (
                clean_data['Volume']
                .fillna(0)
            )

            # Sort by date
            clean_data = clean_data.sort_values(
                'Date'
            )

            # Calculate 50-day SMA
            clean_data['SMA50'] = (
                clean_data['Close']
                .rolling(
                    window=50,
                    min_periods=1
                )
                .mean()
            )

            print(
                f"Successfully processed {sym}: "
                f"{len(clean_data)} rows"
            )

            if clean_data.empty:
                print(f"No valid data for {sym}")
                continue

            color = colors[i % len(colors)]

            valid_symbol_found = True

            # --------------------------------------------------
            # PRICE GRAPH
            # --------------------------------------------------

            price_fig.add_trace(
                go.Scatter(
                    x=clean_data['Date'],
                    y=clean_data['Close'],
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

            # --------------------------------------------------
            # SMA GRAPH
            # --------------------------------------------------

            price_fig.add_trace(
                go.Scatter(
                    x=clean_data['Date'],
                    y=clean_data['SMA50'],
                    mode='lines',
                    name=f'{sym} 50-day SMA',
                    line=dict(
                        color=color,
                        width=2,
                        dash='dash'
                    ),
                    hovertemplate=(
                        f"<b>Symbol:</b> {sym}<br>"
                        "<b>Date:</b> %{x|%Y-%m-%d}<br>"
                        "<b>50-day SMA:</b> %{y:.2f}"
                        "<extra></extra>"
                    )
                )
            )

            # --------------------------------------------------
            # VOLUME GRAPH
            # --------------------------------------------------

            volume_fig.add_trace(
                go.Bar(
                    x=clean_data['Date'],
                    y=clean_data['Volume'],
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

        except Exception as e:

            print(
                f"ERROR while processing {sym}: "
                f"{type(e).__name__}: {e}"
            )

            continue

    # --------------------------------------------------
    # NO VALID DATA
    # --------------------------------------------------

    if not valid_symbol_found:

        empty_fig = go.Figure()

        empty_fig.add_annotation(
            text=(
                "No valid stock data found.<br>"
                "Check the stock symbol or date range."
            ),
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=18)
        )

        empty_fig.update_layout(
            title="Unable to load stock data"
        )

        return empty_fig, empty_fig

    # --------------------------------------------------
    # PRICE FIGURE LAYOUT
    # --------------------------------------------------

    price_fig.update_layout(
        title="Stock Price Comparison with 50-day SMA",
        xaxis_title="Date",
        yaxis_title="Price",
        template='plotly_dark',
        paper_bgcolor='#1f1f1f',
        plot_bgcolor='#1f1f1f',
        font=dict(color='white'),
        hovermode='x unified'
    )

    # --------------------------------------------------
    # VOLUME FIGURE LAYOUT
    # --------------------------------------------------

    volume_fig.update_layout(
        title="Stock Volume Comparison",
        xaxis_title="Date",
        yaxis_title="Volume",
        barmode='group',
        template='plotly_dark',
        paper_bgcolor='#1f1f1f',
        plot_bgcolor='#1f1f1f',
        font=dict(color='white'),
        hovermode='x unified'
    )

    return price_fig, volume_fig


# Render deployment
server = app.server
