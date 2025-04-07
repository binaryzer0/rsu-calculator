# visualization.py
# Changes:
# 1. No changes made. All functionality remains the same.

import pandas as pd
import streamlit as st
import plotly.express as px

def calculate_correct_tax(sale, vest):
    holding_period = (sale["sale_date"] - vest["vest_date"]).days
    if holding_period <= 30 and "tax_within_30_days" in sale:
        return sale["tax_within_30_days"]
    else:
        return sale["capital_gains_tax"]


def display_rsu_details_table(grants):
    if not grants:
        st.warning("No data available. Add grants, vests, and sales to see the details.")
        return

    st.subheader("RSU Details")
    for grant in grants:
        st.write(f"**Grant ID:** {grant['grant_id']}")
        st.write(f"**Grant Date:** {grant['grant_date']}")
        st.write(f"**Symbol:** {grant['symbol']}")
        st.write(f"**Total Stocks:** {grant['num_stocks']}")

        if grant.get("vests"):
            st.write("**Vests:**")
            vest_data = []
            for vest in grant["vests"]:
                vest_data.append({
                    "Vest ID": vest["vest_id"],
                    "Vest Date": vest["vest_date"],
                    "Shares Vested": vest["shares_vested"],
                    "Vest Price": f"${vest['vest_price']}",
                    "Tax at Vest": f"${vest['tax_at_vest']}",
                })
            st.table(pd.DataFrame(vest_data))

        if grant.get("sales"):
            st.write("**Sales:**")
            sale_data = []
            for sale in grant["sales"]:
                vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
                tax = calculate_correct_tax(sale, vest)
                sale_data.append({
                    "Sale ID": sale["sale_id"],
                    "Sale Date": sale["sale_date"],
                    "Shares Sold": sale["shares_sold"],
                    "Sale Price": f"${sale['sale_price']}",
                    "Tax at Sale": f"${tax}",
                })
            st.table(pd.DataFrame(sale_data))

        total_tax_at_vest = sum(v["tax_at_vest"] for v in grant.get("vests", []))
        total_capital_gains_tax = sum(calculate_correct_tax(s, next(v for v in grant["vests"] if v["vest_id"] == s["vest_id"])) for s in grant.get("sales", []))
        totals_data = [{
            "Type": "Totals",
            "Tax at Vest": f"${total_tax_at_vest:,.2f}",
            "Tax at Sale": f"${total_capital_gains_tax:,.2f}",
        }]

        st.table(pd.DataFrame(totals_data))
        st.write("---")

def display_totals(grants):
    total_tax_at_vest = sum(
        v["tax_at_vest"]
        for grant in grants
        for v in grant.get("vests", [])
    )
    total_tax_at_sale = sum(
        calculate_correct_tax(s, next(v for v in grant["vests"] if v["vest_id"] == s["vest_id"]))
        for grant in grants
        for s in grant.get("sales", [])
    )
    st.write(f"**Total Tax at Vest:** ${total_tax_at_vest:,.2f}")
    st.write(f"**Total Tax at Sale:** ${total_tax_at_sale:,.2f}")

def get_australian_tax_year(date_obj):
    year = date_obj.year
    if date_obj.month < 7:
        return f"{year-1}-{year}"
    return f"{year}-{year+1}"

def plot_tax_breakdown(grants):
    tax_data = []
    for grant in grants:
        for vest in grant.get("vests", []):
            tax_year = get_australian_tax_year(vest["vest_date"])
            tax_data.append({
                "Tax Year": tax_year,
                "Type": "Vesting Tax",
                "Amount": vest["tax_at_vest"],
                "Event ID": f"Vest: {vest['vest_id']}",
                "Grant ID": grant["grant_id"],
            })
        for sale in grant.get("sales", []):
            tax_year = get_australian_tax_year(sale["sale_date"])
            vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
            tax = calculate_correct_tax(sale, vest)
            tax_data.append({
                "Tax Year": tax_year,
                "Type": "Tax at Sale",
                "Amount": tax,
                "Event ID": f"Sale: {sale['sale_id']}",
                "Grant ID": grant["grant_id"],
            })

    if not tax_data:
        return None


    df = pd.DataFrame(tax_data)

    fig = px.bar(
        df,
        x="Tax Year",
        y="Amount",
        color="Type",
        title="Tax Breakdown by Financial Year", # Slightly shorter title
        barmode="stack",
        labels={"Amount": "Tax Amount ($)", "Type": "Tax Type"}, # Updated label
        hover_data=["Grant ID", "Event ID"], # Include Event ID for detail
        template="plotly_white" # Apply theme
    )
    fig.update_traces(
        hovertemplate="<b>%{customdata[1]}</b><br>Grant: %{customdata[0]}<br>Tax Year: %{x}<br>Type: %{data.name}<br>Amount: $%{y:,.2f}<extra></extra>", # Custom hover text
        marker_line_color="black",
        marker_line_width=1.5, # Slightly thicker line
    )

    fig.update_layout(
        xaxis_title="Australian Financial Year", # More specific axis title
        yaxis_title="Tax Amount ($)",
        showlegend=True,
        legend_title="Tax Type", # Updated legend title
        xaxis_tickangle=-45,
        yaxis_tickprefix="$", # Add $ prefix to y-axis ticks
        yaxis_tickformat=",.0f" # Format y-axis ticks
    )

    return fig

def plot_capital_gains_by_vest(grants):
    gains_data = []
    for grant in grants:
        for sale in grant.get("sales", []):
            tax_year = get_australian_tax_year(sale["sale_date"])
            capital_gains = sale["capital_gains"]
            gains_data.append({
                "Tax Year": tax_year,
                "Capital Gains/Losses": capital_gains,
                "Type": "Gain" if capital_gains >= 0 else "Loss",
            })

    if not gains_data:
        return None

    df = pd.DataFrame(gains_data)
    df = df.groupby(["Tax Year", "Type"], as_index=False)["Capital Gains/Losses"].sum()

    fig = px.bar(
        df,
        x="Tax Year",
        y="Capital Gains/Losses",
        color="Type",
        title="Capital Gains/Loss Table by Australian Financial year",
        labels={"Capital Gains": "Capital Gains ($)", "Tax Year": "Tax Year"},
        barmode="group",
        text="Capital Gains/Losses",
        color_discrete_map={
            "Gain": "green",
            "Loss": "red",
        },
    )

    fig.update_traces(
        texttemplate='%{text:$,.2f}',
        textposition='outside',
    )

    fig.update_layout(
        xaxis_title="Tax Year",
        yaxis_title="Capital Gains ($)",
        showlegend=True,
        legend_title="Type",
        uniformtext_minsize=8,
        uniformtext_mode='hide',
        xaxis_tickangle=-45,
    )

    return fig

def plot_net_gains(grants):
    net_gains_data = []
    taxes_data = []
    for grant in grants:
        total_tax_at_vest = sum(v["tax_at_vest"] for v in grant.get("vests", []))
        for sale in grant.get("sales", []):
            tax_year = get_australian_tax_year(sale["sale_date"])
            vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
            tax = calculate_correct_tax(sale, vest)
            net_gain = (sale["sale_price"] * sale["shares_sold"]) - tax
            net_gains_data.append({
                "Tax Year": tax_year,
                "Type": "Net Gain",
                "Amount": net_gain,
            })

            
            total_taxes_paid = tax + vest["tax_at_vest"]
            taxes_data.append({
                "Tax Year": tax_year,
                "Type": "Taxes Paid",
                "Amount": total_taxes_paid,
            })
    if not net_gains_data:
        return None


    df = pd.DataFrame(net_gains_data + taxes_data)
    df = df.groupby(["Tax Year", "Type"], as_index=False)["Amount"].sum()

    fig = px.bar(
        df,
        x="Tax Year",
        y="Amount",
        color="Type",
        title="Gains vs Taxes by Australian Financial year",
        labels={"Amount": "Amount ($)", "Tax Year": "Tax Year"},
        barmode="group",
        text="Amount",
    )

    fig.update_traces(
        texttemplate='%{text:$,.2f}',
        textposition='outside',
    )

    fig.update_layout(
        xaxis_title="Tax Year",
        yaxis_title="Amount ($)",
        showlegend=True,
        legend_title="Type",
        uniformtext_minsize=8,
        uniformtext_mode='hide',
        xaxis_tickangle=-45,
    )

    return fig

def plot_stock_performance(grants):
    vest_data = []
    sale_data = []
    for grant in grants:
        for vest in grant.get("vests", []):
            vest_data.append({
                "Grant ID": grant["grant_id"],
                "Vest ID": vest["vest_id"],
                "Price": vest["vest_price"],
                "Type": "Vest Price",
            })

            sales = [s for s in grant.get("sales", []) if s["vest_id"] == vest["vest_id"]]
            for sale in sales:
                sale_data.append({
                    "Grant ID": grant["grant_id"],
                    "Vest ID": vest["vest_id"],
                    "Price": sale["sale_price"],
                    "Type": "Sale Price",
                })

    if not vest_data:
        return None

    vest_df = pd.DataFrame(vest_data)
    sale_df = pd.DataFrame(sale_data)
    combined_df = pd.concat([vest_df, sale_df])
    combined_df["Grant_Vest"] = combined_df["Grant ID"] + " - " + combined_df["Vest ID"]

    fig = px.bar(
        combined_df,
        x="Grant_Vest",
        y="Price",
        color="Type",
        barmode="group",
        title="Stock Performance (Vest Price vs. Sale Price)",
        labels={"Price": "Share Price ($)", "Grant_Vest": "Grant ID - Vest ID"},
    )

    fig.update_layout(
        xaxis_title="Grant ID - Vest ID",
        yaxis_title="Share Price ($)",
        showlegend=True,
        xaxis_tickangle=-45,
    )

    return fig

def generate_tax_breakdown_table(grants):
    tax_data = []
    for grant in grants:
        for vest in grant.get("vests", []):
            tax_year = get_australian_tax_year(vest["vest_date"])
            tax_data.append({
                "Tax Year": tax_year,
                "Type": "Vesting Tax",
                "Amount": vest["tax_at_vest"],
                "Grant ID": grant["grant_id"],
                "Vest ID": vest["vest_id"],
            })
        for sale in grant.get("sales", []):
            tax_year = get_australian_tax_year(sale["sale_date"])
            vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
            tax = calculate_correct_tax(sale, vest)
            tax_data.append({
                "Tax Year": tax_year,
                "Type": "Tax at Sale",
                "Amount": tax,
                "Grant ID": grant["grant_id"],
                "Sale ID": sale["sale_id"],
            })
    if not tax_data:
        return None


    return pd.DataFrame(tax_data)

def generate_capital_gains_table(grants):
    gains_data = []
    for grant in grants:
        for sale in grant.get("sales", []):
            tax_year = get_australian_tax_year(sale["sale_date"])
            capital_gains = sale["capital_gains"]
            gains_data.append({
                "Tax Year": tax_year,
                "Capital Gains": capital_gains,
                "Type": "Gain" if capital_gains >= 0 else "Loss",
                "Grant ID": grant["grant_id"],
                "Sale ID": sale["sale_id"],
            })

    if not gains_data:
        return None

    return pd.DataFrame(gains_data)

def generate_net_gains_table(grants):
    net_gains_data = []
    taxes_data = []
    for grant in grants:
        total_tax_at_vest = sum(v["tax_at_vest"] for v in grant.get("vests", []))
        for sale in grant.get("sales", []):
            tax_year = get_australian_tax_year(sale["sale_date"])
            vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
            tax = calculate_correct_tax(sale, vest)
            net_gain = (sale["sale_price"] * sale["shares_sold"]) - tax
            net_gains_data.append({
                "Tax Year": tax_year,
                "Sale ID": sale["sale_id"],
                "Type": "Net Gain",
                "Amount": net_gain,
                "Grant ID": grant["grant_id"],
            })
            
            total_taxes_paid = tax + vest["tax_at_vest"]
            taxes_data.append({
                "Tax Year": tax_year,
                "Sale ID": sale["sale_id"],
                "Type": "Taxes Paid",
                "Amount": total_taxes_paid,
                "Grant ID": grant["grant_id"],
            })
    if not net_gains_data:
        return None


    df = pd.DataFrame(net_gains_data + taxes_data)
    df = df.sort_values(by=["Tax Year", "Sale ID"])

    return df

def generate_stock_performance_table(grants):
    vest_data = []
    sale_data = []
    for grant in grants:
        for vest in grant.get("vests", []):
            vest_data.append({
                "Grant ID": grant["grant_id"],
                "Vest ID": vest["vest_id"],
                "Price": vest["vest_price"],
                "Type": "Vest Price",
            })
            for sale in grant.get("sales", []):
                if sale["vest_id"] == vest["vest_id"]:
                    sale_data.append({
                        "Grant ID": grant["grant_id"],
                        "Vest ID": vest["vest_id"],
                        "Price": sale["sale_price"],
                        "Type": "Sale Price",
                    })

    if not vest_data:
        return None

    df = pd.concat([pd.DataFrame(vest_data), pd.DataFrame(sale_data)])
    df = df.sort_values(by=["Grant ID", "Vest ID"])

    return df
