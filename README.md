GLPI PDF Project

This project provides a FastAPI application that integrates with GLPI, retrieves ticket information, uses an LLM (Language Model) to summarize the ticket content, and generates a PDF report of the analysis. The PDF is then uploaded to a Wasabi S3 bucket.  The application is containerized using Docker and Docker Compose for easy deployment.

Project Structure:

```bash
glpi_pdf_project/
├── glpi_app/
│ ├── .env # Environment variables (IMPORTANT: See setup below)
│ ├── Dockerfile # Dockerfile for building the application image
│ ├── glpi_connector.py # Handles communication with the GLPI API
│ ├── llm_service.py # Handles LLM interactions and vectorstore creation
│ ├── main.py # FastAPI application logic (webhook, endpoints)
│ ├── pdf_generator.py # Generates PDF reports using ReportLab
│ └── requirements.txt # Python dependencies
│
└── docker-compose.yml # Docker Compose configuration for running the application
```


Setup and Configuration:

1.Environment Variables:

    Create a `.env` file inside the `glpi_app` directory.  This file should contain the following environment variables, with values appropriate for your GLPI instance, Akash Network, and Wasabi S3 bucket:

    ```
    GLPI_URL=https://your-glpi-instance.com/apirest.php  # Replace with your GLPI API URL
    GLPI_APP_TOKEN=your_glpi_app_token               # Replace with your GLPI App Token
    GLPI_USER_TOKEN=your_glpi_user_token             # Replace with your GLPI User Token (optional, but recommended)
    AKASH_API_KEY=sk-your-akash-api-key          # Replace with your Akash API key
    AKASH_API_BASE=https://chatapi.akash.network/api/v1 #Akash API base
    WASABI_ENDPOINT_URL=https://s3.your-wasabi-region.wasabisys.com  # Replace with your Wasabi endpoint URL
    WASABI_ACCESS_KEY_ID=your_wasabi_access_key_id     # Replace with your Wasabi Access Key ID
    WASABI_SECRET_ACCESS_KEY=your_wasabi_secret_access_key  # Replace with your Wasabi Secret Access Key
    WASABI_BUCKET_NAME=your_wasabi_bucket_name         # Replace with your Wasabi Bucket Name
    WASABI_REGION=your-wasabi-region #your wasabi region
    ```

    *   **`GLPI_URL`**:  The base URL for your GLPI API.  Make sure it ends with `/apirest.php`.
    *   **`GLPI_APP_TOKEN`**:  Your GLPI application token.
    *   **`GLPI_USER_TOKEN`**: Your GLPI user token (highly recommended for session management).
    *   **`AKASH_API_KEY`**:  Your API key for the Akash Network (used for LLM access).
    *    **`AKASH_API_BASE`**: Akash Network API base url
    *   **`WASABI_ENDPOINT_URL`**:  The endpoint URL for your Wasabi S3 bucket.
    *   **`WASABI_ACCESS_KEY_ID`**: Your Wasabi Access Key ID.
    *   **`WASABI_SECRET_ACCESS_KEY`**: Your Wasabi Secret Access Key.
    *   **`WASABI_BUCKET_NAME`**: The name of your Wasabi S3 bucket.
     *   **`WASABI_REGION`**: Your wasabi region.

    **Security Note:  Do *not* commit your `.env` file to version control (e.g., Git).  Add `.env` to your `.gitignore` file.  This file contains sensitive credentials.

2.  **Install Docker and Docker Compose:**

    You need to have Docker and Docker Compose installed on your system.  Refer to the official Docker documentation for installation instructions:

    *   Docker: [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)
    *   Docker Compose: [https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/)

## Running the Application

1.  **Navigate to the project directory:**

    ```bash
    cd glpi_pdf_project
    ```

2.  **Build and run the application using Docker Compose:**

    ```bash
    docker-compose up --build
    ```

    This command will:

    *   Build the Docker image for the `glpi-app` service (using the `Dockerfile`).
    *   Start the `glpi-app` container, exposing port 8001.
    *   Use the environment variables from your `.env` file.
    * `--build` option ensures to build the image.

3.  **Access the API:**

    Once the application is running, you can access the following endpoints:

    *   **`/webhook` (POST):**  This is the endpoint that GLPI will call when a new ticket is created.  You'll need to configure a webhook in GLPI to point to this endpoint (see GLPI Webhook Configuration section).
    *   **`/test_llm` (GET):** This is a test endpoint that you can use to verify that the LLM is working correctly.  It sends a simple prompt to the LLM and returns the response.

    You can test the `/test_llm` endpoint by opening your web browser and going to:

    ```
    http://localhost:8001/test_llm
    ```

    You should see a JSON response with the LLM's completion of the test prompt.

## GLPI Webhook Configuration

1.  **Install the GLPI Webhooks Plugin:**  You'll need to install the "Webhooks" plugin in your GLPI instance.

2.  **Configure a New Webhook:**

    *   Go to "Setup" -> "Notifications" -> "Webhooks".
    *   Click the "+" button to add a new webhook.
    *   Give the webhook a name (e.g., "Ticket Creation Webhook").
    *   Set the "Webhook URL" to:  `http://<your-server-ip-or-domain>:8001/webhook`
        *   Replace `<your-server-ip-or-domain>` with the IP address or domain name of the server where your Docker container is running.  If you're running it locally, you might use `localhost` or `127.0.0.1`.
    *   Set the "Event" to "Ticket added".  (This is crucial; the code expects the `"event": "add"` and `"itemtype": "Ticket"` fields in the webhook payload.)
    *   Save the webhook.

3.  **Test the Webhook:**

    *   Create a new ticket in GLPI.
    *   Check the logs of your Docker container (`docker logs <container_id>`).  You should see messages indicating that the webhook was received and that the ticket is being processed.  A PDF should be generated and uploaded to your Wasabi S3 bucket.

## Stopping the Application

To stop the application, press `Ctrl+C` in the terminal where you ran `docker-compose up`.  Alternatively, you can run:


docker-compose down


This will stop and remove the containers.

Code Explanation

glpi_connector.py:

The GLPIConnector class handles all interactions with the GLPI API.

init_session(): Gets a session token from GLPI (using user token if provided).

kill_session(): Terminates the GLPI session.

_ensure_session(): Checks if the session is valid and re-initializes it if necessary. This is important for handling session timeouts. It now actively tests the session.

get_tickets(): Retrieves a list of tickets (with pagination support).

get_ticket(): Retrieves a single ticket by ID.

llm_service.py:

The LLMService class handles interactions with the LLM.

get_embedding_function(): Returns a Hugging Face embedding function (BAAI/bge-large-en-v1.5).

create_vectorstore(): Creates a Chroma vector store from text chunks.

query_llm(): Queries the LLM using RetrievalQA.

rag_completion(): Performs RAG (Retrieval-Augmented Generation) to answer a query based on the provided documents.

process_documents_to_chunks(): Processes GLPI ticket content into text chunks suitable for the vector store.

complete(): Sends a prompt to the LLM and gets a completion.

main.py:

The process_ticket() function orchestrates the entire process: fetches ticket details, uses the LLM to summarize the ticket, and generates the PDF. This function now uses the user token for authentication.

post_process_llm_output() to remove any generic/repetitive text and empty bullet points.

The /webhook endpoint receives webhook events from GLPI, extracts the ticket ID, and starts the process_ticket function in the background.

The /test_llm endpoint is a simple test for the LLM.

pdf_generator.py:

The PDFGenerator class handles PDF creation and uploading to Wasabi S3.

generate_report(): Creates the PDF document, structures the content (title, summarized result, source information), builds the PDF, uploads it to S3, and then deletes the local file.

upload_to_s3(): Uploads a given file to the configured Wasabi S3 bucket.

_add_structured_result: Parses the LLM result into sections and formats them with proper headings and bullet points.

Dockerfile: This file defines how to build the Docker image for the application. It uses a slim Python 3.11 base image, installs dependencies, copies the application code, and sets the command to run the application using Uvicorn.

docker-compose.yml: Defines glpi-app services using build,ports,env_file.


LLM Choice: The code defaults to a Llama3 model. we can experiment with different models and adjust the temperature and max_tokens parameters as needed.


glpi admin page:https://ltimindtree.in1.glpi-network.cloud/front/central.php

cred: admin

password:0000asdfA!




