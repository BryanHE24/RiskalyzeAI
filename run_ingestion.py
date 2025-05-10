# File path: run_ingestion.py
#!/usr/bin/env python3
import logging # Ensure logging is imported first
import sys
from pathlib import Path

# --- Basic Logging Configuration (AT THE VERY TOP) ---
# This should be the first effective call to configure logging for the application.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # Force output to stdout for console visibility
    ]
)
# Create a logger for this main script
logger = logging.getLogger("RUN_INGESTION_MAIN")

# --- Determine Project Root ---
# Assumes run_ingestion.py is in the project root directory
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR

# --- Add Project Root to Python Path ---
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    logger.info(f"Added project root to sys.path: {PROJECT_ROOT}")

# --- Imports (Now should work reliably) ---
try:
    from backend.ingestion import ingest_documents
    from scripts.create_sample_data import create_samples # Assuming create_sample_data.py is in scripts/
except ImportError as e:
    logger.error(f"Failed to import modules. Is the script run correctly relative to the project root? Error: {e}", exc_info=True)
    logger.error(f"Current sys.path: {sys.path}")
    logger.error(f"PROJECT_ROOT was set to: {PROJECT_ROOT}")
    sys.exit(1)
except Exception as ex:
    logger.error(f"An unexpected error occurred during imports: {ex}", exc_info=True)
    sys.exit(1)

# --- Main Function ---
def main():
    logger.info("--- Starting run_ingestion.py script ---")
    # Define directory relative to project root
    sample_data_dir = PROJECT_ROOT / "database" / "sample_data"
    expected_file_count = 105 # 35 samples * 3 file types

    logger.info(f"Target sample data directory: {sample_data_dir.resolve()}")

    # Ensure the sample data directory exists
    try:
        sample_data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {sample_data_dir.resolve()}")
    except OSError as e:
        logger.error(f"Failed to create directory {sample_data_dir}: {e}", exc_info=True)
        sys.exit(1)

    # --- Generate Sample Data ---
    logger.info(f"Generating {expected_file_count} sample files in {sample_data_dir}...")
    try:
        create_samples(output_dir=str(sample_data_dir), count=35)
        logger.info("Sample data generation attempt complete.")
    except Exception as e:
        logger.error(f"Error during create_samples execution: {e}", exc_info=True)
        sys.exit(1)

    # --- Verification Step ---
    logger.info(f"Verifying files in {sample_data_dir.resolve()}...")
    actual_count = 0
    try:
        found_files = list(sample_data_dir.glob('ticket_*.txt'))
        found_files.extend(list(sample_data_dir.glob('ticket_*.pdf')))
        found_files.extend(list(sample_data_dir.glob('ticket_*.docx')))

        actual_count = len(found_files)
        logger.info(f"Verification found {actual_count} files matching ticket_*.{{txt,pdf,docx}} pattern.")

        if actual_count != expected_file_count:
             logger.warning(f"Expected {expected_file_count} files, but verification found {actual_count}.")
             txt_count = len(list(sample_data_dir.glob('ticket_*.txt')))
             pdf_count = len(list(sample_data_dir.glob('ticket_*.pdf')))
             docx_count = len(list(sample_data_dir.glob('ticket_*.docx')))
             logger.warning(f"Counts: TXT={txt_count}, PDF={pdf_count}, DOCX={docx_count}")
             logger.info(f"Sample of files found by verification: {[f.name for f in found_files[:15]]}")
        else:
            logger.info(f"Successfully verified {actual_count} files.")

    except Exception as e:
        logger.error(f"Error during file verification step: {e}", exc_info=True)
        sys.exit(1)

    if actual_count == 0:
        logger.error("Verification found zero matching files. Aborting ingestion.")
        sys.exit(1)

    # --- Start Ingestion ---
    logger.info(f"Starting ingestion process for directory: {sample_data_dir}...")
    ingest_documents(str(sample_data_dir)) # This function is from backend.ingestion
    logger.info("Ingestion process finished.")
    logger.info("--- run_ingestion.py script finished ---")

if __name__ == "__main__":
    main()