# File path: frontend/pages/🎟️_Chat_Assistant.py
# frontend/pages/🎟️_Chat_Assistant.py

import streamlit as st
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import re

# --- Determine Project Root and Add to Python Path ---
try:
    # Get the directory of the current file
    SCRIPT_DIR = Path(__file__).resolve().parent
    # Calculate the project root by going up three levels
    PROJECT_ROOT = SCRIPT_DIR.parent.parent
except NameError:
    # Handle cases where __file__ is not defined (e.g., interactive mode)
    PROJECT_ROOT = Path.cwd()
    logging.warning(f"Could not determine script directory, assuming project root is CWD: {PROJECT_ROOT}")

# Add the project root to the Python path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    logging.info(f"Added project root to sys.path: {PROJECT_ROOT}")

# Now import the backend functions
from backend.openai_agent import get_ticket_summary, get_ticket_resolution

# --- Basic Logging Setup ---
# Consistent logging format
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - CHAT_ASSISTANT - %(message)s')
logger = logging.getLogger("ChatAssistant") # Use a named logger

# --- Load Environment Variables ---
# Load .env file from the project root
try:
    current_file_path = Path(__file__).resolve()
    project_root = current_file_path.parent.parent.parent # Assumes pages -> frontend -> root
    dotenv_path = project_root / '.env'
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
        logger.info(f"Loaded .env file from: {dotenv_path}")
    else:
        logger.warning(f".env file not found at calculated path: {dotenv_path}. Relying on default load_dotenv().")
        load_dotenv() # Try default search path
except Exception as e:
    logger.error(f"Error loading .env file: {e}. Trying default load_dotenv().")
    load_dotenv()

API_KEY_LOADED = os.getenv("OPENAI_API_KEY") is not None
logger.info(f"OpenAI API Key Loaded: {API_KEY_LOADED}")
if not API_KEY_LOADED:
    st.error("⚠️ **Configuration Error:** OpenAI API Key not found. Please ensure it is set in your `.env` file.")
    logger.critical("OpenAI API Key not found in environment variables.")
    # Optionally stop execution if the app cannot function without the key
    # st.stop()

# --- Page Configuration ---
st.set_page_config(page_title="Chat Assistant", layout="wide") # Set page config here if not in main.py
st.title("🎟️ Chat Assistant")
st.markdown("Ask me to summarize or suggest resolutions for tickets (e.g., `summarize ticket #5`, `solve ticket #12`, or `summarize and solve ticket #5`).")

# --- Initialize Chat History ---
if "messages" not in st.session_state:
    logger.info("Initializing chat history in session state.")
    st.session_state.messages = [
        {"role": "assistant", "content": "How can I help with your tickets today? (e.g., 'summarize ticket #5', 'solve ticket #10')"}
    ]

# --- Display Existing Chat Messages ---
logger.debug("Displaying existing chat messages from session state.")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Handle User Input ---
if prompt := st.chat_input("Ask about a ticket..."):
    logger.info(f"Received user prompt: '{prompt}'")
    # Add user message to chat history immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- Process the User's Request (Handles Multiple Actions) ---
    response = "" # Initialize response string
    prompt_lower = prompt.lower()

    with st.spinner("Thinking..."):
        # Regex to find "ticket #<number>" pattern more robustly
        match = re.search(r"ticket\s*#(\d+)", prompt_lower)

        if match:
            ticket_num_str = match.group(1) # Extract the number captured by (\d+)
            # Construct the expected title format used during ingestion
            target_ticket_title = f"ticket_{ticket_num_str}"
            logger.info(f"Found 'ticket #{ticket_num_str}'. Constructed title: '{target_ticket_title}'")

            try:
                # --- Detect Requested Actions ---
                # Check for keywords indicating summary request
                request_summary = "summary" in prompt_lower or "summarize" in prompt_lower
                # Check for keywords indicating resolution request (EXPANDED KEYWORDS)
                request_resolution = ("solve" in prompt_lower or
                                      "resolution" in prompt_lower or
                                      "fix" in prompt_lower or
                                      "solution" in prompt_lower or # Added "solution"
                                      "suggest" in prompt_lower)    # Added "suggest"

                summary_response = ""
                resolution_response = ""
                action_performed = False # Flag to track if any action was taken

                # --- Call Functions Based on Detected Actions ---
                if request_summary:
                    logger.info(f"Action detected: summary for ticket title '{target_ticket_title}'")
                    summary_text = get_ticket_summary(target_ticket_title)
                    action_performed = True
                    # Check if the backend returned an error or valid summary
                    if summary_text is None or "Error:" in str(summary_text) or "Sorry, I could not find" in str(summary_text):
                         logger.error(f"Error getting summary for {target_ticket_title}: {summary_text}")
                         summary_response = f"_(Error retrieving summary for ticket #{ticket_num_str}. Reason: {summary_text})_"
                    else:
                         summary_response = summary_text # Store valid summary

                if request_resolution:
                    logger.info(f"Action detected: resolution for ticket title '{target_ticket_title}'")
                    resolution_text = get_ticket_resolution(target_ticket_title)
                    action_performed = True
                    # Check if the backend returned an error or valid resolution
                    if resolution_text is None or "Error:" in str(resolution_text) or "Sorry, I could not find" in str(resolution_text):
                        logger.error(f"Error getting resolution for {target_ticket_title}: {resolution_text}")
                        resolution_response = f"_(Error retrieving resolution for ticket #{ticket_num_str}. Reason: {resolution_text})_"
                    else:
                        resolution_response = resolution_text # Store valid resolution


                # --- Combine Responses Based on What Was Requested and Successful ---
                response_parts = []
                if request_summary and summary_response: # Add summary if requested and available (or if error message generated)
                    response_parts.append(f"**Summary for Ticket #{ticket_num_str}:**\n{summary_response}")

                if request_resolution and resolution_response: # Add resolution if requested and available
                    # Only add heading if summary wasn't also requested OR if summary failed
                    heading = "**Suggested Solution"
                    if request_summary and summary_response and "Error" not in summary_response :
                         heading = "**Also, Suggested Solution" # Change heading if summary is also present

                    response_parts.append(f"{heading} for Ticket #{ticket_num_str}:**\n{resolution_response}")

                if response_parts:
                    # Combine the parts with a separator if both exist
                    response = "\n\n---\n\n".join(response_parts)
                elif action_performed:
                    # An action was requested but resulted in errors for both summary and resolution
                    response = f"Sorry, I encountered errors trying to get the requested information for ticket #{ticket_num_str}. Please check the logs."
                else:
                    # Ticket number found, but no action keywords (summary/solve etc.)
                    logger.info(f"Ticket title '{target_ticket_title}' identified, but no clear action keyword found.")
                    response = f"Okay, I can look up information for ticket '{target_ticket_title}' (Ticket #{ticket_num_str}). What specific action would you like? (e.g., 'summarize' or 'solve')"

            except Exception as e:
                # Catch potential errors during processing this specific ticket request
                logger.error(f"Error processing prompt for title '{target_ticket_title}': {e}", exc_info=True)
                response = f"Sorry, I encountered an error trying to process your request for ticket #{ticket_num_str}. Please check the system logs or try again later."

        else:
            # "ticket #" pattern was NOT found in the prompt. Handle general queries or give guidance.
            # This part could be expanded later to handle more general QA if needed.
            logger.info("Prompt does not match 'ticket #<number>' pattern. Providing default guidance.")
            response = "I can help with specific tickets identified by their number (e.g., 'summarize ticket #5'). How can I assist?"


        # --- Post-processing the final response string ---
        if response is None:
             logger.error("Generated response was None unexpectedly after processing!")
             response = "Sorry, an internal error occurred, and I received an empty response."
        elif not isinstance(response, str):
             logger.error(f"Backend function returned non-string type: {type(response)}")
             response = "Sorry, an unexpected response format was received from the backend."
        elif not response.strip(): # Check if response is empty or just whitespace AFTER stripping
             logger.warning(f"Generated response was empty or whitespace for prompt: '{prompt}'")
             response = "Sorry, I couldn't generate a specific response for that request." # Avoid empty bubble


    # --- Display Assistant Response ---
    # Only display and add to history if there's a meaningful response string
    if response and response.strip():
        logger.info(f"Displaying generated response (first 100 chars): '{response[:100]}...'")
        with st.chat_message("assistant"):
            st.markdown(response)
        # Add the valid assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        logger.info("Assistant response added to history and displayed.")
    else:
        # Log if response was empty or invalid after processing, but don't display/add
        logger.error(f"Final response was empty or invalid after processing prompt '{prompt}'. No message displayed.")


    # Use st.rerun() to update the chat display immediately after processing
    # This helps make the interaction feel more responsive.
    st.rerun()
