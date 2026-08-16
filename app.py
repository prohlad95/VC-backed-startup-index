import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- Page Configuration ---
st.set_page_config(page_title="VC-Backed Startup Index", layout="wide")

st.title("Indian VC-Backed Startup Index")

# --- Data Processing & Calculation ---
@st.cache_data
def process_index_data():
    # 1. Load the Excel file (ensure this file is uploaded to your GitHub repository)
    file_path = "Historical_Total_Market_Cap (2).xlsx"
    xls = pd.ExcelFile(file_path)
    
    dfs = []
    company_data = []
    
    for sheet in xls.sheet_names:
        df_temp = pd.read_excel(xls, sheet_name=sheet)
        df_temp['Date'] = pd.to_datetime(df_temp['Date'])
        
        mcap_col = [col for col in df_temp.columns if 'Market Cap' in col][0]
        df_temp = df_temp.dropna(subset=['Date'])
        
        # Capture IPO/Listing Date and Valuation for the Companies Tab
        listing_date = df_temp['Date'].min()
        ipo_valuation = df_temp.loc[df_temp['Date'] == listing_date, mcap_col].values[0]
        company_data.append({
            "Company / Ticker": sheet,
            "Listing Date": listing_date.strftime('%Y-%m-%d'),
            "IPO Valuation (₹ Cr)": ipo_valuation
        })
        
        df_temp = df_temp[['Date', mcap_col]].rename(columns={mcap_col: sheet})
        df_temp.set_index('Date', inplace=True)
        dfs.append(df_temp)

    df_mcap = pd.concat(dfs, axis=1)
    df_mcap.sort_index(inplace=True)

    # 2. Chain-Linked Same Store Calculation
    index_data = []
    base_value = 100.0
    prev_live = []
    dates = df_mcap.index

    for i in range(len(dates)):
        dt = dates[i]
        current_mcaps = df_mcap.loc[dt].dropna()
        current_live = current_mcaps.index.tolist()
        
        if i == 0:
            index_val = base_value
        else:
            same_store = list(set(prev_live).intersection(set(current_live)))
            if len(same_store) > 0:
                same_store_prev = df_mcap.loc[dates[i-1], same_store].sum()
                same_store_curr = df_mcap.loc[dt, same_store].sum()
                growth = same_store_curr / same_store_prev
                index_val = index_data[-1]['Startup Index'] * growth
            else:
                index_val = index_data[-1]['Startup Index']
            
        index_data.append({
            'Date': dt,
            'Startup Index': index_val
        })
        prev_live = current_live

    df_index = pd.DataFrame(index_data)
    df_index.set_index('Date', inplace=True)
    
    # 3. Add Actual Nifty 50 Data
    # Read the Nifty 50 Excel file (skip the first row title to hit the actual column headers)
    df_nifty = pd.read_excel("Nifty 50 Monthly Data.xlsx", header=1)
    df_nifty['Date'] = pd.to_datetime(df_nifty['Date'])
    
    # Extract the rebased index column and align it with the Startup Index
    df_nifty = df_nifty[['Date', 'Rebase']].rename(columns={'Rebase': 'Nifty 50'})
    df_nifty.set_index('Date', inplace=True)
    
    # Join into the main index dataframe and handle minor date discrepancies via ffill/bfill
    df_index = df_index.join(df_nifty, how='left')
    df_index['Nifty 50'] = df_index['Nifty 50'].ffill().bfill()
    
    df_companies = pd.DataFrame(company_data)
    return df_index, df_companies

# Load the processed data
df_index, df_companies = process_index_data()

# --- Tab Layout ---
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🏢 Companies", "📝 Methodology"])

# --- Tab 1: Dashboard ---
with tab1:
    st.header("Performance Overview")
    
    # Calculate Key Metrics
    latest_index = df_index['Startup Index'].iloc[-1]
    latest_nifty = df_index['Nifty 50'].iloc[-1]
    
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Startup Index Value", value=f"{latest_index:.2f}", delta=f"{(latest_index - 100):.2f}% All-Time")
    col2.metric(label="Nifty 50 Value", value=f"{latest_nifty:.2f}", delta=f"{(latest_nifty - 100):.2f}% All-Time")
    col3.metric(label="Constituents Count", value=len(df_companies))
    
    st.subheader("Startup Index vs. Nifty 50 (Base = 100)")
    
    # Format data for Altair processing
    df_chart = df_index.reset_index().melt('Date', var_name='Index', value_name='Value')
    
    # Updated Interactive Altair Chart (X-axis swipe enabled, tooltips enhanced)
    chart = alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Value:Q', title='Index Value', scale=alt.Scale(zero=False)),
        color=alt.Color('Index:N', legend=alt.Legend(title="Indices", orient="bottom")),
        tooltip=[
            alt.Tooltip('Date:T', title='Date', format='%Y-%m-%d'),
            alt.Tooltip('Index:N', title='Index'),
            alt.Tooltip('Value:Q', title='Value', format=',.2f')
        ]
    ).properties(
        height=450
    ).interactive(bind_y=False) # The bind_y=False command enables left/right swipe while keeping the height locked!
    
    st.altair_chart(chart, use_container_width=True)

# --- Tab 2: Companies ---
with tab2:
    st.header("Index Constituents")
    st.write("Filter, sort, and search through the 38 index constituents.")
    
    st.dataframe(
        df_companies,
        column_config={
            "IPO Valuation (₹ Cr)": st.column_config.NumberColumn(format="₹ %d Cr")
        },
        use_container_width=True,
        hide_index=True
    )

# --- Tab 3: Methodology ---
with tab3:
    st.header("Whitepaper: Index Methodology")
    st.markdown("""
    ### 1. Objective
    This index is designed to accurately track the performance of publicly traded Indian companies that were originally VC-backed startups.
    
    ### 2. The Chain-Linked "Same Store Growth" Method
    To prevent artificial spikes in the index value when newly listed companies are added to the portfolio, this index employs a Chain-Linked methodology.
    
    * **Inclusion Rule:** A new constituent is only factored into the index's growth percentage starting the month *after* its listing.
    * **Calculation:** Growth is calculated strictly based on the aggregate market capitalization of constituents that were present in *both* the current and previous periods. 
    
    $$ Index_{t} = Index_{t-1} \\times \\left( \\frac{\\sum MarketCap_{SameStore, t}}{\\sum MarketCap_{SameStore, t-1}} \\right) $$
    
    ### 3. Corporate Actions
    * **Stock Splits & Bonuses:** Automatically adjusted via the outstanding shares multiplier.
    * **Delistings:** Removed from the "Same Store" baseline in the period they cease trading, ensuring no downward drag.
    """)
