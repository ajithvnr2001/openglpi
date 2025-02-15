import os
from fastapi import FastAPI, Request, BackgroundTasks
from glpi_connector import GLPIConnector
from llm_service import LLMService
from pdf_generator import PDFGenerator
from dotenv import load_dotenv
from typing import Dict, Any, List
import uvicorn
import json
import re  # Import the regular expression module

load_dotenv()

app = FastAPI()

glpi_url = os.getenv("GLPI_URL")
app_token = os.getenv("GLPI_APP_TOKEN")
user_token = os.getenv("GLPI_USER_TOKEN")
glpi = GLPIConnector(glpi_url, app_token, user_token)
llm_service = LLMService()

async def process_ticket(ticket_id: int):
    """Fetches ticket details, processes with LLM, and generates PDF."""
    try:
        # Fetch Ticket Details
        ticket = glpi.get_ticket(ticket_id)
        if not ticket:
            print(f"Error: Could not retrieve ticket with ID {ticket_id}")
            return
        tickets=[ticket] #making a list to keep same format with previous code.

        # --- IMPROVED PROMPT (Even More Specific) ---
        query = f"""
Analyze the following GLPI ticket content and provide a concise, well-structured summary.  DO NOT add any extra text or filler.  Focus ONLY on summarizing the provided information.

Include the following sections:

1.  **Problem Description:** Describe the issue (what, when, who, where).
2.  **Troubleshooting Steps:** List the steps taken (use bullet points).
3.  **Solution:** Describe the solution (if any).
4.  **Key Information:** Do not mention or guess the Ticket ID.

GLPI Ticket Content:
{ticket.get('content',"")}
        """
        # --- END IMPROVED PROMPT ---

        rag_result = llm_service.rag_completion(tickets, query)
        print(f"RAG Result: {rag_result}")

        # --- POST-PROCESSING ---
        cleaned_result = post_process_llm_output(rag_result)

        # PDF Generation
        pdf_generator = PDFGenerator(f"glpi_ticket_{ticket_id}.pdf")
        source_info = [{"source_id": ticket_id, "source_type": "glpi_ticket"}]
        pdf_generator.generate_report(
            f"Ticket Analysis - #{ticket_id}", cleaned_result, source_info  # CORRECTED:  Pass source_info
        )
        print(f"Report generated: glpi_ticket_{ticket_id}.pdf")

    except Exception as e:
        print(f"Error processing ticket {ticket_id}: {e}")


def post_process_llm_output(text: str) -> str:
    """Cleans up the LLM output by removing unwanted text and empty bullets."""

    # 1. Remove generic/repetitive phrases (using regular expressions)
    text = re.sub(r"Please let me know if you need any further assistance\.?|I'm here to help\.?|Best regards, \[Your Name] IT Support Assistant\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"If you have any further questions or need any additional assistance.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"However, it is assumed that a ticket ID exists in the actual GLPI ticket\..*I don't know\.", "", text, flags=re.IGNORECASE)
    text = re.sub(r"No ticket ID is provided in the given content.*Ticket ID:  \(Unknown\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Note: The provided content does not include a ticket ID\..*I don't know", "", text, flags=re.IGNORECASE)

    # 2. Remove empty bullet points and leading/trailing whitespace
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith("*") and len(line) > 1:  # Keep non-empty bullets
            cleaned_lines.append(line)
        elif not line.startswith("*") and line: # Keep non-empty non-bullet lines.
            cleaned_lines.append(line)


    return "\n".join(cleaned_lines)


@app.post("/webhook")
async def glpi_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handles incoming webhook requests from GLPI."""
    try:
        data: List[Dict[str, Any]] = await request.json()
        print(f"Received webhook data: {data}")  # Log the raw webhook data

        for event in data:
            if event.get("event") == "add" and event.get("itemtype") == "Ticket":
                ticket_id = int(event.get("items_id"))  # Ensure it's an integer
                background_tasks.add_task(process_ticket, ticket_id) #process in background
                return {"message": f"Ticket processing initiated for ID: {ticket_id}"}

        return {"message": "Webhook received, but no relevant event found."}

    except json.JSONDecodeError:
        return {"error": "Invalid JSON payload"}
    except Exception as e:
      return {"error":str(e)}

@app.get("/test_llm")
async def test_llm_endpoint():
    test_prompt = "what is the capital of Assyria"
    response = llm_service.complete(prompt=test_prompt)
    return {"response":response}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) # use any port for your application.
