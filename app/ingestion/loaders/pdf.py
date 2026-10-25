import logfire
import pdfplumber
from pypdf import PdfReader


def parse_pdf(file_path):
    with logfire.span("pdf parsing", filename=file_path):
        reader = PdfReader(file_path)
        pages = [page.extract_text() or "" for page in reader.pages]

        blank = [i for i, text in enumerate(pages) if not text.strip()]
        if blank:
            try:
                with pdfplumber.open(file_path) as pdf:
                    for i in blank:
                        pages[i] = pdf.pages[i].extract_text() or ""
            except Exception as error:
                logfire.warning("pdfplumber failed", error=str(error))

        text = "\n".join(page for page in pages if page.strip())

        if not text:
            logfire.warning("no text found", filename=file_path)

        return text