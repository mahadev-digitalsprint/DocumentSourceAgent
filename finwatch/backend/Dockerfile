FROM python:3.11-slim

# System deps: Tesseract OCR, Poppler (for pdf2image), gcc
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
