FROM ubuntu:22.04

# Системные зависимости
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    ghostscript \
    python3 \
    python3-pip \
    libgl1 \
    libsm6 \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . /app
WORKDIR /app

# Точки монтирования для данных
VOLUME ["/input", "/output", "/checkpoints"]

# Команда по умолчанию
CMD ["python", "run_pipeline.py", \
     "--source", "/input", \
     "--output", "/output", \
     "--mode", "fast"]

