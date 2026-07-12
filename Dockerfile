FROM python:3.11-slim

# ffmpeg нужен для обработки голосовых (.fv), остальное — для Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# База данных хранится в /app/data (можно смонтировать volume)
ENV DB_PATH=/app/data/savemod.db
RUN mkdir -p /app/data

# Health-сервер для keep-alive (Koyeb/Render). Реальный порт берётся из $PORT.
ENV PORT=8000
EXPOSE 8000

CMD ["python", "run.py"]
