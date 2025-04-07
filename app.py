# app.py
# Changes:
# 1. Added a new "Summary" section between "Sales" and "Visualizations".
# 2. The Summary section includes the Sales Table for display purposes only.
# 3. The Summary section is not included in the export.

import streamlit as st
import requests
import pandas as pd
import requests
import pandas as pd
import json
from datetime import datetime
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

# Parse dates when using requests URL
def parse_dates(data):
    for grant in data:
        grant['grant_date'] = datetime.strptime(grant['grant_date'], '%Y-%m-%d').date()
        for vest in grant['vests']:
            vest['vest_date'] = datetime.strptime(vest['vest_date'], '%Y-%m-%d').date()
        for sale in grant['sales']:
            sale['sale_date'] = datetime.strptime(sale['sale_date'], '%Y-%m-%d').date()
    return data
    
def load_sample_data():
    """Load sample JSON data from a URL."""
    sample_data_url = "https://github.com/binaryzer0/rsu-calculator/raw/449666f16b5ab1c356f3746077863f5de722432d/sample.json" 
    try:
        response = requests.get(sample_data_url)
        response.raise_for_status()  # Raise an error for bad status codes
        sample_data = response.json()
        st.session_state["grants"] = parse_dates(sample_data)
        st.session_state["data_loaded"] = True
        st.success("Sample data loaded successfully!")
    except Exception as e:
        st.error(f"Failed to load sample data: {e}")

def add_grant_form():
    with st.expander("Add/Edit Grants", expanded=not st.session_state.get("data_loaded", False)):
        if "grants" not in st.session_state:
            st.session_state["grants"] = []

        st.info("Add, edit, or delete grants directly in the table below. Ensure 'Grant ID' is unique.")

        # Prepare data for the editor
        grant_data_for_editor = [
            {
                "Grant ID": grant["grant_id"],
                "Grant Date": grant["grant_date"],
                "Symbol": grant["symbol"],
                "Number of Stocks": grant["num_stocks"],
            }
            for grant in st.session_state["grants"]
        ]
        grants_df_orig = pd.DataFrame(grant_data_for_editor)

        edited_df = st.data_editor(
            grants_df_orig,
            key="grants_editor",
            num_rows="dynamic",
            # Grant ID is now editable for new rows, but should be unique
            column_config={
                 "Grant ID": st.column_config.TextColumn(required=True),
                 "Grant Date": st.column_config.DateColumn(required=True),
                 "Symbol": st.column_config.TextColumn(required=True),
                 "Number of Stocks": st.column_config.NumberColumn(required=True, min_value=1, step=1),
            },
            use_container_width=True
        )

        # --- State Update Logic ---
        # Convert current state to a dictionary for easy lookup and modification
        grants_dict = {g["grant_id"]: g for g in st.session_state["grants"]}
        edited_grants_dict = {}
        edited_ids = set()
        validation_passed = True
        error_messages = []

        for index, row in edited_df.iterrows():
            grant_id_edited = row["Grant ID"]
            is_existing_row = index < len(grants_df_orig) # Check if the index corresponds to an original row

            # --- ID Immutability Check ---
            if is_existing_row:
                original_grant_id = grants_df_orig.loc[index, "Grant ID"]
                if grant_id_edited != original_grant_id:
                    error_messages.append(f"Row {index+1}: Cannot change the Grant ID ('{original_grant_id}' to '{grant_id_edited}') of an existing grant. Delete and re-add if necessary.")
                    validation_passed = False
                    # Continue validation for other fields if needed, but block state update later
            # --- End ID Immutability Check ---

            # Use the validated/original ID for further checks and dict keys
            grant_id = original_grant_id if is_existing_row else grant_id_edited

            # Basic Validation (using grant_id)
            if not grant_id or pd.isna(grant_id):
                 # This case should primarily catch empty IDs in new rows now
                error_messages.append(f"Row {index+1}: Grant ID cannot be empty.")
                # If it was an existing row where ID change was attempted, we already flagged validation_passed as False
                validation_passed = False
                continue # Skip further processing for this row if ID is invalid

            # Check for duplicates using the final grant_id
            if grant_id in edited_ids:
                 error_messages.append(f"Row {index+1}: Duplicate Grant ID '{grant_id}' found in the table. Please ensure all Grant IDs are unique.")
                 validation_passed = False
                 # Continue validation for other fields if needed

            # Other field validations
            grant_date_val = row["Grant Date"].date() if isinstance(row["Grant Date"], pd.Timestamp) else row["Grant Date"]
            num_stocks_val = int(row["Number of Stocks"]) if not pd.isna(row["Number of Stocks"]) else None
            if pd.isna(grant_date_val) or pd.isna(row["Symbol"]) or num_stocks_val is None or num_stocks_val < 1:
                 error_messages.append(f"Row {index+1} (Grant ID: {grant_id}): Missing or invalid required fields (Grant Date, Symbol, Number of Stocks >= 1).")
                 # If validation failed earlier (e.g., ID change attempt), this ensures it stays failed
                 validation_passed = False
                 # Do not continue to adding to edited_ids or grants_dict if basic fields invalid

            # Only add valid IDs to the set for duplicate checks and final list creation
            if validation_passed or grant_id not in edited_ids: # Avoid adding duplicates if validation failed mid-row
                 edited_ids.add(grant_id)

            # If validation for *this specific row* has passed so far...
            if validation_passed:
                # Check if it's a new grant or an existing one being edited (using the final grant_id)
                if grant_id in grants_dict:
                    # Existing grant: Update fields (ID change was blocked above)
                    grants_dict[grant_id].update({
                        "grant_date": grant_date_val,
                        "symbol": row["Symbol"],
                        "num_stocks": num_stocks_val,
                    })
                    edited_grants_dict[grant_id] = grants_dict[grant_id]
                else:
                    # New grant: Create entry
                    edited_grants_dict[grant_id] = {
                        "grant_id": grant_id,
                        "grant_date": grant_date_val,
                        "symbol": row["Symbol"],
                        "num_stocks": num_stocks_val,
                        "vests": [],  # Initialize empty lists for new grants
                        "sales": [],
                    }

        # --- Final State Update Decision ---
        if not validation_passed:
            # Display all collected error messages
            for msg in error_messages:
                st.error(msg)
            # Crucially, DO NOT update the session state if validation failed
            st.warning("Changes not saved due to validation errors.")
        else:
            # Update session state only if all rows passed validation
            # Convert the edited dictionary back to a list
            # Only keep grants that are present in the final valid edited_ids set (handles deletions)
            st.session_state["grants"] = [edited_grants_dict[gid] for gid in edited_ids if gid in edited_grants_dict]
            # Optional: Add a success message, but might be too noisy for dynamic editing
            # st.success("Grants updated!") # Consider if this is needed

    st.write("---")


def add_vest_form():
    with st.expander("Add/Edit Vests", expanded=not st.session_state.get("data_loaded", False)):
        if "grants" not in st.session_state or not st.session_state["grants"]:
            st.warning("No grants available. Please add a grant first.")
            return

        grant_options = [g["grant_id"] for g in st.session_state["grants"]]
        if not grant_options:
             st.warning("No grants available to add vests to.")
             return

        selected_grant_id = st.selectbox(
            "Select Grant to Add/Edit Vests For",
            options=grant_options,
            key="vest_grant_select",
            index=0 # Default to the first grant if available
        )

        if selected_grant_id:
            st.info(f"Add, edit, or delete vests for Grant ID '{selected_grant_id}' directly in the table below. Ensure 'Vest ID' is unique within this grant.")

            # Find the selected grant
            grant = next((g for g in st.session_state["grants"] if g["grant_id"] == selected_grant_id), None)
            if not grant:
                st.error(f"Selected Grant ID '{selected_grant_id}' not found in session state. This should not happen.")
                return # Should not happen if options are derived from state

            # Prepare data for the editor - ONLY for the selected grant
            vest_data_for_editor = [
                {
                    "Vest ID": vest["vest_id"],
                    "Vest Date": vest["vest_date"],
                    "Shares Vested": vest["shares_vested"],
                    "Vest Price": vest["vest_price"],
                    "Tax Rate at Vest (%)": vest["tax_rate_vest"] * 100,
                    # "Tax at Vest": vest.get("tax_at_vest", 0) # Display calculated tax, but disable editing
                }
                for vest in grant.get("vests", [])
            ]
            vests_df_orig = pd.DataFrame(vest_data_for_editor)

            edited_vest_df = st.data_editor(
                vests_df_orig,
                key=f"vests_editor_{selected_grant_id}", # Unique key per grant
                num_rows="dynamic",
                column_config={
                    "Vest ID": st.column_config.TextColumn(required=True),
                    "Vest Date": st.column_config.DateColumn(required=True),
                    "Shares Vested": st.column_config.NumberColumn(required=True, min_value=1, step=1),
                    "Vest Price": st.column_config.NumberColumn(required=True, min_value=0.0, format="%.2f"),
                    "Tax Rate at Vest (%)": st.column_config.NumberColumn(required=True, min_value=0.0, max_value=100.0, format="%.2f"),
                    # "Tax at Vest": st.column_config.NumberColumn(disabled=True, format="$%.2f"), # Display only
                },
                use_container_width=True
            )

            # --- State Update Logic ---
            # Get the original vests for comparison
            original_vests_dict = {v["vest_id"]: v for v in grant.get("vests", [])}
            edited_vests_list = []
            edited_vest_ids = set()
            validation_passed = True
            error_messages = []

            for index, row in edited_vest_df.iterrows():
                vest_id_edited = row["Vest ID"]
                is_existing_row = index < len(vests_df_orig)

                # --- ID Immutability Check ---
                if is_existing_row:
                    original_vest_id = vests_df_orig.loc[index, "Vest ID"]
                    if vest_id_edited != original_vest_id:
                        error_messages.append(f"Row {index+1}: Cannot change the Vest ID ('{original_vest_id}' to '{vest_id_edited}') of an existing vest. Delete and re-add if necessary.")
                        validation_passed = False
                        # Continue validation for other fields if needed
                # --- End ID Immutability Check ---

                # Use the validated/original ID for further checks and dict keys
                vest_id = original_vest_id if is_existing_row else vest_id_edited

                # Basic Validation (using vest_id)
                if not vest_id or pd.isna(vest_id):
                    error_messages.append(f"Row {index+1}: Vest ID cannot be empty.")
                    validation_passed = False
                    continue # Skip further processing if ID is invalid
                if vest_id in edited_vest_ids:
                    error_messages.append(f"Row {index+1}: Duplicate Vest ID '{vest_id}' found for this grant. Please ensure Vest IDs are unique within Grant '{selected_grant_id}'.")
                    # Continue validation for other fields if needed

                # Other field validations
                vest_date_val = row["Vest Date"].date() if isinstance(row["Vest Date"], pd.Timestamp) else row["Vest Date"]
                shares_val = int(row["Shares Vested"]) if not pd.isna(row["Shares Vested"]) else None
                price_val = float(row["Vest Price"]) if not pd.isna(row["Vest Price"]) else None
                tax_rate_pct_val = float(row["Tax Rate at Vest (%)"]) if not pd.isna(row["Tax Rate at Vest (%)"]) else None

                if pd.isna(vest_date_val) or shares_val is None or shares_val < 1 or price_val is None or price_val < 0 or tax_rate_pct_val is None or tax_rate_pct_val < 0 or tax_rate_pct_val > 100:
                    error_messages.append(f"Row {index+1} (Vest ID: {vest_id}): Missing or invalid required fields (Vest Date, Shares Vested >= 1, Vest Price >= 0, Tax Rate >= 0 and <= 100).")
                    validation_passed = False
                    # Do not continue if basic fields invalid

                # Only add valid IDs to the set
                if validation_passed or vest_id not in edited_vest_ids:
                    edited_vest_ids.add(vest_id)

                # If validation for this row passed...
                if validation_passed:
                    # Prepare vest data dictionary
                    tax_rate = tax_rate_pct_val / 100.0
                    tax_at_vest = calculate_tax_at_vest(shares_val, price_val, tax_rate)

                    vest_data = {
                        "vest_id": vest_id,
                        "vest_date": vest_date_val,
                        "shares_vested": shares_val,
                        "vest_price": price_val,
                        "tax_rate_vest": tax_rate,
                        "tax_at_vest": tax_at_vest, # Store calculated tax
                    }
                    edited_vests_list.append(vest_data) # Add to the list of vests to keep/add

            # --- Final State Update Decision ---
            if not validation_passed:
                for msg in error_messages:
                    st.error(msg)
                st.warning(f"Changes for Grant '{selected_grant_id}' vests not saved due to validation errors.")
            else:
                # Update the 'vests' list for the specific grant in session state only if all rows are valid
                grant["vests"] = edited_vests_list
                # Optional: Success message (might be noisy)
                # st.success(f"Vests for grant '{selected_grant_id}' updated!")

    st.write("---")


def add_sale_form():
    with st.expander("Add/Edit Sales", expanded=not st.session_state.get("data_loaded", False)):
        if "grants" not in st.session_state or not st.session_state["grants"]:
            st.warning("No grants available. Please add a grant first.")
            return

        grant_options = {g["grant_id"]: g for g in st.session_state["grants"] if g.get("vests")} # Only grants with vests
        if not grant_options:
             st.warning("No grants with vests available to add sales to.")
             return

        selected_grant_id = st.selectbox(
            "Select Grant",
            options=list(grant_options.keys()),
            key="sale_grant_select",
            index=0
        )

        selected_grant = grant_options.get(selected_grant_id)
        if not selected_grant:
             st.error("Selected grant not found.") # Should not happen
             return

        vest_options = {v["vest_id"]: v for v in selected_grant.get("vests", [])}
        if not vest_options:
            st.warning(f"Grant '{selected_grant_id}' has no vests to associate sales with.")
            return

        selected_vest_id = st.selectbox(
            f"Select Vest for Grant '{selected_grant_id}' to Add/Edit Sales For",
            options=list(vest_options.keys()),
            key=f"sale_vest_select_{selected_grant_id}", # Dynamic key
            index=0
        )

        selected_vest = vest_options.get(selected_vest_id)
        if not selected_vest:
            st.error("Selected vest not found.") # Should not happen
            return

        st.info(f"Add, edit, or delete sales associated with Vest ID '{selected_vest_id}' (Grant ID: '{selected_grant_id}') directly in the table below. Ensure 'Sale ID' is unique within this grant.")

        # Prepare data for the editor - ONLY for the selected grant and vest
        sale_data_for_editor = [
            {
                "Sale ID": sale["sale_id"],
                "Sale Date": sale["sale_date"],
                "Shares Sold": sale["shares_sold"],
                "Sale Price": sale["sale_price"],
                "Tax Rate at Sale (%)": sale["tax_rate_sale"] * 100,
                # Calculated fields (display only or omit)
                # "Capital Gains": sale.get("capital_gains"),
                # "Tax at Sale": sale.get("capital_gains_tax") # Or calculated tax
            }
            for sale in selected_grant.get("sales", []) if sale.get("vest_id") == selected_vest_id
        ]
        sales_df_orig = pd.DataFrame(sale_data_for_editor)

        edited_sales_df = st.data_editor(
            sales_df_orig,
            key=f"sales_editor_{selected_grant_id}_{selected_vest_id}", # Unique key per grant-vest
            num_rows="dynamic",
            column_config={
                "Sale ID": st.column_config.TextColumn(required=True),
                "Sale Date": st.column_config.DateColumn(required=True),
                "Shares Sold": st.column_config.NumberColumn(required=True, min_value=1, step=1),
                "Sale Price": st.column_config.NumberColumn(required=True, min_value=0.0, format="%.2f"),
                "Tax Rate at Sale (%)": st.column_config.NumberColumn(required=True, min_value=0.0, max_value=100.0, format="%.2f"),
            },
            use_container_width=True
        )

        # --- State Update Logic ---
        # Get the original sales for this specific vest for comparison
        original_sales_dict = {s["sale_id"]: s for s in selected_grant.get("sales", []) if s.get("vest_id") == selected_vest_id}
        edited_sales_list_for_vest = []
        edited_sale_ids = set()
        validation_passed = True
        error_messages = []

        # Get vest details needed for calculations
        vest_price = selected_vest["vest_price"]
        vest_date = selected_vest["vest_date"]

        for index, row in edited_sales_df.iterrows():
            sale_id_edited = row["Sale ID"]
            is_existing_row = index < len(sales_df_orig)

            # --- ID Immutability Check ---
            if is_existing_row:
                original_sale_id = sales_df_orig.loc[index, "Sale ID"]
                if sale_id_edited != original_sale_id:
                    error_messages.append(f"Row {index+1}: Cannot change the Sale ID ('{original_sale_id}' to '{sale_id_edited}') of an existing sale. Delete and re-add if necessary.")
                    validation_passed = False
                    # Continue validation for other fields if needed
            # --- End ID Immutability Check ---

            # Use the validated/original ID for further checks and dict keys
            sale_id = original_sale_id if is_existing_row else sale_id_edited

            # Basic Validation (using sale_id)
            if not sale_id or pd.isna(sale_id):
                error_messages.append(f"Row {index+1}: Sale ID cannot be empty.")
                validation_passed = False
                continue # Skip further processing if ID is invalid
            if sale_id in edited_sale_ids:
                error_messages.append(f"Row {index+1}: Duplicate Sale ID '{sale_id}' found for this vest. Please ensure Sale IDs are unique within Grant '{selected_grant_id}' / Vest '{selected_vest_id}'.")
                # Continue validation for other fields if needed

            # Other field validations
            sale_date_obj = row["Sale Date"].date() if isinstance(row["Sale Date"], pd.Timestamp) else row["Sale Date"]
            shares_val = int(row["Shares Sold"]) if not pd.isna(row["Shares Sold"]) else None
            sale_price_val = float(row["Sale Price"]) if not pd.isna(row["Sale Price"]) else None
            tax_rate_pct_val = float(row["Tax Rate at Sale (%)"]) if not pd.isna(row["Tax Rate at Sale (%)"]) else None

            if pd.isna(sale_date_obj) or shares_val is None or shares_val < 1 or sale_price_val is None or sale_price_val < 0 or tax_rate_pct_val is None or tax_rate_pct_val < 0 or tax_rate_pct_val > 100:
                error_messages.append(f"Row {index+1} (Sale ID: {sale_id}): Missing or invalid required fields (Sale Date, Shares Sold >= 1, Sale Price >= 0, Tax Rate >= 0 and <= 100).")
                validation_passed = False
                # Do not continue if basic fields invalid
            elif sale_date_obj < vest_date:
                 error_messages.append(f"Row {index+1} (Sale ID: {sale_id}): Sale Date ({sale_date_obj}) cannot be before Vest Date ({vest_date}).")
                 validation_passed = False
                 # Do not continue if date invalid

            # Only add valid IDs to the set
            if validation_passed or sale_id not in edited_sale_ids:
                edited_sale_ids.add(sale_id)

            # If validation for this row passed...
            if validation_passed:
                # Prepare sale data dictionary and calculate derived fields
                tax_rate = tax_rate_pct_val / 100.0
                holding_period = (sale_date_obj - vest_date).days
                held_over_year = holding_period > 365

                capital_gains = calculate_gains_at_sale(sale_price_val, vest_price, shares_val)
                capital_gains_tax = calculate_capital_gains_tax(sale_price_val, vest_price, shares_val, tax_rate, held_over_year, holding_period)
                tax_within_30_days = None
                if holding_period <= 30:
                    tax_within_30_days = calculate_tax_at_vest(shares_val, sale_price_val, tax_rate) # Note: Using sale price as per original logic if sold within 30 days

                sale_data = {
                    "sale_id": sale_id,
                    "vest_id": selected_vest_id, # Explicitly link to the selected vest
                    "sale_date": sale_date_obj,
                    "shares_sold": shares_val,
                    "sale_price": sale_price_val,
                    "vest_date": vest_date, # Store associated vest date for reference/calcs
                    "tax_rate_sale": tax_rate,
                    "capital_gains": capital_gains,
                    "capital_gains_tax": capital_gains_tax,
                }
                if tax_within_30_days is not None:
                     sale_data["tax_within_30_days"] = tax_within_30_days

                edited_sales_list_for_vest.append(sale_data) # Add to the list of sales to keep/add for this vest

        # --- Final State Update Decision ---
        if not validation_passed:
            for msg in error_messages:
                st.error(msg)
            st.warning(f"Changes for Grant '{selected_grant_id}', Vest '{selected_vest_id}' sales not saved due to validation errors.")
        else:
            # Update the 'sales' list for the specific grant in session state only if all rows are valid
            # Filter out sales related to the current vest and replace with the edited list
            other_sales = [s for s in selected_grant.get("sales", []) if s.get("vest_id") != selected_vest_id]
            selected_grant["sales"] = other_sales + edited_sales_list_for_vest
            # Optional: Success message
            # st.success(f"Sales for grant '{selected_grant_id}', vest '{selected_vest_id}' updated!")

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
            # Find the corresponding vest first
            try:
                vest = next(v for v in grant["vests"] if v["vest_id"] == sale["vest_id"])
            except StopIteration:
                st.error(f"Data inconsistency: Vest ID '{sale.get('vest_id')}' not found for Sale ID '{sale.get('sale_id')}' in Grant '{grant.get('grant_id')}'. Skipping this sale in summary.")
                continue # Skip this sale if its vest is missing

            # Ensure tax_at_vest is calculated if missing (Defensive check)
            if "tax_at_vest" not in vest:
                 vest["tax_at_vest"] = calculate_tax_at_vest(
                     vest.get("shares_vested", 0), # Use .get for safety
                     vest.get("vest_price", 0),
                     vest.get("tax_rate_vest", 0)
                 )
                 # Note: This calculation might happen multiple times if multiple sales link to the same vest, but it's idempotent.

            # Ensure capital_gains_tax and capital_gains are calculated if missing (Defensive check)
            if "capital_gains_tax" not in sale or "capital_gains" not in sale:
                holding_period = (sale["sale_date"] - vest["vest_date"]).days
                held_over_year = holding_period > 365
                sale["capital_gains_tax"] = calculate_capital_gains_tax(
                    sale.get("sale_price", 0),
                    vest.get("vest_price", 0),
                    sale.get("shares_sold", 0),
                    sale.get("tax_rate_sale", 0),
                    held_over_year,
                    holding_period,
                )
                sale["capital_gains"] = calculate_gains_at_sale(
                    sale.get("sale_price", 0),
                    vest.get("vest_price", 0),
                    sale.get("shares_sold", 0)
                )
                # Also recalculate tax_within_30_days if applicable, as it depends on sale price
                if holding_period <= 30:
                    sale["tax_within_30_days"] = calculate_tax_at_vest(
                        sale.get("shares_sold", 0),
                        sale.get("sale_price", 0),
                        sale.get("tax_rate_sale", 0)
                    )


            # Now calculate tax_at_sale using the guaranteed keys
            holding_period = (sale["sale_date"] - vest["vest_date"]).days # Re-calc or use stored
            if holding_period <= 30 and "tax_within_30_days" in sale:
                tax_at_sale = sale["tax_within_30_days"]
            else:
                # Use .get for safety, defaulting to 0 if somehow still missing
                tax_at_sale = sale.get("capital_gains_tax", 0)

            # Append data using guaranteed keys (and .get for extra safety on calculated fields)
            sale_data.append({
                "Grant ID": grant["grant_id"],
                "Grant Date": grant["grant_date"],
                "Vest ID": vest["vest_id"],
                "Vest Date": vest["vest_date"],
                "Vest Price": vest.get("vest_price", 0),
                "Tax Rate at Vest (%)": vest.get("tax_rate_vest", 0) * 100,
                "Total vest proceeds" : vest.get("vest_price", 0) * sale.get("shares_sold", 0),
                "Tax at Vest": vest.get("tax_at_vest", 0), # Now guaranteed by check above
                "Vest proceeds after taxes" : (vest.get("vest_price", 0) * sale.get("shares_sold", 0) ) - vest.get("tax_at_vest", 0),
                "Sale ID": sale["sale_id"],
                "Sale Date": sale["sale_date"],
                "Shares Sold": sale.get("shares_sold", 0),
                "Sale Price": sale.get("sale_price", 0),
                "Tax Rate at Sale (%)": sale.get("tax_rate_sale", 0) * 100,
                "Total sale proceeds": sale.get("capital_gains", 0), # Guaranteed by check above
                "Tax at Sale": tax_at_sale,
                "Sale proceeds after taxes": sale.get("capital_gains", 0) - tax_at_sale,
                "Net Gain" : ((vest.get("vest_price", 0) * sale.get("shares_sold", 0) ) - vest.get("tax_at_vest", 0)) + (sale.get("capital_gains", 0) - tax_at_sale)
            })

    sales_df = pd.DataFrame(sale_data) if sale_data else pd.DataFrame() # Handle empty case
    st.dataframe(sales_df,
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

    # st.markdown("***This web app allows you to load RSU/Stocks data and calculate taxes for Australian financial year. Data is stored in the browser session so no data is sent back to server. As always, use at your own risk and this is not a financial advice at all.***")
    st.markdown("*Sample data available at:* ***https://raw.githubusercontent.com/binaryzer0/rsu-calculator/main/sample.json***")
    

    if "grants" not in st.session_state:
        st.session_state["grants"] = []
  
    # Sidebar details
    st.sidebar.header("About This App")
    st.sidebar.markdown(
        """
        <style>
        .small-font {
            font-size: 13px;  /* Adjust size as needed */
        }
        </style>
        <div class="small-font">
            <strong>RSU Tax Calculator – Simplify Your Equity Taxes</strong><br><br>
                Easily manage your Restricted Stock Units (RSUs) with this intuitive tax calculator.
                Track grants, vesting, and sales while automatically calculating taxes at each stage.
                Visualize your tax breakdown, capital gains, and stock performance with interactive charts.
                Stay in control of your RSU strategy and maximize your financial outcomes—all in one place.
                Data is stored in the browser session so no data is sent back to server.
                All values are assumed in a single currency.<br><br>
                As always, use at your own risk and this is not a financial advice at all.
        </div>
        """,
        unsafe_allow_html=True
    )
    # st.sidebar.info(
    #     "**RSU Tax Calculator – Simplify Your Equity Taxes**\n\n"
    #     "Easily manage your Restricted Stock Units (RSUs) with this intuitive tax calculator. "
    #     "Track grants, vesting, and sales while automatically calculating taxes at each stage. "
    #     "Visualize your tax breakdown, capital gains, and stock performance with interactive charts. "
    #     "Stay in control of your RSU strategy and maximize your financial outcomes—all in one place."
    #     "Data is stored in the browser session so no data is sent back to server."
    #     "All values are assumed in a single currency.\n\n"
    #     "As always, use at your own risk and this is not a financial advice at all."
    # )
    # https://buymeacoffee.com/binaryzer0

    # Add a button to load sample data
    st.sidebar.header("Try it")
    if st.sidebar.button("Load Sample Data"):
        load_sample_data()
    
    # Export/Import functionality
    st.sidebar.header("Export/Import Data")
    export_data(st.session_state["grants"])
    imported_data = import_data()
    if imported_data:
        st.session_state["grants"] = imported_data
        st.session_state["data_loaded"] = True
    
    st.sidebar.markdown("### ☕ Support This Project")
    st.sidebar.markdown(
        """
        <a href="https://buymeacoffee.com/binaryzer0" target="_blank">
            <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" 
                alt="Buy Me A Coffee" 
                width="200">
        </a>
        """,
        unsafe_allow_html=True
    )

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
            st.write("**Tax type breakdown by Australian Financial year table**")
            st.dataframe(tax_breakdown_table)

    # Capital Gains by Vest
    capital_gains_fig = plot_capital_gains_by_vest(st.session_state.get("grants", []))
    if capital_gains_fig:
        st.plotly_chart(capital_gains_fig)
        capital_gains_table = generate_capital_gains_table(st.session_state.get("grants", []))
        if capital_gains_table is not None:
            st.write("**Capital Gains/Loss Table by Australian Financial year table**")
            st.dataframe(capital_gains_table)

    # Net Gains
    net_gains_fig = plot_net_gains(st.session_state.get("grants", []))
    if net_gains_fig:
        st.plotly_chart(net_gains_fig)
        net_gains_table = generate_net_gains_table(st.session_state.get("grants", []))
        if net_gains_table is not None:
            st.write("**Gains vs Taxes by Australian Financial year Table**")
            st.dataframe(net_gains_table)

    # Stock Performance
    stock_performance_fig = plot_stock_performance(st.session_state.get("grants", []))
    if stock_performance_fig:
        st.plotly_chart(stock_performance_fig)
        stock_performance_table = generate_stock_performance_table(st.session_state.get("grants", []))
        if stock_performance_table is not None:
            st.write("**Stock Performance (Vest Price vs. Sale Price) table**")
            st.dataframe(stock_performance_table)

if __name__ == "__main__":
    main()
