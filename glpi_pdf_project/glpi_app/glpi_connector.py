import requests
import json
from typing import List, Dict, Optional

class GLPIConnector:
    def __init__(self, glpi_url: str, app_token: str, user_token:Optional[str]=None):
        self.glpi_url = glpi_url  # This is now the BASE URL, ending in /apirest.php
        self.app_token = app_token
        self.headers = {
            "Content-Type": "application/json",
            "App-Token": self.app_token,
        }
        self.session_token = None
        self.user_token=user_token

    def init_session(self) -> bool:
        """Initializes a GLPI session and gets the session token."""
        # Construct the FULL URL for initSession
        init_url = f"{self.glpi_url}/initSession"  # CORRECT: Appends /initSession
        if self.user_token:
            self.headers["Authorization"]=f"user_token {self.user_token}"
        try:
            response = requests.get(init_url, headers=self.headers)
            response.raise_for_status()  # Raise an exception for bad status codes
            self.session_token = response.json().get("session_token")
            if self.session_token:
                self.headers["Session-Token"] = self.session_token
                if "Authorization" in self.headers:
                  del self.headers["Authorization"]
                return True
            else:
                print("Error: Could not initialize GLPI session.")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Error initializing session: {e}")
            return False

    def kill_session(self) -> bool:
        """Kills the current GLPI session"""
        # Construct the FULL URL for killSession
        kill_url = f"{self.glpi_url}/killSession" # CORRECT: Appends /killSession

        if not self.session_token:
          return True

        try:
            response = requests.get(kill_url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error killing session: {e}")
            return False

    def _ensure_session(self):
        """Ensures that a valid session token exists before making API calls."""
        if not self.session_token:
            if not self.init_session():
                return False  # Session initialization failed
        return True

    def get_tickets(self, range_str:str="0-10") -> List[Dict]:
        """Retrieves a list of tickets from GLPI."""
        if not self._ensure_session(): # Check for session
            return []

        # Construct the FULL URL for Ticket
        tickets_url = f"{self.glpi_url}/Ticket?range={range_str}" # CORRECT: Appends /Ticket

        try:
            response = requests.get(tickets_url, headers=self.headers)
            response.raise_for_status()
            tickets = response.json()

            # Extract relevant ticket data.  Adapt this based on your needs.
            extracted_tickets = []
            for ticket in tickets:
                extracted_tickets.append({
                    "id": ticket.get("id"),
                    "name": ticket.get("name"),
                    "content": ticket.get("content"),  # May contain HTML
                    "status": ticket.get("status"),
                    "date": ticket.get("date"),
                    # Add other relevant fields here.
                })
            return extracted_tickets

        except requests.exceptions.RequestException as e:
            print(f"Error retrieving tickets: {e}")
            return []

    def get_ticket(self,id) -> Dict:
        """Retrieves a list of tickets from GLPI."""
        if not self._ensure_session(): # Check for session
            return []
        # Construct the FULL URL for a specific Ticket
        tickets_url = f"{self.glpi_url}/Ticket/{id}" # CORRECT: Appends /Ticket/{id}

        try:
            response = requests.get(tickets_url, headers=self.headers)
            response.raise_for_status()
            ticket = response.json()

            # Extract relevant ticket data.  Adapt this based on your needs.

            return ticket


        except requests.exceptions.RequestException as e:
            print(f"Error retrieving tickets: {e}")
            return []
