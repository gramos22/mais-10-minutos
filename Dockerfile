FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py runtime.py ./
COPY templates ./templates
COPY static ./static
COPY artifacts ./artifacts
RUN useradd --uid 10001 --create-home appuser
USER appuser
ENV HOST=0.0.0.0 PORT=8000 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "app.py"]
