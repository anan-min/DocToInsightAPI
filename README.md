# PDF to Insight (DocAPI)

A FastAPI-based backend for uploading DOCX/DOC files, extracting functional requirements, and generating test checklists using RAGFlow and LLMs.

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
- RAGFlow API running and accessible (see `BASE_URL` in `ragflow.py`)
- Dependencies: `fastapi`, `uvicorn`, `aiohttp`, `requests`

## Quick Start
1. Install dependencies:
   ```sh
   pip install fastapi uvicorn aiohttp requests
   ```
2. Start the server:
   ```sh
   uvicorn main:app --reload --port 4444
   ```
3. Use Postman or similar to:
   - Upload a DOCX/DOC file to `/main`
   - Poll `/status/{task_id}` for results
   - Cancel with `/stop/{task_id}` if needed

## Project Structure
- `main.py` - FastAPI app, task management, endpoints
- `ragflow.py` - RAGFlow API client (async + sync)
- `prompt.py` - LLM prompt templates
- `helper.py` - Parsing helpers

## Example Request (Upload)
```sh
curl -F "file=@yourfile.docx" http://localhost:4444/main
```

## Notes
- Only `.docx` and `.doc` files are accepted
- Each analysis is tracked by a unique `task_id`
- Results are cleaned up after 1 hour
- RAGFlow API key and URL are set in `ragflow.py`

## License
MIT
