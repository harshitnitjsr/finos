# ─────────────────────────────────────────────────────────────────────────────
# AFOS — AI Financial Operating System
# Backend Docker Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# Install system dependencies required for OCR and PDF processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Install Python dependencies
# We copy this first to leverage Docker's cache for layers
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the uploads directory for local storage
RUN mkdir -p /app/uploads

# Expose port 8000 for FastAPI
EXPOSE 8000

# Set a healthcheck to ensure the API is responsive
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application using uvicorn
# We use 0.0.0.0 to allow access from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
