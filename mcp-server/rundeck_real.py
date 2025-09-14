import requests
import os
from dotenv import load_dotenv

load_dotenv()

class RundeckClient:
    def __init__(self):
        self.base_url = os.getenv('RUNDECK_URL', 'http://localhost:4440')
        self.api_token = os.getenv('RUNDECK_TOKEN')
        
    def run_job(self, job_id, software, winget_id, version):
        """Execute a Rundeck job using API token with Winget ID"""
        if not self.api_token:
            return "failed", "Rundeck API token not configured"
        
        url = f"{self.base_url}/api/40/job/{job_id}/run"
        headers = {
            "X-Rundeck-Auth-Token": self.api_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Format the arguments for Rundeck with Winget ID
        data = {
            "argString": f"-software '{software}' -winget_id '{winget_id}' -version '{version}'"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            execution_id = result.get('id')
            return "success", f"Rundeck execution started. Execution ID: {execution_id}"
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Rundeck API error: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\nResponse: {e.response.text}"
            return "failed", error_msg
    
    def test_connection(self):
        """Test connection to Rundeck using API token"""
        if not self.api_token:
            return False, "API token not configured"
            
        url = f"{self.base_url}/api/40/projects"
        headers = {
            "X-Rundeck-Auth-Token": self.api_token,
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return True, "Connection successful"
            else:
                return False, f"Connection failed: {response.status_code} - {response.text}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"