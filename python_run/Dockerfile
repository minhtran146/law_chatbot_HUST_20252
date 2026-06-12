# Bước 1: Chọn Image nền (nên dùng -slim để nhẹ nhưng vẫn đủ thư viện cơ bản)
FROM python:3.10-slim

# Bước 2: Đặt biến môi trường
# Không tạo ra các file .pyc (tiết kiệm dung lượng)
ENV PYTHONDONTWRITEBYTECODE=1
# Hiển thị log ngay lập tức lên terminal (quan trọng khi xem docker logs)
ENV PYTHONUNBUFFERED=1

# Bước 3: Thiết lập thư mục làm việc
WORKDIR /app

# Bước 4: Cài đặt các gói hệ thống cần thiết (nếu có dùng các thư viện C)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bước 5: Cài đặt thư viện Python
# Copy requirements trước để tận dụng Docker Cache (không phải cài lại nếu chỉ sửa code)
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates

# Bước 6: Copy mã nguồn vào container
COPY . .

# Bước 7: Auto-start FastAPI với uvicorn
CMD ["uvicorn", "src.fastapi.main_api:app", "--host", "0.0.0.0", "--port", "8002"]