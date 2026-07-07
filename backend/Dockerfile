# =============================================================================
#  Smart Zone Trading Bot — Backend image (produksi, ringan, non-root)
# =============================================================================
FROM python:3.11-slim

# Tidak menulis .pyc & output langsung ter-flush (log rapi di container).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Pasang dependensi lebih dulu agar layer cache efektif.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kode aplikasi.
COPY app ./app

# Direktori data (SQLite) + user non-root. Named volume yang di-mount ke
# /app/data akan mewarisi kepemilikan appuser saat pertama kali dibuat.
RUN mkdir -p /app/data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck memakai endpoint /health (tanpa dependensi tambahan).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else sys.exit(1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
