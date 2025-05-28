# Use an official Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/config/gcloud/service-account.json

# Create app directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project files
COPY . .

# Create config directory and ensure it exists
RUN mkdir -p /app/config/gcloud

# Expose FastAPI port
EXPOSE 8003

# Run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]