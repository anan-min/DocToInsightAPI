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

สร้างรายการตรวจสอบการทดสอบสำหรับความต้องการเชิงฟังก์ชันนี้ โปรดแปลและสร้างรายการทดสอบเป็นภาษาไทย

Return format:
[
    "ตรวจสอบว่าฟอร์มลงทะเบียนรับข้อมูลที่ถูกต้อง",
    "ตรวจสอบการจัดการข้อผิดพลาดเมื่อข้อมูลไม่ครบถ้วน", 
    "ตรวจสอบว่าการเข้าสู่ระบบสำเร็จเมื่อใช้ข้อมูลที่ถูกต้อง",
    "ตรวจสอบว่าการเข้าสู่ระบบล้มเหลวเมื่อใช้ข้อมูลที่ผิด"
]
"""


SYSTEM_PROMPT = """
You are a helpful assistant specialized in analyzing documents and extracting functional requirements. When asked about functional requirements, please provide a comprehensive list based on the document content.
"""