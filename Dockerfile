FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required by OpenCV and video decoders
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy source code and frontend
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY tables.json /app/tables.json
COPY table_tops.json /app/table_tops.json

EXPOSE 8000

ENV PYTHONPATH=/app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
