FROM python:3.11-slim

# Install FFmpeg and fonts
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use Railway's PORT environment variable
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --timeout 120 --log-level info
