# PDF to Insight (DocAPI)

A FastAPI-based backend for uploading DOCX/DOC files, extracting functional requirements, and generating test checklists using RAGFlow and LLMs.

## Quick Start

Choose one of the following methods to run the application:

### Option 1: Run with Docker (Recommended)

**Step 1: Build the Docker image**
```sh
docker build -t doctoinsight-api .
```

**Step 2: Run the container**
```sh
docker run -p 4444:4444 doctoinsight-api
```

- ✅ The app will be available at http://localhost:4444
- ✅ Automatically configured to connect to RAGFlow on your host machine
- ✅ No additional setup required

### Option 2: Run Locally with Python

**Step 1: Create and activate a virtual environment**
```sh
# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate
```

**Step 2: Install dependencies**
```sh
pip install -r requirements.txt
```

**Step 3: (Optional) Set RAGFlow API endpoint**
Only needed if your RAGFlow server is not running on `http://localhost:9380`:
```sh
# Windows PowerShell
$env:RAGFLOW_BASE_URL = "http://your-ragflow-server:9380"

# macOS/Linux
export RAGFLOW_BASE_URL="http://your-ragflow-server:9380"
```

**Step 4: Start the server**
```sh
uvicorn main:app --reload --port 4444
```

- ✅ The app will be available at http://localhost:4444

---

## Testing the API

Once the server is running, you can test it using:

### Using curl:
```sh
curl -F "file=@yourfile.docx" http://localhost:4444/main
```

### Using Postman or similar tools:
1. **Upload a document**: POST to `/main` with a .docx/.doc file
2. **Check status**: GET `/status/{task_id}` to monitor progress
3. **Cancel if needed**: POST `/stop/{task_id}` to cancel processing

---

## Features
- Upload DOCX/DOC files for analysis
- Asynchronous document processing with cancellation support
- Extracts functional requirements from documents
- Generates test checklists for each requirement (Thai/English)
- Task status tracking and cancellation endpoints
- Designed for integration with RAGFlow API

## API Endpoints

### 1. Upload Document
- **POST** `/main`
- **Body:** `file` (form-data, .docx or .doc)
- **Response:** `{ message, task_id, file_name }`
- Starts async analysis and returns a task ID.

### 2. Check Task Status
- **GET** `/status/{task_id}`
- **Response:**
  - `status`: pending | processing | completed | failed | cancelled
  - `message`: human-readable status
  - `processing_time`: seconds
  - `result`: (on success) test checklist

### 3. Cancel Task
- **POST** `/stop/{task_id}`
- **Response:** `{ message }`
- Cancels a running analysis task.

## How It Works
1. **Initialization:**
   - On startup, creates a RAGFlow dataset and chat assistant (shared for all tasks).
2. **Document Analysis:**
   - Uploads and parses the document to RAGFlow
   - Waits for parsing to complete
   - Creates a chat session and extracts functional requirements
   - Generates a test checklist for each requirement
3. **Async & Cancellation:**
   - Each analysis runs in a background asyncio task
   - Users can cancel tasks at any time
   - Uses aiohttp for true async/cancellable HTTP requests

## Requirements
- Python 3.8+
- **RAGFlow API server must be running and accessible** (default: http://localhost:9380)
- Dependencies: `fastapi`, `uvicorn`, `aiohttp`, `requests`

## Prerequisites

⚠️ **Important**: You must have a RAGFlow server running before using this application.

### Starting RAGFlow Server
Before running this project, ensure your RAGFlow server is running and accessible:
- Default URL: `http://localhost:9380`
- The application will display a clear error message if RAGFlow is not available

---

## Project Structure
- `main.py` - FastAPI app, task management, endpoints
- `ragflow.py` - RAGFlow API client (async + sync)
- `prompt.py` - LLM prompt templates
- `helper.py` - Parsing helpers
- `Dockerfile` - Docker configuration
- `requirements.txt` - Python dependencies

## Troubleshooting

### Common Issues:

**"You need to start the RAGFlow server first" error:**
- Ensure your RAGFlow server is running and accessible
- Check the server URL (default: http://localhost:9380)
- For Docker: RAGFlow should be running on your host machine

**Port already in use:**
```sh
# Use a different port
uvicorn main:app --port 8000
# or for Docker
docker run -p 8000:4444 doctoinsight-api
```

**Connection issues in Docker:**
- Make sure RAGFlow is running on your host machine
- The Docker container automatically uses `host.docker.internal` to connect to your host

## Additional Notes
- Only `.docx` and `.doc` files are accepted
- Each analysis is tracked by a unique `task_id`
- Results are automatically cleaned up after 1 hour
- The application supports real-time task cancellation

## License
MIT
