import re
import xml.etree.ElementTree as ET
import zipfile

import logfire

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SLIDE = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def read_paragraphs(xml_bytes, namespace):
    root = ET.fromstring(xml_bytes)
    for paragraph in root.iter(namespace + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
        if text.strip():
            yield text


def slide_number(name):
    return int(re.search(r"(\d+)\.xml$", name).group(1))


def parse_office(file_path):
    with logfire.span("office parsing", filename=file_path):
        with zipfile.ZipFile(file_path) as archive:
            if file_path.lower().endswith(".docx"):
                lines = read_paragraphs(archive.read("word/document.xml"), WORD)
            else:
                names = [n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
                names.sort(key=slide_number)
                lines = (line for name in names for line in read_paragraphs(archive.read(name), SLIDE))
            text = "\n".join(lines)

        if not text.strip():
            logfire.warning("no text found", filename=file_path)

        return text