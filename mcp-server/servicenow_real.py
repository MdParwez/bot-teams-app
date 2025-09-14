import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv()

class ServiceNowClient:
    def __init__(self):
        self.instance_url = os.getenv('SNOW_INSTANCE')
        self.username = os.getenv('SNOW_USERNAME')
        self.password = os.getenv('SNOW_PASSWORD')
        
    def create_incident(self, user_id, software, version):
        """Create a real ServiceNow incident"""
        if not all([self.instance_url, self.username, self.password]):
            print("ServiceNow credentials not configured")
            return None
            
        api_url = f"{self.instance_url}/api/now/table/incident"
        
        # Encode credentials
        credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Create incident data
        incident_data = {
            "short_description": f"Software installation request: {software} {version}",
            "description": f"User {user_id} requested installation of {software} version {version} via Teams Bot",
            "urgency": "3",
            "impact": "3",
            "caller_id": user_id,
            "category": "software",
            "subcategory": "installation",
            "assignment_group": "it support"
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=incident_data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if 'result' in result and 'number' in result['result']:
                print(f"✅ Created ServiceNow incident: {result['result']['number']}")
                return result['result']['number']
            else:
                print(f"Unexpected ServiceNow response: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"ServiceNow API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None
    
    def update_incident(self, incident_number, status, comments):
        """Update a ServiceNow incident with required fields for closed states"""
        if not all([self.instance_url, self.username, self.password]):
            print("ServiceNow credentials not configured")
            return False
            
        # First get the incident sys_id
        api_url = f"{self.instance_url}/api/now/table/incident?number={incident_number}"
        
        credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json"
        }
        
        try:
            # Get the incident
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            incidents = response.json().get('result', [])
            
            if not incidents:
                print(f"No incident found with number: {incident_number}")
                return False
                
            incident_sys_id = incidents[0]['sys_id']
            
            # Update the incident
            update_url = f"{self.instance_url}/api/now/table/incident/{incident_sys_id}"
            
            # Prepare update data based on status
            update_data = {
                "state": status,
                "comments": comments
            }
            
            # Add required fields for closed/resolved states
            if status in ["6", "7", "Resolved", "Closed"]:
                update_data["close_notes"] = f"Resolved via Teams Bot automation: {comments}"
                update_data["close_code"] = "Solved (Work Around)"  # This might be the required "Resolution code"
                update_data["resolution_code"] = "Solved (Work Around)"  # Try both field names
                
                # Some ServiceNow instances might use different field names
                # Try these common field names for resolution information
                update_data["u_resolution_code"] = "Solved (Work Around)"
                update_data["resolution_notes"] = f"Resolved via Teams Bot automation: {comments}"
            
            update_response = requests.patch(update_url, headers=headers, json=update_data, timeout=30)
            update_response.raise_for_status()
            print(f"✅ Updated ServiceNow incident: {incident_number}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"ServiceNow update error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return False