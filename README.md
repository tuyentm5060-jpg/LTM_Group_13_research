# TCP Server Load Benchmark

Dự án khảo sát ảnh hưởng của số lượng client TCP đồng thời lên latency, throughput, error rate và mức sử dụng CPU của server echo asyncio.

## 1. Giới thiệu nhanh

Project này gồm 3 phần chính:

- server: lắng nghe TCP và echo lại payload
- load generator: tạo nhiều client đồng thời, đo latency/throughput/error/CPU
- analysis: tổng hợp dữ liệu và vẽ biểu đồ

## 2. Cấu trúc thư mục

```text
LTM_Group_13_research/
├── src/
│   ├── common/
│   │   └── protocol.py
│   ├── server/
│   │   ├── run_server.py
│   │   └── __init__.py
│   ├── load_generator/
│   │   ├── run_load.py
│   │   └── __init__.py
│   └── ...
├── experiments/
│   ├── run_all.py
│   ├── analysis/
│   │   └── analyze.py
│   ├── raw-data/
│   └── figures/
├── tests/
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── README.md
└── .venv/   (khi bạn tạo môi trường ảo)
```

## 3. Thiết lập môi trường

Windows PowerShell:

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Linux/macOS:

```bash
cd /path/to/LTM_Group_13_research
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## 4. Chạy server

Mở 1 terminal, ở thư mục project:

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
.\.venv\Scripts\Activate.ps1
python -m src.server.run_server --host 127.0.0.1 --port 9000 --timeout 5.0 --max-payload 65536
```

Server sẽ in ra dòng tương tự:

```text
SERVER_READY pid=12345 host=127.0.0.1 port=9000
```

Nhớ giữ terminal này mở để server chạy.

## 5. Chạy load test một lần

Mở terminal thứ 2, ở cùng thư mục project:

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
.\.venv\Scripts\Activate.ps1
python -m src.load_generator.run_load `
  --host 127.0.0.1 `
  --port 9000 `
  --clients 10 `
  --warmup 5 `
  --duration 20 `
  --payload-size 1024 `
  --server-pid 12345 `
  --run-id c10_r1 `
  --out-dir experiments/raw-data
```

Giải thích các tham số quan trọng:

- `--clients`: số client đồng thời
- `--warmup`: thời gian bỏ qua trước khi bắt đầu đo
- `--duration`: thời gian đo chính
- `--server-pid`: PID của process server để đo CPU
- `--out-dir`: folder lưu dữ liệu thô

## 6. Chạy toàn bộ benchmark nhanh

Nếu muốn chạy theo dạng tự động cho nhiều mức client và nhiều lần lặp:

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
.\.venv\Scripts\Activate.ps1
python experiments/run_all.py --clients 1 10 50 --repeats 3 --warmup 5 --duration 20 --out-dir experiments/raw-data
```

Script này sẽ:

- start server tự động
- chạy 3 lần cho mỗi mức client
- lưu raw-data vào `experiments/raw-data/`
- dừng server ở cuối

## 7. Tổng hợp và vẽ biểu đồ

Sau khi đã có dữ liệu JSON/CSV trong `experiments/raw-data/`, chạy:

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
.\.venv\Scripts\Activate.ps1
python experiments/analysis/analyze.py --in-dir experiments/raw-data --out-dir experiments/figures
```

Output sẽ bao gồm:

- `experiments/figures/latency_vs_clients.png`
- `experiments/figures/throughput_vs_clients.png`
- `experiments/figures/cpu_vs_clients.png`
- `experiments/raw-data/summary.csv`
- `experiments/raw-data/runs_detail.csv`

## 8. Chạy test nhanh

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
.\.venv\Scripts\Activate.ps1
pytest -q
```

## 9. Protocol

Dữ liệu được gửi theo format:

```text
[4-byte big-endian length][16-byte requestId][payload]
```

- `length` = `len(requestId) + len(payload)`
- server kiểm tra payload và request ID
- nếu payload quá lớn hoặc request sai format thì bỏ qua / đóng kết nối

## 10. File output chi tiết

Mỗi lần load generator chạy sẽ tạo các file như:

```text
raw_requests_<run_id>.csv
per_second_<run_id>.csv
cpu_<run_id>.csv
meta_<run_id>.json
```

Trong đó:

- `raw_requests_<run_id>.csv`: từng request, thời gian gửi/nhận, latency, status
- `per_second_<run_id>.csv`: số request và latency theo từng giây
- `cpu_<run_id>.csv`: sample CPU của server
- `meta_<run_id>.json`: summary của run hiện tại

## 11. Tóm tắt lệnh chạy nhanh nhất

Nếu bạn muốn chạy theo đúng workflow của project, chỉ cần:

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
.\.venv\Scripts\Activate.ps1
python experiments/run_all.py --clients 1 10 50 --repeats 3 --warmup 5 --duration 20 --out-dir experiments/raw-data
python experiments/analysis/analyze.py --in-dir experiments/raw-data --out-dir experiments/figures
```

## 12. Chạy cả project bằng 1 lệnh

File [run_all.ps1](run_all.ps1) đã được thêm để tự động:

- start server
- chạy benchmark cho 1, 10, 50 client
- lặp 3 lần mỗi mức
- tổng hợp và vẽ biểu đồ
- dừng server ở cuối

Cách dùng:

```powershell
cd D:\Workplace\Research\LTM_Group_13_research
.\run_all.ps1
```

Đây là cách chạy tiện nhất cho demo hoặc báo cáo.

