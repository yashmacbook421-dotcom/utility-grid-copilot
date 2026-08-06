FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# sentence-transformers pulls in the full CUDA-enabled torch build by default
# (~4GB, almost entirely unused nvidia libs, since this only ever runs on
# CPU) — enough alone to blow past a 512MB container. Installing the CPU-only
# wheel first means the requirements.txt install below sees torch's
# dependency already satisfied and never pulls the GPU build.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
