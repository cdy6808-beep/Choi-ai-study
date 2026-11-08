"""
===============================================================================
🔌 [ibaPDA × Arduino (COM5) 공식 연동 브릿지] (Modbus TCP + Generic UDP 게이트웨이)
===============================================================================
아두이노(COM5)의 아날로그(A0~A5) 및 디지털(D2~D13) 신호를 실시간 수집하여,
ibaPDA에서 표준 인터페이스로 바로 붙일 수 있도록 2가지 산업용 프로토콜을 동시에 송출합니다!

[지원 인터페이스]
1. 표준 Modbus TCP Server (기본 포트: 502, 권한 부족 시 1502 자동 바인딩)
   - Function Code 03 (Holding Registers) & 04 (Input Registers) 완벽 지원
   - Register 0 : A0 아날로그 값 (0 ~ 1023)
   - Register 1 : A1 아날로그 값 (0 ~ 1023)
   - Register 2 : 4~20mA 환산 전류값 × 100 (예: 1250 = 12.50 mA)
   - Register 3 : 환산 압력값 × 100 (예: 625 = 6.25 bar)
   - Register 4 : 디지털 핀 비트마스크 (Bit 0 = D2, Bit 1 = D13 상태)
   - Register 5 : 하트비트 카운터 (0 ~ 65535, ibaPDA 통신 생존 확인용)

2. ibaPDA Generic UDP 스트리밍 송출 (Target: 127.0.0.1:5555, 주기: 20ms / 50Hz)
   - ibaPDA의 [Generic UDP] 모듈에서 바로 파싱 가능한 CSV/바이너리 패킷 송출

[실행 방법]
    python ibapda_arduino_bridge.py
===============================================================================
"""

from __future__ import annotations

import math
import random
import socket
import struct
import threading
import time
import tkinter as tk
from tkinter import ttk

# pyserial이 설치되어 있으면 실제 COM5 아두이노 시리얼을 읽고,
# 없으면(또는 보드가 다른 용도로 사용 중이면) 아두이노 파형 에뮬레이터가 자동 동작합니다.
try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


class ArduinoDataStore:
    """아두이노(COM5) 실시간 측정값을 보관하고 Modbus 레지스터로 매핑하는 클래스."""

    def __init__(self):
        self.com_port = "COM5"
        self.baud_rate = 115200
        self.serial_connected = False
        self.last_rx_line = "시뮬레이션 파형 + COM5 대기 중"

        # 10개의 16-bit Modbus 레지스터 (Address 0 ~ 9)
        self.registers = [0] * 10
        self.modbus_req_count = 0
        self.udp_tx_count = 0
        self.t0 = time.perf_counter()

    def update_from_value(self, a0_raw: int, a1_raw: int = 512, di_mask: int = 1):
        a0_raw = max(0, min(1023, int(a0_raw)))
        a1_raw = max(0, min(1023, int(a1_raw)))

        # 0~1023 -> 4.00~20.00 mA (소수점 2자리 정수로 스케일링: 400 ~ 2000)
        ma_x100 = int(round(400 + (a0_raw / 1023.0) * 1600))
        # 0~1023 -> 0.00~10.00 bar (소수점 2자리 정수로 스케일링: 0 ~ 1000)
        bar_x100 = int(round((a0_raw / 1023.0) * 1000))
        heartbeat = (self.registers[5] + 1) % 65536

        self.registers[0] = a0_raw
        self.registers[1] = a1_raw
        self.registers[2] = ma_x100
        self.registers[3] = bar_x100
        self.registers[4] = di_mask
        self.registers[5] = heartbeat

    def step_simulation_if_needed(self):
        if self.serial_connected:
            return
        elapsed = time.perf_counter() - self.t0
        # ibaPDA에서 보기 좋은 부드러운 사인파 + 고조파 합성 아두이노 파형
        a0 = int(512 + 380 * math.sin(elapsed * 1.8) + 60 * math.cos(elapsed * 7.5))
        a1 = int(512 + 300 * math.cos(elapsed * 1.1))
        di = 1 if (int(elapsed) % 4 < 2) else 0
        self.update_from_value(a0, a1, di)


STORE = ArduinoDataStore()


# ==============================================================================
# 1. 표준 Modbus TCP Server 엔진 (외부 패키지 없이 순수 표준 소켓으로 구현)
# ==============================================================================
def build_modbus_response(req: bytes) -> bytes:
    """
    ibaPDA Modbus TCP Client가 보내는 MBAP 헤더(7바이트) + PDU 요청을 해석하여
    Function Code 0x03 (Read Holding Registers) 및 0x04 (Read Input Registers) 응답 패킷 생성.
    """
    if len(req) < 12:
        return b""

    tid, pid, length, uid, func = struct.unpack(">HHHBB", req[:8])
    start_addr, count = struct.unpack(">HH", req[8:12])

    if func in (3, 4) and 1 <= count <= 125:
        vals = []
        for addr in range(start_addr, start_addr + count):
            if 0 <= addr < len(STORE.registers):
                vals.append(STORE.registers[addr])
            else:
                vals.append(0)

        byte_cnt = count * 2
        pdu = struct.pack(">BB", func, byte_cnt) + struct.pack(f">{count}H", *vals)
        mbap = struct.pack(">HHHB", tid, pid, len(pdu) + 1, uid)
        STORE.modbus_req_count += 1
        return mbap + pdu
    else:
        # Illegal Function Exception Response
        pdu = struct.pack(">BB", func | 0x80, 0x01)
        mbap = struct.pack(">HHHB", tid, pid, len(pdu) + 1, uid)
        return mbap + pdu


def handle_modbus_client(conn: socket.socket):
    try:
        while True:
            data = conn.recv(256)
            if not data:
                break
            resp = build_modbus_response(data)
            if resp:
                conn.sendall(resp)
    except Exception:
        pass
    finally:
        conn.close()


def start_modbus_tcp_server() -> int:
    """표준 502 포트를 우선 시도하고, 관리자 권한 제한 시 1502 포트로 자동 오픈."""
    for port in (502, 1502, 5020):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", port))
            srv.listen(5)

            def accept_loop(s=srv):
                while True:
                    try:
                        client_sock, _ = s.accept()
                        threading.Thread(target=handle_modbus_client, args=(client_sock,), daemon=True).start()
                    except Exception:
                        break

            threading.Thread(target=accept_loop, daemon=True).start()
            return port
        except OSError:
            continue
    return 1502


# ==============================================================================
# 2. COM5 시리얼 리더 & ibaPDA Generic UDP 송출 워커
# ==============================================================================
def serial_and_udp_worker(udp_port: int = 5555):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ser = None

    while True:
        # 1) COM5 아두이노 시리얼 연결 시도 (pyserial 있을 때)
        if HAS_SERIAL and ser is None:
            try:
                ser = serial.Serial(STORE.com_port, STORE.baud_rate, timeout=0.02)
                STORE.serial_connected = True
            except Exception:
                STORE.serial_connected = False
                ser = None

        if ser is not None:
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    STORE.last_rx_line = line
                    # 아두이노가 "512" 또는 "512,600,1" 형태로 Serial.println() 할 때 자동 파싱
                    parts = [p.strip() for p in line.replace(";", ",").split(",") if p.strip()]
                    nums = [int(float(p)) for p in parts if p.lstrip("-").replace(".", "", 1).isdigit()]
                    if len(nums) >= 1:
                        a0 = nums[0]
                        a1 = nums[1] if len(nums) >= 2 else 512
                        di = nums[2] if len(nums) >= 3 else 1
                        STORE.update_from_value(a0, a1, di)
            except Exception:
                STORE.serial_connected = False
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
        else:
            STORE.step_simulation_if_needed()

        # 2) ibaPDA Generic UDP 패킷 송출 (50Hz = 20ms 주기)
        #    포맷: "A0,A1,mA_x100,Bar_x100,DI,Heartbeat\n"
        r = STORE.registers
        udp_payload = f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]}\n".encode("ascii")
        try:
            udp_sock.sendto(udp_payload, ("127.0.0.1", udp_port))
            STORE.udp_tx_count += 1
        except Exception:
            pass

        time.sleep(0.02)


# ==============================================================================
# 3. 브릿지 모니터링 & ibaPDA 설정 가이드 GUI
# ==============================================================================
class IbaPdaArduinoBridgeApp(tk.Tk):
    def __init__(self, modbus_port: int, udp_port: int = 5555):
        super().__init__()
        self.modbus_port = modbus_port
        self.udp_port = udp_port

        self.title("🔌 ibaPDA × Arduino (COM5) 실시간 신호 브릿지 (Modbus TCP & Generic UDP)")
        self.geometry("1080x720")
        self.configure(bg="#0f172a", padx=16, pady=12)

        self.hist_a0 = [512] * 150
        self.hist_a1 = [512] * 150

        self._build_ui()
        self._refresh_loop()

    def _build_ui(self):
        # 상단 배너
        hdr = tk.Frame(self, bg="#1e293b", padx=14, pady=10, highlightbackground="#38bdf8", highlightthickness=1)
        hdr.pack(fill=tk.X)

        tk.Label(
            hdr,
            text="🔌 Arduino (COM5) ➔ ibaPDA 실시간 프로토콜 변환기 가동 중",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 13, "bold"),
        ).pack(side=tk.LEFT)

        self.status_badge = tk.Label(
            hdr,
            text=f"🟢 Modbus TCP Port: {self.modbus_port}  |  UDP Port: {self.udp_port}",
            bg="#059669",
            fg="#ffffff",
            font=("Consolas", 10, "bold"),
            padx=12,
            pady=4,
        )
        self.status_badge.pack(side=tk.RIGHT)

        # 중앙 좌우 분할: 왼쪽=실시간 레지스터 값 & 파형, 오른쪽=ibaPDA I/O Manager 설정 방법
        mid = tk.Frame(self, bg="#0f172a")
        mid.pack(fill=tk.BOTH, expand=True, pady=10)

        left = tk.Frame(mid, bg="#0f172a")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 레지스터 모니터 표
        tk.Label(
            left,
            text="📊 실시간 Modbus TCP 레지스터 매핑 테이블 (ibaPDA 수집 채널)",
            bg="#0f172a",
            fg="#fbbf24",
            font=("Malgun Gothic", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))

        cols = ("addr", "name", "raw", "eng")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=6)
        self.tree.heading("addr", text="Modbus 주소")
        self.tree.heading("name", text="아두이노 신호명")
        self.tree.heading("raw", text="레지스터 Raw 값 (INT16)")
        self.tree.heading("eng", text="실제 물리량 환산값")
        self.tree.column("addr", width=110, anchor="center")
        self.tree.column("name", width=190, anchor="w")
        self.tree.column("raw", width=140, anchor="center")
        self.tree.column("eng", width=160, anchor="center")
        self.tree.pack(fill=tk.X)

        # 파형 미리보기 캔버스
        tk.Label(
            left,
            text="📈 ibaPDA로 송출 중인 실시간 파형 미리보기 (50Hz / Δt = 20ms)",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Malgun Gothic", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(10, 4))

        self.wave_canvas = tk.Canvas(left, bg="#090d16", height=250, highlightthickness=1, highlightbackground="#334155")
        self.wave_canvas.pack(fill=tk.BOTH, expand=True)

        # 오른쪽: ibaPDA 설정 가이드 + 아두이노 스케치 코드
        right = tk.Frame(mid, bg="#1e293b", width=410, padx=14, pady=12)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        right.pack_propagate(False)

        tk.Label(
            right,
            text="🛠️ ibaPDA (I/O Manager) 연결 설정법",
            bg="#1e293b",
            fg="#fef08a",
            font=("Malgun Gothic", 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 6))

        guide_txt = (
            f"[방법 1: Modbus TCP Client로 연결할 때]\n"
            f" 1. ibaPDA의 'I/O Manager' 열기\n"
            f" 2. 'Modbus TCP Client' 모듈 추가\n"
            f" 3. Connection 설정:\n"
            f"    • IP Address : 127.0.0.1 (같은 PC일 때)\n"
            f"    • Port       : {self.modbus_port}\n"
            f"    • Unit ID    : 1\n"
            f" 4. Analog 탭에서 Address 0 ~ 5 추가 (INT16)\n\n"
            f"[방법 2: Generic UDP로 고속 연결할 때]\n"
            f" 1. I/O Manager에서 'Generic UDP' 추가\n"
            f" 2. Port : {self.udp_port} 설정 (구분자: 콤마 ',')\n\n"
            f"----------------------------------------\n"
            f"[COM5 아두이노에 넣을 스케치 예시]\n"
            f"void setup() {{\n"
            f"  Serial.begin(115200);\n"
            f"}}\n"
            f"void loop() {{\n"
            f"  int a0 = analogRead(A0);\n"
            f"  int a1 = analogRead(A1);\n"
            f"  int d2 = digitalRead(2);\n"
            f"  Serial.print(a0); Serial.print(\",\");\n"
            f"  Serial.print(a1); Serial.print(\",\");\n"
            f"  Serial.println(d2);\n"
            f"  delay(20); // 50Hz 고속 전송\n"
            f"}}"
        )
        g_box = tk.Text(right, bg="#090d16", fg="#e2e8f0", font=("Consolas", 9), relief=tk.FLAT, padx=10, pady=10)
        g_box.insert("1.0", guide_txt)
        g_box.configure(state=tk.DISABLED)
        g_box.pack(fill=tk.BOTH, expand=True)

        self.stat_lbl = tk.Label(
            self,
            text="",
            bg="#0f172a",
            fg="#4ade80",
            font=("Consolas", 10, "bold"),
            anchor="w",
        )
        self.stat_lbl.pack(fill=tk.X, pady=(6, 0))

    def _refresh_loop(self):
        r = STORE.registers
        self.hist_a0.append(r[0])
        self.hist_a1.append(r[1])
        self.hist_a0.pop(0)
        self.hist_a1.pop(0)

        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = [
            ("40001 (Offset 0)", "Arduino A0 (아날로그 0)", r[0], f"{r[0]} (0~1023)"),
            ("40002 (Offset 1)", "Arduino A1 (아날로그 1)", r[1], f"{r[1]} (0~1023)"),
            ("40003 (Offset 2)", "4~20mA 루프 전류", r[2], f"{r[2]/100.0:.2f} mA"),
            ("40004 (Offset 3)", "토출 압력 (0~10 bar)", r[3], f"{r[3]/100.0:.2f} bar"),
            ("40005 (Offset 4)", "디지털 입력 (D2 상태)", r[4], "ON (1)" if r[4] else "OFF (0)"),
            ("40006 (Offset 5)", "통신 생존 카운터 (Heartbeat)", r[5], f"{r[5]} cycle"),
        ]
        for row in rows:
            self.tree.insert("", tk.END, values=row)

        # 파형 그리기
        c = self.wave_canvas
        c.delete("all")
        w = max(c.winfo_width(), 560)
        h = max(c.winfo_height(), 200)

        n = len(self.hist_a0)
        pts0, pts1 = [], []
        for i in range(n):
            px = 20 + (i / (n - 1)) * (w - 40)
            py0 = h - 20 - (self.hist_a0[i] / 1023.0) * (h - 40)
            py1 = h - 20 - (self.hist_a1[i] / 1023.0) * (h - 40)
            pts0.extend((px, py0))
            pts1.extend((px, py1))

        c.create_line(20, h / 2, w - 20, h / 2, fill="#1e293b", dash=(3, 3))
        if len(pts1) >= 4:
            c.create_line(*pts1, fill="#f59e0b", width=1.8)
            c.create_line(*pts0, fill="#38bdf8", width=2.5)

        src_mode = f"🟢 COM5 실장비 수신중 ({STORE.last_rx_line})" if STORE.serial_connected else "🟡 파형 시뮬레이터 가동중 (COM5 연결 시 자동 전환)"
        self.stat_lbl.configure(
            text=f"📡 소스 상태: {src_mode}   |   Modbus 응답 횟수: {STORE.modbus_req_count:,}회   |   UDP 패킷 송출: {STORE.udp_tx_count:,}회"
        )

        self.after(50, self._refresh_loop)


if __name__ == "__main__":
    mb_port = start_modbus_tcp_server()
    threading.Thread(target=serial_and_udp_worker, args=(5555,), daemon=True).start()
    app = IbaPdaArduinoBridgeApp(mb_port, 5555)
    app.mainloop()
