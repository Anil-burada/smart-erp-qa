# Use the official Playwright browser/dependency image. Match Python Playwright package.
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ERPQA_HEADLESS=1
WORKDIR /workspace
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt 'playwright==1.64.1'
COPY . /workspace
EXPOSE 8766
CMD ["sh", "-c", "if [ ! -f data/erpqa.sqlite3 ]; then python scripts/seed_mock_demo.py; fi; exec python -m uvicorn backend.api:app --host 0.0.0.0 --port 8766"]
