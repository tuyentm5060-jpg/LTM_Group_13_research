# LTM Group 13 — TCP Server Load Research

## 1. Giới thiệu

Ứng dụng desktop gồm Client GUI và TCP Server, dùng để khảo sát ảnh hưởng của
số client đồng thời đến RTT, latency, throughput và tỷ lệ lỗi của server.
Client gửi request chứa `requestId` và `payload`; server trả lại dữ liệu để client
kiểm tra tính chính xác và đo thời gian phản hồi.

## 2. Chức năng

- Nhập host, port, số client, số request/client, kích thước payload, timeout và think time trên GUI.
- Tạo nhiều client TCP đồng thời, mỗi client giữ một kết nối để gửi nhiều request.
- Gửi tuần tự trên mỗi kết nối: nhận response của request trước rồi mới gửi request tiếp theo.
- Server echo lại `requestId` và `payload`; client kiểm tra cả hai trường.
- Xử lý timeout, ngắt kết nối, dữ liệu không hợp lệ và payload vượt giới hạn.
- Lỗi ở một kết nối được xử lý riêng, các kết nối khác tiếp tục hoạt động.
- Hiển thị trạng thái client: `SUCCESS`, `FAILED`, `STOPPED` và chi tiết kết quả.
- Đo RTT trung bình, min/max, p50, p95, p99, throughput và tỷ lệ lỗi.
- Xuất dữ liệu từng request ra CSV.
- Chạy benchmark qua CLI, hỗ trợ warm-up, đo theo thời gian và lặp theo cấu hình JSON.
- GUI chạy phần tạo tải trong worker thread, cập nhật giao diện qua hàng đợi sự kiện.
- Server ghi log khởi động/dừng ở mức INFO; ngắt kết nối và lỗi client ở mức DEBUG.


## 3. Giao thức

- Port mặc định: `9000`.
- Mỗi frame gồm 4 byte độ dài unsigned big-endian, theo sau là JSON UTF-8.
- Độ dài trong header là số byte của phần JSON, không tính 4 byte header.
- `requestId`: chuỗi không rỗng, tối đa 128 ký tự.
- `payload`: chuỗi, kiểm tra kích thước theo số byte UTF-8.
- Payload mặc định của client: 1.024 byte, không tính overhead JSON và header.
- Giới hạn payload mặc định của server: 65.536 byte; frame tối đa 512 KiB.
- Server đọc đủ header và body, hỗ trợ frame bị chia nhỏ hoặc nhiều frame được gửi liền nhau.
- Server có timeout riêng cho việc đọc toàn bộ frame và gửi response.
- Dữ liệu sai hoặc timeout làm đóng riêng kết nối đó; server không gửi error frame.

Ví dụ request và response echo tương ứng:

```json
{
  "requestId": "c1-r1-example",
  "payload": "hello"
}
```

### Mã lỗi trả về client

## 4. Cấu hình

Server nhận cấu hình bằng tham số dòng lệnh; client nhận cấu hình qua GUI hoặc CLI.
CLI đọc file `experiments/configs/baseline.json` khi dùng tùy chọn `--config`:

```json
{
  "host": "127.0.0.1",
  "port": 9000,
  "client_counts": [1, 10, 50],
  "repetitions": 3,
  "payload_bytes": 1024,
  "warmup_seconds": 5,
  "measurement_seconds": 20,
  "timeout_seconds": 5,
  "max_payload_bytes": 65536
}
```

- Chạy lần lượt 1, 10, 50 client; mỗi mức lặp 3 lần.
- Mỗi lượt có warm-up 5 giây và đo chính thức theo thời lượng cấu hình 20 giây.
- Các request warm-up không được đưa vào thống kê chính thức.
- Server không tự đọc file này. Giới hạn payload của server được đặt bằng `--max-payload-bytes`.
- Think time là khoảng nghỉ giữa các request, mặc định 0 giây.

## 4. Cấu trúc thư mục

```text
LTM_Group_13_research/
├── README.md
├── requirements.txt                   # Công cụ đo CPU và vẽ biểu đồ
├── requirements-dev.txt               # Thư viện kiểm thử
├── pyproject.toml                     # Cấu hình pytest
│
├── src/
│   ├── common/
│   │   └── protocol.py                # Framing, đọc/ghi và kiểm tra message
│   ├── server/
│   │   ├── __main__.py                # Khởi chạy server, đọc tham số dòng lệnh
│   │   └── app.py                     # TCP echo, timeout, disconnect, dọn kết nối
│   ├── load_generator/
│   │   ├── main.py                    # Khởi chạy GUI hoặc CLI
│   │   ├── generator.py               # Chạy bộ tạo tải
│   │   ├── benchmark.py               # CLI, cấu hình JSON và các lần lặp
│   │   ├── metrics.py                 # Tính chỉ số và xuất CSV
│   │   ├── client/
│   │   │   ├── tcp_client.py          # Kết nối, gửi request, kiểm tra echo, đo RTT
│   │   │   └── client_manager.py      # Điều phối nhiều client, tổng hợp kết quả
│   │   └── gui/
│   │       └── main_window.py         # Giao diện cấu hình và kết quả
│   └── experiments/
│       └── raw-data/
│           └── raw_metrics.csv        # CSV của lượt chạy thử hiện có
│
├── experiments/
│   ├── configs/
│   │   └── baseline.json              # Cấu hình các mức tải và số lần lặp
│   ├── raw-data/                      # Nơi lưu CSV khi chạy từ gốc project
│   ├── analysis/                      # Script và bảng tổng hợp từ CSV
│   │   ├── analyze.py
│   │   ├── summary.csv
│   │   └── by_client.csv
│   └── figures/                       # Biểu đồ RTT được tạo từ dữ liệu
│       ├── rtt_by_client.png
│       └── rtt_distribution.png
│
└── tests/
    ├── test_server.py                 # Echo, dữ liệu lỗi, timeout, disconnect
    └── test_load_generator.py         # Percentile, tích hợp client/server và CSV
```

## 5. Cài đặt và chạy 
### POWER SHELL – THIẾT LẬP MÔI TRƯỜNG ẢO 

python -m venv .venv 
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt 

### Server 
```powershell 
$env:PYTHONPATH = "src" 
python -m server --host 127.0.0.1 --port 9000 --timeout 5 --max-payload-bytes 65536 
``` 
Dừng server bằng Ctrl+C.
### Client GUI
```powershell 
$env:PYTHONPATH = "src" 
python -m load_generator.main 
```

### Phân tích CSV và vẽ biểu đồ

```powershell
python -m pip install matplotlib==3.10.8
python experiments/analysis/analyze.py
```

Kết quả mỗi lần chạy sẽ cập nhật các file sau:

| File | Nội dung |
|---|---|
| `experiments/analysis/summary.csv` | Tổng request, thành công/lỗi, tỷ lệ lỗi, RTT trung bình, min/max, p50/p95/p99 |
| `experiments/analysis/by_client.csv` | Các chỉ số tương tự, tổng hợp riêng từng client |
| `experiments/figures/rtt_by_client.png` | So sánh RTT trung bình và p95 của từng client |
| `experiments/figures/rtt_distribution.png` | Phân bố RTT và các đường đánh dấu trung bình/p95 |

Lưu kết quả riêng cho nhiều lượt bằng `--summary-dir` và `--figures-dir`:

```powershell
python experiments/analysis/analyze.py --input experiments/raw-data/raw_10c_rep1.csv --summary-dir experiments/analysis/10c_rep1 --figures-dir experiments/figures/10c_rep1
```

