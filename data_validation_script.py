import csv
import json
import re
import logging
from datetime import datetime

def configure_logging():
    """
    Configures logging to a file with a timestamp.
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'job_log_{timestamp}.txt'
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filemode='w'
    )
    return log_filename

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
    log_filename = configure_logging()
    print(f"Logging to {log_filename}")

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

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    input_csv_file = 'Corprate_data_dummy.csv'
    clean_data_csv = f'clean_data_{timestamp}.csv'
    error_data_csv = f'error_data_{timestamp}.csv'

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

                if mobile:
                    # Remove country code prefixes
                    if mobile.startswith('+682'):
                        mobile = mobile[4:].strip()
                    elif mobile.startswith('682'):
                        mobile = mobile[3:].strip()

                    if mobile != original_mobile:
                        logging.info(f"USPCID '{uspcid}', USCLID '{usclid}' mobile_no changed from '{original_mobile}' to '{mobile}'.")
                        row_data['Mobile_no'] = mobile

                    if not mobile.isdigit():
                        logging.warning(f"USPCID '{uspcid}', USCLID '{usclid}' has an invalid mobile number format: {original_mobile}")
                    elif len(mobile) != 7:
                        logging.warning(f"USPCID '{uspcid}', USCLID '{usclid}' has an invalid mobile number format: {original_mobile}")
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
                dob_rule = rules.get('DOB', {})
                is_required = dob_rule.get('required', False)
                date_format_str = dob_rule.get('format', 'DD/MM/YYYY').replace('DD', '%d').replace('MM', '%m').replace('YYYY', '%Y')

                if not dob_str:
                    if is_required:
                        error_description.append("missing date of birth")
                else:
                    try:
                        # Attempt to parse and reformat to ensure correctness
                        dob_obj = datetime.strptime(dob_str, date_format_str)
                        row_data['DOB'] = dob_obj.strftime(date_format_str)
                    except ValueError:
                        # Simple attempt to fix common issues, like wrong separators
                        try:
                            corrected_dob = dob_str.replace('-', '/').replace('.', '/')
                            dob_obj = datetime.strptime(corrected_dob, date_format_str)
                            row_data['DOB'] = dob_obj.strftime(date_format_str)
                            logging.info(f"USPCID '{uspcid}', USCLID '{usclid}' DOB '{dob_str}' was corrected to '{row_data['DOB']}'.")
                        except ValueError:
                            error_description.append("invalid date of birth")

                # --- Write to appropriate file ---
                if error_description:
                    error_writer.writerow(original_row_values + [",".join(error_description)])
                else:
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
