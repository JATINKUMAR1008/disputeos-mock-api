FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code — wildcard so we don't have to remember to update
# this line every time a new module is added (this exact bug shipped to
# Render once when models.py and store.py were added in v2.0).
COPY *.py ./

EXPOSE 8888

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]
