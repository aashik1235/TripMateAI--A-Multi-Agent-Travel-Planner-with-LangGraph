# 1. Use Python 3.11
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Python environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements file
COPY requirements.txt .

# 6. Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy project files
COPY . .

# 8. Create required directories
RUN mkdir -p uploads data

# 9. Expose application port
EXPOSE 8000

# 10. Start FastAPI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]