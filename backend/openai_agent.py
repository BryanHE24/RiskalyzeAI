# File path: backend/openai_agent.py
import os
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import text, exc as sqlalchemy_exc # For DB functions if they remain here
import logging
import re # For regular expression-based cleaning

# Get a logger instance for this module
logger = logging.getLogger(__name__)

load_dotenv()

# --- Initialize OpenAI Client ---
client = None
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.critical("OPENAI_API_KEY environment variable not found!")
    else:
        client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
    client = None


# --- Database Functions (Used by summary/resolution/insights) ---
def get_ticket_from_db_by_title(ticket_title):
    """Fetch ticket from database using the title"""
    from backend.db import engine as db_engine
    if db_engine is None:
        logger.error("Database engine not available for get_ticket_from_db_by_title (db.py reported an issue).")
        return None
    if not ticket_title:
        logger.warning("get_ticket_from_db_by_title called with empty title.")
        return None
    try:
        with db_engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, title, description, category, status, resolved_at, file_name, file_type, created_at FROM tickets WHERE title = :title LIMIT 1"),
                {"title": ticket_title}
            )
            ticket_data = result.mappings().first()
            if ticket_data:
                logger.debug(f"Successfully fetched ticket by title: '{ticket_title}'. DB ID: {ticket_data.get('id', 'N/A')}")
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
    from backend.db import engine as db_engine
    if db_engine is None:
        logger.error("Database engine not available for get_tickets_df (db.py reported an issue).")
        return pd.DataFrame()
    logger.info("Attempting to fetch all tickets into DataFrame for openai_agent.")
    try:
        query = text("SELECT id, title, description, category, status, resolved_at, file_name, file_type, created_at FROM tickets ORDER BY created_at DESC")
        with db_engine.connect() as conn:
            df = pd.read_sql(query, conn)
            logger.info(f"Successfully fetched {len(df)} tickets into DataFrame (openai_agent).")
            return df
    except sqlalchemy_exc.SQLAlchemyError as db_err:
        logger.error(f"Database error fetching all tickets (openai_agent): {db_err}", exc_info=True)
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error fetching all tickets (openai_agent): {e}", exc_info=True)
        return pd.DataFrame()


# --- OpenAI Generic API Call Function ---
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6))
def call_openai_api(prompt_messages, model="gpt-3.5-turbo", temperature=0.3, max_tokens=500):
    """
    Generic OpenAI API caller with retry logic and model/param flexibility.
    Accepts a list of prompt messages.
    """
    if client is None:
        logger.error("OpenAI client is not initialized. Cannot call API.")
        return "Error: OpenAI client not configured."

    user_prompt_preview = ""
    for msg in prompt_messages:
        if msg["role"] == "user":
            user_prompt_preview = msg["content"][:100]
            break
    logger.info(f"Calling OpenAI API with model {model}. User prompt preview: '{user_prompt_preview}...'")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=prompt_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        content = response.choices[0].message.content.strip()
        log_response_len = min(len(content), 200)
        logger.info(f"Received OpenAI response. Length: {len(content)}. First {log_response_len} chars: '{content[:log_response_len]}{'...' if len(content) > log_response_len else ''}'")
        if not content:
             logger.warning("OpenAI API returned an empty response.")
        return content
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}", exc_info=True)
        raise


# --- UPDATED BATCH CATEGORIZATION FUNCTION ---
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6))
def categorize_ticket_batch(texts, categories=None):
    """
    Categorize multiple tickets efficiently using OpenAI with improved prompt,
    robust parsing, and cost-aware settings.
    """
    if client is None:
        logger.error("OpenAI client is not initialized. Cannot categorize tickets.")
        return ["Error: OpenAI Not Configured"] * len(texts) if texts else []

    if not texts:
        logger.warning("categorize_ticket_batch called with empty list of texts.")
        return []
    num_tickets = len(texts)

    if not categories:
        categories = [
            "Network Security", "Phishing Attack", "Malware Infection",
            "Access Control", "Policy Violation", "Data Leak",
            "Hardware Issue", "Software Issue", "Other"
        ]
    sorted_categories_for_matching = sorted(categories, key=len, reverse=True)

    logger.info(f"Attempting to categorize {num_tickets} tickets using categories: {categories}")

    # Refined prompt
    system_prompt = f"""You are an IT ticket categorization AI. Your sole task is to classify {num_tickets} IT tickets.
Each ticket is provided in the user message, separated by '---'.
For EACH of the {num_tickets} input tickets, you MUST output EXACTLY ONE category on a new line.
Use ONLY categories from this list: {', '.join(categories)}.
If a ticket is unclear or doesn't fit, use 'Other'.

Your response MUST contain exactly {num_tickets} lines.
NO other text. NO explanations. NO numbering. NO blank lines.
ONLY one category name per line.

Example of expected output format if you were given 3 tickets (where num_tickets would be 3):
Phishing Attack
Network Security
Other

Confirm: You will provide exactly {num_tickets} lines of output, each containing only a category name.
"""
    user_prompt_content = "---\n".join(texts)
    
    prompt_messages_for_api = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt_content}
    ]

    estimated_output_tokens_per_ticket = 10
    max_tokens_for_output = num_tickets * estimated_output_tokens_per_ticket
    max_tokens_for_output = max(50, max_tokens_for_output)
    max_tokens_for_output = min(max_tokens_for_output, 1500)

    logger.info(f"Setting max_tokens for OpenAI completion to: {max_tokens_for_output}")

    try:
        raw_categories_response = call_openai_api(
            prompt_messages=prompt_messages_for_api,
            model="gpt-3.5-turbo",
            temperature=0.0,
            max_tokens=max_tokens_for_output
        )
        if "Error:" in raw_categories_response :
             logger.error(f"call_openai_api returned an error: {raw_categories_response}")
             return [raw_categories_response] * num_tickets

        parsed_lines = [line.strip() for line in raw_categories_response.splitlines()]
        assigned_categories_from_llm = [line for line in parsed_lines if line]

        num_received = len(assigned_categories_from_llm)

        if num_received != num_tickets:
            logger.error(
                f"FATAL: Mismatched category count after parsing! Expected {num_tickets}, got {num_received}. "
                f"Input texts count: {len(texts)}. Raw response was: '{raw_categories_response}'"
            )
            logger.debug(f"Parsed lines ({num_received}): {assigned_categories_from_llm}")
            return ["Error: Count Mismatch"] * num_tickets

        final_categories = []
        mismatched_category_names_count = 0
        for i, llm_output_line in enumerate(assigned_categories_from_llm):
            simple_cleaned_cat_text = re.sub(r"^\s*\d+\.?\s*[:\-]?\s*", "", llm_output_line).strip()
            best_match_found = None

            if simple_cleaned_cat_text in categories:
                best_match_found = simple_cleaned_cat_text
            else:
                for known_cat in sorted_categories_for_matching:
                    if known_cat in simple_cleaned_cat_text:
                        best_match_found = known_cat
                        logger.warning(
                            f"Ticket {i+1}/{num_tickets}: LLM output line '{llm_output_line}' (cleaned to '{simple_cleaned_cat_text}') was not an exact category. "
                            f"Extracted known category '{known_cat}' by substring match."
                        )
                        break
            
            if best_match_found:
                final_categories.append(best_match_found)
            else:
                logger.warning(
                    f"Ticket {i+1}/{num_tickets}: LLM output line '{llm_output_line}' (cleaned to '{simple_cleaned_cat_text}') did not match or contain any known categories: {categories}. "
                    f"Assigning 'Other'."
                )
                final_categories.append("Other")
                mismatched_category_names_count += 1

        if mismatched_category_names_count > 0:
             logger.info(f"{mismatched_category_names_count} out of {num_tickets} tickets were assigned 'Other' due to mismatch or unidentifiable category names from LLM.")

        logger.info(f"Successfully processed and finalized {len(final_categories)} categories for {num_tickets} tickets.")
        return final_categories

    except Exception as e:
        logger.error(f"Batch categorization API call or response processing failed unexpectedly: {e}", exc_info=True)
        raise


# --- Functions for Summary, Resolution, Insights (Using the generic API caller) ---
def get_ticket_summary(ticket_title):
    logger.info(f"--- Entering get_ticket_summary for ticket_title: '{ticket_title}' ---")
    ticket = get_ticket_from_db_by_title(ticket_title)
    if not ticket:
        logger.warning(f"get_ticket_summary: Ticket '{ticket_title}' not found.")
        return f"Sorry, I could not find a ticket with the title '{ticket_title}'."

    category = ticket.get('category', 'N/A')
    title_val = ticket.get('title', 'N/A')
    description = ticket.get('description', 'No description available.')
    logger.info(f"get_ticket_summary: Fetched data for ticket '{ticket_title}'. DB ID: {ticket.get('id')}, Category: {category}")

    system_message_summary = "You are an expert at summarizing IT support tickets."
    user_message_summary = f"""
    Please summarize the key information from the following IT support ticket.
    The ticket is in the '{category}' category.

    Ticket Title: {title_val}
    Full Description (first 1000 characters):
    ---
    {description[:1000]}
    ---

    Provide the summary as exactly 3 concise bullet points, focusing on the core issue and context.
    Required format:
    - [Issue or observation 1]
    - [Issue or observation 2]
    - [Relevant detail or impact 3]
    """
    prompt_messages = [
        {"role": "system", "content": system_message_summary},
        {"role": "user", "content": user_message_summary}
    ]
    
    summary_response = call_openai_api(prompt_messages, model="gpt-3.5-turbo", temperature=0.2, max_tokens=200)
    logger.info(f"--- Exiting get_ticket_summary for ticket_title: '{ticket_title}' ---")
    return summary_response


def get_ticket_resolution(ticket_title):
    logger.info(f"--- Entering get_ticket_resolution for ticket_title: '{ticket_title}' ---")
    ticket = get_ticket_from_db_by_title(ticket_title)
    if not ticket:
        logger.warning(f"get_ticket_resolution: Ticket '{ticket_title}' not found.")
        return f"Sorry, I could not find a ticket with the title '{ticket_title}'."

    category = ticket.get('category', 'N/A')
    title_val = ticket.get('title', 'N/A')
    description = ticket.get('description', 'No description available.')
    logger.info(f"get_ticket_resolution: Fetched data for ticket '{ticket_title}'. DB ID: {ticket.get('id')}, Category: {category}")

    system_message_resolution = "You are an expert IT support specialist providing resolution steps."
    user_message_resolution = f"""
    Analyze the following support ticket and provide clear, actionable resolution steps.
    The ticket category is '{category}'.

    Ticket Title: {title_val}
    Full Description (first 1500 characters):
    ---
    {description[:1500]}
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
    prompt_messages = [
        {"role": "system", "content": system_message_resolution},
        {"role": "user", "content": user_message_resolution}
    ]

    resolution_response = call_openai_api(prompt_messages, model="gpt-3.5-turbo", temperature=0.3, max_tokens=700)
    logger.info(f"--- Exiting get_ticket_resolution for ticket_title: '{ticket_title}' ---")
    return resolution_response


def generate_insights(df=None):
    if client is None:
        logger.error("OpenAI client not available for generate_insights")
        return "Error: AI Insights generation not available."

    logger.info("--- Entering generate_insights ---")
    if df is None or df.empty:
        logger.info("generate_insights: DataFrame not provided or empty, fetching from DB.")
        df = get_tickets_df()

    if df is None or df.empty:
        logger.warning("generate_insights: No ticket data available for analysis after attempting fetch.")
        return "No ticket data available to generate insights."

    sample_size = min(len(df), 50)
    df_subset = df.sample(n=sample_size, random_state=1) if len(df) > sample_size else df.copy()
    logger.info(f"generate_insights: Analyzing DataFrame subset with {len(df_subset)} rows (sampled if original > 50).")

    cols_for_ai = ['title', 'category', 'created_at', 'status']
    if 'resolution_time_hours' in df_subset.columns and df_subset['resolution_time_hours'].notna().any():
        cols_for_ai.append('resolution_time_hours')

    existing_cols_in_subset = [col for col in cols_for_ai if col in df_subset.columns]
    if not existing_cols_in_subset:
        logger.warning("generate_insights: No relevant columns found in the subset for AI analysis.")
        return "Not enough data in the selected columns to generate insights."
        
    df_subset_str = df_subset[existing_cols_in_subset].astype(str).to_string(index=False, max_rows=15, max_cols=len(existing_cols_in_subset))

    system_message_insights = "You are an AI data analyst specializing in IT support ticket trends."
    user_message_insights = f"""
    Analyze the following sample of IT support ticket data. The full dataset has {len(df)} tickets.
    The sample below contains {len(df_subset)} tickets and includes columns: {', '.join(existing_cols_in_subset)}.
    ---
    {df_subset_str}
    ---

    Based on this sample and your knowledge of IT support, provide 3 key actionable insights for an IT manager.
    Focus on identifying patterns, potential risks, or areas for operational improvement.
    For each insight, provide a brief explanation and a concise, actionable recommendation.

    Format your response clearly:
    **Insight 1: [Briefly state the insight]**
       *Explanation:* [Provide a short explanation of why this is an insight]
       *Recommendation:* [Provide a concrete, actionable step]

    **Insight 2: [Briefly state the insight]**
       *Explanation:* ...
       *Recommendation:* ...

    **Insight 3: [Briefly state the insight]**
       *Explanation:* ...
       *Recommendation:* ...
    """
    prompt_messages = [
        {"role": "system", "content": system_message_insights},
        {"role": "user", "content": user_message_insights}
    ]

    insights_response = call_openai_api(prompt_messages, model="gpt-3.5-turbo", temperature=0.5, max_tokens=600)
    logger.info(f"--- Exiting generate_insights ---")
    return insights_response