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

st.title("Portfolio Balancer")

# Initialize session state for portfolio if it doesn't exist
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_portfolio()

# get a list of NYSE S&P 500 tickers and TSX
sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
}
response = requests.get(sp500_url, headers=headers)
sp500_table = pd.read_html(response.text)
sp500_table[0].to_csv("sp500_tickers.csv", index=False)

tsx_url = "https://stockanalysis.com/list/toronto-stock-exchange/"
response = requests.get(tsx_url, headers=headers)
tsx_table = pd.read_html(response.text)
tsx_table[0].to_csv("tsx_tickers.csv", index=False)

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
countries = {"CANADIAN": 0, "US": 0, "FOREIGN": 0}
categories = {}
#current portfolio balance
if balance_button:
    for stock in st.session_state.portfolio:
        stock_data = yf.Ticker(stock['Ticker'])
        if 'country' in stock_data.info:
            if stock_data.info['country'] == "Canada" or stock['Ticker'].endswith(".TO") or stock['Ticker'].endswith(".V"):
                countries["CANADIAN"] += stock['Amount Owned'] * stock_data.info['previousClose']
            elif stock_data.info['country'] == "United States":
                countries["US"] += stock['Amount Owned'] * stock_data.info['previousClose']
            else:
                countries["FOREIGN"] += stock['Amount Owned'] * stock_data.info['previousClose']

        if 'sector' in stock_data.info:
            category = stock_data.info['sector']
            if category not in categories:
                categories[category] = 0
            categories[category] += stock['Amount Owned'] * stock_data.info['previousClose']
        else:
            market = stock_data.info['market']
            if market == 'us_market':
                countries["US"] += stock['Amount Owned'] * stock_data.info['previousClose']
            elif market == 'canadian_market':
                countries["CANADIAN"] += stock['Amount Owned'] * stock_data.info['previousClose']
            else:
                countries["FOREIGN"] += stock['Amount Owned'] * stock_data.info['previousClose']


    total_countries = sum(countries.values())
    total_categories = sum(categories.values())
    
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






