# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Phạm Anh Quân
**Vai trò trong nhóm:** MCP Owner
**Ngày nộp:** 14/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py`
- Functions tôi implement: `list_tools`, `dispatch_tool`, `tool_get_ticket_info`, `tool_check_access_permission`, `tool_create_ticket`, `tool_search_kb` cùng với cấu trúc `TOOL_SCHEMAS`.

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Trong nhóm, tôi phụ trách xây dựng Mock MCP Server. Đây là cầu nối trung tâm để Worker (đặc biệt là Synthesis Node / Ticket Worker) có thể giao tiếp với các hệ thống backend giải lập (Hệ thống Ticket Jira nội bộ và Access Policy rule). Các Worker thay vì gọi API hard-code thì sẽ dùng tính năng function calling của LLM thông qua hàm `dispatch_tool` của tôi đề xuất. Hệ thống đóng vai trò cung cấp dữ kiện thời gian thực (real-time context) giúp các Agent trả lời Ticket.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
Tôi đã thiết kế logic dispatch dynamic qua `TOOL_REGISTRY` mapping function để xử lý các tool call như log thực tế trả xuống: `[MCP create_ticket] MOCK: IT-9883 | P1 | ...` đang hoạt động ổn định trên file `mcp_server.py`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi quyết định xây dựng Dispatch Layer và Tool Discovery dựa trên Dictionary mapping (`TOOL_REGISTRY`) và schema JSON nguyên bản thay vì dùng các SDK Class Object phức tạp trong Python.

**Lý do:**
Việc thiết kế bằng một function đơn giản `dispatch_tool(tool_name, tool_input)` giúp LLM (client) nhận và parse đối số dictionary tự nhiên nhất có thể. Trong điều kiện của môn học và lab giới hạn thời gian (Sprint 3), sử dụng in-memory Python Dict registry có tốc độ truy xuất siêu nhanh (đạt chuẩn ~ms cho hàm lookup), giảm overhead khi phải format OOP instance mà vẫn giữ nguyên được format Tool Call tiêu chuẩn của Model Context Protocol.

**Trade-off đã chấp nhận:**
Cách này đồng nghĩa với việc Server chưa phải là hệ thống mạng phân tán thật sự (Networked Server) mà chỉ là Mock Library in-memory của Python. Khi Production, cần phải wrap bằng giao thức HTTP/REST API hoặc stdio daemon.

**Bằng chứng từ trace/code:**
Logic của Dispatch Layer mà tôi tự cài đặt trong code:
```python
def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' không tồn tại. Available: {list(TOOL_REGISTRY.keys())}"}
    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        return tool_fn(**tool_input)
    except Exception as e:
        return {"error": f"Tool '{tool_name}' execution failed: {e}"}
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** TypeError do tham số đầu vào (arguments parameter) từ tool_input do LLM generated truyền xuống bị thiết sót field bắt buộc hoặc sai kiểu dữ liệu truyền vào hàm.

**Symptom (pipeline làm gì sai?):**
Trong quá trình test ban đầu, hàm `check_access_permission` cần tham số int là `access_level`, tuy nhiên Worker thỉnh thoảng hallucinate sinh ra chuỗi string `"3"`. Hoặc khi tra ticket, thiếu trường dẫn tới call logic Python bị thiếu biến `TypeError: missing 1 required positional argument...`. Error bung thẳng lên Exception Python làm toàn bộ node Agent crash ngang.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Lỗi nằm ở Dispatch Layer `mcp_server.py`. Trước đây tôi gọi trực tiếp `result = tool_fn(**tool_input)` mà bảo vệ thiếu logic Exception. Hành vi này không support self-healing workflow cho LLM agent.

**Cách sửa:**
Tôi đã thêm block catch `TypeError` bên trong `dispatch_tool()`. Thay vì crash, hệ thống trả về thông báo lỗi dạng dict/json kèm theo block schema chuẩn `TOOL_SCHEMAS[tool_name]["inputSchema"]`. Điều này giúp Model Language tự đọc được schema mà request lại function đúng format.

**Bằng chứng trước/sau:**
Đoạn catch exception tôi implement sau khi sửa:
```python
    except TypeError as e:
        # Tự động gửi scheme về lại cho LLM để fix args nhập lầm
        return {
            "error": f"Invalid input for tool '{tool_name}': {e}",
            "schema": TOOL_SCHEMAS[tool_name]["inputSchema"],
        }
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi thiết lập cấu trúc Schema (JSON schema cho LLM input/output format) rất logic, tuân thủ chặt syntax MCP, giúp quá trình mapping Function Calling vào LLM worker mượt mà.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Phần MOCK data (`MOCK_TICKETS` và `ACCESS_RULES`) hiện tại tôi thiết lập hơi tĩnh và hard-code trong RAM. Chưa có tính năng Write State (ví dụ tạo Ticket mới có lưu xuống JSON file) nên khởi động lại sẽ reset data.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_
Nếu schema không đúng hoặc handler bị bug, Worker phụ trách Ticket Tra Cứu và Policy Check (SOP) sẽ bị mù thông tin, do toàn bộ Database Access phụ thuộc vào API function của `mcp_server.py`.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_
Phụ thuộc vào Worker (LLM) Owner trong việc handle thông tin Output của hàm trả về hợp lý vào Prompt sinh câu trả lời tự nhiên. Ngoài quá trình truy xuất `tool_search_kb` tôi cũng cần Integration ChromaDB từ Retrieval Builder để thay thế Fallback mock data.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ nâng cấp (upgrade) file `mcp_server.py` bằng việc bọc nó qua FastAPI implementation (tức Option Advanced của Sprint 3). Việc thiết lập server HTTP thực tế chạy ở port `8000` với giao thức `REST/JSON` thay vì chạy local in-memory import module sẽ giúp hệ thống pipeline test được khả năng Fault Tolerance và Network Timeout — phản ánh thiết kế hạ tầng thực tế phân tán của Multi-Agent so với Monolithic Python scripts.

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*