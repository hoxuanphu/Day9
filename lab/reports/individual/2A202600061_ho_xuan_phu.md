# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Hồ Xuân Phú  
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ  

---

## 1. Tôi phụ trách phần nào? (150 từ)

Trong Sprint 1, tôi chịu trách nhiệm chính về kiến trúc điều phối (orchestration) của toàn bộ hệ thống. Tôi đảm nhận việc thiết kế và lập trình các thành phần cốt lõi trong file `graph.py` để chuyển đổi pipeline RAG từ dạng nguyên khối sang dạng đồ thị (graph-based).

Cụ thể, tôi đã thực hiện:
- Định nghĩa `AgentState` để lưu trữ dữ liệu xuyên suốt đồ thị.
- Lập trình `supervisor_node` để phân tích query và ra quyết định routing.
- Xây dựng hàm `build_graph` để kết nối các node (Supervisor, Workers, Synthesis).

Công việc của tôi đóng vai trò là "bộ não" điều khiển. Tôi định nghĩa các contract dữ liệu để các Worker Owner biết được input/output cần tuân thủ. Toàn bộ các worker đều phụ thuộc vào entry point và logic điều hướng mà tôi xây dựng.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (200 từ)

**Quyết định:** Tôi chọn thực hiện điều phối thủ công (Manual Orchestration) bằng Python thay vì sử dụng thư viện `langgraph`.

**Lý do:**
Ban đầu, tôi dự định sử dụng `langgraph` để tận dụng các tính năng sẵn có. Tuy nhiên, môi trường ảo của nhóm chưa cài đặt đủ các thư viện phụ thuộc (`langchain-core`, `langgraph`), và việc cài đặt bổ sung gặp lỗi phân quyền trong lab. Để đảm bảo Sprint 1 hoàn thành đúng hạn và script có thể chạy ngay lập tức trên máy của các thành viên khác mà không cần cấu hình phức tạp, tôi đã tự viết hàm `run()` điều phối.

**Trade-off:**
Việc này giúp hệ thống đạt latency cực thấp (gần như 0ms cho phần điều hướng) và không có dependency bên thứ ba. Tuy nhiên, chúng tôi sẽ thiếu đi cơ chế "checkpointing" (ghi nhớ trạng thái) của LangGraph. Trong bối cảnh Lab hiện tại, sự ổn định và tốc độ được tôi ưu tiên hàng đầu.

**Bằng chứng:**
Hàm `build_graph()` trong `graph.py` hiện tại sử dụng logic rẽ nhánh trực tiếp:
```python
if route == "human_review":
    state = human_review_node(state)
    state = retrieval_worker_node(state)
elif route == "policy_tool_worker":
    state = policy_tool_worker_node(state)
    ....
```

---

## 3. Tôi đã sửa một lỗi gì? (200 từ)

**Lỗi:** `UnicodeDecodeError` khi indexing và `UnicodeEncodeError` khi in kết quả tiếng Việt.

**Symptom:**
Chương trình bị crash ngay lập tức khi đọc tài liệu gốc hoặc khi in các ký tự như "▶" hay chữ tiếng Việt có dấu. Điều này khiến nhóm không thể kiểm tra kết quả routing.

**Root cause:**
Console mặc định của Windows (máy lab) sử dụng bảng mã `CP1258`, không tương thích với định dạng `UTF-8` của các file tài liệu và chuỗi ký tự trong code.

**Cách sửa:**
Tôi đã sửa lại hàm `open()` trong script indexing để luôn dùng `encoding='utf-8'`. Đồng thời, trong `graph.py`, tôi đã reconfigure lại `sys.stdout` ngay từ đầu script.

**Bằng chứng:**
Đoạn code xử lý tại dòng 313 của `graph.py`:
```python
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```
Sau khi sửa, pipeline đã chạy thành công và in ra được toàn bộ log có tiếng Việt mà không gặp lỗi.

---

## 4. Tôi tự đánh giá đóng góp của mình (150 từ)

Tôi tự đánh giá mình đã hoàn thành tốt vai trò thiết kế khung xương cho hệ thống. Bộ logic routing dựa trên keyword mà tôi xây dựng hoạt động rất ổn định, phân loại chính xác các trường hợp SLA P1 và Refund.

Tuy nhiên, tôi vẫn còn điểm yếu là cấu trúc `AgentState` hơi rườm rà. Nếu có thêm thời gian, tôi sẽ tinh gọn các trường dữ liệu để Worker Owner dễ nắm bắt hơn. Nhóm phụ thuộc vào tôi ở phần khởi tạo luồng; nếu graph lỗi, toàn bộ worker sẽ không thể thực thi. Ngược lại, tôi phụ thuộc vào các bạn ở Sprint 2 để có dữ liệu thực tế thay vì các placeholder hiện tại.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (100 từ)

Tôi sẽ nâng cấp Supervisor lên **LLM-based classifier**. Hiện tại, keyword "khẩn cấp" có thể xuất hiện trong cả query IT Helpdesk và Policy Refund. Việc dùng LLM sẽ giúp Supervisor hiểu ngữ cảnh tốt hơn, tránh việc routing nhầm sang `retrieval` khi thực tế là một câu hỏi về `policy`. Điều này sẽ giúp cải thiện điểm số ở các câu hỏi "multi-hop" lắt léo mà trace hiện tại chưa xử lý triệt để.

---
*Lưu file này với tên: `reports/individual/ho_xuan_phu.md`*
