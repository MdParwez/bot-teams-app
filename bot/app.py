import os
import json
import time
import sqlite3
import aiohttp
import asyncio
from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    ActivityHandler,
)
from botbuilder.integration.aiohttp import BotFrameworkHttpAdapter
from botbuilder.schema import Activity, ActivityTypes

# ================== CONFIG ==================
APP_ID = os.getenv("MICROSOFT_APP_ID", "")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "")
DB_PATH = "software.db"
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:5000")

# ================== DB ==================
def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Software catalog with winget IDs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS software_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            software_name TEXT NOT NULL,
            version TEXT NOT NULL,
            rundeck_job_id TEXT,
            winget_id TEXT
        )
    """)
    # Requests table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            software_name TEXT NOT NULL,
            version TEXT NOT NULL,
            status TEXT DEFAULT 'requested',
            ticket_number TEXT,
            logs TEXT,
            requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            approved_by TEXT,
            approved_at DATETIME,
            accepted_at DATETIME,
            finished_at DATETIME
        )
    """)
    conn.commit()
    conn.close()

def seed_data():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM software_catalog")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO software_catalog (software_name, version, rundeck_job_id, winget_id) VALUES (?,?,?,?)",
            [
                ("Google Chrome", "117.0", "your-universal-job-id", "Google.Chrome"),
                ("VS Code", "1.90", "your-universal-job-id", "Microsoft.VisualStudioCode"),
                ("Slack", "4.35", "your-universal-job-id", "SlackTechnologies.Slack"),
                ("Firefox", "latest", "your-universal-job-id", "Mozilla.Firefox"),
                ("Zoom", "latest", "your-universal-job-id", "Zoom.Zoom")
            ]
        )
    conn.commit()
    conn.close()

# Database helper functions
def insert_request(user_id, software, version):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_requests (user_id, software_name, version, status) VALUES (?,?,?, 'requested')",
        (user_id, software, version),
    )
    req_id = cur.lastrowid
    conn.commit()
    conn.close()
    return req_id

def update_request(req_id, **fields):
    if not fields:
        return
    conn = get_connection()
    cur = conn.cursor()
    cols = ", ".join([f"{k}=?" for k in fields.keys()])
    vals = list(fields.values()) + [req_id]
    cur.execute(f"UPDATE user_requests SET {cols} WHERE id=?", vals)
    conn.commit()
    conn.close()

def fetch_request(req_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, software_name, version, status, ticket_number FROM user_requests WHERE id=?", (req_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_software_list():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT software_name, version, winget_id FROM software_catalog")
    rows = cur.fetchall()
    conn.close()
    return rows

# ================== REAL INTEGRATIONS ==================
async def create_ticket_real(user_id, software, version):
    """Create a real ServiceNow ticket via MCP server"""
    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "user_id": user_id,
                "software": software,
                "version": version
            }
            async with session.post(
                f"{MCP_SERVER_URL}/api/create_ticket",
                json=data,
                timeout=30
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("ticket_number")
                else:
                    print(f"MCP server error: {response.status}")
                    return None
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return None

async def update_ticket_real(ticket_number, status, comments):
    """Update a real ServiceNow ticket via MCP server"""
    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "ticket_number": ticket_number,
                "status": status,
                "comments": comments
            }
            async with session.post(
                f"{MCP_SERVER_URL}/api/update_ticket",
                json=data,
                timeout=30
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("success", False)
                else:
                    print(f"MCP server error: {response.status}")
                    return False
    except Exception as e:
        print(f"Error updating ticket: {e}")
        return False

async def run_rundeck_job_real(job_id, software, winget_id, version):
    """Execute a real Rundeck job via MCP server with Winget ID"""
    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "job_id": job_id,
                "software": software,
                "winget_id": winget_id,
                "version": version
            }
            async with session.post(
                f"{MCP_SERVER_URL}/api/run_job",
                json=data,
                timeout=30
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("status", "failed"), result.get("message", "Unknown error")
                else:
                    return "failed", f"MCP server error: {response.status}"
    except Exception as e:
        return "failed", f"Error running job: {e}"

# ================== ADAPTIVE CARDS ==================
def card_select_software():
    choices = [
        {
            "title": f"{name} ({ver})",
            "value": json.dumps({"software": name, "version": ver, "winget_id": winget_id}),
        }
        for name, ver, winget_id in get_software_list()
    ]
    card = {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "Select software to install:", "weight": "Bolder", "size": "Medium"},
            {
                "type": "Input.ChoiceSet",
                "id": "software_selection",
                "style": "compact",
                "choices": [{"title": c["title"], "value": c["value"]} for c in choices],
            },
        ],
        "actions": [{"type": "Action.Submit", "title": "Submit", "data": {"action": "select_software"}}],
    }
    return Activity(
        type=ActivityTypes.message,
        attachments=[{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    )

def card_approval(request_id, software, version, ticket_number):
    card = {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "Install Request Approval", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": f"Ticket: {ticket_number}"},
            {"type": "TextBlock", "text": f"Software: {software}"},
            {"type": "TextBlock", "text": f"Version: {version}"},
            {"type": "TextBlock", "text": "Approve or Reject this request."},
        ],
        "actions": [
            {"type": "Action.Submit", "title": "Approve", "data": {"action": "approve_request", "request_id": request_id}},
            {"type": "Action.Submit", "title": "Reject", "data": {"action": "reject_request", "request_id": request_id}},
        ],
    }
    return Activity(
        type=ActivityTypes.message,
        attachments=[{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    )

def card_confirm_install(request_id, software, version):
    card = {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "Ready to install. Proceed?", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": f"Software: {software} (v{version})"},
        ],
        "actions": [
            {"type": "Action.Submit", "title": "Proceed", "data": {"action": "accept_install", "request_id": request_id}},
        ],
    }
    return Activity(
        type=ActivityTypes.message,
        attachments=[{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    )

# ================== BOT ==================
class TeamsSoftwareBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        text_raw = (turn_context.activity.text or "").strip()
        text = text_raw.lower()
        value = turn_context.activity.value
        user_id = turn_context.activity.from_property.id

        # Handle all Adaptive Card submissions
        if value and isinstance(value, dict) and value.get("action"):
            action = value.get("action")
            if action == "select_software":
                # Parse selection
                selection = value.get("software_selection")
                try:
                    data = json.loads(selection)
                    software, version, winget_id = data["software"], data["version"], data.get("winget_id", "")
                except Exception:
                    await turn_context.send_activity("⚠️ Invalid selection payload.")
                    return

                # 1) Log request
                req_id = insert_request(user_id, software, version)

                # 2) Create REAL Ticket in ServiceNow via MCP
                ticket_number = await create_ticket_real(user_id, software, version)
                if ticket_number:
                    update_request(req_id, ticket_number=ticket_number, status="ticket_created")
                    await turn_context.send_activity(f"📨 Ticket created: {ticket_number}. Waiting for approval…")
                    
                    # 3) Send approval card to supervisor (in real scenario)
                    await turn_context.send_activity(card_approval(req_id, software, version, ticket_number))
                else:
                    await turn_context.send_activity("⚠️ Failed to create ServiceNow ticket. Please try again.")
                return

            elif action == "approve_request":
                req_id = int(value.get("request_id"))
                row = fetch_request(req_id)
                if not row:
                    await turn_context.send_activity("⚠️ Request not found.")
                    return
                _, req_user, software, version, _, ticket_number = row
                
                # Update request in DB
                update_request(req_id, status="approved", approved_by=user_id, approved_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                
                # Update REAL Ticket in ServiceNow via MCP
                success = await update_ticket_real(ticket_number, "approved", f"Request approved by {user_id}")
                if success:
                    await turn_context.send_activity(f"✅ Approved request {req_id} (Ticket {ticket_number}).")
                else:
                    await turn_context.send_activity(f"✅ Approved request {req_id} but failed to update ServiceNow.")
                
                # Ask requester to proceed
                await turn_context.send_activity(card_confirm_install(req_id, software, version))
                return

            elif action == "reject_request":
                req_id = int(value.get("request_id"))
                row = fetch_request(req_id)
                if not row:
                    await turn_context.send_activity("⚠️ Request not found.")
                    return
                _, _, software, version, _, ticket_number = row
                
                # Update request in DB
                update_request(req_id, status="rejected", approved_by=user_id, approved_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                
                # Update REAL Ticket in ServiceNow via MCP
                success = await update_ticket_real(ticket_number, "rejected", f"Request rejected by {user_id}")
                if success:
                    await turn_context.send_activity(f"❌ Rejected request {req_id} (Ticket {ticket_number}).")
                else:
                    await turn_context.send_activity(f"❌ Rejected request {req_id} but failed to update ServiceNow.")
                return

            elif action == "accept_install":
                req_id = int(value.get("request_id"))
                row = fetch_request(req_id)
                if not row:
                    await turn_context.send_activity("⚠️ Request not found.")
                    return
                _, _, software, version, status, ticket_number = row
                if status != "approved":
                    await turn_context.send_activity("⚠️ Request is not approved yet.")
                    return

                update_request(req_id, status="accepted", accepted_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                await turn_context.send_activity("🚀 Starting installation…")
                update_request(req_id, status="running")

                # Get Rundeck job ID and Winget ID from catalog
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT rundeck_job_id, winget_id FROM software_catalog WHERE software_name=?", (software,))
                catalog_row = cur.fetchone()
                conn.close()
                
                if not catalog_row:
                    await turn_context.send_activity("⚠️ Software not found in catalog.")
                    return
                    
                job_id, winget_id = catalog_row
                
                # Execute REAL Rundeck job via MCP with Winget ID
                job_status, logs = await run_rundeck_job_real(job_id, software, winget_id, version)
                
                if job_status == "success":
                    update_request(req_id, status="installed", logs=logs, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                    # Update REAL Ticket in ServiceNow via MCP
                    await update_ticket_real(ticket_number, "completed", f"Installation completed successfully.\n{logs}")
                    await turn_context.send_activity(f"✅ Installation completed.\n\nLogs:\n{logs}")
                else:
                    update_request(req_id, status="failed", logs=logs, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                    # Update REAL Ticket in ServiceNow via MCP
                    await update_ticket_real(ticket_number, "failed", f"Installation failed.\n{logs}")
                    await turn_context.send_activity(f"❌ Installation failed.\n\nLogs:\n{logs}")
                return

        # If not a card submit: decide by text intent
        if any(kw in text for kw in ["install", "software", "setup", "add program"]):
            await turn_context.send_activity(card_select_software())
            return

        # Otherwise, respond with help
        await turn_context.send_activity("I can help you install software. Type 'install' to get started.")

# ================== SERVER ==================
def init_app():
    init_db()
    seed_data()
    app = web.Application()
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", lambda r: web.json_response({"ok": True}))
    return app

SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
ADAPTER = BotFrameworkHttpAdapter(SETTINGS)
BOT = TeamsSoftwareBot()

async def messages(req: web.Request) -> web.Response:
    auth_header = req.headers.get("Authorization", "")
    response = await ADAPTER.process_activity(req, auth_header, BOT.on_turn)
    if response:
        return web.Response(status=response.status)
    return web.Response(status=200)

if __name__ == "__main__":
    web.run_app(init_app(), host="localhost", port=3978)