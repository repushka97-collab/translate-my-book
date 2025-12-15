#!/bin/bash
set -e

echo "🚀 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    poppler-utils tesseract-ocr libtesseract-dev \
    libgl1 libsm6 ghostscript libfontconfig1 \
    libfreetype6 libharfbuzz0b libxcb-cursor0 \
    libxcb-xfixes0 libxrender1 libxext6

echo "🐍 Creating virtual environment..."
python3 -m venv pdf_env
source pdf_env/bin/activate

echo "📦 Installing Python packages..."
pip install --upgrade pip setuptools wheel

# Критические библиотеки для PDF
pip install --no-cache-dir \
    pymupdf==1.24.4 pdfplumber==0.11.1 pdf2docx==0.5.8 \
    pypdf==4.3.1 pdfminer.six==20231228 ocrmypdf==15.1.0

# Для векторной графики
pip install --no-cache-dir \
    opencv-python-headless==4.10.0.84 Pillow==10.4.0 \
    svgwrite==1.4.3 svgpathtools==1.5.1 scikit-image==0.23.2 \
    weasyprint==61.0

# Для ML/AI
pip install --no-cache-dir \
    layoutparser[all]==0.3.4 doctr==0.10.0 transformers==4.44.2 \
    torch==2.4.0 torchvision==0.19.0 sentencepiece==0.2.0

# Специализированные
pip install --no-cache-dir \
    mathpix==1.0.0 tabula-py==2.10.0 camelot-py[cv]==0.11.0 \
    fonttools==4.53.1 colour-science==0.4.8

# Для оптимизации
pip install --no-cache-dir \
    dask==2024.8.0 joblib==1.4.2 memory-profiler==0.61.0 \
    pdf-diff==2.0.0 perceptualdiff==1.0.1 structural-similarity==0.2.5

echo "✅ All dependencies installed successfully!"
echo "🔧 Next steps:"
echo "1. Source the environment: source pdf_env/bin/activate"
echo "2. Set your Mathpix API key: export MATHPIX_APP_ID=your_id MATHPIX_APP_KEY=your_key"
echo "3. Run your PDF translation script"