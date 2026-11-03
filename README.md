# LTM Group 13 — TCP Server Load Research

Khảo sát ảnh hưởng của số client TCP đồng thời đến latency, throughput, error rate
và CPU của server. Đã có server skeleton asyncio; bộ tạo tải và benchmark chưa triển khai.

## Thiết lập Python (Windows / PowerShell)

Yêu cầu Python >= 3.11. Môi trường hiện tại đã tạo bằng Python 3.13.14.

```powershell
cd LTM_Group_13_research
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python scripts/check_environment.py
```

Nếu PowerShell chặn activate, sử dụng trực tiếp interpreter, không cần đổi execution policy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/check_environment.py
```

Trong VS Code: `Python: Select Interpreter` → `.venv\Scripts\python.exe`.
Linux/macOS: tạo bằng `python3 -m venv .venv`, kích hoạt bằng `source .venv/bin/activate`.

## Cấu trúc

```text
src/
  server/                 # TCP server (process riêng)
  load_generator/         # Bộ tạo tải; mỗi client một kết nối TCP
  common/                 # Protocol, cấu hình và kiểu dữ liệu dùng chung
experiments/
  configs/                # Cấu hình tái lập các kịch bản
  raw-data/               # CSV/JSON thô từ các lần chạy
  analysis/               # Script phân tích và kiểm chứng độc lập
  figures/                # Biểu đồ từ dữ liệu thực nghiệm
tests/                    # Kiểm thử protocol và tích hợp
scripts/                  # Công cụ hỗ trợ môi trường
docs/                     # Thiết kế, phương pháp đo, báo cáo, đóng góp
```

`load_generator` dùng dấu gạch dưới để làm package Python. Server và bộ tạo tải
sẽ dùng thư viện chuẩn (`asyncio`, `socket`, `json`, `argparse`); `psutil` dành cho
đo CPU, `matplotlib` dành cho biểu đồ, `pytest` dành cho kiểm thử.

## Kế hoạch thí nghiệm

`experiments/configs/baseline.json` chuẩn bị các mức 1, 10, 50 client,
3 lần lặp/mức, payload 1024 byte, warm-up 5 giây, đo chính thức 20 giây.
Đây là cấu hình dự kiến, chưa có chương trình đọc và thực thi cấu hình.

Server đã có framing, echo requestId/payload, timeout, disconnect và giới hạn payload.
Cần triển khai load generator, đo lường và lệnh tái tạo thí nghiệm.

Checklist yêu cầu và quyết định ban đầu: [docs/research-plan.md](docs/research-plan.md).
Không commit `.venv`, cache hoặc log tạm. Dữ liệu thô và biểu đồ có chủ đích được
giữ trong Git để tái lập nghiên cứu. Không đưa thông tin cá nhân vào dữ liệu đo.

## Chạy server skeleton

Tại thư mục project, sau khi kích hoạt `.venv`:

```powershell
$env:PYTHONPATH = "src"
python -m server --host 127.0.0.1 --port 9000 --timeout 5 --max-payload-bytes 65536
```

Dừng bằng Ctrl+C. Linux/macOS: `PYTHONPATH=src python -m server`.
Server dùng một coroutine cho mỗi kết nối, hỗ trợ nhiều request trên một kết nối.
Mỗi frame gồm 4 byte độ dài unsigned big-endian và JSON UTF-8 có `requestId`
(chuỗi không rỗng, tối đa 128 ký tự) và `payload` (chuỗi, giới hạn theo byte UTF-8).
Response trả lại đúng hai trường này. Frame tối đa 512 KiB; payload mặc định 64 KiB.
Dữ liệu sai hoặc timeout sẽ đóng riêng kết nối đó, không gửi error frame.
Timeout áp dụng cho việc đọc toàn bộ một frame và drain response, mỗi bước riêng.
Server không log từng request ở mức INFO để hạn chế ảnh hưởng đến benchmark.

Chạy kiểm thử: `python -m pytest -q`.
