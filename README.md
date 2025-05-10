<!-- File path: README.md -->
# Riskalyze AI: Visualize. Analyze. Riskalyze.

**Riskalyze AI** is a comprehensive solution for managing, analyzing, and resolving IT support and risk tickets. It leverages AI to automatically categorize tickets, provide summaries, suggest resolutions, and generate actionable insights from your ticket data (This a sample so we create our own database and we manually add AI generated tickets to the database), categorize them, and generate insights, empowering teams to work more efficiently and proactively address issues.

## Main Features

*   **Ticket Management:** Create, categorize, and manage risk tickets.
*   **Analytics Dashboard:** Visualize risk data and generate insights.
*   **Chat Assistant:** Interact with a chat assistant to get help and information.

## Features 

*   **Automated Document Ingestion:** Processes `.txt`, `.pdf`, and `.docx` files, extracting content to create new tickets.
*   **AI-Powered Ticket Categorization:** Utilizes OpenAI's GPT models to automatically assign categories to new tickets based on their content.
*   **Intelligent Chat Assistant:**
    *   Provides concise summaries of ticket descriptions.
    *   Suggests detailed, actionable resolution steps.
*   **Comprehensive Analytics Dashboard:**
    *   Visualizes key metrics: total tickets, daily volume, category distribution, status breakdown.
    *   Tracks ticket trends over time (daily, weekly, monthly).
    *   Analyzes resolution times and highlights bottlenecks.
    *   Offers AI-generated insights from the overall ticket data.
    *   Interactive filters for date range, category, and status.
    *   Data export functionality (CSV).
*   **Scalable Backend:** Built with Python, SQLAlchemy for database interaction.
*   **User-Friendly Frontend:** Interactive web interface powered by Streamlit.

## Technologies

*   **Backend:** Python, SQLAlchemy, PyMySQL
*   **AI Integration:** OpenAI API (GPT-3.5-turbo)
*   **Frontend:** Streamlit, Plain CSS
*   **Data Handling:** Pandas
*   **Document Processing:** PyMuPDF (Fitz), python-docx
*   **Database:** MySQL (or any SQLAlchemy-compatible RDBMS)
*   **Environment Management:** python-dotenv

## Project Structure
![Screenshot from 2025-05-10 13-51-47](https://github.com/user-attachments/assets/32423260-3a58-4d15-bdb7-6d0d086f604e)


## Setup and Installation

### Prerequisites

*   Python 3.9 or higher
*   Access to a MySQL database (or other SQLAlchemy-compatible database)
*   OpenAI API Key

### Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/BryanHE24/RiskalyzeAI
    cd RiskalyzeAI
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows
    # venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables:**
    *   Create the `.env` file with your credentials:
        ```env
        OPENAI_API_KEY="sk-your_openai_api_key"
        DATABASE_URL="mysql+pymysql://user:password@host:port/database_name"
        ```
        *Example `DATABASE_URL` for local MySQL:* `mysql+pymysql://root:your_password@localhost/riskalyze_db`

5.  **Set Up the Database:**
    *   Ensure your MySQL server is running.
    *   Create a database (e.g., `riskalyze_db`).
    *   Connect to your database and execute the `database/sample_data/schema.sql` script to create the `tickets` table.
        ```bash
        # Example using mysql CLI
        mysql -u your_user -p your_database_name < database/sample_data/schema.sql
        ```

## Usage

1.  **Populate with Sample Data (Optional but Recommended for First Run):**
    This script will generate sample `.txt`, `.pdf`, and `.docx` files in `database/sample_data/` and then ingest them into the database.
    ```bash
    python run_ingestion.py
    ```

2.  **Run AI Categorization (Optional):**
    If you ingested data that has 'Pending' categories (like the sample data), run this script to have the AI categorize them:
    ```bash
    python scripts/run_categorization.py
    ```
    *Note: This will make calls to the OpenAI API and may incur costs.*

3.  **Run the Streamlit Application:**
    ```bash
    streamlit run frontend/main.py
    ```
    The application will typically be available at `http://localhost:8501`.

    Navigate through the sidebar:
    *   **Chat Assistant:** Interact with the AI for ticket summaries and resolution suggestions.
    *   **Analytics Dashboard:** Explore ticket data, visualizations, and AI-generated insights.


## Future Enhancements

*   User authentication and role-based access.
*   Real-time ticket updates and notifications.
*   More sophisticated risk scoring models.
*   Integration with existing ticketing systems (e.g., JIRA, Zendesk).
*   Ability to manually edit ticket details and categories via the UI.
*   Automated report generation.
*   Fine-tuning models for domain-specific language.


## Images

![Screenshot from 2025-04-13 21-15-02](https://github.com/user-attachments/assets/028497e4-0460-4400-a85c-cf36cce2a020)
![Screenshot from 2025-04-13 21-16-36](https://github.com/user-attachments/assets/a818cbcf-2cb9-4e7e-a12f-f9b642525776)
![Screenshot from 2025-04-13 21-20-03](https://github.com/user-attachments/assets/6148736f-fd89-41a6-9630-f666cee1318e)
![Screenshot from 2025-04-13 21-20-34](https://github.com/user-attachments/assets/f2a41150-830b-4fbd-9d94-535dae386350)
![Screenshot from 2025-04-13 21-20-46](https://github.com/user-attachments/assets/e7a994db-b2b7-42a0-b54a-672eeceed907)
![Screenshot from 2025-04-13 21-20-52](https://github.com/user-attachments/assets/7940d48f-e2ee-4d6b-b487-c22a3ebaf577)
![Screenshot from 2025-04-13 21-20-58](https://github.com/user-attachments/assets/1ae13042-acc7-4888-b7cc-24343ed83957)

