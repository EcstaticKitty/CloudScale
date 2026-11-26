
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ templates/

# Create a non-root user
RUN useradd --create-home appuser
USER appuser

# Expose Gunicorn application port
EXPOSE 10000

# Start application using Gunicorn
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} app:app"]
