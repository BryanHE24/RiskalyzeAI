# File path: backend/ingestion.py
import os
import traceback
from pathlib import Path
# from time import sleep # Optional, uncomment if needed
from dotenv import load_dotenv
from data_processing.document_loader import load_pdf, load_txt, load_docx
from backend.db import insert_ticket
from sqlalchemy.exc import SQLAlchemyError
import logging

# Get a logger instance for this module
logger = logging.getLogger(__name__)

load_dotenv()
# client = OpenAI() # Keep if needed for OpenAI agent integration

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
        logger.error("Traceback for file processing error:", exc_info=True)
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
        # Log processing attempt for each file using the module's logger
        logger.info(f"Processing file {i + 1}/{total_files}: {filepath.name}...")
        content = process_file(filepath)

        if content is not None:
            try:
                # Attempt to insert the processed content into the database
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
                    logger.error(f"  -> FAILED to insert ticket for {filepath.name}. Check DB logs or previous 'engine not available' / DB error messages.")
                    failure_count += 1

            except SQLAlchemyError as db_err: # This catch block might be redundant if insert_ticket handles all SQLAlc errors
                logger.error(f"  -> DB INSERTION FAILED for {filepath.name} (SQLAlchemyError): {db_err}", exc_info=True)
                failure_count += 1
            except Exception as general_err:
                logger.error(f"  -> UNEXPECTED ERROR during insertion phase for {filepath.name}: {general_err}", exc_info=True)
                failure_count += 1
        else:
            logger.info(f"  -> Failed to process file content for {filepath.name} (see error message above).")
            failure_count += 1

        # sleep(0.1) # Optional delay

    logger.info("--- Ingestion Summary ---") # Add newline for readability before summary
    logger.info(f"Total files found: {total_files}")
    logger.info(f"Successfully processed and inserted: {success_count}")
    logger.info(f"Failed to process or insert: {failure_count}")
    logger.info("-------------------------") # Add newline after summary