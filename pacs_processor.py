import shutil
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List

import pandas as pd

# --- CONFIGURATION ---
class Config:
    # Use the script's location as the base, or default to current working directory if script location is unknown
    BASE_DIR = Path(__file__).parent / "PACS002" if "__file__" in globals() else Path("PACS002")
    PENDING_DIR = BASE_DIR / "Pending"
    PROCESSED_DIR = BASE_DIR / "Processed"
    OUTPUT_EXCEL = BASE_DIR / "PACS002_Error_Report.xlsx"

    # Namespaces based on your sample file
    NAMESPACES = {
        'saa': 'urn:swift:saa:xsd:saa.2.0',
        'pacs': 'urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10',
        'head': 'urn:iso:std:iso:20022:tech:xsd:head.001.001.02'
    }

    REQUIRED_MSG_ID = "pacs.002.001.10"
    MAX_WORKERS = 5

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_text_safe(element: Optional[ET.Element], path: str, ns: Optional[Dict[str, str]] = None) -> str:
    """
    Helper to extract text from an XML element.
    Returns 'Not Found' if the tag is missing or the element is None.
    """
    if element is None:
        return "Not Found"
    try:
        found = element.find(path, ns)
        if found is not None and found.text:
            return found.text.strip()
        return "Not Found"
    except Exception as e:
        logger.debug(f"Error extracting path '{path}': {e}")
        return "Not Found"

def extract_data_from_xml(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parses a single XML file and extracts the required fields.
    Returns a dictionary with the data or None if extraction fails or validation fails.
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # --- CONDITION D: Check MessageIdentifier ---
        # Note: Depending on XML structure, header might be namespaced or not.
        # We try finding it with the 'saa' namespace first.
        msg_id_tag = root.find('.//saa:MessageIdentifier', Config.NAMESPACES)

        if msg_id_tag is None:
            # Fallback in case namespace prefix isn't strictly enforced in Header
            msg_id_tag = root.find('.//MessageIdentifier')

        if msg_id_tag is None or msg_id_tag.text != Config.REQUIRED_MSG_ID:
            logger.warning(f"Skipping {file_path.name}: Incorrect MessageIdentifier or Header not found.")
            return None

        # --- Navigate to the Document Body ---
        # The relevant data is inside Body > Document > FIToFIPmtStsRpt
        doc_root = root.find('.//pacs:FIToFIPmtStsRpt', Config.NAMESPACES)

        if doc_root is None:
            logger.warning(f"Skipping {file_path.name}: FIToFIPmtStsRpt block not found.")
            return None

        # --- DATA EXTRACTION ---
        # We look inside TxInfAndSts as that is where transaction level details live
        tx_inf = doc_root.find('./pacs:TxInfAndSts', Config.NAMESPACES)

        data_row = {
            'File Name': file_path.name,
            'MsgId': get_text_safe(doc_root, './pacs:GrpHdr/pacs:MsgId', Config.NAMESPACES),
            'OrgnlMsgId': get_text_safe(tx_inf, './pacs:OrgnlGrpInf/pacs:OrgnlMsgId', Config.NAMESPACES),
            'OrgnlCreDtTm': get_text_safe(tx_inf, './pacs:OrgnlGrpInf/pacs:OrgnlCreDtTm', Config.NAMESPACES),
            'TxSts': get_text_safe(tx_inf, './pacs:TxSts', Config.NAMESPACES),
            'Reason Cd': get_text_safe(tx_inf, './pacs:StsRsnInf/pacs:Rsn/pacs:Cd', Config.NAMESPACES),
            'AddtlInf': get_text_safe(tx_inf, './pacs:StsRsnInf/pacs:AddtlInf', Config.NAMESPACES),
            'InstgAgt BIC': get_text_safe(tx_inf, './pacs:InstgAgt/pacs:FinInstnId/pacs:BICFI', Config.NAMESPACES),
            'InstdAgt BIC': get_text_safe(tx_inf, './pacs:InstdAgt/pacs:FinInstnId/pacs:BICFI', Config.NAMESPACES),
            'OrgnInstrId': get_text_safe(tx_inf, './pacs:OrgnlInstrId', Config.NAMESPACES)
        }

        return data_row

    except ET.ParseError as e:
        logger.error(f"XML Parse Error in {file_path.name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error processing {file_path.name}: {e}")
        return None

def process_file_wrapper(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Wrapper for processing a file to be used in ThreadPoolExecutor.
    """
    return extract_data_from_xml(file_path)

def main():
    # --- SETUP DIRECTORIES ---
    if not Config.PENDING_DIR.exists():
        logger.error(f"Directory '{Config.PENDING_DIR}' does not exist.")
        return

    # Create Processed directory if it doesn't exist
    Config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # List all XML and TXT files (using glob with case checking)
    # Note: glob is case-sensitive on Linux. To handle .XML, .xml, .TXT, .txt, etc.
    # we can iterate over all files and check extensions.

    all_files = [
        f for f in Config.PENDING_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in ('.xml', '.txt')
    ]

    if not all_files:
        logger.info("No valid files found in Pending folder.")
        return

    logger.info(f"Found {len(all_files)} files. Processing...")

    results: List[Dict[str, Any]] = []
    processed_files: List[Path] = []

    # --- MULTI-THREADING (Condition E) ---
    # Using ThreadPoolExecutor to process files in parallel
    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        # Submit all files to the executor
        future_to_file = {executor.submit(process_file_wrapper, f): f for f in all_files}

        for future in future_to_file:
            file_path = future_to_file[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
                    processed_files.append(file_path)
            except Exception as exc:
                logger.error(f"{file_path.name} generated an exception: {exc}")

    # --- SAVE TO EXCEL ---
    if results:
        df = pd.DataFrame(results)

        # Re-ordering columns to match your list exactly
        columns_order = [
            'File Name', 'MsgId', 'OrgnlMsgId', 'OrgnlCreDtTm',
            'TxSts', 'Reason Cd', 'AddtlInf', 'InstgAgt BIC', 'InstdAgt BIC', 'OrgnInstrId'
        ]

        # Ensure only columns that exist are selected (in case of logic update)
        final_cols = [c for c in columns_order if c in df.columns]
        df = df[final_cols]

        try:
            df.to_excel(Config.OUTPUT_EXCEL, index=False)
            logger.info(f"Successfully created '{Config.OUTPUT_EXCEL}' with {len(df)} rows.")

            # --- MOVE FILES (Condition B & C) ---
            logger.info("Moving processed files...")
            for file_path in processed_files:
                dst = Config.PROCESSED_DIR / file_path.name
                try:
                    # shutil.move handles path objects in newer Python versions
                    shutil.move(str(file_path), str(dst))
                except Exception as e:
                    logger.error(f"Could not move {file_path.name}: {e}")
            logger.info("Done.")

        except Exception as e:
            logger.error(f"Error saving Excel file: {e}")
            logger.warning("Files were NOT moved due to Excel save error.")
    else:
        logger.info("No valid data extracted. Excel file not created.")

if __name__ == '__main__':
    main()
