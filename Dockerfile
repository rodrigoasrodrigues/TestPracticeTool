FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/app/static/uploads

EXPOSE 5000

CMD ["sh", "-c", "python init_db.py && exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers=2 --threads=4 --timeout=120 --access-logfile - --error-logfile - run:app"]
