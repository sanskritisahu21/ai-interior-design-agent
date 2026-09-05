FROM python:3.11-slim

WORKDIR /app

# Copy application code and database
COPY . /app

# Ensure standard output is not buffered
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

CMD ["python", "run_app.py", "--serve"]
