FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY projects/ ./projects/
ENV PYTHONPATH=/app

EXPOSE 8501 8502 8503 8504
