# 🤖 Teams Bot App for Automated Software Installation

A **Microsoft Teams Bot** that enables users to request and install real software seamlessly through chat.
The bot integrates with **ServiceNow** for approval workflows and **Rundeck** for execution, automating end-to-end software deployment across enterprise systems.

---

## ✨ Features

✅ **Chat-driven automation** – Install software by simply typing a request in Microsoft Teams
✅ **Approval Workflow** – Requests automatically logged and approved in **ServiceNow**
✅ **Orchestration & Execution** – **Rundeck** handles job scheduling and software installation
✅ **Audit & Compliance** – All actions logged for governance and compliance
✅ **Role-based Access Control** – Only authorized users can request or approve installations
✅ **Scalable & Extensible** – Add new software packages or extend to new environments easily

---

## 🏗️ Architecture

```mermaid
flowchart LR
    User[Teams User] -->|Request: "Install Visual Studio"| Bot[Teams Bot App]
    Bot --> SN[ServiceNow]
    SN -->|Approval| Bot
    Bot --> RD[Rundeck]
    RD -->|Executes Installation| Target[Target System]
    Target --> Bot
    Bot --> User[Teams User (confirmation)]
```

---

## 🛠️ Tech Stack

* **Frontend / Interface**: Microsoft Teams Bot (Azure Bot Service)
* **Workflow / ITSM**: ServiceNow
* **Orchestration / Automation**: Rundeck
* **Backend**: Node.js / Python (bot framework SDK)


---

## 🚀 Getting Started

### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/teams-bot-servicenow-rundeck.git
cd teams-bot-servicenow-rundeck
```

### 2️⃣ Configure environment

Create a `.env` file with your settings:

```env
# Azure Bot
MICROSOFT_APP_ID=your_app_id
MICROSOFT_APP_PASSWORD=your_app_password

# ServiceNow
SN_INSTANCE=https://your-instance.service-now.com
SN_USERNAME=your_servicenow_user
SN_PASSWORD=your_servicenow_password

# Rundeck
RUNDECK_URL=https://rundeck.yourdomain.com
RUNDECK_TOKEN=your_rundeck_api_token
```

### 3️⃣ Install dependencies

```bash
npm install
```

### 4️⃣ Run locally

```bash
npm start
```

---

## 💡 Example Use Cases

* *"Install Visual Studio Code on my laptop"*
* *"Update Chrome to latest version on Finance team systems"*
* *"Install PostgreSQL on QA server"*

Workflow:

1. User requests via Teams
2. Bot logs request in **ServiceNow**
3. Manager approves in ServiceNow
4. Bot triggers **Rundeck job** for software installation
5. User gets status/confirmation in Teams

---
