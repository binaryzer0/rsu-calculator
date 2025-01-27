# app.py
# Changes:
# 1. Added a new "Summary" section between "Sales" and "Visualizations".
# 2. The Summary section includes the Sales Table for display purposes only.
# 3. The Summary section is not included in the export.

import streamlit as st
import pandas as pd
from utils.calculations import calculate_tax_at_vest, calculate_capital_gains_tax, calculate_gains_at_sale
from utils.data_handling import export_data, import_data
from utils.visualization import (
    display_rsu_details_table,
    display_totals,
    plot_tax_breakdown,
    plot_capital_gains_by_vest,
    plot_net_gains,
    plot_stock_performance,
    generate_tax_breakdown_table,
    generate_capital_gains_table,
    generate_net_gains_table,
    generate_stock_performance_table,
)

# Set page configuration (wide mode)
st.set_page_config(layout="wide")

def add_grant_form():
    with st.expander("Add/Edit Grants", expanded=not st.session_state.get("data_loaded", False)):
        if "grants" not in st.session_state:
            st.session_state["grants"] = []

        with st.form("grant_form"):
            grant_id = st.text_input("Grant ID", key="grant_id")
            grant_date = st.date_input("Grant Date", key="grant_date")
            symbol = st.text_input("Stock Symbol", key="symbol")
            num_stocks = st.number_input("Number of Stocks", min_value=1, step=1, key="num_stocks")
            submit = st.form_submit_button("Add/Update Grant")

            if submit:
                if not grant_id:
                    st.error("Grant ID is required.")
                    return
                grants = st.session_state.get("grants", [])
                if grant_id in [g["grant_id"] for g in grants]:
                    grant = next(g for g in grants if g["grant_id"] == grant_id)
                    grant.update({
                        "grant_date": grant_date,
                        "symbol": symbol,
                        "num_stocks": num_stocks,
                    })
                    st.success("Grant updated successfully!")
                else:
                    new_grant = {
                        "grant_id": grant_id,
                        "grant_date": grant_date,
                        "symbol": symbol,
                        "num_stocks": num_stocks,
                        "vests": [],
                        "sales": [],
                    }
                    grants.append(new_grant)
                    st.session_state["grants"] = grants
                    st.success("Grant added successfully!")

        if st.session_state.get("grants"):
            st.write("**Grants Table**")
            grant_data = [
                {
                    "Grant ID": grant["grant_id"],
                    "Grant Date": grant["grant_date"],
                    "Symbol": grant["symbol"],
                    "Number of Stocks": grant["num_stocks"],
                }
                for grant in st.session_state["grants"]
            ]
            grants_df = pd.DataFrame(grant_data)
            edited_df = st.data_editor(
                grants_df,
                key="grants_editor",
                num_rows="dynamic",
                column_config={
                    "Grant ID": {"disabled": True},
                },
            )

            if st.button("Update Grants"):
                if len(edited_df) > len(grants_df):
                    st.error("New rows cannot be added directly in the table. Use the form above to add new grants.")
                else:
                    # Update session state with edited data
                    for index, row in edited_df.iterrows():
                        grant_id = row["Grant ID"]
                        grant = next(g for g in st.session_state["grants"] if g["grant_id"] == grant_id)
                        grant.update({
                            "grant_date": row["Grant Date"],
                            "symbol": row["Symbol"],
                            "num_stocks": row["Number of Stocks"],
                        })
                    st.success("Grants updated successfully!")

            st.warning("To add new grants, use the form above. The table is for editing or deleting existing data only.")

    st.write("---")

def add_vest_form():
    with st.expander("Add/Edit Vests", expanded=not st.session_state.get("data_loaded", False)):
        if "grants" not in st.session_state or not st.session_state["grants"]:
            st.warning("No grants available. Please add a grant first.")
            return

        with st.form("vest_form"):
            grant_id = st.selectbox(
                "Select Grant",
                options=[g["grant_id"] for g in st.session_state["grants"]],
                key="vest_grant_id",
            )
            vest_id = st.text_input("Vest ID", key="vest_id")
            vest_date = st.date_input("Vest Date", key="vest_date")
            shares_vested = st.number_input("Shares Vested", min_value=1, step=1, key="shares_vested")
            vest_price = st.number_input("Vest Price per Share", min_value=0.0, key="vest_price")
            tax_rate_vest = st.number_input("Tax Rate at Vest (%)", min_value=0.0, max_value=100.0, key="tax_rate_vest") / 100
            submit = st.form_submit_button("Add/Update Vest")

            if submit:
                if not vest_id:
                    st.error("Vest ID is required.")
                    return
                grant = next(g for g in st.session_state["grants"] if g["grant_id"] == grant_id)
                if vest_id in [v["vest_id"] for v in grant["vests"]]:
                    vest = next(v for v in grant["vests"] if v["vest_id"] == vest_id)
                    vest.update({
                        "vest_date": vest_date,
                        "shares_vested": shares_vested,
                        "vest_price": vest_price,
                        "tax_rate_vest": tax_rate_vest,
                        "tax_at_vest": calculate_tax_at_vest(shares_vested, vest_price, tax_rate_vest),
                    })
                    st.success("Vest updated successfully!")
                else:
                    new_vest = {
                        "vest_id": vest_id,
                        "vest_date": vest_date,
                        "shares_vested": shares_vested,
                        "vest_price": vest_price,
                        "tax_rate_vest": tax_rate_vest,
                        "tax_at_vest": calculate_tax_at_vest(shares_vested, vest_price, tax_rate_vest),
                    }
                    grant["vests"].append(new_vest)
                    st.success("Vest added successfully!")

        if st.session_state.get("grants"):
            st.write("**Vests Table**")
            vest_data = []
            for grant in st.session_state["grants"]:
                for vest in grant["vests"]:
                    if "tax_at_vest" not in vest:
                        vest["tax_at_vest"] = calculate_tax_at_vest(
                            vest["shares_vested"],
                            vest["vest_price"],
                            vest["tax_rate_vest"],
                        )
                    vest_data.append({
                        "Grant ID": grant["grant_id"],
                        "Vest ID": vest["vest_id"],
                        "Vest Date": vest["vest_date"],
                        "Shares Vested": vest["shares_vested"],
                        "Vest Price": vest["vest_price"],
                        "Tax Rate at Vest (%)": vest["tax_rate_vest"] * 100,
                        "Tax at Vest": vest["tax_at_vest"],
                    })

            vests_df = pd.DataFrame(vest_data)
            edited_df = st.data_editor(
                vests_df,
                key="vests_editor",
                num_rows="dynamic",
                column_config={
                    "Grant ID": {"disabled": True},
                    "Vest ID": {"disabled": True},
                    "Tax at Vest": {"disabled": True},
                },
            )

            if st.button("Update Vests"):
                if len(edited_df) > len(vests_df):
                    st.error("New rows cannot be added directly in the table. Use the form above to add new vests.")
                else:
                    # Update session state with edited data
                    for index, row in edited_df.iterrows():
                        grant_id = row["Grant ID"]
                        vest_id = row["Vest ID"]
                        grant = next(g for g in st.session_state["grants"] if g["grant_id"] == grant_id)
                        vest = next(v for v in grant["vests"] if v["vest_id"] == vest_id)
                        vest.update({
                            "vest_date": row["Vest Date"],
                            "shares_vested": row["Shares Vested"],
                            "vest_price": row["Vest Price"],
                            "tax_rate_vest": row["Tax Rate at Vest (%)"] / 100,
                            "tax_at_vest": calculate_tax_at_vest(
                                row["Shares Vested"],
                                row["Vest Price"],
                                row["Tax Rate at Vest (%)"] / 100,
                            ),
                        })
                    st.success("Vests updated successfully!")

            st.warning("To add new vests, use the form above. The table is for editing or deleting existing data only.")

    st.write("---")

def add_sale_form():
    with st.expander("Add/Edit Sales", expanded=not st.session_state.get("data_loaded", False)):
        if "grants" not in st.session_state or not st.session_state["grants"]:
            st.warning("No grants available. Please add a grant first.")
            return

        with st.form("sale_form"):
            grant_id = st.selectbox(
                "Select Grant",
                options=[g["grant_id"] for g in st.session_state["grants"]],
                key="sale_grant_id",
            )
            vest_id = st.selectbox(
                "Select Vest",
                options=[v["vest_id"] for v in next(g for g in st.session_state["grants"] if g["grant_id"] == grant_id)["vests"]],
                key="sale_vest_id",
            )
            sale_id = st.text_input("Sale ID", key="sale_id")
            sale_date = st.date_input("Sale Date", key="sale_date")
            shares_sold = st.number_input("Shares Sold", min_value=1, step=1, key="shares_sold")
            sale_price = st.number_input("Sale Price per Share", min_value=0.0, key="sale_price")
            tax_rate_sale = st.number_input("Tax Rate at Sale (%)", min_value=0.0, max_value=100.0, key="tax_rate_sale") / 100
            held_over_year = st.checkbox("Held for more than a year?", key="held_over_year")
            submit = st.form_submit_button("Add/Update Sale")

            if submit:
                if not sale_id:
                    st.error("Sale ID is required.")
                    return
                grant = next(g for g in st.session_state["grants"] if g["grant_id"] == grant_id)
                vest = next(v for v in grant["vests"] if v["vest_id"] == vest_id)

                holding_period = (sale_date - vest["vest_date"]).days
                held_over_year = holding_period > 365

                if sale_id in [s["sale_id"] for s in grant["sales"]]:
                    sale = next(s for s in grant["sales"] if s["sale_id"] == sale_id)
                    sale.update({
                        "sale_date": sale_date,
                        "shares_sold": shares_sold,
                        "sale_price": sale_price,
                        "vest_date": vest["vest_date"],
                        "tax_rate_sale": tax_rate_sale,
                        "capital_gains": calculate_gains_at_sale(sale_price, vest["vest_price"], shares_sold),
                        "capital_gains_tax": calculate_capital_gains_tax(
                            sale_price, vest["vest_price"], shares_sold, tax_rate_sale, held_over_year
                        ),
                    })
                    st.success("Sale updated successfully!")
                else:
                    new_sale = {
                        "sale_id": sale_id,
                        "vest_id": vest_id,
                        "sale_date": sale_date,
                        "shares_sold": shares_sold,
                        "sale_price": sale_price,
                        "vest_date": vest["vest_date"],
                        "tax_rate_sale": tax_rate_sale,
                        "capital_gains": calculate_gains_at_sale(sale_price, vest["vest_price"], shares_sold),
                        "capital_gains_tax": calculate_capital_gains_tax(
                            sale_price, vest["vest_price"], shares_sold, tax_rate_sale, held_over_year
                        ),
                    }
                    grant["sales"].append(new_sale)
                    st.success("Sale added successfully!")

        if st.session_state.get("grants"):
            st.write("**Sales Table**")
            sale_data = []
            for grant in st.session_state["grants"]:
                for sale in grant.get("sales", []):
                    if "capital_gains_tax" not in sale:
                        vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
                        holding_period = (sale["sale_date"] - vest["vest_date"]).days
                        held_over_year = holding_period > 365
                        sale["capital_gains_tax"] = calculate_capital_gains_tax(
                            sale["sale_price"],
                            vest["vest_price"],
                            sale["shares_sold"],
                            sale["tax_rate_sale"],
                            held_over_year,
                        )
                        sale["capital_gains"] = calculate_gains_at_sale(sale["sale_price"], vest["vest_price"], sale["shares_sold"])

                    vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
                    sale_data.append({
                        "Sale ID": sale["sale_id"],
                        "Grant ID": grant["grant_id"],
                        "Grant Date": grant["grant_date"],
                        "Vest Date": vest["vest_date"],
                        "Sale Date": sale["sale_date"],
                        "Shares Sold": sale["shares_sold"],
                        "Vest Price": vest["vest_price"],
                        "Sale Price": sale["sale_price"],
                        "Tax Rate at Sale (%)": sale["tax_rate_sale"] * 100,
                        "Capital Gains": sale["capital_gains"],
                        "Capital Gains Tax": sale["capital_gains_tax"],
                    })

            sales_df = pd.DataFrame(sale_data)
            edited_df = st.data_editor(
                sales_df,
                key="sales_editor",
                num_rows="dynamic",
                column_config={
                    "Grant ID": {"disabled": True},
                    "Sale ID": {"disabled": True},
                    "Grant Date": {"disabled": True},
                    "Vest Date": {"disabled": True},
                    "Vest Price": {"disabled": True},
                    "Capital Gains Tax": {"disabled": True},
                },
            )

            if st.button("Update Sales"):
                if len(edited_df) > len(sales_df):
                    st.error("New rows cannot be added directly in the table. Use the form above to add new sales.")
                else:
                    # Update session state with edited data
                    for index, row in edited_df.iterrows():
                        grant_id = row["Grant ID"]
                        sale_id = row["Sale ID"]
                        grant = next(g for g in st.session_state["grants"] if g["grant_id"] == grant_id)
                        sale = next(s for s in grant["sales"] if s["sale_id"] == sale_id)
                        vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
                        holding_period = (row["Sale Date"] - vest["vest_date"]).days
                        held_over_year = holding_period > 365
                        sale.update({
                            "sale_date": row["Sale Date"],
                            "shares_sold": row["Shares Sold"],
                            "sale_price": row["Sale Price"],
                            "tax_rate_sale": row["Tax Rate at Sale (%)"] / 100,
                            "capital_gains_tax": calculate_capital_gains_tax(
                                row["Sale Price"],
                                vest["vest_price"],
                                row["Shares Sold"],
                                row["Tax Rate at Sale (%)"] / 100,
                                held_over_year,
                            ),
                        })
                    st.success("Sales updated successfully!")

            st.warning("To add new sales, use the form above. The table is for editing or deleting existing data only.")

    st.write("---")

def add_summary_section():
    st.header("Summary")
    if "grants" not in st.session_state or not st.session_state["grants"]:
        st.warning("No data available. Add grants, vests, and sales to see the summary.")
        return

    # Display the Sales Table in the Summary section
    # st.write("**Sales Table**")
    sale_data = []
    for grant in st.session_state["grants"]:
        for sale in grant.get("sales", []):
            if "capital_gains_tax" not in sale:
                vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
                holding_period = (sale["sale_date"] - vest["vest_date"]).days
                held_over_year = holding_period > 365
                sale["capital_gains_tax"] = calculate_capital_gains_tax(
                    sale["sale_price"],
                    vest["vest_price"],
                    sale["shares_sold"],
                    sale["tax_rate_sale"],
                    held_over_year,
                )
                sale["capital_gains"] = calculate_gains_at_sale(sale["sale_price"], vest["vest_price"], sale["shares_sold"])

            vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
            sale_data.append({
                "Grant ID": grant["grant_id"],
                "Grant Date": grant["grant_date"],
                "Vest ID": vest["vest_id"],
                "Vest Date": vest["vest_date"],
                "Vest Price": vest["vest_price"],
                "Tax Rate at Vest (%)": vest["tax_rate_vest"] * 100,
                "Total vest proceeds" : vest["vest_price"] * sale["shares_sold"],
                "Tax at Vest": vest["tax_at_vest"],
                "Vest proceeds after taxes" : (vest["vest_price"] * sale["shares_sold"] ) - vest["tax_at_vest"],
                "Sale ID": sale["sale_id"],
                "Sale Date": sale["sale_date"],
                "Shares Sold": sale["shares_sold"],
                "Sale Price": sale["sale_price"],
                "Tax Rate at Sale (%)": sale["tax_rate_sale"] * 100,
                "Total sale proceeds": sale["capital_gains"],
                "Tax at sale": sale["capital_gains_tax"],
                "Sale proceeds after taxes": sale["capital_gains"] - sale["capital_gains_tax"],
                "Net Gain" : ((vest["vest_price"] * sale["shares_sold"] ) - vest["tax_at_vest"]) + (sale["capital_gains"] - sale["capital_gains_tax"])
            })

    sales_df = pd.DataFrame(sale_data)
    st.dataframe(
        sales_df,
        column_config={
            "Vest Price": st.column_config.NumberColumn(
                help="The price of the stock at Vest in USD",
                format="$ %.2f"
            ),
            "Sale Price": st.column_config.NumberColumn(
                help="The price of stock at Sale in USD",
                format="$ %.2f"
            ),
            "Tax at Vest": st.column_config.NumberColumn(
                help="Tax at Vest in USD",
                format="$ %.2f"
            )
        },
        hide_index=True
    )
    #st.dataframe(sales_df)

def main():
    st.title("RSU Tax Calculator")
    st.markdown("*Sample data:* ***https://github.com/binaryzer0/rsu-calculator/raw/refs/heads/main/sample.json***")
    st.sidebar.header("Navigation")

    if "grants" not in st.session_state:
        st.session_state["grants"] = []

    # Export/Import functionality
    st.sidebar.header("Export/Import Data")
    export_data(st.session_state["grants"])
    imported_data = import_data()
    if imported_data:
        st.session_state["grants"] = imported_data
        st.session_state["data_loaded"] = True

    # Add Grant, Vest, and Sale forms
    add_grant_form()
    add_vest_form()
    add_sale_form()

    # Add Summary section
    add_summary_section()

    # Display graphs
    st.header("Visualizations")

    # Tax Breakdown
    tax_breakdown_fig = plot_tax_breakdown(st.session_state.get("grants", []))
    if tax_breakdown_fig:
        st.plotly_chart(tax_breakdown_fig)
        tax_breakdown_table = generate_tax_breakdown_table(st.session_state.get("grants", []))
        if tax_breakdown_table is not None:
            st.write("**Tax Breakdown Table**")
            st.dataframe(tax_breakdown_table)

    # Capital Gains by Vest
    capital_gains_fig = plot_capital_gains_by_vest(st.session_state.get("grants", []))
    if capital_gains_fig:
        st.plotly_chart(capital_gains_fig)
        capital_gains_table = generate_capital_gains_table(st.session_state.get("grants", []))
        if capital_gains_table is not None:
            st.write("**Capital Gains Table**")
            st.dataframe(capital_gains_table)

    # Net Gains
    net_gains_fig = plot_net_gains(st.session_state.get("grants", []))
    if net_gains_fig:
        st.plotly_chart(net_gains_fig)
        net_gains_table = generate_net_gains_table(st.session_state.get("grants", []))
        if net_gains_table is not None:
            st.write("**Net Gains Table**")
            st.dataframe(net_gains_table)

    # Stock Performance
    stock_performance_fig = plot_stock_performance(st.session_state.get("grants", []))
    if stock_performance_fig:
        st.plotly_chart(stock_performance_fig)
        stock_performance_table = generate_stock_performance_table(st.session_state.get("grants", []))
        if stock_performance_table is not None:
            st.write("**Stock Performance Table**")
            st.dataframe(stock_performance_table)

if __name__ == "__main__":
    main()
