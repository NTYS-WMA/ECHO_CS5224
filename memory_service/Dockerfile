FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements (without mem0ai)
COPY server/requirements.txt .
RUN sed '/mem0ai/d' requirements.txt > requirements_no_mem0.txt && \
    pip install --no-cache-dir -r requirements_no_mem0.txt

# Copy our modified mem0 source code and performance monitoring
COPY mem0 /app/mem0
COPY performance_monitoring /app/performance_monitoring

# Install dependencies for mem0 (including PostgreSQL support)
RUN pip install --no-cache-dir openai posthog protobuf pytz qdrant-client sqlalchemy psycopg2-binary volcengine-python-sdk

# Copy application code
COPY server .

# Create history directory
RUN mkdir -p /app/history

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
# Add both mem0 source and performance monitoring to Python path
ENV PYTHONPATH="/app:/app/performance_monitoring:${PYTHONPATH}"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
