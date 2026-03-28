FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . ./ai_generation_service/

# Expose service port
EXPOSE 8003

# Run with uvicorn
CMD ["uvicorn", "ai_generation_service.app:app", "--host", "0.0.0.0", "--port", "8003"]
