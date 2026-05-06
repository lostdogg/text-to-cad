# ===== Build stage =====
FROM python:3.11-slim AS backend-base

WORKDIR /app

# System deps for trimesh / scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# Create exports directory
RUN mkdir -p exports

ENV MODE=cloud
ENV HOST=0.0.0.0
ENV PORT=8000
ENV EXPORT_DIR=/app/exports

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
