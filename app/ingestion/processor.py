import json
import sys
import uuid
from pathlib import Path

import logfire
from qdrant_client import QdrantClient, models

from app.config import setting
from app.ingestion.chunking.splitter import chunk_text
from app.ingestion.domains import get_domain
from app.ingestion.loaders.html import parse_html
from app.ingestion.loaders.office import parse_office
from app.ingestion.loaders.pdf import parse_pdf
from app.ingestion.loaders.text import parse_text
from app.services.retrieval.embedding import embed_texts, get_embedding_dim

logfire.configure(
    token=setting.LOGFIRE_TOKEN,
    service_name="enterprise-ingestion-service",
    send_to_logfire="if-token-present",
)

PROCESSED_DIR = Path("processed_data")
UPLOAD_BATCH = 100

client = QdrantClient(url=setting.QDRANT_CLUSTER_ENDPOINT, api_key=setting.QDRANT_API_KEY)


def get_source_type(name, default):
    if "true" in name.lower():
        return "true"
    if "noisy" in name.lower():
        return "noisy"
    return default


def remove_repeated_lines(text):
    lines = []
    last = None
    for line in text.splitlines():
        key = line.strip().lower()
        if len(key) > 3 and key == last:
            continue
        if key:
            last = key
        lines.append(line)
    return "\n".join(lines)


def save_processed(filename, source_type, domain, chunks):
    folder = PROCESSED_DIR / source_type
    folder.mkdir(parents=True, exist_ok=True)
    data = {"filename": filename, "source_type": source_type, "domain": domain, "chunks": chunks}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    (folder / f"{filename}.json").write_text(text, encoding="utf-8")


def process_file(path, source_type):
    with logfire.span("process file", file=path.name, source=source_type):
        try:
            extension = path.suffix.lower()
            file_path = str(path)

            if extension == ".pdf":
                text = parse_pdf(file_path)
            elif extension in (".html", ".htm"):
                text = parse_html(file_path)
            elif extension == ".txt":
                text = parse_text(file_path)
            elif extension in (".docx", ".pptx"):
                text = parse_office(file_path)
            else:
                logfire.warning("unsupported file type", file=path.name)
                return

            chunks = chunk_text(remove_repeated_lines(text))
            if not chunks:
                logfire.warning("no text found", file=path.name)
                return

            domain = get_domain(path.stem)
            if domain == "general":
                logfire.warning("no domain set for this file, add it to domains.py", file=path.name)

            ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_type}/{path.name}/{i}")) for i in range(len(chunks))]
            if len(client.retrieve(setting.QDRANT_COLLECTION, ids=ids, with_payload=False)) == len(ids):
                logfire.info("already indexed", file=path.name)
                return

            save_processed(path.name, source_type, domain, chunks)

            vectors = embed_texts(chunks)
            points = [
                models.PointStruct(
                    id=ids[i],
                    vector=vector,
                    payload={
                        "text": chunk,
                        "source": path.name,
                        "source_type": source_type,
                        "domain": domain,
                    },
                )
                for i, (chunk, vector) in enumerate(zip(chunks, vectors))
            ]

            for start in range(0, len(points), UPLOAD_BATCH):
                client.upsert(
                    collection_name=setting.QDRANT_COLLECTION,
                    points=points[start : start + UPLOAD_BATCH],
                )

            logfire.info("file indexed", file=path.name, domain=domain, chunks=len(points))
        except Exception:
            logfire.exception("failed to process file", file=path.name)


def process_directory(folder, source_type):
    with logfire.span("scan directory", path=str(folder), source=source_type):
        for path in sorted(Path(folder).iterdir()):
            if path.is_file():
                process_file(path, source_type)


def run_ingestion(base_dir, source_type=None, wipe=False):
    with logfire.span("ingestion", base_directory=str(base_dir)):
        collection = setting.QDRANT_COLLECTION

        if wipe and client.collection_exists(collection):
            client.delete_collection(collection)

        if not client.collection_exists(collection):
            client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(
                    size=get_embedding_dim(),
                    distance=models.Distance.COSINE,
                ),
            )

        base = Path(base_dir)
        subdirs = sorted(p for p in base.iterdir() if p.is_dir())

        if not subdirs:
            process_directory(base, source_type or get_source_type(base.name, "general"))
        else:
            for subdir in subdirs:
                process_directory(subdir, get_source_type(subdir.name, subdir.name))


if __name__ == "__main__":
    wipe = "--wipe" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--wipe"]

    target = args[0] if args else "DATA"
    source_type = args[1] if len(args) > 1 else None

    if not Path(target).exists():
        sys.exit(f"path '{target}' does not exist")

    run_ingestion(target, source_type, wipe)
    logfire.info("ingestion finished")