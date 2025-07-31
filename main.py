from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import uvicorn
import tempfile

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

ragflow = RAGFlowClient()


@app.get("/")
async def root():
    return {"message": "Welcome to the PDF Upload API. Use POST /main to upload a PDF file."}


@app.post("/main")
async def main(
    file: UploadFile = File(...),
):
    try:
        if not file or (not file.filename.endswith('.docx') and not file.filename.endswith('.doc')):
            raise HTTPException(
                status_code=400, detail="Invalid file type. Please upload a PDF file.")
        file_content = await file.read()
        file_name = file.filename
        print(f"Received file: {file_name}")

        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, file_name)
        logger.info(f"Saving file to: {file_path}")

        with open(file_path, "wb") as f:
            f.write(file_content)

        test_checklist = ragflow.analyze_document(file_path)
        print(f"test_checklist: {test_checklist}")

        return {
            "message": f"File '{file_name}' uploaded and analyzed successfully.",
            "test_checklist": test_checklist,
            "file_name": file_name
        }
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(
            status_code=500, detail="Error processing the file.")


app.add_api_route("/main", main, methods=["POST"])
app.add_api_route("/", root, methods=["GET"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4444)
