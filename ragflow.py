import time
import aiohttp
import asyncio
import os
import requests
from prompt import FUNCTIONAL_REQUIREMENTS_PROMPT, TEST_CHECKLIST_PROMPT
from helper import parse_chat_completion_result
import random

# retries mechanism for chat completion
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1

RAGFLOW_API_KEY = "ragflow-M3MzFmNTgwNmNmNTExZjBiY2M4OTY4Yz"
BASE_URL = "http://localhost:9380"
PARSED = "1"

# RAGFLOW ENDPOINT
# DATASET
CREATE_DATASET = "/api/v1/datasets"
LIST_DATASETS = "/api/v1/datasets"
# DOCUMENT
UPLOAD_DOCUMENT = "/api/v1/datasets/{dataset_id}/documents"
PARSE_DOCUMENT = "/api/v1/datasets/{dataset_id}/chunks"
LIST_DOCUMENTS = "/api/v1/datasets/{dataset_id}/documents"
# CHAT
CREATE_CHAT_ASSISTANT = "/api/v1/chats"
UPDATE_CHAT_ASSISTANT = "/api/v1/chats/{chat_id}"
CREATE_CHAT_SESSION = "/api/v1/chats/{chat_id}/sessions"
CREATE_CHAT_COMPLETION = "/api/v1/chats/{chat_id}/completions"

# header
HEADERS = {
    "Authorization": f"Bearer {RAGFLOW_API_KEY}",
    "Content-Type": "application/json"
}

FILE_HEADER = {
    "Authorization": f"Bearer {RAGFLOW_API_KEY}",
}


"""
RAGFLOW CLIENT
    INIT: 
        1. create dataset => {{dataset_id}}
        2. create chat assistant and configs model => {{chat_id}}

    ANALYZE DOCUMENT:
        1. upload document => {{documentd_id, document_name}}
        2. parse document 
        3. check document status using list documents until status is complete => {{status}}
        4. create chat assistant session => {{session_id}}
        6. get functional requirements from chat completion
        7. loop through each functional requirement and generate test checklist one by one using chat completion 
            ((one bye one => prevent exceeeding context window size of chat assistant))
"""


class RAGFlowClient:
    # create dataset and chat assistant and configs model
    def __init__(self):
        self.dataset_id = None
        self.chat_id = None
        self._lock = asyncio.Lock()
        self.dataset_added = False

        self.initialize()

    def initialize(self):
        dataset_id = self.create_dataset()
        chat_id = self.create_chat_assistant()

        self.dataset_id = dataset_id
        self.chat_id = chat_id

    # upload and parse document then analyze data
    async def analyze_document(self, file_path, cancellation_event=None):
        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError("Operation cancelled before starting")

        document_info = await self.upload_document(self.dataset_id, file_path, cancellation_event)
        if not document_info:
            raise Exception("Failed to upload document")

        document_id = document_info.get('id')
        document_name = document_info.get('name')

        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError("Operation cancelled after upload")

        await self.parse_document(document_id, cancellation_event)
        await self.wait_for_parsing_complete(self.dataset_id, document_id, cancellation_event)

        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError("Operation cancelled after parsing")

        async with self._lock:
            if not self.dataset_added:
                await self.update_chat_assistant(self.chat_id, self.dataset_id, cancellation_event)

        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError(
                "Operation cancelled after chat assistant update")

        session_id = await self.create_chat_session(cancellation_event)
        functional_requirements_list = await self.get_functional_requirements(
            session_id, document_name, cancellation_event
        )
        print(f"functional_requirements_list: {functional_requirements_list}")

        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError(
                "Operation cancelled after getting functional requirements")

        test_checklist = await self.generate_test_checklist(
            session_id,
            functional_requirements_list,
            document_name,
            cancellation_event
        )
        return test_checklist

    # create dataset for upload the document and update dataset id
    def create_dataset(self):
        """
        curl --location --request POST 'http://localhost:9380/api/v1/datasets' \
        --header 'Content-Type: application/json' \
        --header 'Authorization: ••••••' \
        --data '{
            "name": "pdfToInsight"
        }'
        """
        url = f"{BASE_URL}{CREATE_DATASET}"
        payload = {
            "name": f"pdfToInsight_{int(time.time())}",
            "description": "PDF analysis dataset for extracting insights",
            "chunk_method": "naive",
            # left everything else default for now
        }
        try:
            response = requests.post(url, headers=HEADERS, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("code") == 0:
                dataset_info = result.get("data")
                self.dataset_id = dataset_info['id']
                print(f"✅ Dataset created: {self.dataset_id}")
                return dataset_info['id']
            else:
                raise Exception(
                    f"Failed to create dataset: {result.get('message')}")
        except Exception as e:
            print(f"❌ Error creating dataset: {e}")
            raise Exception("Failed to create dataset")

    # template done fix the payload accordingly
    def create_chat_assistant(self):
        """
        curl --location 'http://localhost:9380/api/v1/chats' \
        --header 'Content-Type: application/json' \
        --header 'Authorization: Bearer ••••••' \
        --data '{
            "dataset_ids": ["{{dataset_id}}"],
            "name":"chat_{{$timestamp}}",
            "prompt": {
            "similarity_threshold": 0.2, 
            "keywords_similarity_weight": 0.5
            }
        }'
        """
        url = f"{BASE_URL}{CREATE_CHAT_ASSISTANT}"
        payload = {
            # update datset_id after there is a parsed file
            "dataset_ids": [],
            "name": f"chat_{int(time.time())}",
            "prompt": {
                "similarity_threshold": 0.2,
                "keywords_similarity_weight": 0.5
            }
        }

        try:
            response = requests.post(url, headers=HEADERS, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("code") == 0:
                chat_info = result.get("data")
                chat_id = chat_info['id']
                self.chat_id = chat_id
                print(f"✅ Chat assistant created: {self.chat_id}")
                return chat_id
            else:
                raise Exception(
                    f"Failed to create chat assistant: {result.get('message')}")

        except Exception as e:
            print(f"❌ Error creating chat assistant: {e}")
            raise Exception("Failed to create chat assistant")

    # create chat session based on the chat assitant for analyzing the document
    async def create_chat_session(self, cancellation_event=None):
        """
        curl --location 'http://localhost:9380/api/v1/chats/00677f346d1711f08d728e5d69e84a39/sessions' \
        --header 'Content-Type: application/json' \
        --header 'Authorization: Bearer ••••••' \
        --data '{
            "name": "session_{{$timestamp}}"
        }'
        """
        url = f"{BASE_URL}{CREATE_CHAT_SESSION.format(chat_id=self.chat_id)}"
        payload = {
            "name": f"Analysis_Session_{int(time.time())}"
        }

        try:
            async with aiohttp.ClientSession() as session:
                if cancellation_event and cancellation_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled")

                async with session.post(url, headers=HEADERS, json=payload, timeout=30) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if result.get("code") == 0:
                        session_info = result.get("data")
                        session_id = session_info['id']
                        print(f"✅ Chat session created: {session_id}")
                        return session_id
                    else:
                        raise Exception(
                            f"Failed to create chat session: {result.get('message')}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"❌ Error creating chat session: {e}")
            raise

    # retry function
    @staticmethod
    async def async_retry(fn, *args, retries=MAX_RETRIES, base_delay=RETRY_BASE_DELAY, **kwargs):
        for attempt in range(1, retries + 1):
            try:
                return await fn(*args, **kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if attempt == retries:
                    print(f"❌ Final attempt failed: {e}")
                    raise
                delay = base_delay * (2 ** (attempt - 1)) + \
                    random.uniform(0, 0.5)
                print(
                    f"⚠️ Attempt {attempt} failed. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

    # use chat session created to get chat completion
    async def chat_completion(self, session_id, question, cancellation_event=None):
        """
        curl --location 'http://localhost:9380/api/v1/chats/{{chat_id}}/completions' \
        --header 'Content-Type: application/json' \
        --header 'Authorization: Bearer ••••••' \
        --data '{
            "question": "{{prompt}}",
            "stream": true,
            "session_id":"{{session_id}}"
        }'
        """
        # pass chat request to async_retry to apply retries mechanism
        async def _chat_request():
            url = f"{BASE_URL}{CREATE_CHAT_COMPLETION.format(chat_id=self.chat_id)}"
            payload = {
                "question": question,
                "session_id": session_id,
                "stream": False
            }
            async with aiohttp.ClientSession() as session:
                if cancellation_event and cancellation_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled")

                async with session.post(url, headers=HEADERS, json=payload, timeout=120) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if result.get("code") == 0:
                        data = result.get("data", {})
                        return data.get("answer", "")
                    else:
                        raise Exception(
                            f"Failed to get chat completion: {result.get('message')}")

        return await RAGFlowClient.async_retry(_chat_request)

    async def upload_document(self, dataset_id: str, file_path: str, cancellation_event=None):
        """
        curl --location 'http://localhost:9380/api/v1/datasets/1629aa2a6cf611f08399968c9561210e/documents' \
        --header 'Authorization: Bearer ••••••' \
        --form 'file=@"{{file}}"'
        """
        url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents"

        try:
            if cancellation_event and cancellation_event.is_set():
                raise asyncio.CancelledError("Operation cancelled")

            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Create form data
            data = aiohttp.FormData()
            data.add_field('file',
                           file_content,
                           filename=os.path.basename(file_path),
                           content_type='application/octet-stream')

            headers = {'Authorization': HEADERS['Authorization']}

            async with aiohttp.ClientSession() as session:
                if cancellation_event and cancellation_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled")

                async with session.post(url, headers=headers, data=data, timeout=60) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('code') == 0:
                            # Return the document info from the upload response
                            documents = result.get('data', [])
                            if documents:
                                print(
                                    f"✅ Document uploaded successfully: {documents[0].get('name')}")
                                return documents[0]
                            else:
                                print(
                                    "❌ Upload succeeded but no document data returned")
                                return None
                        else:
                            print(
                                f"❌ Upload failed: {result.get('message', 'Unknown error')}")
                            return None
                    else:
                        print(f"❌ HTTP error during upload: {response.status}")
                        return None

        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")
            return None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"❌ Error uploading document: {str(e)}")
            return None

    def is_document_exist(self, dataset_id, file_path):
        pass

    async def parse_document(self, document_id, cancellation_event=None):
        """
        curl --location 'http://localhost:9380/api/v1/datasets/1629aa2a6cf611f08399968c9561210e/chunks' \
        --header 'Content-Type: application/json' \
        --header 'Authorization: Bearer ••••••' \
        --data '{
            "document_ids": ["{{document_id}}"]
        }'
        """
        url = f"{BASE_URL}/api/v1/datasets/{self.dataset_id}/chunks"
        payload = {
            "document_ids": [document_id],
        }
        try:
            async with aiohttp.ClientSession() as session:
                if cancellation_event and cancellation_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled")

                async with session.post(url, headers=HEADERS, json=payload, timeout=30) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if result.get("code") == 0:
                        print(f"✅ {document_id} parsing started (asynchronous)")
                        return True
                    else:
                        raise Exception(
                            f"Failed to start document parsing: {result.get('message')}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"❌ Error starting document parsing: {e}")
            return False

    async def wait_for_parsing_complete(self, dataset_id: str, document_id: str, cancellation_event=None, timeout=600):
        # list documents and check status every 5 seconds until status is complete
        """
        curl --location 'http://localhost:9380/api/v1/datasets/1629aa2a6cf611f08399968c9561210e/documents' \
        --header 'Authorization: Bearer ••••••'
        """
        url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents"
        start_time = time.time()

        print("⏳ Waiting for document parsing to complete...")
        while time.time() - start_time < timeout:
            try:
                if cancellation_event and cancellation_event.is_set():
                    raise asyncio.CancelledError(
                        "Operation cancelled during parsing wait")

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=HEADERS, timeout=30) as response:
                        response.raise_for_status()
                        result = await response.json()

                        if result.get("code") == 0:
                            documents = result.get("data", [])['docs']
                            for document in documents:
                                if document.get("id") == document_id:
                                    status = document.get("run")
                                    if status == "DONE":
                                        print(
                                            f"✅ {document_id} parsing complete")
                                        return True
                        print(f"{document_id} parsing status: {status}")

                        # Check for cancellation before sleeping
                        if cancellation_event and cancellation_event.is_set():
                            raise asyncio.CancelledError(
                                "Operation cancelled during parsing wait")

                        await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"❌ Error checking parsing status: {e}")
                await asyncio.sleep(5)

        print("❌ Document parsing timed out")
        return False

    async def get_functional_requirements(self, session_id, document_name, cancellation_event=None):
        """
        document_name: {document_name}
        List the functional requirements found in this document.
        Return format:
        [
            "Users must be able to register and log in.",
            "Admins can manage user roles.",
            "System should send confirmation emails after purchase."
        ]
        """
        try:
            if cancellation_event and cancellation_event.is_set():
                raise asyncio.CancelledError("Operation cancelled")

            # ask the chat assistant to get functional requirements
            print("📝 Getting functional requirements from the document...")
            print(f"document_name: {document_name}")
            chat_completion = await self.chat_completion(
                session_id,
                FUNCTIONAL_REQUIREMENTS_PROMPT.format(
                    document_name=document_name),
                cancellation_event
            )

            print(f"chat_completion: {chat_completion}")
            if not chat_completion:
                raise ValueError(
                    "No functional requirements found in the document.")
            else:
                functional_requirements = parse_chat_completion_result(
                    chat_completion)
                return functional_requirements
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"❌ Error getting functional requirements: {e}")
            raise

    # ask the chat assistant to generate test checklist based on functional requirements each requirement are one chat completion
    async def generate_test_checklist(self, session_id, functional_requirements, document_name, cancellation_event=None):
        """
        document_name: {document_name}

        functional_requirement:
        {functional_requirement}

        Generate a test checklist for this functional requirement.

        Return format:
        [
            "Verify registration form accepts valid inputs.",
            "Check error handling for missing fields.",
            "Ensure login succeeds with correct credentials.",
            "Ensure login fails with incorrect credentials."
        ]
        """
        testchecklist = []
        try:
            for requirement in functional_requirements:
                if cancellation_event and cancellation_event.is_set():
                    raise asyncio.CancelledError(
                        "Operation cancelled during test checklist generation")

                print(
                    f"📋 Generating test checklist for requirement: {requirement}")
                chat_completion = await self.chat_completion(
                    session_id,
                    TEST_CHECKLIST_PROMPT.format(
                        document_name=document_name,
                        functional_requirement=requirement,
                    ),
                    cancellation_event
                )

                if not chat_completion:
                    raise ValueError(
                        "No test checklist generated for the requirement.")
                else:
                    _testchecklist = parse_chat_completion_result(
                        chat_completion)
                    print(
                        f"✅ Test checklist generated for requirement: {_testchecklist}")
                    testchecklist.append({
                        "requirement": requirement,
                        "testchecklist": _testchecklist
                    })

            print("✅ All Test checklist generated successfully")
            return testchecklist
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"❌ Error generating test checklist: {e}")
            raise

    async def update_chat_assistant(self, chat_id, dataset_id, cancellation_event=None):
        """
        Update the chat assistant with the latest dataset.

        curl --location --request PUT 'http://localhost:9380/api/v1/chats/{{chat_id}}' \
        --header 'Content-Type: application/json' \
        --header 'Authorization: Bearer ••••••' \
        --data '{
            "dataset_ids": ["{{dataset_id}}"],
            "prompt": {
                "similarity_threshold": 0.2, 
                "keywords_similarity_weight": 0.5
            }
        }'
        """

        try:
            if cancellation_event and cancellation_event.is_set():
                raise asyncio.CancelledError("Operation cancelled")

            url = f"{BASE_URL}{UPDATE_CHAT_ASSISTANT.format(chat_id=chat_id)}"
            payload = {
                "dataset_ids": [dataset_id],
                "prompt": {
                    "similarity_threshold": 0.2,
                    "keywords_similarity_weight": 0.5
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=HEADERS, json=payload, timeout=30) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if result.get("code") == 0:
                        print(
                            f"✅ Chat assistant updated with dataset {dataset_id}")
                        self.dataset_added = True
                    else:
                        raise Exception(
                            f"Failed to update chat assistant: {result.get('message')}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"❌ Error updating chat assistant: {e}")\


    def is_dataset_include_parsed_file(self, dataset_id):
        """
        Check if the dataset includes the parsed file.

        curl --location --request GET 'http://localhost:9380/api/v1/datasets' \
        --header 'Content-Type: application/json' \
        --header 'Authorization: Bearer ••••••' 

        """
        try:
            url = f"{BASE_URL}{LIST_DATASETS}"
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            result = response.json()

            if result.get("code") == 0:
                datasets = result.get("data", [])
                for dataset in datasets:
                    if dataset.get("id") == dataset_id:
                        chunk_count = dataset.get("chunk_count", 0)
                        if chunk_count > 0:
                            print(
                                f"✅ Dataset {dataset_id} includes parsed file.")
                            return True

            print(f"❌ Dataset {dataset_id} does not include parsed file.")
            return False

        except Exception as e:
            print(f"❌ Error checking dataset for parsed file: {e}")
            return False

    def update_chat_assistant_with_dataset(self):
        # check dataset to add to chat assitant
        # update chat assistant
        dataset_id = self.dataset_id
        chat_id = self.chat_id
        if dataset_id is None:
            raise ValueError(
                "Dataset ID is not set. Please create a dataset first.")
        try:
            if self.is_dataset_include_parsed_file(dataset_id):
                self.update_chat_assistant(chat_id, dataset_id)
            else:
                print(
                    "❌ Dataset does not include parsed file. Skipping chat assistant update.")
                return
        except Exception as e:
            print(f"❌ Error updating chat assistant: {e}")
            raise
