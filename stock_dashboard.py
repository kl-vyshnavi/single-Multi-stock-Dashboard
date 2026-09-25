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
        empty_fig.update_layout(title="No symbols entered")
        return empty_fig, empty_fig

    for i, sym in enumerate(symbols):

        try:
            data = yf.download(
                sym,
                start=start_date,
                end=end_date,
                interval="1d"
            )

            if data.empty:
                print(f"No data for {sym}")
                continue

            # Flatten MultiIndex columns if needed
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [
                    '_'.join(col).strip()
                    for col in data.columns.values
                ]

            data = data.reset_index()

            data['Date'] = pd.to_datetime(data['Date'])
            data = data.sort_values('Date')

            data['Close'] = pd.to_numeric(
                data[f'Close_{sym}'],
                errors='coerce'
            ).ffill()

            data['Volume'] = pd.to_numeric(
                data[f'Volume_{sym}'],
                errors='coerce'
            ).fillna(0)

            data['SMA50'] = (
                data['Close']
                .rolling(window=50, min_periods=1)
                .mean()
            )

            color = colors[i % len(colors)]

            valid_symbol_found = True

            print(f"Fetched {sym}: {len(data)} rows")

        except Exception as e:
            print(f"Error fetching {sym}: {e}")
            continue

        # Price line with markers and hover
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

        # SMA line with hover
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

        # Volume bars with hover
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

    if not valid_symbol_found:

        empty_fig = go.Figure()

        empty_fig.update_layout(
            title="No valid data for the entered symbols"
        )

        return empty_fig, empty_fig

    # Price figure layout
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

    # Volume figure layout
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
