# Dockerfile  ->  the API image (FastAPI + LangGraph agent)
#
# Build it from the project root:
#   docker build -t enterprise-rag-api:local .
#
# It has two stages:
#   1) "builder"  installs all Python packages and downloads the small guardrails model.
#   2) "runtime"  copies only the finished result into a clean, small image.

# Use the same Python version you use on your PC. Check it with: python --version
ARG PYTHON_VERSION=3.12


# ---------- Stage 1: builder ----------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  FASTEMBED_CACHE_PATH=/opt/models

# A virtual environment, so we can copy all packages to the next stage in one piece.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY requirements-api.txt requirements.lock.txt ./

# - the extra index gives the small CPU-only torch (about 200 MB, not 3 GB with GPU files)
# - "-c requirements.lock.txt" keeps the exact versions you tested on your PC
RUN pip install \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  -r requirements-api.txt \
  -c requirements.lock.txt

# Safety check: stop the build if GPU (nvidia) packages sneaked in.
RUN ! pip list | grep -i "^nvidia"

# NeMo Guardrails needs a small model (all-MiniLM-L6-v2, about 90 MB).
# Download it now, so the API does not download it again on every start.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

# Proof: load it again with the internet switched off (HF_HUB_OFFLINE=1).
# If this step passes, the saved copy is complete and the API can start without internet.
RUN HF_HUB_OFFLINE=1 python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"


# ---------- Stage 2: runtime ----------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/opt/venv/bin:${PATH}" \
  FASTEMBED_CACHE_PATH=/opt/models \
  HF_HUB_OFFLINE=1
# HF_HUB_OFFLINE=1 = use only the model saved in the image, never call the HuggingFace website.
# Note: this also means the local backup embedding model (mxbai-embed-large-v1) cannot be
# downloaded. That is fine while JINA_API_KEY is set, because then only Jina is used.

# libgomp1 is a tiny system library (some math packages need it; this is cheap insurance).
# Then we make a normal user: the app must not run as root.
RUN apt-get update \
  && apt-get install -y --no-install-recommends libgomp1 \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --system --gid 10001 app \
  && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
  && mkdir -p /app \
  && chown app:app /app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /opt/models /opt/models
COPY --chown=app:app app/ ./app/

USER app
EXPOSE 8000

# /health only answers "ok" and calls no outside service, so it is cheap and safe to call often.
# start-period is long because the API checks its connections when it starts.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# One worker on purpose: the model and the agent live in memory.
# To handle more users later, run more containers (Kubernetes replicas), not more workers.
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]