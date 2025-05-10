# File path: run_ingestion.py
#!/usr/bin/env python3
import logging
import sys
from pathlib import Path

# --- Determine Project Root (More Robust Method) ---
# This assumes 'run_ingestion.py' is in 'RiskAgentAPP/scripts/'
# If your structure is different, adjust accordingly.
try:
    SCRIPT_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = SCRIPT_DIR.parent # Goes up one level from 'scripts' to 'RiskAgentAPP'
except NameError:
    # __file__ is not defined if running interactively or via some tools
    # Fallback to assuming current working directory is project root
    PROJECT_ROOT = Path.cwd()
    logging.warning(f"Could not determine script directory, assuming project root is CWD: {PROJECT_ROOT}")

# --- Add Project Root to Python Path ---
# This helps ensure modules are found correctly regardless of CWD
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    logging.info(f"Added project root to sys.path: {PROJECT_ROOT}")

# --- Imports (Now should work reliably) ---
try:
    from backend.ingestion import ingest_documents
    from scripts.create_sample_data import create_samples
except ImportError as e:
    logging.error(f"Failed to import modules. Is the script run correctly relative to the project root? Error: {e}")
    logging.error(f"Current sys.path: {sys.path}")
    sys.exit(1)

# --- Logging Configuration ---
# (Your existing logging config seems fine, keeping it)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Main Function ---
def main():
    # Define directory relative to project root
    sample_data_dir = PROJECT_ROOT / "database" / "sample_data"
    expected_file_count = 105 # 35 samples * 3 file types

    logging.info(f"Target sample data directory: {sample_data_dir.resolve()}")

    # Ensure the sample data directory exists
    try:
        sample_data_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Ensured directory exists: {sample_data_dir.resolve()}")
    except OSError as e:
        logging.error(f"Failed to create directory {sample_data_dir}: {e}")
        sys.exit(1) # Stop if we can't create the dir

    # --- Generate Sample Data ---
    logging.info(f"Generating {expected_file_count} sample files in {sample_data_dir}...")
    try:
        # Pass the absolute path as a string to create_samples
        create_samples(output_dir=str(sample_data_dir), count=35)
        logging.info("Sample data generation attempt complete.")
    except Exception as e:
        logging.error(f"Error during create_samples execution: {e}", exc_info=True) # Log traceback
        # Decide whether to continue or exit - let's exit if generation fails
        sys.exit(1)

    # --- Verification Step ---
    logging.info(f"Verifying files in {sample_data_dir.resolve()}...")
    try:
        # Use glob to find all files matching the expected patterns directly
        found_files = list(sample_data_dir.glob('ticket_*.txt'))
        found_files.extend(list(sample_data_dir.glob('ticket_*.pdf')))
        found_files.extend(list(sample_data_dir.glob('ticket_*.docx')))

        actual_count = len(found_files)
        logging.info(f"Verification found {actual_count} files matching ticket_*.{{txt,pdf,docx}} pattern.")

        if actual_count != expected_file_count:
             logging.warning(f"Expected {expected_file_count} files, but verification found {actual_count}.")
             # Log counts per extension found by glob
             txt_count = len(list(sample_data_dir.glob('ticket_*.txt')))
             pdf_count = len(list(sample_data_dir.glob('ticket_*.pdf')))
             docx_count = len(list(sample_data_dir.glob('ticket_*.docx')))
             logging.warning(f"Counts: TXT={txt_count}, PDF={pdf_count}, DOCX={docx_count}")
             # List some found files for checking
             logging.info(f"Sample of files found by verification: {[f.name for f in found_files[:15]]}")
        else:
            logging.info(f"Successfully verified {actual_count} files.")

    except Exception as e:
        logging.error(f"Error during file verification step: {e}", exc_info=True)
        sys.exit(1) # Exit if verification fails

    # --- Check if file count is zero before proceeding ---
    if actual_count == 0:
        logging.error("Verification found zero matching files. Aborting ingestion.")
        sys.exit(1)

    # --- Start Ingestion ---
    logging.info(f"Starting ingestion process for directory: {sample_data_dir}...")
    # Pass the absolute path as a string to ingest_documents
    ingest_documents(str(sample_data_dir))
    logging.info("Ingestion process finished.")

    # Note: The DB check part seems external or added manually by you previously.
    # You would need to add DB query logic here if you want this script to report the final count.


if __name__ == "__main__":
    main()
