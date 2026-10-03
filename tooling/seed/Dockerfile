FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY import_institution_contacts.py .
USER 65534:65534
ENTRYPOINT ["python", "/app/import_institution_contacts.py"]
