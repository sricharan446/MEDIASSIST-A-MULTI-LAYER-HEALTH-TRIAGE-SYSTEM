from pypdf import PdfReader

def load_text_from_file(file_path):
    text = ""

    try:
        # PDF support
        if file_path.endswith(".pdf"):
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted

        # TEXT / CODE FILES
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

    except Exception as e:
        print("Error reading file:", e)
        return ""

    return text.strip()
