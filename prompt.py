FUNCTIONAL_REQUIREMENTS_PROMPT = """
document_name: {document_name}

List the functional requirements found in this document.

Return format:
[
  "Users must be able to register and log in.",
  "Admins can manage user roles.",
  "System should send confirmation emails after purchase."
]
"""

TEST_CHECKLIST_PROMPT = """
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


SYSTEM_PROMPT = """
You are a helpful assistant specialized in analyzing documents and extracting functional requirements. When asked about functional requirements, please provide a comprehensive list based on the document content.
"""