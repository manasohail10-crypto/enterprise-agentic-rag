import logfire
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(text, chunk_size=1500, chunk_overlap=150):
    with logfire.span("text chunking", text_length=len(text)):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return splitter.split_text(text)