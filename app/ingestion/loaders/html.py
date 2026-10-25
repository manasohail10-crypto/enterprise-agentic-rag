import logfire
from bs4 import BeautifulSoup


def parse_html(file_path):
    with logfire.span("html parsing", filename=file_path):
        with open(file_path, "rb") as file:
            soup = BeautifulSoup(file, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        lines = [" ".join(text.split()) for text in soup.stripped_strings]
        return "\n".join(lines)