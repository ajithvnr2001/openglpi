import os
from fastapi import FastAPI, Request, BackgroundTasks
from glpi_connector import GLPIConnector
from llm_service import LLMService
from pdf_generator import PDFGenerator
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

glpi = GLPIConnector(
    glpi_url=os.getenv("GLPI_URL"),
    app_token=os.getenv("GLPI_APP_TOKEN"),
    user_token=os.getenv("GLPI_USER_TOKEN")
)
llm_service = LLMService()

async def process_ticket(ticket_id: int):
    try:
        ticket = glpi.get_ticket(ticket_id)
        if not ticket:
            return
        query = "Provide a detailed summary of this ticket including key issues and suggested resolution steps."
        rag_result = llm_service.rag_completion([ticket], query)
        
        pdf_generator = PDFGenerator(f"glpi_ticket_{ticket_id}.pdf")
        pdf_generator.generate_report(
            title=f"Ticket Analysis - #{ticket_id}",
            query=query,
            result=rag_result,
            source_info=[{
                "source_id": ticket_id,
                "source_type": "glpi_ticket",
                "date_created": ticket.get("date")
            }]
        )
    except Exception as e:
        print(f"Error processing ticket: {e}")
    finally:
        glpi.kill_session()

@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        for event in data:
            if event.get("event") == "add" and event.get("itemtype") == "Ticket":
                ticket_id = int(event["items_id"])
                background_tasks.add_task(process_ticket, ticket_id)
                return {"status": "processing_started"}
        return {"status": "no_action_taken"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
