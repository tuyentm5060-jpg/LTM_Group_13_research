# Kế hoạch nghiên cứu

## Câu hỏi và phạm vi

Số client đồng thời ảnh hưởng thế nào đến latency, throughput và CPU của TCP server?
Chỉ xây dựng một mô hình server, console app. Server skeleton dùng asyncio,
mỗi kết nối một coroutine. Không mở rộng sang so sánh nhiều mô hình.

## Protocol cần triển khai

- Đã triển khai: JSON UTF-8, tiền tố độ dài 4 byte unsigned big-endian.
- Request/response có requestId và payload; client kiểm tra cả hai.
- Đọc đủ header/body theo vòng lặp, không giả định một receive là một message.
- Xác định giới hạn frame và payload; xử lý EOF, timeout, dữ liệu sai.
- Payload 1024 byte phải được định nghĩa theo byte payload, tách khỏi overhead JSON.

## Đo lường cần triển khai

- Server và load generator chạy ở hai process; mỗi client logic giữ một kết nối riêng.
- Ghi thời gian bằng đồng hồ monotonic; loại warm-up khỏi thống kê.
- Ghi từng request: run_id, clients, request_id, latency_ms, success, error.
- Ghi summary: thời gian đo thực tế, số thành công/thất bại, latency trung bình,
  p95, throughput (thành công/giây), error rate (thất bại/tổng request), CPU server.
- Chốt cách tính percentile, request đang chờ khi hết giờ, chu kỳ và cách chuẩn hóa CPU.
- Ít nhất 1/10/50 client, mỗi mức 3 lần lặp, cùng payload và điều kiện đo.
- Script độc lập kiểm chứng ít nhất 3 trường hợp về số thành công, throughput hoặc error rate.
- Ít nhất 2 biểu đồ, thể hiện cả biến động giữa các lần chạy.

## Kiểm thử cần bổ sung

- Một client và nhiều client đồng thời.
- requestId/payload chính xác, message bị chia nhỏ hoặc gộp.
- Disconnect bất thường, timeout, dữ liệu sai, payload vượt giới hạn.
- Server vẫn phục vụ client khác sau một client lỗi.

## Hồ sơ

- Báo cáo PDF 4–6 trang nội dung chính: câu hỏi/phạm vi, lý thuyết, kiến trúc/protocol,
  phương pháp, kết quả, phân tích, giới hạn, kết luận, tài liệu tham khảo.
- Ghi cấu hình máy, môi trường, cách đo, số lần lặp và các giới hạn.
- Source, README tái lập thí nghiệm, configs, raw data, analysis, figures.
- Bảng đóng góp 5 thành viên; slide/video theo yêu cầu môn học.
- Ít nhất 3 nguồn, gồm tài liệu học phần và nguồn học thuật/kỹ thuật chính thức.
- Khai báo AI: Codex hỗ trợ đọc yêu cầu, tạo cấu trúc project, thiết lập môi trường,
  nhóm cần cập nhật khai báo khi sử dụng thêm. AI không là nguồn kỹ thuật chính.
