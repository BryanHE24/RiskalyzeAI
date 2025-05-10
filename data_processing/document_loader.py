# File path: data_processing/document_loader.py
# -----------------------------
# data_processing/document_loader.py

from docx import Document
import fitz  # PyMuPDF

def load_txt(file_path):
    """Load text file with multiple encoding attempts"""
    encodings = ['utf-8', 'latin-1', 'utf-16', 'ascii']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read().strip()
                if not content:
                    raise ValueError("Empty file")
                return content
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError(f"Failed to decode {file_path}")

def load_pdf(file_path):
    """Load PDF file text"""
    try:
        doc = fitz.open(file_path)
        return "".join([page.get_text() for page in doc])
    except Exception as e:
        print(f"⚠️ PDF load error: {str(e)}")
        return ""

def load_docx(file_path):
    """Load DOCX file text"""
    try:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"⚠️ DOCX load error: {str(e)}")
        return ""
