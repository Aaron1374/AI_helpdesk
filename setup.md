# Complete Setup Guide: AI L1 IT Helpdesk

This guide covers everything you need to set up and run the AI Helpdesk project from scratch. It assumes you are starting with a fresh computer and explains every required step.

---

## Phase 1: Install System Prerequisites

Before touching any code, ensure you have the following foundational software installed on your machine.

### 1. Git (For downloading the code)
- **Windows:** Download and install [Git for Windows](https://git-scm.com/download/win).
- **macOS:** Open Terminal and type `git --version`. If it's not installed, macOS will prompt you to install the Command Line Tools.
- **Linux (Ubuntu/Debian):** Run `sudo apt install git`.

### 2. Docker Desktop (For running the Database and Application)
Docker makes it incredibly easy to run complex software without manually configuring databases.
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- Start Docker Desktop and ensure the Docker Engine is running (look for the green whale or "Running" status indicator in the app).

### 3. Python 3.10+ (For running the backend locally / tests)
- Download and install [Python](https://www.python.org/downloads/). 
- **Important for Windows:** During installation, explicitly check the box that says **"Add Python to PATH"**.

### 4. Node.js & npm (For running the frontend locally / tests)
- Download and install the LTS version of [Node.js](https://nodejs.org/). This will automatically install `npm` (Node Package Manager).

### 5. An IDE / Code Editor
- Download and install [Visual Studio Code (VS Code)](https://code.visualstudio.com/) or your preferred code editor.

---

## Phase 2: Clone and Configure the Project

### 1. Download the Code
Open your terminal (or Command Prompt / PowerShell on Windows) and run:
```bash
git clone <your-repository-url>
cd helpdesk
```
*(If you are already in the `helpdesk` folder, you can skip this step.)*

### 2. Get an OpenAI API Key
Because this application uses AI to power its helpdesk chatbot, it requires access to OpenAI's language models.
1. Go to [platform.openai.com](https://platform.openai.com/).
2. Create an account and add billing details.
3. Generate a new API Key. **Copy this key, you will only see it once.**

### 3. Create the Environment Configuration File
The application needs to know your API key and database settings.
1. In the root `helpdesk` folder, create a new file named exactly `.env` (do not add a `.txt` extension).
2. Open `.env` in your text editor and paste the following:

```env
# Select the model provider without changing Python code:
# openai, google/gemini, xai/grok, openai_compatible, or ollama
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0

# OpenAI
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=
OPENAI_ORG_ID=

# Google Gemini (use when LLM_PROVIDER=google)
GOOGLE_API_KEY=

# xAI Grok (use when LLM_PROVIDER=xai)
XAI_API_KEY=
XAI_BASE_URL=https://api.x.ai/v1

# Embeddings. Gemini defaults to gemini-embedding-001;
# OpenAI-compatible providers default to text-embedding-3-small.
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

# Database Configuration (Docker Compose handles this automatically)
DATABASE_URL=postgresql://helpdesk_user:helpdesk_password@db:5432/helpdesk_db

# Security Key for JWT Authentication
SECRET_KEY=supersecretkey
```
Save and close the file.

To switch providers, edit only `.env`, then restart the backend:

```env
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=your-google-key
EMBEDDING_PROVIDER=google
EMBEDDING_MODEL=gemini-embedding-001
```

For Grok:

```env
LLM_PROVIDER=xai
LLM_MODEL=grok-3-mini
XAI_API_KEY=your-xai-key
```

Apply changes with:

```bash
docker compose up --build -d backend
```

---

## Phase 3: Running the Application (The Easy Way)

The absolute easiest way to run this application is using Docker Compose. It will automatically download PostgreSQL with the `pgvector` extension, build the Python backend, build the React frontend, and connect them all together.

### 1. Start Docker Compose
In your terminal, from the root `helpdesk` folder, run:
```bash
docker-compose up --build -d
```
*Note: The first time you run this, it may take 5–10 minutes to download and build all the necessary container images.*

### 2. Initialize the Database Schema (Alembic Migrations)
The database container is running, but it is empty. We need to tell the backend to build the tables.
Run this command in your terminal:
```bash
docker-compose exec backend alembic upgrade head
```
You should see output indicating that migrations (like `baseline_0001`, `1234abcd5678`, etc.) were successfully applied.

### 3. Access the Application
- **Employee Chat Portal (Frontend):** Open your web browser and go to [http://localhost:5173](http://localhost:5173)
- **Engineer Dashboard:** (Included in the frontend routing, typically accessible via a button or `/engineer` path)
- **Backend API Documentation:** Open your web browser and go to [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Phase 4: Local Development Setup (For editing code)

If you plan to edit the code, run tests, or don't want to use Docker for the application layer, you will need to set up the environments locally. 

*(You still need Docker running to host the PostgreSQL database)*.

### 1. Start Only the Database
```bash
# Stop everything if it's already running
docker-compose down

# Start just the database container
docker-compose up -d db
```

### 2. Set Up the Python Backend
Open a terminal and navigate to the `backend` folder:
```bash
cd backend
```

**Create a Virtual Environment:**
This isolates Python packages from your global system.
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

**Install Backend Dependencies:**
```bash
pip install -r requirements.txt
```

**Run Database Migrations (if not already done):**
```bash
# Ensure your .env file is one level up, or set DATABASE_URL locally:
# export DATABASE_URL=postgresql://helpdesk_user:helpdesk_password@localhost:5432/helpdesk_db
alembic upgrade head
```

**Start the Backend Server:**
```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Set Up the React Frontend
Open a **new** terminal window and navigate to the `frontend` folder:
```bash
cd frontend
```

**Install Frontend Dependencies:**
```bash
npm install
```

**Start the Frontend Development Server:**
```bash
npm run dev
```
The frontend will now be accessible at `http://localhost:5173`.

---

## Phase 5: Running Tests

To ensure everything is working correctly, you can execute the test suites.

### 1. Backend Tests (Pytest)
Ensure you are in the `backend` folder with your virtual environment activated:
```bash
cd backend
pytest tests/
```

### 2. Frontend End-to-End Tests (Playwright)
Ensure you are in the `frontend` folder. The application must be running (either via Docker Compose or local development servers) for these to pass.
```bash
cd frontend
npm install -D @playwright/test
npx playwright install  # Downloads required browser binaries
npx playwright test
```

---

## Troubleshooting

- **"Docker daemon is not running" error:** Ensure Docker Desktop is open and fully booted up.
- **"ModuleNotFoundError: No module named 'langchain_openai'" (or similar):** Ensure you ran `pip install -r requirements.txt` while your virtual environment was activated.
- **Database Connection Refused:** If running locally, ensure the database port mapping in your `.env` says `@localhost:5432` instead of `@db:5432` (which is the Docker internal network name).
- **Frontend isn't updating when I save files:** Ensure you ran `npm run dev` in the frontend folder, rather than relying solely on the Docker container, as Windows file-watching into Docker volumes can sometimes be finicky.
