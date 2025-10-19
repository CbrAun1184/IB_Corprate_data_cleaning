import csv
import json
import re
from datetime import datetime
from importlib.metadata import requires


def validate_email(email):
    """
    Validates the format of an email address.
    :param email:
    :return:
    """
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(regex,email)

def log_message(log_file, message):
    """
    Write a message to the job log file.
    :param log_file:
    :param message:
    :return:
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_file.write(f"[{timestamp}] {message}\n")

def main():
    """
    Main function to validate the CSV data
    :return:
    """
    try:
        with open('validation_rules.json','r') as f:
            rules = json.load(f)
    except FileNotFoundError:
        print("Error: validation rules.json not found")
        return

    input_csv_file = 'Corprate_data_dummy.csv'
    clean_data_csv = 'clean_data.csv'
    error_data_csv = 'error_data.csv'
    job_log_file = 'job_log.txt'

    try:
        with open(input_csv_file,'r',newline='') as infile, \
             open(clean_data_csv,'w',newline='') as clean_file, \
             open(error_data_csv,'w',newline='') as error_file, \
             open(job_log_file,'w') as log:

            reader = csv.reader(infile)
            clean_writer = csv.writer(clean_file)
            error_writer = csv.writer(error_file)

            header = next(reader)
            # Rename columns to match JSON keys
            header_map = {
                'Mobile_No': 'Mobile_no',
                'AC_NO': 'Acc_no'
            }
            processed_header = [header_map.get(h, h) for h in header]

            clean_writer.writerow(header)
            error_header = header + ['error_desc']
            error_writer.writerow(error_header)

            log_message(log, "Job Started: Data Validation")

            for i, row in enumerate(reader,1):
                # Create a dictionary from the row
                try:
                    row_data = dict(zip(processed_header, row))
                except IndexError:
                    log_message(log, f"ERROR: Row{i} has incorrect number of columns. Skipping")
                    continue

                error_description = []

                # --- Field-by-field validation ---

                # 1. USPCID Validation
                uspcid = row_data.get('USPCID','').strip()
                if rules['USCLID']['required'] and not uspcid:
                    error_description.append("missing USPCID")

                # 2. USCLID  Validation
                usclid = row_data.get('USPCID', '').strip()
                if rules['USCLID']['required'] and not usclid:
                    error_description.append("missing USCLID")

                # 3. Email Validation
                email = row_data.get('email_add', '').strip()
                if rules['email_add']['required'] and not email:
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
                        log_message(log, f"INFO: USPCID '{uspcid}', USCLID '{usclid}' mobile_no changed from '{original_mobile}' to '{mobile}'.")
                        row_data['Mobile_no'] = mobile

                    if not mobile.isdigit() or len(mobile) != 5:
                        error_description.append(f"invalid mobile number format: {original_mobile}")
                    else:
                        first_digit = mobile[0]
                        if first_digit in ['2','3','4']:
                            log_message(log, F"WARNING: USPCID '{uspcid}',USCLID '{usclid}' number '{mobile} is not a mobile number.'")
                        elif first_digit not in ['5','7','8']:
                            log_message(log, f"WARNING USPCID '{uspcid}' , USCLID '{usclid}' ,has a mobile number '{mobile}' outside expected ranges.")
                else:
                    log_message(log, f"INFO: USPCID '{uspcid}', USCLID '{usclid}' has no mobile number.")

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
                        log_message(log, f"INFO: USPCID '{uspcid}', USCLID '{usclid}' Acc_no changed from '{original_acc_no}' to '{acc_no}'.")

                # 6 Date of Birth (DOB) validation and formatting
                dob_str = row_data.get('DOB', '').strip()
                if rules['DOB']['required'] and not dob_str:
                    error_description.append("invalid date of birth")
                elif dob_str:
                    try:
                        # Attempt to parse and reforamt to ensure correctness
                        dob_obj = datetime.strptime(dob_str,'%d/%m/%Y')
                        row_data['DOB'] = dob_obj.strftime('%d/%m/%Y')
                    except ValueError:
                        # Simple attempt tp fix common issues, like wring separators
                        try:
                            corrected_dob = dob_str.replace('-','/').replace('.','/')
                            dob_obj = datetime.strptime(corrected_dob,'%d/%m/%Y')
                            row_data['DOB'] = dob_obj.strftime('%d/%m/%Y')
                            log_message(log, f"INFO: USPCID '{uspcid}', USCLID '{usclid}' DOB '{dob_str}' was corrected to ' {row_data['DOB']}'.")
                        except ValueError:
                            error_description.append("invalid date of birth")

                # --- Write to appropriate file ---
                if error_description:
                    error_row = list(row_data.values())
                    # Ensure the row has the same number of columns as the original header
                    original_row_values = [row_data.get(h,'') for h in processed_header]
                    error_writer.writerow(original_row_values + [",".join(error_description)])
                else:
                    # Write the cleaned row back in the original header
                    clean_row = [row_data.get(h,'') for h in processed_header]
                    clean_writer.writerow(clean_row)

            log_message(log, "Job Finished.")

    except FileNotFoundError:
        print(f"Error: Input file '{input_csv_file}' not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    main()