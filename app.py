import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import os
import requests

from styles import TABLE_STYLE

PORTFOLIO_FILE = "portfolio_data.json"

def load_portfolio():
    """Load portfolio from file if it exists"""
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def save_portfolio(portfolio):
    """Save portfolio to file"""
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portfolio, f, indent=2)
    except IOError:
        st.error("Error saving portfolio data")

def recommend_trades(label, bucket_targets, bucket_values, holdings, key, total):
    """Show a rebalancing plan and per-stock trades for a set of buckets.

    bucket_targets: {bucket: target_fraction}
    bucket_values:  {bucket: current_dollar_value}
    holdings:       list of per-stock dicts (ticker, shares, price, value, ...)
    key:            holding field to group by ('country' or 'sector')
    total:          total portfolio dollar value across these buckets
    """
    target_sum = sum(bucket_targets.values())
    if abs(target_sum - 1.0) > 0.01:
        st.warning(f"Target allocations add up to {target_sum * 100:.1f}%, not 100%. Adjust them so they sum to 100%.")
        return
    if total == 0:
        st.warning("Could not value the portfolio (no prices available).")
        return

    # dollar amount to move per bucket: positive = buy, negative = sell
    bucket_delta = {
        bucket: bucket_targets[bucket] * total - bucket_values.get(bucket, 0)
        for bucket in bucket_targets
    }

    st.subheader(f"Rebalancing Plan (by {label})")
    for bucket, delta in bucket_delta.items():
        action = "buy" if delta > 0 else "sell"
        st.write(f"{bucket}: {action} ${abs(delta):,.2f}")

    st.subheader("Suggested Trades")
    # simple strategy: split each bucket's dollar delta across the stocks in that
    # bucket, weighted by how much of each you currently hold.
    any_trades = False
    for bucket, delta in bucket_delta.items():
        if abs(delta) < 0.01:
            continue

        bucket_stocks = [h for h in holdings if h[key] == bucket]
        bucket_value = bucket_values.get(bucket, 0)

        if not bucket_stocks or bucket_value == 0:
            action = "buy" if delta > 0 else "sell"
            st.write(f"{bucket}: need to {action} ${abs(delta):,.2f}, but you hold no {bucket} stocks to distribute this across.")
            continue

        for h in bucket_stocks:
            if h['price'] <= 0:
                continue
            weight = h['value'] / bucket_value
            dollar_change = delta * weight
            share_change = int(dollar_change / h['price'])  # whole shares only
            if share_change == 0:
                continue
            action = "Buy" if share_change > 0 else "Sell"
            est = abs(share_change) * h['price']
            st.write(f"{action} {abs(share_change)} shares of {h['ticker']} (~${est:,.2f})")
            any_trades = True

    if not any_trades:
        st.write("Your portfolio is already close enough to the target — no whole-share trades needed.")

# get a list of NYSE S&P 500 tickers and TSX
def get_sp500_tickers():
    """Get the list of NYSE S&P 500 tickers"""
    if os.path.exists("sp500_tickers.csv"):
        return
    sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }
    response = requests.get(sp500_url, headers=headers)
    sp500_table = pd.read_html(response.text)
    sp500_table[0].to_csv("sp500_tickers.csv", index=False)

def get_tsx_tickers():
    """Get the list of TSX tickers"""
    if os.path.exists("tsx_tickers.csv"):
        return
    tsx_url = "https://stockanalysis.com/list/toronto-stock-exchange/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }
    response = requests.get(tsx_url, headers=headers)
    tsx_table = pd.read_html(response.text)
    tsx_table[0].to_csv("tsx_tickers.csv", index=False)

get_sp500_tickers()
get_tsx_tickers()

st.title("Portfolio Balancer")

# Initialize session state for portfolio if it doesn't exist
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_portfolio()


# a table that has the ticker and amount of shares owned
ticker_data = st.text_input("Enter the ticker of the stock")
amount_owned = st.number_input("Enter the amount of shares owned", value=0)

# a button to add the stock to the portfolio
if st.button("Add Stock"):
    if ticker_data and amount_owned > 0:
        # Check if ticker already exists
        existing_index = next((i for i, stock in enumerate(st.session_state.portfolio) if stock['Ticker'] == ticker_data.upper()), None)
        if existing_index is not None:
            # Update existing stock
            st.session_state.portfolio[existing_index]['Amount Owned'] = amount_owned
            st.success(f"Updated {ticker_data.upper()} to {amount_owned} shares")
        else:
            # Add new stock
            st.session_state.portfolio.append({
                'Ticker': ticker_data.upper(),
                'Amount Owned': amount_owned
            })
            st.success(f"Stock {ticker_data.upper()} added to portfolio with {amount_owned} shares")
        save_portfolio(st.session_state.portfolio)
    else:
        st.warning("Please enter a valid ticker and amount of shares")

# a button to remove the stock from the portfolio
if st.button("Remove Stock"):
    if ticker_data:
        ticker_upper = ticker_data.upper()
        initial_length = len(st.session_state.portfolio)
        st.session_state.portfolio = [stock for stock in st.session_state.portfolio if stock['Ticker'] != ticker_upper]
        if len(st.session_state.portfolio) < initial_length:
            st.success(f"Stock {ticker_upper} removed from portfolio")
            save_portfolio(st.session_state.portfolio)
        else:
            st.warning(f"Stock {ticker_upper} not found in portfolio")
    else:
        st.warning("Please enter a ticker to remove")

# let user decide whether to balance by country or by sector
balance_by_country = st.checkbox("Balance by country")
balance_by_sector = st.checkbox("Balance by sector")

# if balance by country, let user enter the target allocation for each country
if balance_by_country:
    target_alloc_canada = st.number_input("Enter the target allocation for Canada", value=0.5)
    target_alloc_us = st.number_input("Enter the target allocation for the US", value=0.3)
    target_alloc_foreign = st.number_input("Enter the target allocation for foreign countries", value=0.2)

# sector targets depend on which sectors you hold, so they're set after balancing
if balance_by_sector:
    st.caption("Click 'Balance Portfolio' to set a target for each sector you hold.")

st.markdown(TABLE_STYLE, unsafe_allow_html=True)



# Display portfolio from session state
st.header("Stocks Added")
if st.session_state.portfolio:
    portfolio_data = pd.DataFrame(st.session_state.portfolio)
    st.table(portfolio_data)
else:
    st.info("No stocks in portfolio yet. Add stocks using the form above.")


# Button to clear all portfolio data
if st.button("Clear All Portfolio Data"):
    st.session_state.portfolio = []
    # Remove the file if it exists
    if os.path.exists(PORTFOLIO_FILE):
        os.remove(PORTFOLIO_FILE)

balance_button = st.button("Balance Portfolio")

#current portfolio balance
if balance_button:
    countries = {"CANADIAN": 0, "US": 0, "FOREIGN": 0}
    categories = {}
    holdings = []  # per-stock details so we can recommend trades for each one
    for stock in st.session_state.portfolio:
        stock_data = yf.Ticker(stock['Ticker'])
        info = stock_data.info
        price = info.get('previousClose', 0)
        shares = stock['Amount Owned']
        value = shares * price

        country = None
        if 'country' in info:
            if info['country'] == "Canada" or stock['Ticker'].endswith(".TO") or stock['Ticker'].endswith(".V"):
                country = "CANADIAN"
            elif info['country'] == "United States":
                country = "US"
            else:
                country = "FOREIGN"
            countries[country] += value

        sector = None
        if 'sector' in info and info['sector'] not in ('etf', 'mutual fund'): # not etfs or mutual funds (which have no sector)
            sector = info['sector']
            categories[sector] = categories.get(sector, 0) + value

        holdings.append({
            'ticker': stock['Ticker'],
            'shares': shares,
            'price': price,
            'value': value,
            'country': country,
            'sector': sector,
        })

    # persist so the rebalancing UI survives the reruns the sector inputs trigger
    st.session_state.balance = {
        'countries': countries,
        'categories': categories,
        'holdings': holdings,
        'total_countries': sum(countries.values()),
        'total_categories': sum(categories.values()),
    }

# render the breakdowns and rebalancing plan from the stored balance (if any)
if st.session_state.get('balance'):
    balance = st.session_state.balance
    countries = balance['countries']
    categories = balance['categories']
    holdings = balance['holdings']
    total_countries = balance['total_countries']
    total_categories = balance['total_categories']

    if total_categories > 0:
        st.subheader("Sector Breakdown")
        for category in categories:
            percentage = (categories[category]/total_categories) * 100
            st.write(f"{category}: {percentage:.2f}%")

    if total_countries > 0:
        st.subheader("Country Breakdown")
        for country in countries:
            percentage = (countries[country]/total_countries) * 100
            st.write(f"{country}: {percentage:.2f}%")

    if balance_by_country:
        # get target allocation for each country
        target_allocation = {
            "CANADIAN": target_alloc_canada,
            "US": target_alloc_us,
            "FOREIGN": target_alloc_foreign
        }
        recommend_trades("Country", target_allocation, countries, holdings, "country", total_countries)

    if balance_by_sector:
        if total_categories == 0:
            st.warning("No sector data available for your holdings.")
        else:
            st.subheader("Sector Targets")
            st.caption("Set a target % for each sector. They should add up to 100%.")
            sectors = list(categories.keys())
            equal_weight = round(100 / len(sectors), 2)  # sensible default
            sector_targets = {}
            for sector in sectors:
                pct = st.number_input(
                    f"Target % for {sector}",
                    min_value=0.0,
                    max_value=100.0,
                    value=equal_weight,
                    step=1.0,
                    key=f"sector_target_{sector}",
                )
                sector_targets[sector] = pct / 100
            recommend_trades("Sector", sector_targets, categories, holdings, "sector", total_categories)






