# File path: backend/ingestion.py
import os
import traceback  # Added for detailed error reporting
from pathlib import Path
from time import sleep # Keep if you might add delays later, otherwise optional
# from openai import OpenAI # Keep this if you plan to use OpenAI later, otherwise remove (Currently not used in this file)
from dotenv import load_dotenv
from data_processing.document_loader import load_pdf, load_txt, load_docx
from backend.db import insert_ticket # Removed 'engine' import as it's not directly used here
from sqlalchemy.exc import SQLAlchemyError # To catch database errors specifically
import logging # Import logging


logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Avoid adding multiple handlers if already configured
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - INGESTION - %(message)s')


load_dotenv()
# client = OpenAI() # Keep this if needed for future OpenAI agent integration

MAX_CONTENT_LENGTH = 5000

def process_file(filepath):
    """
    Processes a single file based on its extension.
    Returns the file content as a string or None if processing fails.
    """
    ext = filepath.suffix.lower()
    try:
        if ext == '.pdf':
            return load_pdf(filepath)
        elif ext == '.txt':
            return load_txt(filepath)
        elif ext == '.docx':
            return load_docx(filepath)
        else:
            logger.warning(f"Skipping unsupported file type: {filepath.name}")
            return None
    except Exception as e:
        logger.error(f"--- ERROR PROCESSING FILE: {filepath.name} ---")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {e}")
        logger.error("Traceback:", exc_info=True)  # Log the full stack trace
        logger.error("---------------------------------------------")
        return None

def ingest_documents(directory):
    """
    Finds supported documents in a directory, processes them,
    and attempts to insert their content into the database.
    Reports a summary of successes and failures.
    """
    source_path = Path(directory)
    if not source_path.is_dir():
        logger.error(f"Error: Directory not found: {directory}")
        return

    files_to_process = [f for f in source_path.iterdir()
                        if f.is_file() and f.suffix.lower() in ('.pdf', '.txt', '.docx')]

    total_files = len(files_to_process)
    success_count = 0
    failure_count = 0

    if total_files == 0:
        logger.info(f"No supported files (.pdf, .txt, .docx) found in '{directory}'.")
        return

    logger.info(f"Found {total_files} files to process in '{directory}'. Starting ingestion...")

    for i, filepath in enumerate(files_to_process):
        logger.info(f"Processing file {i + 1}/{total_files}: {filepath.name}...")
        content = process_file(filepath)

        if content is not None:
            try:
                # Attempt to insert the processed content into the database
                # Capture the return value of insert_ticket
                inserted_successfully = insert_ticket(
                    title=filepath.stem,
                    description=content[:MAX_CONTENT_LENGTH],
                    category="Pending",
                    file_name=filepath.name,
                    file_type=filepath.suffix[1:].lower()
                )

                if inserted_successfully:
                    success_count += 1
                    logger.info(f"  -> Successfully processed and inserted: {filepath.name}")
                else:
                    # insert_ticket should have logged the specific reason for failure
                    # (e.g., DB engine not available, or SQL error during its execution)
                    logger.error(f"  -> FAILED to insert ticket for {filepath.name}. Check previous logs for details.")
                    failure_count += 1

            except SQLAlchemyError as db_err: # Should ideally be caught within insert_ticket
                logger.error(f"  -> DB INSERTION FAILED for {filepath.name}: {db_err}", exc_info=True)
                failure_count += 1
            except Exception as general_err: # Catch any other unexpected errors
                logger.error(f"  -> UNEXPECTED ERROR during insertion phase for {filepath.name}: {general_err}", exc_info=True)
                failure_count += 1
        else:
            # process_file already printed the detailed error message
            logger.info(f"  -> Failed to process file content for {filepath.name} (see error message above).")
            failure_count += 1

        # sleep(0.1) # Usually not needed unless hitting API rate limits

    logger.info("\n--- Ingestion Summary ---")
    logger.info(f"Total files found: {total_files}")
    logger.info(f"Successfully processed and inserted: {success_count}")
    logger.info(f"Failed to process or insert: {failure_count}")
    logger.info("-------------------------\n")