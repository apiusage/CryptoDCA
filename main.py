import streamlit as st
import pandas as pd
import sqlite3
import requests
import matplotlib.pyplot as plt

def calculate_allocation(capital, percentage):
    return capital * (percentage / 100)

def calculate_risk_capital(capital, multiplier):
    return capital * multiplier

def get_crypto_names(api_key):
    url = 'https://web-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    headers = {
        'X-CMC_PRO_API_KEY': api_key,
    }

    crypto_names = []

    try:
        for start in range(1, 20000, 5000):
            params = {
                'start': start,
                'limit': 5000,
            }

            r = requests.get(url, params=params, headers=headers)
            data = r.json()

            for item in data['data']:
                symbol = item['symbol']
                crypto_names.append(symbol)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching cryptocurrency names: {e}")
        return []

    return crypto_names

def coin_already_exists(data, coin_name):
    return coin_name in data["coin_name"].values

def create_table():
    connection = sqlite3.connect('crypto_data.db')
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_allocation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_name TEXT,
            allocation_percentage REAL,
            allocated_capital REAL
        )
    ''')
    connection.commit()
    connection.close()

def save_to_db(data):
    connection = sqlite3.connect('crypto_data.db')
    cursor = connection.cursor()

    # Drop the existing table and recreate it
    cursor.execute('DROP TABLE IF EXISTS crypto_allocation')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_allocation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_name TEXT,
            allocation_percentage REAL,
            allocated_capital REAL
        )
    ''')

    # Insert data into the table
    for index, row in data.iterrows():
        cursor.execute('''
            INSERT INTO crypto_allocation (coin_name, allocation_percentage, allocated_capital)
            VALUES (?, ?, ?)
        ''', (row['coin_name'], row['allocation_percentage'], row['allocated_capital']))

    connection.commit()
    connection.close()

def load_from_db():
    connection = sqlite3.connect('crypto_data.db')
    data = pd.read_sql_query('SELECT coin_name, allocation_percentage, allocated_capital FROM crypto_allocation',
                             connection)
    connection.close()
    return data

def pie_chart(data):
    fig, ax = plt.subplots()
    ax.pie(data["allocation_percentage"], labels=data["coin_name"], autopct='%1.1f%%', startangle=90)
    ax.set_aspect('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    return fig

def main():
    create_table()

    st.title("Crypto Portfolio Allocator")

    # Initialize session state
    if 'capital' not in st.session_state:
        st.session_state.capital = 50

    # Step 0: Allow the user to enter a capital value
    user_input_capital = st.text_input("Enter the amount of capital:", value=str(st.session_state.capital))

    try:
        capital = float(user_input_capital)
        st.session_state.capital = capital  # Update session state only when the user input is a valid float
    except ValueError:
        st.warning("Please enter a valid numeric value for capital.")
        return

    # Display table with allocation based on risk
    st.header("Allocation Based on Risk")
    risk_allocation_data = {
        "0 ≤ Risk < 0.1": calculate_risk_capital(capital, 5),
        "0.1 ≤ Risk < 0.2": calculate_risk_capital(capital, 4),
        "0.2 ≤ Risk < 0.3": calculate_risk_capital(capital, 3),
        "0.3 ≤ Risk < 0.4": calculate_risk_capital(capital, 2),
        "0.4 ≤ Risk < 0.5": calculate_risk_capital(capital, 1),
        "0.5 ≤ Risk < 0.6": 0,
        "0.6 ≤ Risk < 0.7": calculate_risk_capital(capital, 1),
        "0.7 ≤ Risk < 0.8": calculate_risk_capital(capital, 2),
        "0.8 ≤ Risk < 0.9": calculate_risk_capital(capital, 3),
        "0.9 ≤ Risk ≤ 1.0": calculate_risk_capital(capital, 4)
    }
    risk_allocation_df = pd.DataFrame(list(risk_allocation_data.items()), columns=["Risk Range", "Allocation Value"])
    st.table(risk_allocation_df)

    # Step 1: Retrieve the amount of capital from the user
    st.header("Crypto Coin Allocation")

    # Allow the user to select the risk range
    selected_risk_range = st.selectbox("Select Risk Range:", risk_allocation_df["Risk Range"])

    if selected_risk_range == "0.5 ≤ Risk < 0.6":
        st.warning("Do nothing for this risk range.")
        return

    # Get the corresponding right column value for the selected risk range
    selected_allocation_value = risk_allocation_df[risk_allocation_df["Risk Range"] == selected_risk_range]["Allocation Value"].values[0]

    # Load data from the database
    data = load_from_db()

    api_key = '32c03197-f921-4a61-a539-d7daea4ee1f4'

    # Fetch cryptocurrency names from CoinMarketCap
    crypto_names = get_crypto_names(api_key)

    if 'allocation_percentage' not in st.session_state:
        st.session_state.allocation_percentage = 1.0

    if crypto_names:
        # Allow the user to add coins and allocation percentages
        coin_name = st.selectbox("Select Coin Name:", crypto_names)
        allocation_percentage = st.number_input(
            "Enter Allocation Percentage:", min_value=0.01, max_value=100.0,
            value=st.session_state.allocation_percentage
        )

        if st.button("Add Coin"):
            # Check if the total allocation percentage will exceed 100
            if (data["allocation_percentage"].sum() + allocation_percentage) > 100:
                st.warning("Total allocation percentage cannot exceed 100%. Please adjust your allocations.")
            else:
                # Check if the selected coin already exists in the table
                if coin_already_exists(data, coin_name):
                    st.warning("This coin is already in the table. Please select a different coin.")
                else:
                    new_row = (coin_name, allocation_percentage, "0")
                    data = pd.concat([data, pd.DataFrame([new_row], columns=["coin_name", "allocation_percentage",
                                                                             "allocated_capital"])], ignore_index=True)
                    save_to_db(data)  # Save the entire updated dataframe to the database
                    st.session_state.allocation_percentage = allocation_percentage  # Update session state for allocation_percentage

    # Display the table
    if not data.empty:
        # Update allocated_capital dynamically based on the latest capital input and allocation_percentage
        data["allocated_capital"] = data.apply(lambda row: calculate_allocation(selected_allocation_value, row["allocation_percentage"]), axis=1)

        # Show the total percentage and total allocated capital in the last row
        total_allocation_percentage = data["allocation_percentage"].sum()
        total_allocated_capital = data["allocated_capital"].sum()
        total_row = pd.DataFrame([{"coin_name": "Total", "allocation_percentage": total_allocation_percentage,
                                   "allocated_capital": total_allocated_capital}])

        # Simple styling for the table
        st.table(pd.concat([data, total_row], ignore_index=True).drop(columns=["id"], errors="ignore"))

        # Add a dropdown for deleting a coin
        selected_coin = st.selectbox("Select Coin to Delete:", data["coin_name"])
        delete_button = st.button("Delete Selected Coin")

        if delete_button:
            with st.spinner("Deleting..."):
                data = data[data["coin_name"] != selected_coin]
                save_to_db(data)  # Save the entire updated dataframe to the database

        # Show the pie chart for Allocation Percentage
        st.header("Pie Chart: Allocation Percentage")
        fig = pie_chart(data)
        st.pyplot(fig)

if __name__ == "__main__":
    main()
