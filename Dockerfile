# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app


# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RAGFLOW_BASE_URL=http://host.docker.internal:9380

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Create virtual environment
RUN python -m venv /opt/venv

# Activate virtual environment and install dependencies
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Expose port (adjust if your app uses a different port)
EXPOSE 4444

# Run the application
CMD ["python", "main.py"]
