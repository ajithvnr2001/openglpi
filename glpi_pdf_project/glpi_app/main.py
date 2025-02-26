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
    """Fetches ticket, processes with LLM, generates PDF (multi-step)."""
    try:
        ticket = glpi.get_ticket(ticket_id)
        if not ticket:
            print(f"Error: Could not retrieve ticket {ticket_id}")
            return
        tickets = [ticket]
        ticket_content = ticket.get('content', "")

        # --- Step 1: Initial Summarization (Broad Strokes) ---
        initial_query = f"""
Analyze the following GLPI ticket content and produce a concise summary.
AVOID ALL conversational phrases, introductions, and conclusions.

Output MUST be structured EXACTLY as follows:

1.  **Problem Description:**  Describe the issue concisely.
2.  **Troubleshooting Steps:** List ALL troubleshooting steps, using bullet points (*).
3.  **Solution:** Describe the solution, if one was found. If not, state "No solution found."

GLPI Ticket Content:
{ticket_content}
        """
        initial_result = llm_service.rag_completion(tickets, initial_query)
        print(f"Initial RAG Result: {initial_result}")
        initial_result = post_process_llm_output(initial_result) # Clean up.

        # --- Step 2: Targeted Extraction for Key Information ---
        key_info = {}  # Store extracted info here

        # Define prompts for each key information item
        key_info_prompts = {
            "affected_systems": "List the affected system(s) from the GLPI ticket content. Be concise.",
            "error_messages": "Extract all error messages from the GLPI ticket content.  If none, respond with 'None'.",
            "affected_users": "List all affected users from the GLPI ticket content. If none, respond with 'None'.",
            "start_time": "What is the start time of the issue described in the GLPI ticket content?",
            "suspected_causes": "List the suspected cause(s) of the issue from the GLPI ticket content. Be concise.",
            "resolution_steps": "Briefly list the steps taken to *resolve* the issue (if different from troubleshooting) from the GLPI ticket content.",
        }

        for key, prompt in key_info_prompts.items():
            full_prompt = f"{prompt}\n\nGLPI Ticket Content:\n{ticket_content}"
            response = llm_service.complete(prompt=full_prompt) # No RAG here, just completion.
            print(f"Key Info ({key}) RAW Response: {response}")
            key_info[key] = post_process_key_info_item(response) # Clean up *each item*.
            print(f"Key Info ({key}) Cleaned: {key_info[key]}")


        # --- Step 3: Assemble and Generate PDF ---

        pdf_generator = PDFGenerator(f"glpi_ticket_{ticket_id}.pdf")
        source_info = [{"source_id": ticket_id, "source_type": "glpi_ticket"}]
        pdf_generator.generate_report(
            f"Ticket Analysis - #{ticket_id}",
            initial_result,  # The initial summary (Problem, Steps, Solution)
            source_info,
            key_info  # Pass the structured key_info dictionary
        )
        print(f"Report generated: glpi_ticket_{ticket_id}.pdf")

    except Exception as e:
        print(f"Error processing ticket {ticket_id}: {e}")
    finally:
        glpi.kill_session()


def post_process_llm_output(text: str) -> str:
    """Cleans LLM output for initial summary sections."""
    text = re.sub(r"(?i)please let me know if you need any further assistance[\.,]?|i'm here to help[\.,]?|best regards, \[your name] it support assistant[\.,]?", "", text)
    text = re.sub(r"(?i)if you have any further questions or need any additional assistance.*", "", text)
    text = re.sub(r"(?i)however, it is assumed that a ticket id exists in the actual glpi ticket\.?.*i don't know\.?", "", text)
    text = re.sub(r"(?i)no ticket id is provided in the given content.*ticket id:  \(unknown\)", "", text)
    text = re.sub(r"(?i)note: the provided content does not include a ticket id\.?.*i don't know", "", text)

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith("*") and len(line) > 1:
            cleaned_lines.append(line)
        elif not line.startswith("*") and line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def post_process_key_info_item(text: str) -> str:
    """Cleans a SINGLE key information item (removes extra text)."""
    text = text.strip()
    # Remove any leading/trailing quotes or other non-alphanumeric characters
    text = re.sub(r"^[\W_]+|[\W_]+$", "", text)
    return text


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
        return {"error": str(e)}



@app.get("/test_llm")
async def test_llm_endpoint():
    test_prompt = "what is the capital of Assyria"
    response = llm_service.complete(prompt=test_prompt)
    return {"response":response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
