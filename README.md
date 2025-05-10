<!-- File path: README.md -->
# RiskAgentAPP

## Description

RiskAgentAPP is a tool for managing and analyzing risk tickets. It allows users to get tickets from  a Database (This a sample so we create our own database and we manually add ai generated tickets to the database), categorize them, and generate insights.

## Features

*   **Ticket Management:** Create, categorize, and manage risk tickets.
*   **Analytics Dashboard:** Visualize risk data and generate insights.
*   **Chat Assistant:** Interact with a chat assistant to get help and information.

## Technologies

*   Python
*   FastAPI
*   Streamlit
*   Langchain
*   OpenAI API
*   MySQL DATABASE


## Setup

1.  Clone the repository:

    ```bash
    git clone <repository_url>
    ```
2.  Install the dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Run the backend:

    ```bash
    python3 backend/main.py
    ```
2.  Run the frontend:

    ```bash
    streamlit run frontend/main.py
