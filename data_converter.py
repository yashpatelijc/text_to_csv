import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Text to CSV Converter", layout="wide")
st.title("Text File to Perfect CSV Converter")

st.markdown("""
This app lets you upload your raw OHLC data file (CSV or TXT).  
It cleans up column names (removing extra spaces), renames a **Last** column to **Close** if present,  
combines separate **Date** and **Time** columns into a single **Date** column,  
allows you to filter the data by date, and then download or save the processed CSV file.
""")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload your OHLC text file (CSV or TXT)", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        # Read the file assuming comma-separated values.
        df = pd.read_csv(uploaded_file, sep=",")
    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.stop()

    st.markdown("### Raw File Preview")
    st.dataframe(df.head())

    # --- Clean Column Names ---
    df.columns = df.columns.str.strip()  # Remove extra spaces from column names
    
    # Rename "Last" column to "Close" if it exists.
    if "Last" in df.columns:
        df.rename(columns={"Last": "Close"}, inplace=True)
    
    # --- Combine Date and Time Columns (if available) ---
    if "Date" in df.columns and "Time" in df.columns:
        st.info("Combining 'Date' and 'Time' columns into a single 'Date' column...")
        try:
            combined_datetime = df["Date"].astype(str) + " " + df["Time"].astype(str)
            # Let pandas infer the format (or specify your actual format here if known)
            df["Date"] = pd.to_datetime(
                combined_datetime,
                errors="coerce",               # force failures to NaT
                infer_datetime_format=True     # try to infer common datetime patterns
            )
            
            # how many rows failed?
            invalid = df["Date"].isna().sum()
            if invalid:
                st.warning(f"{invalid} rows failed to parse and will be dropped.")
                before = len(df)
                df = df.dropna(subset=["Date"])
                after = len(df)
                st.info(f"Dropped {before - after} rows after combining Date/Time.")
            
            # now you can safely drop Time
            df = df.drop(columns=["Time"])

        except Exception as e:
            st.error(f"Error combining Date and Time columns: {e}")
            st.stop()
    else:
        st.info("No separate 'Time' column found.")

    # --- Ensure Date Column is Datetime ---
    if "Date" in df.columns:
        # Force conversion to datetime and drop rows that cannot be parsed.
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", infer_datetime_format=True)
        if df["Date"].isnull().any():
            st.warning("Some rows have invalid Date values and will be dropped.")
            df = df.dropna(subset=["Date"])
        st.write("Date column type:", df["Date"].dtype)

        # --- DATA QUALITY LOG & FIX ---
        st.markdown("### Data Quality Log (Ordering & Duplicates)")

        # 1. Log Ordering Mistakes
        # Check if dates are monotonic increasing
        if not df["Date"].is_monotonic_increasing:
            st.warning("Data is not in strict chronological order.")
            # Find rows where the date is smaller than the previous row's date
            # These are the specific rows causing the disorder
            out_of_order_mask = df["Date"] < df["Date"].shift(1)
            out_of_order_rows = df[out_of_order_mask]
            
            with st.expander(f"View {len(out_of_order_rows)} Out-of-Order Rows"):
                st.write("The following rows appeared out of sequence and will be re-ordered:")
                st.dataframe(out_of_order_rows)
        else:
            st.success("Data is already in chronological order.")

        # 2. Fix Ordering (Sort)
        df = df.sort_values(by="Date")

        # 3. Log & Fix Duplicates
        # Check for duplicates after sorting
        if df.duplicated(subset=["Date"]).any():
            st.warning("Duplicate timestamps found.")
            
            # Identify all duplicates to show the user
            # keep=False marks ALL duplicates as True so we can see the groups
            dupes_log = df[df.duplicated(subset=["Date"], keep=False)].copy()
            
            # Mark the "Action" column
            # 'duplicated(keep='first')' returns False for the first occurrence (Keep) 
            # and True for subsequent ones (Remove)
            is_duplicate_subsequent = dupes_log.duplicated(subset=["Date"], keep='first')
            dupes_log["Action"] = "Kept"
            dupes_log.loc[is_duplicate_subsequent, "Action"] = "Removed"

            with st.expander(f"View {len(dupes_log)} Duplicate Rows & Actions"):
                st.write("The following table shows all duplicate timestamps and which row was kept vs removed:")
                st.dataframe(dupes_log)
            
            # Actually remove the duplicates from the main dataframe
            df = df.drop_duplicates(subset=["Date"], keep="first")
            st.info("Duplicates have been removed (kept the first occurrence).")
        else:
            st.success("No duplicate timestamps found.")

    else:
        st.error("No 'Date' column found in the file.")
        st.stop()

    st.markdown("### Processed File Preview")
    st.dataframe(df.head())

    # --- Date Range Filter ---
    st.markdown("### Date Range Filter")
    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()
    date_range = st.date_input("Select date range", [min_date, max_date], min_value=min_date, max_value=max_date)
    if len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]
        st.markdown("### Filtered Data Preview")
        st.dataframe(df_filtered.head())
    else:
        df_filtered = df

    # --- Save Options ---
    st.markdown("### Save Options")
    default_folder = "C:/Users/yash.patel/Python Projects/Algo_Builder/data/Product Data/New/"
    folder_path = st.text_input("Folder Path", value=default_folder)
    full_file_name = st.text_input("Full Processed File Name", value="converted_data.csv")
    filtered_file_name = st.text_input("Filtered File Name", value="filtered_data.csv")
    
    # Set the desired date format for CSV output
    date_fmt = "%m/%d/%Y %H:%M"
    
    # Convert DataFrames to CSV bytes using the specified date format.
    csv_data_full = df.to_csv(index=False, date_format=date_fmt).encode("utf-8")
    csv_data_filtered = df_filtered.to_csv(index=False, date_format=date_fmt).encode("utf-8")
    
    st.download_button(
        label="Download Complete Processed CSV",
        data=csv_data_full,
        file_name=full_file_name,
        mime="text/csv"
    )
    st.download_button(
        label="Download Filtered CSV",
        data=csv_data_filtered,
        file_name=filtered_file_name,
        mime="text/csv"
    )
    
    if st.button("Save Complete Processed CSV to Folder"):
        try:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            full_path = os.path.join(folder_path, full_file_name)
            # Added newline="" to prevent extra blank lines
            with open(full_path, "w", encoding="utf-8", newline="") as f:
                f.write(df.to_csv(index=False, date_format=date_fmt))
            st.success(f"File saved to {full_path}")
        except Exception as e:
            st.error(f"Error saving file: {e}")
    
    if st.button("Save Filtered CSV to Folder"):
        try:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            filtered_path = os.path.join(folder_path, filtered_file_name)
            # Added newline="" to prevent extra blank lines
            with open(filtered_path, "w", encoding="utf-8", newline="") as f:
                f.write(df_filtered.to_csv(index=False, date_format=date_fmt))
            st.success(f"Filtered file saved to {filtered_path}")
        except Exception as e:
            st.error(f"Error saving file: {e}")
else:
    st.info("Please upload a file to begin the conversion process.")