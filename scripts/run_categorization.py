# File path: scripts/run_categorization.py
#!/usr/bin/env python3
import sys
from pathlib import Path
import pandas as pd
import logging
import time # Import time for potential delays between batches

# --- Setup Project Root and Path ---
# This assumes run_categorization.py is in the 'scripts' directory.
try:
    SCRIPT_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = SCRIPT_DIR.parent # Project root is one level up from 'scripts'
except NameError: # Fallback if __file__ is not defined (e.g., interactive use)
    PROJECT_ROOT = Path.cwd()
    # If CWD is not project root, imports might fail. This assumes script is run appropriately.

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    # This print might be redundant if logging is configured right after.
    print(f"Added project root to sys.path: {PROJECT_ROOT}")

# --- Logging Configuration (SHOULD BE DONE EARLY) ---
# Configure logging for this script. Modules it imports will inherit this if they don't override.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # Ensure logs go to console
    ]
)
logger = logging.getLogger("CATEGORIZER_SCRIPT") # Logger for this script

# --- Imports (After path and logging setup) ---
try:
    from backend.db import engine # For database connection
    from backend.openai_agent import categorize_ticket_batch
    from sqlalchemy import text, exc as sqlalchemy_exc
except ImportError as e:
    logger.error(f"ERROR: Failed to import modules: {e}", exc_info=True)
    logger.error(f"Current sys.path: {sys.path}")
    sys.exit(1)
except Exception as ex:
    logger.error(f"An unexpected error occurred during imports: {ex}", exc_info=True)
    sys.exit(1)


# --- Database Functions (Specific to this script) ---
def get_pending_tickets():
    """Fetches ID, title, and description of tickets with category 'Pending' or NULL."""
    if engine is None:
        logger.error("Database engine not available (db.py reported an issue). Cannot fetch pending tickets.")
        return pd.DataFrame()
    query = text("SELECT id, title, description FROM tickets WHERE category = 'Pending' OR category IS NULL OR category = ''")
    logger.info("Fetching tickets with category 'Pending', NULL, or empty...")
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            logger.info(f"Found {len(df)} tickets with category 'Pending', NULL, or empty.")
            return df
    except Exception as e:
        logger.error(f"Error fetching pending tickets: {e}", exc_info=True)
        return pd.DataFrame()

def update_ticket_category(ticket_id, new_category):
    """Updates the category for a specific ticket ID."""
    if engine is None:
        logger.error(f"Database engine not available. Cannot update ticket ID {ticket_id}.")
        return False
    update_stmt = text("UPDATE tickets SET category = :category WHERE id = :id")
    logger.debug(f"Updating ticket ID {ticket_id} to category '{new_category}'...")
    try:
        with engine.connect() as conn:
            result = conn.execute(update_stmt, {"category": new_category, "id": ticket_id})
            conn.commit()
            if result.rowcount > 0:
                logger.debug(f"Successfully updated ticket ID {ticket_id} to '{new_category}'.")
                return True
            else:
                logger.warning(f"No rows updated for ticket ID {ticket_id} (category may already be '{new_category}' or ID not found).")
                return False # Or True if no update needed is considered success
    except Exception as e:
        logger.error(f"Error updating category for ticket ID {ticket_id} to '{new_category}': {e}", exc_info=True)
        return False

# --- BATCH PROCESSING FUNCTION ---
def process_batch(batch_df, target_categories):
    """Processes a single batch of tickets for categorization."""
    if batch_df.empty:
        return {}

    batch_size = len(batch_df)
    logger.info(f"-- Processing batch of {batch_size} tickets --")

    MAX_DESC_LEN = 500 # Max description length to send to OpenAI for categorization
    texts_to_categorize = [
        f"Title: {row['title']}\nDescription: {str(row['description'])[:MAX_DESC_LEN]}"
        for index, row in batch_df.iterrows()
    ]
    batch_ticket_ids = batch_df['id'].tolist()

    predicted_categories = categorize_ticket_batch(texts_to_categorize, categories=target_categories)

    if not predicted_categories or len(predicted_categories) != batch_size:
        logger.error(f"Categorization returned an invalid list or wrong number of items. Expected {batch_size}, got {len(predicted_categories if predicted_categories else [])}.")
        return None # Indicates failure for this batch

    # Check for error strings returned by categorize_ticket_batch itself
    if any("Error:" in str(cat) for cat in predicted_categories):
        logger.error(f"Failed to categorize batch due to errors from categorize_ticket_batch: {predicted_categories}")
        # Log the first error encountered as a sample
        first_error = next((cat for cat in predicted_categories if "Error:" in str(cat)), "Unknown error")
        logger.debug(f"Sample error from batch: {first_error}")
        return None # Indicates failure

    results = {ticket_id: category for ticket_id, category in zip(batch_ticket_ids, predicted_categories)}
    return results


# --- Main Categorization Logic ---
def main():
    logger.info("="*30)
    logger.info("Starting ticket categorization process...")
    logger.info("="*30)

    if engine is None:
         logger.critical("Database engine is not initialized. Cannot run categorization. Exiting.")
         return

    pending_df = get_pending_tickets()

    if pending_df.empty:
        logger.info("No pending tickets found to categorize. Exiting.")
        return

    BATCH_SIZE = 10  # TESTING WITH SMALLER BATCH SIZE
    DELAY_BETWEEN_BATCHES = 1 # Seconds

    target_categories = [
        "Network Security", "Phishing Attack", "Malware Infection",
        "Access Control", "Policy Violation", "Data Leak",
        "Hardware Issue", "Software Issue", "Other"
    ]

    num_tickets = len(pending_df)
    num_batches = (num_tickets + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"Total tickets to process: {num_tickets}. Processing in {num_batches} batches of size up to {BATCH_SIZE}.")

    all_results = {}
    processed_count_from_api = 0 # Tickets for which we got a non-error response from API
    failed_api_batches = 0

    for i in range(num_batches):
        start_index = i * BATCH_SIZE
        end_index = start_index + BATCH_SIZE
        batch_df = pending_df.iloc[start_index:end_index]

        logger.info(f"--- Starting Batch {i+1}/{num_batches} (Tickets {start_index+1}-{min(end_index, num_tickets)}) ---")

        batch_results = process_batch(batch_df.copy(), target_categories) # Pass a copy to avoid SettingWithCopyWarning

        if batch_results is None: # process_batch returns None on failure
            logger.error(f"Batch {i+1} failed categorization processing.")
            failed_api_batches += 1
        else:
            all_results.update(batch_results)
            processed_count_from_api += len(batch_results) # Count successfully processed items in this batch

        if i < num_batches - 1:
            logger.info(f"Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    logger.info(f"--- Batch API processing finished. Successfully received API results for {processed_count_from_api} tickets. Failed API batches: {failed_api_batches} ---")

    if not all_results:
         logger.warning("No successful categorization results obtained from API. Skipping database update.")
         return

    logger.info(f"Updating categories in the database for {len(all_results)} tickets with API results...")
    db_update_success_count = 0
    db_update_error_count = 0
    mapped_to_other_count = 0

    for ticket_id, predicted_category in all_results.items():
        final_category = predicted_category
        if final_category not in target_categories: # Should be handled by categorize_ticket_batch, but double check
             logger.warning(f"Category '{final_category}' for ticket ID {ticket_id} is not in target list. Remapping to 'Other'. This indicates an issue in categorize_ticket_batch logic.")
             final_category = 'Other'
             mapped_to_other_count += 1
        
        if update_ticket_category(ticket_id, final_category):
            db_update_success_count += 1
        else:
            db_update_error_count += 1

    logger.info("-"*30)
    logger.info("Final Categorization Summary:")
    logger.info(f"  Total pending tickets found: {num_tickets}")
    logger.info(f"  Tickets for which API results were obtained: {processed_count_from_api} (across {num_batches - failed_api_batches} successful API batches)")
    logger.info(f"  Successfully updated in DB: {db_update_success_count}")
    logger.info(f"  Categories remapped to 'Other' (fallback by this script): {mapped_to_other_count}") # Should ideally be 0
    logger.info(f"  Failed database updates: {db_update_error_count}")
    logger.info(f"  Number of failed API batches (Mismatched count, etc.): {failed_api_batches}")
    logger.info("-"*30)

if __name__ == "__main__":
    main()