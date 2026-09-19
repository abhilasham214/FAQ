FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models

WORKDIR /app

# CPU-only torch first: the default wheel bundles CUDA and adds ~2 GB to the image.
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
# Hosting platforms (Render, Railway, ...) inject $PORT; default to 8000 for docker-compose.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
