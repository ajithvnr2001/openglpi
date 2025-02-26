import os
from fastapi import FastAPI, Request, BackgroundTasks
from glpi_connector import GLPIConnector
from llm_service import LLMService
from pdf_generator import PDFGenerator
from dotenv import load_dotenv
from typing import Dict, Any, List
import uvicorn
import json
import re

load_dotenv()

app = FastAPI()

glpi_url = os.getenv("GLPI_URL")
app_token = os.getenv("GLPI_APP_TOKEN")
user_token = os.getenv("GLPI_USER_TOKEN")
glpi = GLPIConnector(glpi_url, app_token, user_token)
llm_service = LLMService()

async def process_ticket(ticket_id: int):
    """Fetches ticket, processes with LLM, and generates PDF."""
    try:
        ticket = glpi.get_ticket(ticket_id)
        if not ticket:
            print(f"Error: Could not retrieve ticket {ticket_id}")
            return
        tickets=[ticket]

        # --- EXTREMELY SPECIFIC PROMPT (Revised Again) ---
        query = f"""
Analyze the following GLPI ticket content and provide a detailed, concise summary.
DO NOT add any extra text, filler, or conversational phrases.  Focus ONLY on
summarizing the provided information accurately and completely.  DO NOT
truncate any information. Be as complete as possible.

Include these sections, exactly as named:

1.  **Problem Description:**  Describe the issue in detail, including what happened,
    when it happened, who is affected, and where it occurred.
2.  **Troubleshooting Steps:** List ALL troubleshooting steps taken, using bullet points.
    Be specific and complete.
3.  **Solution:**  Describe the solution in detail, if a solution was found.
    If no solution was found, state "No solution found."
4.  **Key Information:** Extract ALL key pieces of information of the ticket. Do not mention or guess the Ticket ID.

GLPI Ticket Content:
{ticket.get('content',"")}
        """
        # --- END EXTREMELY SPECIFIC PROMPT ---

        rag_result = llm_service.rag_completion(tickets, query)
        print(f"RAG Result: {rag_result}")

        cleaned_result = post_process_llm_output(rag_result)

        pdf_generator = PDFGenerator(f"glpi_ticket_{ticket_id}.pdf")
        source_info = [{"source_id": ticket_id, "source_type": "glpi_ticket"}]
        pdf_generator.generate_report(f"Ticket Analysis - #{ticket_id}", cleaned_result, source_info)
        print(f"Report generated: glpi_ticket_{ticket_id}.pdf")

    except Exception as e:
        print(f"Error processing ticket {ticket_id}: {e}")

    finally:
      glpi.kill_session()


def post_process_llm_output(text: str) -> str:
    """Cleans LLM output (remove unwanted text, empty bullets)."""

    # 1. Remove VERY specific phrases (more cautious)
    text = re.sub(r"(?i)please let me know if you need any further assistance[\.,]?|i'm here to help[\.,]?|best regards, \[your name] it support assistant[\.,]?", "", text)
    text = re.sub(r"(?i)if you have any further questions or need any additional assistance.*", "", text)
    text = re.sub(r"(?i)however, it is assumed that a ticket id exists in the actual glpi ticket\.?.*i don't know\.?", "", text)
    text = re.sub(r"(?i)no ticket id is provided in the given content.*ticket id:  \(unknown\)", "", text)
    text = re.sub(r"(?i)note: the provided content does not include a ticket id\.?.*i don't know", "", text)


    # 2. Remove empty bullets and leading/trailing whitespace
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith("*") and len(line) > 1:  # Keep non-empty bullets
            cleaned_lines.append(line)
        elif not line.startswith("*") and line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)



@app.post("/webhook")
async def glpi_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handles incoming webhook requests from GLPI."""
    try:
        data: List[Dict[str, Any]] = await request.json()
        print(f"Received webhook data: {data}")

        for event in data:
            if event.get("event") == "add" and event.get("itemtype") == "Ticket":
                ticket_id = int(event.get("items_id"))
                background_tasks.add_task(process_ticket, ticket_id)
                return {"message": f"Ticket processing initiated for ID: {ticket_id}"}

        return {"message": "Webhook received, no relevant event."}

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
    uvicorn.run(app, host="0.0.0.0", port=8001)
