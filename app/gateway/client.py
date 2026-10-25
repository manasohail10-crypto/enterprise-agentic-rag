from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders

from app.config import setting


def make_headers(feature="rag"):
    return createHeaders(
        api_key=setting.PORTKEY_API_KEY,
        config=setting.PORTKEY_PRIMARY_CONFIG_ID,
        metadata={"feature": feature, "_user": "rag-system"},
    )


portkey_client = OpenAI(
    api_key=setting.PORTKEY_API_KEY,
    base_url=PORTKEY_GATEWAY_URL,
    default_headers=make_headers(),
)


def get_langchain_llm(feature="rag"):
    return ChatOpenAI(
        api_key=setting.PORTKEY_API_KEY,
        base_url=PORTKEY_GATEWAY_URL,
        model=setting.GROQ_MODEL,
        default_headers=make_headers(feature),
    )


def get_async_openai_client(feature="rag"):
    return AsyncOpenAI(
        api_key=setting.PORTKEY_API_KEY,
        base_url=PORTKEY_GATEWAY_URL,
        default_headers=make_headers(feature),
    )


def extract_cache_status(raw_response):
    return raw_response.headers.get("x-portkey-cache-status", "MISS").upper()