# Kết quả thực nghiệm TCP Server — TV4

## Nguồn dữ liệu và phương pháp
- Dữ liệu: `raw-data.zip` do nhóm cung cấp, 9 file `raw_{1,10,50}c_rep{1,2,3}.csv`; không tính `raw_metrics.csv` (lượt GUI cũ).
- Tổng **2,397,122 request**; tất cả OK, 1.024 byte payload, không có request ID trùng trong cùng lượt, không có giá trị RTT âm đối với bản ghi OK.
- Average RTT tính từ toàn bộ request thành công của mỗi lượt. **P95 sử dụng nearest-rank (ceil(0,95×n) - 1) trên dãy RTT đã sắp xếp**, giống hàm `calculate_percentile` trong `src/load_generator/metrics.py` của nhóm.
- Bảng mỗi mức tải là **trung bình số học của ba lượt**, không phải gộp trực tiếp mọi request.
- Throughput lấy từ chỉ số đã in trong ảnh Terminal cho mỗi lượt do CSV không chứa thời lượng thực tế với độ chính xác đầy đủ. `elapsed_from_terminal.csv` lưu thời lượng được in (làm tròn 3 chữ số) và thông lượng được in (2 chữ số), giúp truy vết nguồn; không nên tính lại throughput từ mốc timestamp đầu/cuối CSV.
- Mỗi lượt có warm-up 5 giây và thời gian đo mục tiêu 20 giây theo cấu hình benchmark của nhóm. CPU Server **chưa được ghi nhận** trong các file này.

## Bảng chính thức
| Số Client | Avg RTT (ms) | P95 (ms) | Throughput (req/s) | Error rate | Tổng request |
|---|---:|---:|---:|---:|---:|
| 1 | 0.0945 | 0.1296 | 8944.06 | 0.00% | 536,556 |
| 10 | 0.6316 | 0.7479 | 15356.64 | 0.00% | 924,266 |
| 50 | 3.1687 | 3.5815 | 15604.26 | 0.00% | 936,300 |


## Biểu đồ
- `scenario_latency.png`: Average RTT và P95 theo 1, 10, 50 Client, hiển thị dao động min–max của 3 lượt.
- `scenario_throughput.png`: Throughput theo 1, 10, 50 Client, hiển thị min–max của 3 lượt.
- `repeatability_rtt.png`: Biến động Average RTT theo 3 lượt lặp.

## Nhận xét khoa học
- Độ trễ tăng rõ: Average RTT tăng từ **0.094 ms** (1 Client) lên **3.169 ms** (50 Client). P95 cũng tăng từ **0.130 ms** lên **3.582 ms**.
- Throughput tăng từ **8,944 req/s** tại 1 Client lên **15,357 req/s** tại 10 Client; sau đó lên **15,604 req/s** tại 50 Client, tăng thêm khoảng **1.6%**. Xu hướng phù hợp với giả thuyết throughput bắt đầu bão hòa, nhưng chưa đủ chứng minh điểm bão hòa chính xác.
- Error rate bằng 0% ở cả 9 lượt. Điều này hỗ trợ giả thuyết tỷ lệ lỗi thấp trong môi trường loopback và mức tải đã thử.
- Chưa thể đánh giá giả thuyết CPU của Server khi chưa đo CPU riêng cho process Server.

## Những hạn chế cần báo cáo
1. Server và Load Generator cùng chạy trên một máy; loopback `127.0.0.1` không đại diện mạng LAN/Internet thực.
2. Chỉ ba mức tải và ba lượt lặp mỗi mức, chưa có phân tích sự bất định sâu.
3. CSV lưu RTT nhưng không chứa elapsed duration chính xác/CPU; thông lượng đã đối chiếu với ảnh Terminal; cần bổ sung metadata tự động trong các lần thực nghiệm tương lai.
4. Dữ liệu chỉ gồm các request hoàn tất trong pha đo; nếu có request đang chờ khi kết thúc cửa sổ đo, cần mô tả cách chương trình benchmark xử lý ở mức code.

## Thông số môi trường thực nghiệm (từ máy người chạy)
- CPU Intel Core i5-11400H, 6 lõi/12 luồng, 2.70 GHz; RAM 16.888.967.168 bytes (xấp xỉ 15.73 GiB), Windows 11 Home Single Language 10.0.22631; Python 3.12.0.
- TCP asyncio trên `127.0.0.1:9000`; payload 1024 byte; timeout 5 s; think time 0 s; 3 lần lặp; warm-up 5 s + đo 20 s.
- **CPU Usage (%)** của process Server: chưa có dữ liệu, không điền số giả định.

## Cách sử dụng trong báo cáo
- Đưa `scenario_summary.csv` vào bảng kết quả mục phân tích dữ liệu; đưa `scenario_latency.png` và `scenario_throughput.png` vào mục biểu đồ.
- Giữ `scenario_runs.csv` ở phụ lục để chứng minh tính lặp lại.
- Nếu công bố throughput trong bài, nêu nguồn là thông lượng do benchmark CLI báo cáo (đối chiếu từ screenshot, không suy diễn từ timestamp).
