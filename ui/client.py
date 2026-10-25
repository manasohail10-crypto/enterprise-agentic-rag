import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_URL = os.getenv("RAG_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")


class ApiError(Exception):
    pass


def ask(base_url, question, thread_id):
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    start = time.perf_counter()

    try:
        response = requests.post(
            f"{base_url}/query",
            json={"q": question, "thread_id": thread_id},
            headers=headers,
            timeout=120,
        )
    except requests.ConnectionError:
        raise ApiError(f"The API is not running at {base_url}. Start it with: uvicorn app.api:app --port 8000")
    except requests.Timeout:
        raise ApiError("The answer took too long. Try again in a moment.")

    if response.status_code == 401:
        raise ApiError("The API key is missing or wrong. Put the same API_KEY in your .env file for the API and this page.")
    if response.status_code == 429:
        raise ApiError("Too many questions in one minute. Wait a little, then ask again.")
    if response.status_code >= 400:
        try:
            request_id = response.json().get("request_id")
        except ValueError:
            request_id = None
        suffix = f" Request ID: {request_id}" if request_id else ""
        raise ApiError(f"The API could not answer (error {response.status_code}). Check the API window for details.{suffix}")

    result = response.json()
    result["seconds"] = time.perf_counter() - start
    return result


def get_health(base_url):
    try:
        response = requests.get(f"{base_url}/ready", timeout=30)
        return response.status_code, response.json()
    except (requests.RequestException, ValueError):
        return None