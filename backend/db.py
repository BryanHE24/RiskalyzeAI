# File path: backend/db.py
# backend/db.py

import os
import pandas as pd
from sqlalchemy import create_engine, text, exc as sqlalchemy_exc # Import exceptions
from dotenv import load_dotenv
import logging

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - DB - %(message)s')

load_dotenv()

# --- Database Connection ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logging.critical("DATABASE_URL environment variable not set!")
    # Depending on your app structure, you might raise an error or exit here
    engine = None
else:
    try:
        engine = create_engine(DATABASE_URL)
        # Optional: Test connection on creation
        with engine.connect() as conn:
             logging.info("Database engine created and connection tested successfully.")
    except Exception as e:
        logging.critical(f"Failed to create database engine: {e}", exc_info=True)
        engine = None

# --- Database Functions ---

def get_tickets_df():
    """
    Fetches all ticket data including id, title, description, category,
    file_name, file_type, created_at, status, and resolved_at into a DataFrame.
    Returns an empty DataFrame on error.
    """
    if engine is None:
        logging.error("Database engine is not available. Cannot fetch tickets.")
        return pd.DataFrame()

    # Explicitly list all columns, including the new 'status' and 'resolved_at'
    query = text("""
        SELECT
            id,
            title,
            description,
            category,
            file_name,
            file_type,
            created_at,
            status,         -- Added status column
            resolved_at     -- Added resolved_at column
        FROM tickets
        ORDER BY created_at DESC; -- Optional: Order by creation date
    """)

    logging.info("Attempting to fetch all tickets from DB for DataFrame.")
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            logging.info(f"Successfully fetched {len(df)} tickets into DataFrame.")
            # Basic check for expected columns after fetch (optional)
            expected_cols = ['id', 'title', 'description', 'category', 'status', 'resolved_at', 'created_at']
            missing_cols = [col for col in expected_cols if col not in df.columns]
            if missing_cols:
                 logging.warning(f"Fetched DataFrame is missing expected columns: {missing_cols}. Check DB schema and query.")
            return df
    except sqlalchemy_exc.SQLAlchemyError as db_err:
        logging.error(f"Database error fetching all tickets: {db_err}", exc_info=True)
        return pd.DataFrame() # Return empty DataFrame on DB error
    except Exception as e:
        logging.error(f"Unexpected error fetching all tickets: {e}", exc_info=True)
        return pd.DataFrame() # Return empty DataFrame on other errors


def insert_ticket(title, description, category, file_name=None, file_type=None):
    """
    Inserts a new ticket into the database.
    Initial status will be the default ('Open'). resolved_at will be NULL.
    """
    if engine is None:
        logging.error("Database engine is not available. Cannot insert ticket.")
        return False # Indicate failure

    logging.info(f"Attempting to insert ticket with title: {title}")
    try:
        with engine.connect() as conn:
            # Note: status and resolved_at are handled by DB defaults now
            insert_statement = text("""
                INSERT INTO tickets
                (title, description, category, file_name, file_type)
                VALUES (:title, :desc, :category, :file_name, :file_type)
            """)
            conn.execute(
                insert_statement,
                {
                    "title": title,
                    "desc": description,
                    "category": category,
                    "file_name": file_name,
                    "file_type": file_type
                 }
            )
            conn.commit() # Commit the transaction
            logging.info(f"Successfully inserted ticket: {title}")
            return True # Indicate success
    except sqlalchemy_exc.SQLAlchemyError as db_err:
        logging.error(f"Database error inserting ticket '{title}': {db_err}", exc_info=True)
        return False # Indicate failure
    except Exception as e:
        logging.error(f"Unexpected error inserting ticket '{title}': {e}", exc_info=True)
        return False # Indicate failure

# You might need functions to UPDATE status and resolved_at later, e.g.:
# def update_ticket_status(ticket_id, new_status, resolved_timestamp=None):
#     """Updates the status and optionally resolved_at timestamp for a ticket."""
#     if engine is None: return False
#     logging.info(f"Attempting to update ticket ID {ticket_id} to status '{new_status}'")
#     try:
#         with engine.connect() as conn:
#             if new_status == 'Closed' and resolved_timestamp is None:
#                  # If closing, set resolved_at to now if not provided
#                  resolved_timestamp = datetime.now()
#
#             update_statement = text("""
#                 UPDATE tickets
#                 SET status = :status,
#                     resolved_at = :resolved_at -- This will update resolved_at
#                 WHERE id = :id
#             """)
#             conn.execute(
#                 update_statement,
#                 {"status": new_status, "resolved_at": resolved_timestamp, "id": ticket_id}
#             )
#             conn.commit()
#             logging.info(f"Successfully updated ticket ID {ticket_id}.")
#             return True
#     except Exception as e:
#          logging.error(f"Error updating ticket ID {ticket_id}: {e}", exc_info=True)
#          return False
