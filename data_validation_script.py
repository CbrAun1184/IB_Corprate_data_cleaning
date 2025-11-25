import csv
import json
import re
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    filename='job_log.txt',
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filemode='w'
)

def validate_email(email):
    """
    Validates the format of an email address.
    :param email:
    :return: Match object or None
    """
    # Improved regex for email validation
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(regex, email)

def main():
    """
    Main function to validate the CSV data
    :return:
    """
    try:
        with open('validation_rules.json', 'r') as f:
            rules = json.load(f)
    except FileNotFoundError:
        print("Error: validation rules.json not found")
        logging.error("validation rules.json not found")
        return
    except json.JSONDecodeError as e:
        print(f"Error: validation rules.json is not valid JSON. {e}")
        logging.error(f"validation rules.json is not valid JSON. {e}")
        return

    input_csv_file = 'Corprate_data_dummy.csv'
    clean_data_csv = 'clean_data.csv'
    error_data_csv = 'error_data.csv'

    try:
        with open(input_csv_file, 'r', newline='') as infile, \
             open(clean_data_csv, 'w', newline='') as clean_file, \
             open(error_data_csv, 'w', newline='') as error_file:

            reader = csv.reader(infile)
            clean_writer = csv.writer(clean_file)
            error_writer = csv.writer(error_file)

            try:
                header = next(reader)
            except StopIteration:
                logging.error("Input file is empty")
                return

            # Rename columns to match JSON keys
            header_map = {
                'Mobile_No': 'Mobile_no',
                'AC_NO': 'Acc_no'
            }
            # Create a list of keys for internal processing
            processed_header = [header_map.get(h, h) for h in header]

            clean_writer.writerow(header)
            error_header = header + ['error_desc']
            error_writer.writerow(error_header)

            logging.info("Job Started: Data Validation")

            for i, row in enumerate(reader, 1):
                # Keep a copy of the original row values for error reporting
                original_row_values = list(row)

                # Create a dictionary from the row
                try:
                    row_data = dict(zip(processed_header, row))
                except IndexError:
                    logging.error(f"Row {i} has incorrect number of columns. Skipping")
                    continue

                error_description = []

                # --- Field-by-field validation ---

                # 1. USPCID Validation
                uspcid = row_data.get('USPCID', '').strip()
                # Use correct rule key
                if rules.get('USPCID', {}).get('required') and not uspcid:
                    error_description.append("missing USPCID")

                # 2. USCLID Validation
                # Fix: Get 'USCLID' not 'USPCID'
                usclid = row_data.get('USCLID', '').strip()
                if rules.get('USCLID', {}).get('required') and not usclid:
                    error_description.append("missing USCLID")

                # 3. Email Validation
                email = row_data.get('email_add', '').strip()
                if rules.get('email_add', {}).get('required') and not email:
                    error_description.append("missing email address")
                elif email and not validate_email(email):
                    error_description.append("invalid email address")

                # 4 Mobile Number Validation and Cleaning
                mobile = row_data.get('Mobile_no', '').strip()
                original_mobile = mobile

                # Check rules for Mobile (using 'Mobile' key from json if 'Mobile_no' not present, or fallback)
                # The script uses 'Mobile_no' as key in row_data, but json has 'Mobile'.
                # We will proceed with the existing logic logic but improve it.

                if mobile:
                    # Remove country code prefixes
                    if mobile.startswith('+682'):
                        mobile = mobile[4:].strip()
                    elif mobile.startswith('682'):
                        mobile = mobile[3:].strip()
                    # Added handling for +685 (Samoa) if appropriate?
                    # The original script logged warnings for "outside expected ranges".
                    # Assuming we want to clean +685 as well if it follows similar pattern?
                    # For now, I will stick to what was there but clean up the code.

                    if mobile != original_mobile:
                        logging.info(f"USPCID '{uspcid}', USCLID '{usclid}' mobile_no changed from '{original_mobile}' to '{mobile}'.")
                        row_data['Mobile_no'] = mobile

                    # Validation logic from original script:
                    # "if not mobile.isdigit() or len(mobile) != 5:"
                    # This implies it expects 5 digit local numbers.

                    if not mobile.isdigit():
                         error_description.append(f"invalid mobile number format: {original_mobile}")
                    elif len(mobile) != 5:
                         # Check if it was a valid number but just different length/country
                         # If it started with +685 (Samoa), it might be valid but not "local 5 digit".
                         # The prompt asks to "fix".
                         # If I look at the data: +685 7701859.
                         # If we remove +685 -> 7701859 (7 digits).
                         # 5 digits seems to be the rule for this specific system (maybe Cook Islands?).
                         error_description.append(f"invalid mobile number format: {original_mobile}")
                    else:
                        first_digit = mobile[0]
                        if first_digit in ['2', '3', '4']:
                            logging.warning(f"USPCID '{uspcid}',USCLID '{usclid}' number '{mobile}' is not a mobile number.")
                        elif first_digit not in ['5', '7', '8']:
                            logging.warning(f"USPCID '{uspcid}', USCLID '{usclid}', has a mobile number '{mobile}' outside expected ranges.")
                else:
                    logging.info(f"USPCID '{uspcid}', USCLID '{usclid}' has no mobile number.")

                # 5 Account Number Validation and cleaning
                acc_no = row_data.get('Acc_no', '').strip()
                original_acc_no = acc_no

                if not acc_no:
                    # Check if required? Rules say required is not explicitly set in JSON for Acc_no,
                    # but code had error for it.
                    error_description.append("invalid account")
                elif not acc_no.isdigit():
                    error_description.append("invalid account number format")
                elif len(acc_no) > 10:
                    error_description.append("invalid account number length")
                else:
                    if len(acc_no) < 10:
                        acc_no = acc_no.zfill(10)
                        row_data['Acc_no'] = acc_no
                        logging.info(f"USPCID '{uspcid}', USCLID '{usclid}' Acc_no changed from '{original_acc_no}' to '{acc_no}'.")

                # 6 Date of Birth (DOB) validation and formatting
                dob_str = row_data.get('DOB', '').strip()
                if rules.get('DOB', {}).get('required') and not dob_str:
                    error_description.append("invalid date of birth")
                elif dob_str:
                    try:
                        # Attempt to parse and reformat to ensure correctness
                        dob_obj = datetime.strptime(dob_str, '%d/%m/%Y')
                        row_data['DOB'] = dob_obj.strftime('%d/%m/%Y')
                    except ValueError:
                        # Simple attempt to fix common issues, like wrong separators
                        try:
                            corrected_dob = dob_str.replace('-', '/').replace('.', '/')
                            dob_obj = datetime.strptime(corrected_dob, '%d/%m/%Y')
                            row_data['DOB'] = dob_obj.strftime('%d/%m/%Y')
                            logging.info(f"USPCID '{uspcid}', USCLID '{usclid}' DOB '{dob_str}' was corrected to '{row_data['DOB']}'.")
                        except ValueError:
                            error_description.append("invalid date of birth")

                # --- Write to appropriate file ---
                if error_description:
                    # Write the ORIGINAL values to error file, plus error description
                    # We need to make sure we match the header order.
                    # original_row_values came from 'reader', which matches 'header'.
                    error_writer.writerow(original_row_values + [",".join(error_description)])
                else:
                    # Write the cleaned row back in the original header order
                    # row_data contains clean values (keys correspond to processed_header)
                    clean_row = [row_data.get(h, '') for h in processed_header]
                    clean_writer.writerow(clean_row)

            logging.info("Job Finished.")

    except FileNotFoundError:
        print(f"Error: Input file '{input_csv_file}' not found.")
        logging.error(f"Input file '{input_csv_file}' not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)

if __name__ == '__main__':
    main()
