# File path: backend/db.py
import os
import pandas as pd
from sqlalchemy import create_engine, text, exc as sqlalchemy_exc
from dotenv import load_dotenv
import logging

# Get a logger instance for this module
logger = logging.getLogger(__name__)

load_dotenv()

# --- Database Connection ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = None # Initialize engine to None

if not DATABASE_URL:
    logger.critical("DATABASE_URL environment variable not set!")
    # engine remains None
else:
    try:
        engine = create_engine(DATABASE_URL)
        # Test connection on creation
        with engine.connect() as conn:
             logger.info("Database engine created and connection tested successfully.")
    except sqlalchemy_exc.SQLAlchemyError as sa_err:
        logger.critical(f"SQLAlchemy error creating database engine or testing connection: {sa_err}", exc_info=True)
        engine = None
    except RuntimeError as rt_err: # For issues like missing 'cryptography'
        logger.critical(f"RuntimeError creating database engine: {rt_err}", exc_info=True)
        engine = None
    except Exception as e:
        logger.critical(f"Failed to create database engine due to an unexpected error: {e}", exc_info=True)
        engine = None

# --- Database Functions ---

def get_tickets_df():
    """
    Fetches all ticket data including id, title, description, category,
    file_name, file_type, created_at, status, and resolved_at into a DataFrame.
    Returns an empty DataFrame on error.
    """
    if engine is None:
        logger.error("Database engine is not available. Cannot fetch tickets.")
        return pd.DataFrame()

    query = text("""
        SELECT
            id,
            title,
            description,
            category,
            file_name,
            file_type,
            created_at,
            status,
            resolved_at
        FROM tickets
        ORDER BY created_at DESC;
    """)

    logger.info("Attempting to fetch all tickets from DB for DataFrame.")
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            logger.info(f"Successfully fetched {len(df)} tickets into DataFrame.")
            expected_cols = ['id', 'title', 'description', 'category', 'status', 'resolved_at', 'created_at']
            missing_cols = [col for col in expected_cols if col not in df.columns]
            if missing_cols:
                 logger.warning(f"Fetched DataFrame is missing expected columns: {missing_cols}. Check DB schema and query.")
            return df
    except sqlalchemy_exc.SQLAlchemyError as db_err:
        logger.error(f"Database error fetching all tickets: {db_err}", exc_info=True)
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error fetching all tickets: {e}", exc_info=True)
        return pd.DataFrame()


def insert_ticket(title, description, category, file_name=None, file_type=None):
    """
    Inserts a new ticket into the database.
    Returns True on success, False on failure.
    """
    if engine is None:
        logger.error("Database engine is not available. Cannot insert ticket.")
        return False

    # logger.info(f"Attempting to insert ticket with title: {title}") # Moved logging to ingestion.py for this specific call
    try:
        with engine.connect() as conn: # Ensure connection is properly managed
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
            conn.commit()
            # logger.info(f"Successfully inserted ticket: {title}") # Moved to ingestion.py
            return True
    except sqlalchemy_exc.SQLAlchemyError as db_err:
        logger.error(f"Database error inserting ticket '{title}': {db_err}", exc_info=True)
        # Rollback might be needed if 'conn' was established but commit failed or an error occurred before commit
        # However, with 'with engine.connect() as conn:' and 'conn.commit()', SQLAlchemy handles rollbacks
        # on unhandled exceptions within the 'with' block. Explicit rollback can be added if paranoid.
        return False
    except Exception as e:
        logger.error(f"Unexpected error inserting ticket '{title}': {e}", exc_info=True)
        return False