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
llm_service = LLMService()  # We'll still use this for the initial summary.

async def process_ticket(ticket_id: int):
    """Fetches ticket, processes with LLM + rules, generates PDF."""
    try:
        ticket = glpi.get_ticket(ticket_id)
        if not ticket:
            print(f"Error: Could not retrieve ticket {ticket_id}")
            return
        tickets = [ticket]
        ticket_content = ticket.get('content', "")

        # --- Step 1: Initial Summarization (LLM - As Before) ---
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
        initial_result = post_process_llm_output(initial_result)  # Clean up.


        # --- Step 2: Key Information Extraction (RULE-BASED) ---
        key_info = {}

        # 1. Affected Systems
        key_info["affected_systems"] = extract_affected_systems(ticket_content)

        # 2. Error Messages
        key_info["error_messages"] = extract_error_messages(ticket_content)

        # 3. Affected Users
        key_info["affected_users"] = extract_affected_users(ticket_content)

        # 4. Start Time
        key_info["start_time"] = extract_start_time(ticket_content)

        # 5. Suspected Causes
        key_info["suspected_causes"] = extract_suspected_causes(ticket_content)

        # 6. Resolution Steps
        key_info["resolution_steps"] = extract_resolution_steps(ticket_content)


        # --- Step 3: Assemble and Generate PDF ---
        pdf_generator = PDFGenerator(f"glpi_ticket_{ticket_id}.pdf")
        source_info = [{"source_id": ticket_id, "source_type": "glpi_ticket"}]
        pdf_generator.generate_report(
            f"Ticket Analysis - #{ticket_id}",
            initial_result,
            source_info,
            key_info
        )
        print(f"Report generated: glpi_ticket_{ticket_id}.pdf")

    except Exception as e:
        print(f"Error processing ticket {ticket_id}: {e}")
    finally:
        glpi.kill_session()



def post_process_llm_output(text: str) -> str:
    """Cleans LLM output for initial summary sections (unchanged)."""
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


# --- Extraction Functions (Rule-Based) ---

def extract_affected_systems(content: str) -> str:
    """Extracts affected systems using regex and string manipulation."""
    match = re.search(r"The finance system \((.*?)\) is crashing", content)
    if match:
        system_name = match.group(1)
        # Check for server name
        server_match = re.search(r"Checked the FinSys server \((.*?)\)", content)
        if server_match:
            server_name = server_match.group(1)
            return f"{system_name}, {server_name}"  # Return combined
        return system_name
    return "Not Found"

def extract_error_messages(content: str) -> str:
    """Extracts error messages (within code blocks)."""
    error_matches = re.findall(r"```(.*?)```", content, re.DOTALL)
    if error_matches:
        return "\n".join(error_matches).strip()
    return "None"

def extract_affected_users(content: str) -> str:
    """Extracts affected users using regex."""
    user_matches = re.findall(r"\* ([\w\s]+) \([\w@\.]+\)", content)
    if user_matches:
         return "\n".join(user_matches)
    return "None"

def extract_start_time(content: str) -> str:
    """Extracts the start time using regex."""
    match = re.search(r"around (\d{1,2}:\d{2} [AP]M) on (\w+ \d{1,2}, \d{4})", content)
    if match:
        time = match.group(1)
        date = match.group(2)
        return f"{time}, {date}"
    return "Not Found"

def extract_suspected_causes(content: str) -> str:
    """Extracts suspected causes (using bullet-point logic)."""
    match = re.search(r"Suspected Cause:(.*?)(?:Solution:|Affected Users:)", content, re.DOTALL | re.IGNORECASE)
    if match:
        causes_section = match.group(1).strip()
        causes = [line.strip("* ").strip() for line in causes_section.split("\n") if line.strip("* ").strip()]
        return "\n".join(causes) if causes else "None"
    return "None"

def extract_resolution_steps(content: str) -> str:
    """Extract solution (using bullet-point logic)."""
    match = re.search(r"Solution:(.*?)(?:Key Information:|Affected Users:)", content, re.DOTALL | re.IGNORECASE) # Find text after "Solution:"
    if match:
        solution_section = match.group(1).strip()
        # Split into lines, remove leading/trailing whitespace and asterisks, and filter out empty lines
        solution_lines = [line.strip("* ").strip() for line in solution_section.split("\n") if line.strip("* ").strip()]
        return  "\n".join(solution_lines) if solution_lines else "None"
    return "None"



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
    uvicorn.run(app, host="0.0.0.0", port="8001")
