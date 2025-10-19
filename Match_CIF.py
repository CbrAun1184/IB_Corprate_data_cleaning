from csv import excel
import pandas as pd

def perform_xlookup_equivalent(file_path):
    """
    Perform a data lookup operation equivalent to XLOOKUP in the Excel
    to move columns D anf E from sheet1 into columns B and C
    of the IBUSRQDC1_sm sheet, matching on column B of sheet1 and
    column I of IBUSRQDC1__sm.

    Args:
        file_path (str): The path of the Excel file containing both sheets
    :param file_path:
    :return:
    """

    try:
        # 1. Read the two required sheets into separate DataFrames
        df_target = pd.read_excel(file_path, sheet_name='IBUSRQDC1__sm')
        df_source = pd.read_excel(file_path, sheet_name='Sheet1')

        # 2. Select the columns needed from the source sheet (sheet1)
        # We need the match column (B) and the data columns (D,E)
        df_source_lookup =   df_source[['B','D','E']]

        # Rename columns to their descriptive names or final names for clarity before merge
        # Assuming the column names are just B, D, E in Sheet1 and I in IBUSRQDC1__sm
        df_target.rename(columns={'I': 'Match_Key'}, inplace=True)
        df_source_lookup.rename(columns={'B': 'Match_Key',
                                          'D': 'New_Col_C_Data',
                                          'E': 'New_col_B_Data'}, inplace=True)

        # 3. Perform the 'XLOOKUP' equivalent using a left merge
        # 'left' merge ensures all rows from the target sheet are kept (like XLOOUP)
        # We join on 'Match_key' (Sheet1B:B and ISUSRQDC1__sm!I:I)
        df_final = pd.merge(
            df_target,
            df_source_lookup,
            on='Match_Key',
            how='left'
        )

        # 4. Prepare the final DataFrame for output
        # Rename the columns to their target names (B and C)
        # Note: DataFrames column names are not restricted to A, B, C... like Excel
        df_final.rename(columns={'New_Col_B_Data': 'B (from E)',
                                 'New_Col_C_Data': 'C (from D)',
                                 'Match_Key': 'I'}, inplace=True)

        # Handle 'Not Found' equivalent: pandas uses NaN for non-matches.
        # We can fill NaNs in the new columns with a string like "Not Found"
        df_final['B (from E)'].fillna('Not Found',inplace=True)
        df_final['C (from D)'].fillna('Not Found',inplace=True)

        # 5. Write the result to a new Excel file
        output_file = 'Result_IBUSRQDC1_sm_with_lookups.xlsx'
        df_final.to_excel(output_file,sheet_name='IBUSRQDC1__sm_Result', index=False)

        print(f"✅ Success! Data has been merged and saved to: {output_file}")

    except FileNotFoundError:
        print(f"❌ Error: The file at path '{file_path}' was not found)
    except ValueError as e:
        print(f"❌ Error reading sheets. Check if the sheet names 'IBUSRQDC1__sm' and 'Sheet1' are correct.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- Set the path to your Excel file ---
excel_file_path = 'your_excel_file.xlsx'

# Call the function to run the process
perform_xlookup_equivalent(excel_file_path)




