from docx import Document

def extract_text_from_docx(path: str) -> str:
    try:
        doc = Document(path)
    except Exception as e:
        print("Ошибка открытия файла:", path)
        raise e

    return "\n".join(p.text for p in doc.paragraphs)