# File path: backend/openai_agent.py
# backend/openai_agent.py

import os
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.db import engine  # Assuming db.py defines 'engine' correctly
from sqlalchemy import text, exc as sqlalchemy_exc # Import exceptions
import logging

# --- Basic Logging Setup ---
# Ensure logging is configured early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__) # Use a named logger

load_dotenv()
# --- Initialize OpenAI Client ---
client = None # Initialize client as None
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.critical("OPENAI_API_KEY environment variable not found!")
    else:
        client = OpenAI(api_key=api_key)
        # Optional: Test connection if needed, but adds startup time/cost
        # client.models.list()
        logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
    client = None # Ensure client is None if initialization fails

# --- Database Functions ---
# (Keep your existing DB functions like get_ticket_from_db_by_title, get_tickets_df)
# Make sure they handle potential None engine gracefully if needed elsewhere
def get_ticket_from_db_by_title(ticket_title):
    """Fetch ticket from database using the title"""
    if engine is None:
        logger.error("Database engine not available for get_ticket_from_db_by_title")
        return None
    logger.info(f"Attempting to fetch ticket by title: '{ticket_title}' from DB.")
    if not ticket_title:
        logger.warning("get_ticket_from_db_by_title called with empty title.")
        return None
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, title, description, category, status, resolved_at, file_name, file_type, created_at FROM tickets WHERE title = :title LIMIT 1"),
                {"title": ticket_title}
            )
            ticket_data = result.mappings().first()
            if ticket_data:
                logger.info(f"Successfully fetched ticket by title: '{ticket_title}'. DB ID: {ticket_data.get('id', 'N/A')}")
            else:
                logger.warning(f"Ticket with title: '{ticket_title}' not found in DB.")
            return ticket_data
    except sqlalchemy_exc.SQLAlchemyError as db_err:
        logger.error(f"Database error fetching ticket title '{ticket_title}': {db_err}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching ticket title '{ticket_title}': {e}", exc_info=True)
        return None

def get_tickets_df():
    """Fetch all tickets as DataFrame"""
    if engine is None:
        logger.error("Database engine not available for get_tickets_df")
        return pd.DataFrame()
    logger.info("Attempting to fetch all tickets into DataFrame.")
    try:
        # Make sure to select all necessary columns, including status/resolved_at if they exist
        query = text("SELECT id, title, description, category, status, resolved_at, file_name, file_type, created_at FROM tickets")
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            logger.info(f"Successfully fetched {len(df)} tickets into DataFrame.")
            return df
    except sqlalchemy_exc.SQLAlchemyError as db_err:
        logger.error(f"Database error fetching all tickets: {db_err}", exc_info=True)
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error fetching all tickets: {e}", exc_info=True)
        return pd.DataFrame()


# --- OpenAI Functions ---
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_openai_api(prompt):
    """Generic OpenAI API caller with retry logic"""
    if client is None:
        logger.error("OpenAI client is not initialized. Cannot call API.")
        return "Error: OpenAI client not configured."

    logger.info(f"Calling OpenAI API. Prompt length: {len(prompt)}. First 100 chars: {prompt[:100]}...")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500 # Adjust if needed for specific calls like summary/resolution
        )
        content = response.choices[0].message.content.strip()
        logger.info(f"Received OpenAI response. Length: {len(content)}. First 100 chars: {content[:100]}...")
        if not content:
             logger.warning("OpenAI API returned an empty response.")
        return content
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}", exc_info=True)
        return "Error: Unable to get a response from the AI assistant at this time."


# --- UPDATED BATCH CATEGORIZATION FUNCTION ---
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def categorize_ticket_batch(texts, categories=None):
    """Categorize multiple tickets efficiently using OpenAI with improved prompt and token limit."""
    if client is None:
        logger.error("OpenAI client is not initialized. Cannot categorize tickets.")
        # Return list of errors matching input length
        return ["Error: OpenAI Not Configured"] * len(texts) if texts else []

    if not texts:
        logger.warning("categorize_ticket_batch called with empty list of texts.")
        return []
    num_tickets = len(texts)

    if not categories:
        # Define standard categories here
        categories = [
            "Network Security", "Phishing Attack", "Malware Infection",
            "Access Control", "Policy Violation", "Data Leak",
            "Hardware Issue", "Software Issue", "Other"
        ]
    logger.info(f"Attempting to categorize {num_tickets} tickets using categories: {categories}")

    # Improved system prompt for clarity and strictness
    system_prompt = f"""You are an IT ticket categorization assistant.
Classify EACH of the following {num_tickets} IT tickets based on their content.
The tickets are separated by '---'.
Use ONLY ONE category from the following list for each ticket: {', '.join(categories)}.
Your response MUST contain exactly {num_tickets} lines. Each line must contain only the category name for the corresponding ticket.
Do NOT add any extra text, explanations, numbers, or blank lines before or after the list.
If a ticket doesn't fit well into the specific categories, use the category 'Other'.

Example if you received 3 tickets:
Phishing Attack
Network Security
Other
"""

    # Dynamically calculate max_tokens needed
    # Avg category length ~15-20 chars + newline (~1 char) = ~16-21 tokens per category
    # Add buffer (e.g., 5-10 extra per ticket)
    estimated_tokens = num_tickets * 25
    # Set a reasonable lower/upper bound
    max_tokens_limit = max(200, estimated_tokens) # Min 200 tokens, scales up
    max_tokens_limit = min(max_tokens_limit, 3000) # Set an upper ceiling if needed (depends on model limits too)
    logger.info(f"Setting max_tokens for categorization to: {max_tokens_limit}")


    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Cost-effective choice
            messages=[{
                "role": "system",
                "content": system_prompt
            }, {
                "role": "user",
                "content": "---\n".join(texts) # Use separator
            }],
            temperature=0.0, # Low temperature for consistency
            max_tokens=max_tokens_limit # Use calculated limit
        )
        raw_categories_response = response.choices[0].message.content.strip()
        logger.info(f"Raw OpenAI categorization response received (length {len(raw_categories_response)}):\n{raw_categories_response[:500]}...") # Log start of raw response

        # Split lines AND filter out potential empty strings resulting from extra newlines
        assigned_categories = [cat.strip() for cat in raw_categories_response.split("\n") if cat.strip()]
        num_received = len(assigned_categories)

        # Strict count check - CRITICAL for correct assignment
        if num_received != num_tickets:
            logger.error(f"FATAL: Mismatched category count! Expected {num_tickets}, got {num_received}. Cannot reliably assign categories. Raw response logged above.")
            # Return an error list to signal failure clearly
            return ["Error: Count Mismatch"] * num_tickets

        # Optional: Validate category names against the provided list
        # If a category isn't in the list, map it to 'Other'
        final_categories = [cat if cat in categories else "Other" for cat in assigned_categories]
        mismatched_names = sum(1 for i, cat in enumerate(assigned_categories) if cat != final_categories[i])
        if mismatched_names > 0:
             logger.warning(f"{mismatched_names} predicted categories were not in the target list and were mapped to 'Other'.")

        logger.info(f"Successfully received and validated {len(final_categories)} categories.")
        return final_categories

    except Exception as e:
        logger.error(f"Batch categorization API call failed: {e}", exc_info=True)
        # Return list of errors matching input length
        return ["Error: API Call Failed"] * num_tickets


# --- Functions for Summary, Resolution, Insights ---
# (Keep your existing get_ticket_summary, get_ticket_resolution, generate_insights)
# Ensure they use get_ticket_from_db_by_title and handle None results gracefully

def get_ticket_summary(ticket_title):
    """Generate concise ticket summary using ticket title"""
    logger.info(f"--- Entering get_ticket_summary for ticket_title: '{ticket_title}' ---")
    ticket = get_ticket_from_db_by_title(ticket_title)
    if not ticket:
        logger.warning(f"get_ticket_summary: Ticket '{ticket_title}' not found.")
        return f"Sorry, I could not find a ticket with the title '{ticket_title}'."

    category = ticket.get('category', 'N/A')
    title = ticket.get('title', 'N/A')
    description = ticket.get('description', 'No description available.')
    logger.info(f"get_ticket_summary: Fetched data for ticket '{ticket_title}'. DB ID: {ticket.get('id')}, Category: {category}")

    prompt = f"""
    Please summarize the key information from the following IT support ticket.
    The ticket is in the '{category}' category.

    Ticket Title: {title}
    Full Description:
    ---
    {description}
    ---

    Provide the summary as exactly 3 concise bullet points, focusing on the core issue and context.
    Required format:
    - [Issue or observation 1]
    - [Issue or observation 2]
    - [Relevant detail or impact 3]
    """
    logger.info(f"get_ticket_summary: Constructed prompt for OpenAI (length {len(prompt)}):\n{prompt[:500]}...")
    summary_response = call_openai_api(prompt)
    logger.info(f"get_ticket_summary: Received raw response from call_openai_api for ticket '{ticket_title}':\n{summary_response}")
    logger.info(f"--- Exiting get_ticket_summary for ticket_title: '{ticket_title}' ---")
    return summary_response


def get_ticket_resolution(ticket_title):
    """Generate actionable resolution steps using ticket title"""
    logger.info(f"--- Entering get_ticket_resolution for ticket_title: '{ticket_title}' ---")
    ticket = get_ticket_from_db_by_title(ticket_title)
    if not ticket:
        logger.warning(f"get_ticket_resolution: Ticket '{ticket_title}' not found.")
        return f"Sorry, I could not find a ticket with the title '{ticket_title}'."

    category = ticket.get('category', 'N/A')
    title = ticket.get('title', 'N/A')
    description = ticket.get('description', 'No description available.')
    logger.info(f"get_ticket_resolution: Fetched data for ticket '{ticket_title}'. DB ID: {ticket.get('id')}, Category: {category}")

    prompt = f"""
    You are an expert IT support specialist. Analyze the following support ticket and provide clear, actionable resolution steps.
    The ticket category is '{category}'.

    Ticket Title: {title}
    Full Description:
    ---
    {description}
    ---

    Provide detailed steps organized under the following headings. Be specific and practical.
    If a section is not applicable, state "Not Applicable".

    **1. Immediate Actions / Triage:**
    (Steps to quickly assess, contain, or provide temporary relief)
    - [Step 1]
    - [Step 2]
    ...

    **2. Investigation / Root Cause Analysis:**
    (Steps to understand the underlying problem)
    - [Step 1]
    - [Step 2]
    ...

    **3. Long-term Solution / Fix:**
    (Steps to permanently resolve the issue)
    - [Step 1]
    - [Step 2]
    ...

    **4. Prevention (If Applicable):**
    (Steps to prevent recurrence)
    - [Tip 1]
    - [Tip 2]
    ...
    """
    logger.info(f"get_ticket_resolution: Constructed prompt for OpenAI (length {len(prompt)}):\n{prompt[:500]}...")
    resolution_response = call_openai_api(prompt)
    logger.info(f"get_ticket_resolution: Received raw response from call_openai_api for ticket '{ticket_title}':\n{resolution_response}")
    logger.info(f"--- Exiting get_ticket_resolution for ticket_title: '{ticket_title}' ---")
    return resolution_response


def generate_insights(df=None):
    """Generate data-driven insights from ticket data"""
    if client is None:
        logger.error("OpenAI client not available for generate_insights")
        return "Error: AI Insights generation not available."

    logger.info("--- Entering generate_insights ---")
    if df is None:
        logger.info("generate_insights: DataFrame not provided, fetching from DB.")
        df = get_tickets_df() # This fetches all data

    if df is None or df.empty:
        logger.warning("generate_insights: No ticket data available for analysis.")
        return "No ticket data available to generate insights."

    # Use the provided DataFrame (which might be filtered or sampled by caller)
    df_subset = df
    logger.info(f"generate_insights: Analyzing DataFrame subset with {len(df_subset)} rows.")

    # Define columns to include based on availability
    cols_for_ai = ['title', 'category', 'created_at']
    if 'status' in df_subset.columns: cols_for_ai.append('status')
    if 'resolution_time_hours' in df_subset.columns: cols_for_ai.append('resolution_time_hours')

    # Select only existing columns and convert to string for the prompt
    df_subset_str = df_subset[[col for col in cols_for_ai if col in df_subset.columns]].astype(str).to_string(index=False)

    # Construct the prompt for insights
    # The prompt used in the Dashboard code is more detailed, consider unifying or passing context
    prompt = f"""
    Analyze the following IT support ticket data and provide 3 key insights that would be easily understandable for someone without a technical background. For each insight, provide a brief explanation and an actionable recommendation.

    Ticket Data Sample:
    ---
    {df_subset_str}
    ---

    Format your response clearly with 3 numbered points:
    1. **Overall Trend:** (e.g., Increase in phishing attempts, common hardware failures)
    2. **Top Risk Category:** (Which category appears most frequently or seems most critical?)
    3. **Potential Recurring Issue:** (Is there a specific type of problem hinted at by multiple titles?)
    4. **Efficiency Note:** (Comment on status distribution or resolution times if available)
    5. **Data Quality/Recommendation:** (Any comment on data or suggestion for action?)
    """
    logger.info(f"generate_insights: Constructed prompt for OpenAI (length {len(prompt)}):\n{prompt[:500]}...")
    insights_response = call_openai_api(prompt)
    logger.info(f"generate_insights: Received raw response from call_openai_api:\n{insights_response}")
    logger.info("--- Exiting generate_insights ---")
    return insights_response
