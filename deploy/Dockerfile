FROM python:3.11-slim-bookworm
WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-6 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libglib2.0-0 libxss1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (only if you plan to use Playwright in container)
RUN python -m playwright install --with-deps

COPY . /app

ENV PYTHONUNBUFFERED=1

CMD ["python3", "scripts/manager.py"]
