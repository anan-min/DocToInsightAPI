from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import uvicorn
import tempfile
import uuid
import time
import asyncio
from ragflow import RAGFlowClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF Upload API",)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAGFlow client - crashes if not properly configured
try:
    ragflow = RAGFlowClient()
except Exception as e:
    error_msg = str(e)
    if "Invalid RAGFlow API key" in error_msg:
        print("❌ Invalid RAGFlow API key. Please set RAGFLOW_API_KEY environment variable.")
        print("Usage:")
        print("  Docker: docker run -e RAGFLOW_API_KEY='your-key-here' -p 4444:4444 doctoinsight-api")
        print("  Python: RAGFLOW_API_KEY='your-key-here' python main.py")
        raise SystemExit(1)
    elif "Access forbidden" in error_msg:
        print("❌ Access forbidden. Please check your RAGFlow API key permissions.")
        raise SystemExit(1)
    elif "You need to start the RAGFlow server first" in error_msg:
        print("❌ You need to start the RAGFlow server first.")
        raise SystemExit(1)
    else:
        print(f"❌ RAGFlow initialization failed: {error_msg}")
        raise SystemExit(1)


analysis_results = {}
running_tasks = {}
cancellation_events = {}


@app.get("/")
async def root():
    return {"message": "Welcome to document analysis API. Please upload a document file."}


@app.post("/main")
async def main(
    file: UploadFile = File(...),
):
    try:
        file_name, file_path = await upload_file(file)

        task_id = str(uuid.uuid4())
        start_time = time.time()
        analysis_results[task_id] = {
            "status": "pending",
            "start_time": start_time,
            "progress": "Analysis queued for processing"
        }

        if len(analysis_results) > 100:
            cleanup_old_results()

        # Create asyncio task for cancellation support
        task = asyncio.create_task(analyze_document_async(task_id, file_path))
        running_tasks[task_id] = task

        # Don't wait for the task, let it run in background
        # The task will update analysis_results when complete

        return {
            "message": f"File '{file_name}' uploaded successfully. Analysis started.",
            "task_id": task_id,
            "file_name": file_name
        }
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(
            status_code=500, detail="Error processing the file.")


@app.get("/status/{task_id}")
async def get_analysis_results(task_id: str):
    if task_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Task not found")

    result = analysis_results[task_id]
    add_status_message(result)

    return result


@app.post("/stop/{task_id}")
async def stop_analysis(task_id: str):
    if task_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Task not found")

    if analysis_results[task_id]["status"] == "cancelled" or analysis_results[task_id]["status"] == "completed":
        return {"message": "Analysis already completed or cancelled"}

    # Set cancellation event first to stop ongoing operations
    if task_id in cancellation_events:
        cancellation_events[task_id].set()

    # Cancel the running task if it exists
    if task_id in running_tasks:
        task = running_tasks[task_id]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Clean up
        running_tasks.pop(task_id, None)

    # Clean up cancellation event
    if task_id in cancellation_events:
        cancellation_events.pop(task_id, None)

    # Update status with detailed cancellation info
    start_time = analysis_results[task_id].get("start_time", time.time())
    current_progress = analysis_results[task_id].get(
        "progress", "Analysis in progress")
    analysis_results[task_id]["status"] = "cancelled"
    analysis_results[task_id]["message"] = f"Analysis cancelled during: {current_progress}"
    analysis_results[task_id]["start_time"] = start_time
    analysis_results[task_id]["end_time"] = time.time()  # Track when cancelled
    analysis_results[task_id]["progress"] = "Analysis cancelled by user request"

    return {"message": "Analysis cancelled successfully"}


def update_progress(task_id, message):
    """Update progress for a specific task"""
    if task_id in analysis_results:
        analysis_results[task_id]["progress"] = message


def add_status_message(result):
    if result["status"] == "pending":
        result["message"] = "Analysis is queued for processing"
    elif result["status"] == "processing":
        result["message"] = "Document is being analyzed..."
    elif result["status"] == "completed":
        result["message"] = "Analysis completed successfully"
    elif result["status"] == "failed":
        error_detail = result.get("error", "Unknown error")
        result["message"] = f"Analysis failed: {error_detail}"
    elif result["status"] == "cancelled":
        # Keep the detailed cancellation message from stop_analysis
        if "message" not in result or result["message"] == "Analysis was cancelled":
            result["message"] = "Analysis was cancelled by user"

    # Calculate processing time from start_time
    if "start_time" in result:
        if result["status"] in ["completed", "failed", "cancelled"] and "end_time" in result:
            # Use the actual completion time for finished tasks
            processing_time = result["end_time"] - result["start_time"]
        else:
            # Use current time for ongoing tasks
            processing_time = time.time() - result["start_time"]
        result["processing_time"] = round(processing_time, 2)


async def analyze_document_async(task_id, file_path):
    """Async version of analyze_document_background for cancellation support"""
    cancellation_event = None
    try:
        # Create cancellation event for this task
        cancellation_event = asyncio.Event()
        cancellation_events[task_id] = cancellation_event

        # Keep the original start_time when updating to processing
        start_time = analysis_results[task_id]["start_time"]
        analysis_results[task_id] = {
            "status": "processing",
            "start_time": start_time,  # Preserve original start time
            "progress": "Initializing document analysis"
        }

        # Check if cancelled before starting
        if task_id in running_tasks and running_tasks[task_id].cancelled():
            cancellation_event.set()
            return

        # Run the async analysis directly with cancellation support
        result = await ragflow.analyze_document(file_path, cancellation_event,
                                                progress_callback=lambda msg: update_progress(task_id, msg))

        # Check if cancelled after analysis
        if task_id in running_tasks and running_tasks[task_id].cancelled():
            return

        analysis_results[task_id] = {
            "status": "completed",
            "result": result,
            "start_time": start_time,
            "end_time": time.time(),  # Track completion time
            "progress": "Analysis completed successfully"
        }

    except asyncio.CancelledError:
        start_time = analysis_results[task_id]["start_time"]
        current_progress = analysis_results[task_id].get(
            "progress", "Analysis in progress")
        analysis_results[task_id] = {
            "status": "cancelled",
            "start_time": start_time,
            "end_time": time.time(),  # Track cancellation time
            "progress": f"{current_progress}",
            "message": f"Analysis cancelled during: {current_progress}"
        }
        raise  # Re-raise to properly handle cancellation
    except Exception as e:
        start_time = analysis_results[task_id]["start_time"]
        current_progress = analysis_results[task_id].get(
            "progress", "Analysis in progress")
        error_msg = str(e)
        analysis_results[task_id] = {
            "status": "failed",
            "error": error_msg,
            "start_time": start_time,
            "end_time": time.time(),  # Track failure time
            "progress": f"Failed during: {current_progress} - {error_msg}",
            "message": f"Analysis failed during: {current_progress}",
            "failure_stage": current_progress
        }
    finally:
        # Clean up the temporary file and running task reference
        try:
            os.remove(file_path)
        except:
            pass

        # Remove from running tasks and cancellation events
        if task_id in running_tasks:
            running_tasks.pop(task_id, None)
        if task_id in cancellation_events:
            cancellation_events.pop(task_id, None)


async def upload_file(file):
    if not file or (not file.filename.endswith('.docx') and not file.filename.endswith('.doc')):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Please upload a doc file.")
    file_content = await file.read()
    file_name = file.filename
    print(f"Received file: {file_name}")

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, file_name)
    logger.info(f"Saving file to: {file_path}")

    with open(file_path, "wb") as f:
        f.write(file_content)
    return file_name, file_path


def cleanup_old_results():
    """Remove results older than 1 hour"""
    current_time = time.time()
    to_remove = []
    for task_id, result in analysis_results.items():
        if current_time - result.get("start_time", 0) > 3600:  # 1 hour
            to_remove.append(task_id)

    for task_id in to_remove:
        # Cancel running task if it exists
        if task_id in running_tasks:
            task = running_tasks[task_id]
            if not task.done():
                task.cancel()
            running_tasks.pop(task_id, None)

        # Set cancellation event and clean up
        if task_id in cancellation_events:
            cancellation_events[task_id].set()
            cancellation_events.pop(task_id, None)

        # Remove result
        analysis_results.pop(task_id, None)
        print(f"Cleaned up old result for task {task_id}")


app.add_api_route("/", root, methods=["GET"])
app.add_api_route("/main", main, methods=["POST"])
app.add_api_route("/status/{task_id}", get_analysis_results, methods=["GET"])
app.add_api_route("/stop/{task_id}", stop_analysis, methods=["POST"])


if __name__ == "__main__":
    print("Server started on http://localhost:4444")
    uvicorn.run(app, host="0.0.0.0", port=4444)
