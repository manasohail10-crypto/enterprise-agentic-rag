import os

# The settings class needs these keys to exist. The tests never call a real service,
# so fake values are enough. Real values in your environment or .env are not touched.
for key in (
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "QDRANT_API_KEY",
    "QDRANT_CLUSTER_ENDPOINT",
    "PORTKEY_API_KEY",
    "PORTKEY_PRIMARY_CONFIG_ID",
):
    os.environ.setdefault(key, "test-value")