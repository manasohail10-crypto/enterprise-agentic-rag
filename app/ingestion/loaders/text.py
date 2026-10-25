import logfire


def parse_text(file_path):
    with logfire.span("text parsing", filename=file_path):
        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as file:
            return file.read()