# ── Build stage ──
FROM python:3.14-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libffi-dev libjpeg62-turbo-dev zlib1g-dev libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Production stage ──
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libjpeg62-turbo libwebp7 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home terminchen

WORKDIR /app
COPY . .

RUN mkdir -p /app/uploads/avatars && chown -R terminchen:terminchen /app /app/uploads

USER terminchen

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "2", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "wsgi:application"]
