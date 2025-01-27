# data_handling.py
# Changes:
# 1. Added session state flag "data_loaded" to track if data is imported via JSON.
# 2. No other changes to core functionality.

import json
from datetime import datetime, date
import streamlit as st

def convert_dates_to_strings(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_dates_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates_to_strings(item) for item in obj]
    return obj

def convert_strings_to_dates(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.endswith("_date") and isinstance(value, str):
                obj[key] = datetime.strptime(value, "%Y-%m-%d").date()
            elif isinstance(value, (dict, list)):
                convert_strings_to_dates(value)
    elif isinstance(obj, list):
        for item in obj:
            convert_strings_to_dates(item)
    return obj

def export_data(grants):
    if not grants:
        st.warning("No data to export.")
        return

    grants_serializable = convert_dates_to_strings(grants)

    st.sidebar.download_button(
        label="Export Data",
        data=json.dumps(grants_serializable, indent=2),
        file_name="rsu_data.json",
        mime="application/json",
    )

def import_data():
    uploaded_file = st.sidebar.file_uploader("Import Data", type=["json"])
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            data = convert_strings_to_dates(data)

            def remove_calculatable_keys(obj):
                if isinstance(obj, dict):
                    for key, value in list(obj.items()):
                        if key in ["capital_gains_tax", "tax_at_vest"]:
                            del obj[key]
                        elif isinstance(value, (dict, list)):
                            remove_calculatable_keys(value)
                elif isinstance(obj, list):
                    for item in obj:
                        remove_calculatable_keys(item)
                return obj

            data = remove_calculatable_keys(data)

            st.success("Data imported successfully!")
            st.session_state["data_loaded"] = True
            return data
        except json.JSONDecodeError:
            st.error("Invalid JSON file. Please upload a valid JSON file.")
    return None