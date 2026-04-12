#!/bin/bash
# Script tự động deploy, chạy và thu thập output từ GPU server

set -e

echo "🚀 Bắt đầu quá trình deploy và chạy LLaVA fine-tuning..."

# Kiểm tra kết nối đến GPU server bằng SSH (thay vì ping)
echo "🔍 Kiểm tra kết nối đến GPU server (10.8.0.7) bằng SSH..."
if ! ssh emie@10.8.0.7 "echo 'Connection test successful'" > /dev/null 2>&1; then
    echo "❌ Không thể kết nối đến GPU server. Vui lòng kiểm tra VPN và kết nối mạng."
    exit 1
fi
echo "✅ GPU server online"

# Kiểm tra file nén có tồn tại không
if [ ! -f "/tmp/llava_finetune_static/llava_finetune.tar.gz" ]; then
    echo "❌ File nén không tồn tại. Vui lòng chạy các bước chuẩn bị trước."
    exit 1
fi
echo "✅ File nén đã sẵn sàng: /tmp/llava_finetune_static/llava_finetune.tar.gz"

# Gửi file code lên server
echo "📤 Đang gửi code lên server..."
ssh emie@10.8.0.7 "rm -f /home/emie/llava_finetune.tar.gz" > /dev/null 2>&1
scp /tmp/llava_finetune_static/llava_finetune.tar.gz emie@10.8.0.7:/home/emie/llava_finetune.tar.gz

# Giải nén và cài đặt môi trường trên server
echo "🔧 Đang giải nén và cài đặt môi trường trên server..."
ssh emie@10.8.0.7 "mkdir -p /home/emie/llava_finetune && cd /home/emie/llava_finetune && rm -rf * && echo 'Đang giải nén...' && tar -xzf /home/emie/llava_finetune.tar.gz && echo 'Giải nén xong!' && ls -la" > /dev/null 2>&1

# Kiểm tra xem đã giải nén thành công chưa
echo "🔍 Kiểm tra nội dung thư mục sau khi giải nén..."
ssh emie@10.8.0.7 "ls -la /home/emie/llava_finetune/" > /dev/null 2>&1

# Kiểm tra và sử dụng Python đúng trên server
echo "🔧 Đang xác định môi trường Python trên server..."
PYTHON_CMD=$(ssh emie@10.8.0.7 "which python3 || which python")
if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Không tìm thấy Python trên server. Vui lòng cài đặt Python3."
    exit 1
fi
echo "✅ Sử dụng Python: $PYTHON_CMD"

# Cài đặt các thư viện với phiên bản tương thích
# Fix: Cài đặt torch, torchvision, torchaudio với phiên bản tương thích
ssh emie@10.8.0.7 "cd /home/emie/llava_finetune && $PYTHON_CMD -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121" > /dev/null 2>&1

# Cài đặt transformers và các thư viện khác
ssh emie@10.8.0.7 "cd /home/emie/llava_finetune && $PYTHON_CMD -m pip install --upgrade transformers accelerate peft bitsandbytes pillow ultralytics" > /dev/null 2>&1

# Kiểm tra xem file train_llava_lora.py có tồn tại không
echo "🔍 Kiểm tra file train_llava_lora.py..."
ssh emie@10.8.0.7 "ls -la /home/emie/llava_finetune/scripts/train_llava_lora.py" > /dev/null 2>&1

# Chạy fine-tuning và thu thập output real-time
echo "⚡ Đang chạy fine-tuning trên GPU server..."
ssh emie@10.8.0.7 "cd /home/emie/llava_finetune && $PYTHON_CMD scripts/train_llava_lora.py" > /tmp/llava_output.log 2>&1

echo "✅ Hoàn thành! Quá trình fine-tuning đã bắt đầu trên GPU server."
echo "💡 Để theo dõi tiến trình: ssh emie@10.8.0.7 'watch -n 1 nvidia-smi'"
echo "📝 Output đã được ghi vào: /tmp/llava_output.log (trên server)"
echo "👉 Để xem output: ssh emie@10.8.0.7 'cat /tmp/llava_output.log'"