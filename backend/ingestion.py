# File path: backend/ingestion.py
import os
import traceback  # Added for detailed error reporting
from pathlib import Path
from time import sleep
from openai import OpenAI # Keep this if you plan to use OpenAI later, otherwise remove
from dotenv import load_dotenv
from data_processing.document_loader import load_pdf, load_txt, load_docx # Corrected import path assuming document_loader.py is in data_processing
from backend.db import engine, insert_ticket
from sqlalchemy.exc import SQLAlchemyError # To catch database errors specifically

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
            # Optional: Handle unexpected but allowed file types if necessary
            print(f"Skipping unsupported file type: {filepath.name}")
            return None
    except Exception as e:
        # Enhanced error logging
        print(f"\n--- ERROR PROCESSING FILE: {filepath.name} ---")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        print("Traceback:")
        traceback.print_exc()  # Print the full stack trace
        print("---------------------------------------------\n")
        return None # Return None on failure so the main loop can continue

def ingest_documents(directory):
    """
    Finds supported documents in a directory, processes them,
    and attempts to insert their content into the database.
    Reports a summary of successes and failures.
    """
    source_path = Path(directory)
    if not source_path.is_dir():
        print(f"Error: Directory not found: {directory}")
        return

    # Ensure we only process files with the expected extensions
    files_to_process = [f for f in source_path.iterdir()
                        if f.is_file() and f.suffix.lower() in ('.pdf', '.txt', '.docx')]

    total_files = len(files_to_process)
    success_count = 0
    failure_count = 0

    if total_files == 0:
        print(f"No supported files (.pdf, .txt, .docx) found in '{directory}'.")
        return

    print(f"Found {total_files} files to process in '{directory}'. Starting ingestion...")

    for i, filepath in enumerate(files_to_process):
        print(f"Processing file {i + 1}/{total_files}: {filepath.name}...")
        content = process_file(filepath)

        if content is not None:
            try:
                # Attempt to insert the processed content into the database
                insert_ticket(
                    title=filepath.stem, # Use filename without extension as title
                    description=content[:MAX_CONTENT_LENGTH], # Truncate if necessary
                    category="Pending", # Default category
                    file_name=filepath.name,
                    file_type=filepath.suffix[1:].lower() # Store 'pdf', 'txt', 'docx'
                )
                success_count += 1
                print(f"  -> Successfully processed and inserted.")
            except SQLAlchemyError as db_err:
                # Catch potential database errors during insertion
                print(f"  -> DB INSERTION FAILED for {filepath.name}: {db_err}")
                failure_count += 1
            except Exception as general_err:
                # Catch any other unexpected errors during the insertion step
                print(f"  -> UNEXPECTED ERROR during insertion phase for {filepath.name}: {general_err}")
                traceback.print_exc() # Also print traceback for these errors
                failure_count += 1
        else:
            # process_file already printed the detailed error message
            print(f"  -> Failed to process file content (see error message above).")
            failure_count += 1

        # sleep(0.1) # Usually not needed unless hitting external API rate limits or causing excessive load

    # Print the final summary
    print("\n--- Ingestion Summary ---")
    print(f"Total files found: {total_files}")
    print(f"Successfully processed and inserted: {success_count}")
    print(f"Failed to process or insert: {failure_count}")
    print("-------------------------\n")

# Example of how to potentially call this if running this file directly
# if __name__ == "__main__":
#    target_directory = "database/sample_data" # Or get from command line args
#    ingest_documents(target_directory)
