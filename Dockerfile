
# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install ffmpeg (for video/gif → webm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py /app/

# Default: polling; override with env to use webhook
# ENV USE_WEBHOOK=false
# ENV WEBHOOK_URL=
# ENV PORT=8080

CMD ["python","bot.py"]
