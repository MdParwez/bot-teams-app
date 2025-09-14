from flask import Flask, request, jsonify
from servicenow_real import ServiceNowClient
from rundeck_real import RundeckClient
import os
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize clients
snow_client = ServiceNowClient()
rundeck_client = RundeckClient()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "MCP Server"})

@app.route('/api/create_ticket', methods=['POST'])
def create_ticket():
    """Create a ServiceNow incident ticket"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        user_id = data.get('user_id')
        software = data.get('software')
        version = data.get('version')
        
        if not all([user_id, software, version]):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Create ticket in ServiceNow
        ticket_number = snow_client.create_incident(user_id, software, version)
        
        if ticket_number:
            return jsonify({
                "success": True,
                "ticket_number": ticket_number,
                "message": "Incident created successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to create incident in ServiceNow"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/update_ticket', methods=['POST'])
def update_ticket():
    """Update a ServiceNow incident ticket"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        ticket_number = data.get('ticket_number')
        status = data.get('status')
        comments = data.get('comments')
        
        if not all([ticket_number, status]):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Map our status to ServiceNow states
        # Using numeric states (1=New, 2=In Progress, 6=Resolved, 7=Closed)
        state_map = {
            "approved": "2",  # In Progress
            "rejected": "7",  # Closed
            "completed": "6",  # Resolved
            "failed": "7"     # Closed
        }
        
        snow_state = state_map.get(status, "2")  # Default to In Progress
        
        # Update ticket in ServiceNow
        success = snow_client.update_incident(ticket_number, snow_state, comments)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Incident updated successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to update incident in ServiceNow"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/run_job', methods=['POST'])
def run_job():
    """Execute a Rundeck job with Winget ID"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        job_id = data.get('job_id')
        software = data.get('software')
        winget_id = data.get('winget_id')
        version = data.get('version')
        
        if not all([job_id, software, winget_id, version]):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Execute job in Rundeck with Winget ID
        status, message = rundeck_client.run_job(job_id, software, winget_id, version)
        
        return jsonify({
            "status": status,
            "message": message
        })
            
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('MCP_PORT', 5000))
    print(f"Starting MCP Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)