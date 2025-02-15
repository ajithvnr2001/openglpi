import os
from fastapi import FastAPI, Request, BackgroundTasks
from glpi_connector import GLPIConnector
from llm_service import LLMService
from pdf_generator import PDFGenerator
from dotenv import load_dotenv
from typing import Dict, Any, List
import uvicorn
import json

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

        # --- IMPROVED PROMPT ---
        query = f"""
You are an expert IT support assistant.  Analyze the following GLPI ticket and provide a concise, well-structured summary.

Include the following sections in your summary:

1.  **Problem Description:** Briefly describe the issue, including:
    *   What is the problem?
    *   When did it start?
    *   Who is affected?
    *   Where are they affected (location)?

2.  **Troubleshooting Steps:** List the steps already taken to diagnose the issue. Use bullet points.

3.  **Solution:** If a solution is provided in the ticket, describe it clearly. If no solution is given, state "No solution provided."

4. **Key Information:**
    * Ticket ID.

Here is the GLPI ticket content:
{ticket.get('content',"")}
        """
        # --- END IMPROVED PROMPT ---
        rag_result = llm_service.rag_completion(tickets, query)
        print(f"RAG Result: {rag_result}")

        # PDF Generation
        pdf_generator = PDFGenerator(f"glpi_ticket_{ticket_id}.pdf")
        source_info = [{"source_id": ticket_id, "source_type": "glpi_ticket"}]
        pdf_generator.generate_report(
            f"Ticket Analysis - #{ticket_id}", query, rag_result, source_info  # Pass the original query here
        )
        print(f"Report generated: glpi_ticket_{ticket_id}.pdf")

    except Exception as e:
        print(f"Error processing ticket {ticket_id}: {e}")

    finally:
      glpi.kill_session() # session will be killed.

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
