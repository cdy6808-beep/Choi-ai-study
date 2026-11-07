"""
===============================================================================
🏭 [실습 1 - PC용] 현장 PLC / 아두이노(COM5) 계측 시뮬레이션 무선 서버
===============================================================================
이 프로그램을 PC에서 실행하면, 내 PC가 현장의 '스마트 펌프 제어반(PLC + 4~20mA 압력전송기)'이 됩니다!
같은 공유기(Wi-Fi)에 연결된 휴대폰 Termux에서 접속하여:
  1) 실시간 4~20mA 전류 / 압력(bar) / 펌프 상태(RUN/STOP)를 모니터링하고,
  2) 휴대폰 Termux에서 PC의 펌프를 원격으로 [기동(RUN)], [정지(STOP)], [고장 테스트(FAULT)] 할 수 있습니다!

[PC에서 실행 방법]
    python pc_plc_field_server.py
===============================================================================
"""

from __future__ import annotations

import json
import math
import random
import socket
import threading
import time
import tkinter as tk
from http.server import BaseHTTPRequestHandler, HTTPServer


def get_local_wifi_ip() -> str:
    """내 PC의 공유기(Wi-Fi/LAN) 내부 IP 주소를 자동으로 찾습니다."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class FieldEquipmentState:
    def __init__(self):
        self.pump_run = 1
        self.elapsed_sec = 0
        self.pressure_bar = 6.0
        self.current_ma = 13.6
        self.fault_mode = None      # None, "OVERPRESSURE", "CAVITATION", "WIRE_BREAK"
        self.last_cmd = "초기 가동 중 (정상)"
        self.connected_phones = 0
        self.start_holdoff = 5      # 기동 후 5초간 오버슈트 배제

    def step_1sec(self):
        self.elapsed_sec += 1
        if self.pump_run == 1:
            if self.elapsed_sec <= 4:
                # 펌프 기동 직후 초기 오버슈팅(Surge)!
                overshoot = [3.1, 3.5, 2.1, 0.8][self.elapsed_sec - 1]
                self.pressure_bar = 6.0 + overshoot
            else:
                self.pressure_bar = 6.0 + random.uniform(-0.12, 0.12)
        else:
            if self.elapsed_sec <= 3:
                # 펌프 정지 직후 수격 현상(Water Hammer)!
                hammer = [-0.6, 1.2, 0.3][self.elapsed_sec - 1]
                self.pressure_bar = hammer
            else:
                self.pressure_bar = 0.0 + random.uniform(-0.02, 0.02)

        # 고장 주입 시나리오 반영
        if self.fault_mode == "OVERPRESSURE":
            self.pressure_bar = 9.25 + random.uniform(-0.08, 0.08)
        elif self.fault_mode == "CAVITATION":
            self.pressure_bar = 2.10 + random.uniform(-0.1, 0.1)

        # 4~20mA 변환 (0~10 bar -> 4~20 mA)
        if self.fault_mode == "WIRE_BREAK":
            self.current_ma = 3.45  # 단선/언더레인지 (< 4mA)
        else:
            self.current_ma = round(4.0 + (self.pressure_bar / 10.0) * 16.0, 2)
        self.pressure_bar = round(self.pressure_bar, 2)

        # 오버슈트 배제 판정
        if self.pump_run == 1:
            raw_out = (self.pressure_bar > 7.5) or (self.pressure_bar < 4.5) or (self.current_ma < 4.0)
            is_masked = (self.elapsed_sec <= self.start_holdoff) and (self.fault_mode is None)
        else:
            raw_out = (self.pressure_bar > 0.5) or (self.pressure_bar < -0.25) or (self.current_ma < 4.0)
            is_masked = (self.elapsed_sec <= 3) and (self.fault_mode is None)

        if raw_out and is_masked:
            self.status_code = "MASKED"
            self.status_text = f"🛡️ 기동/정지 과도구간 ({self.elapsed_sec}초차 오버슈트 자동배제)"
        elif raw_out and not is_masked:
            self.status_code = "ALARM"
            if self.current_ma < 4.0:
                self.status_text = "🚨 루프 단선 경보! (전류 < 4.0mA)"
            elif self.pressure_bar > 7.5:
                self.status_text = "🚨 정격 운전 중 비정상 과압 경보!"
            else:
                self.status_text = "🚨 정격 운전 중 저압/공동현상 경보!"
        else:
            self.status_code = "NORMAL"
            self.status_text = "✅ 정상 운전 중" if self.pump_run else "⚪ 펌프 대기(STOP)"

    def to_dict(self) -> dict:
        return {
            "pump_run": self.pump_run,
            "elapsed_sec": self.elapsed_sec,
            "pressure_bar": self.pressure_bar,
            "current_ma": self.current_ma,
            "status_code": getattr(self, "status_code", "NORMAL"),
            "status_text": getattr(self, "status_text", "✅ 정상"),
            "last_cmd": self.last_cmd,
        }


STATE = FieldEquipmentState()


class PLCRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 콘솔 로그 깔끔하게 유지

    def do_GET(self):
        STATE.connected_phones += 1
        if self.path.startswith("/cmd/"):
            cmd = self.path.split("/cmd/")[-1].upper()
            if cmd == "RUN":
                STATE.pump_run = 1
                STATE.elapsed_sec = 0
                STATE.fault_mode = None
                STATE.last_cmd = "📱 휴대폰에서 [펌프 기동(RUN)] 명령 수신!"
            elif cmd == "STOP":
                STATE.pump_run = 0
                STATE.elapsed_sec = 0
                STATE.fault_mode = None
                STATE.last_cmd = "📱 휴대폰에서 [펌프 정지(STOP)] 명령 수신!"
            elif cmd == "OVERPRESSURE":
                STATE.fault_mode = "OVERPRESSURE"
                STATE.last_cmd = "📱 휴대폰에서 [과압 고장 테스트] 실행!"
            elif cmd == "CAVITATION":
                STATE.fault_mode = "CAVITATION"
                STATE.last_cmd = "📱 휴대폰에서 [저압 공동현상 테스트] 실행!"
            elif cmd == "WIRE_BREAK":
                STATE.fault_mode = "WIRE_BREAK"
                STATE.last_cmd = "📱 휴대폰에서 [4mA 루프 단선 테스트] 실행!"
            elif cmd == "RESET":
                STATE.fault_mode = None
                STATE.last_cmd = "📱 휴대폰에서 [고장 해제(정상 복귀)] 실행!"

        payload = json.dumps(STATE.to_dict(), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class PCFieldServerGUI(tk.Tk):
    def __init__(self, ip: str, port: int):
        super().__init__()
        self.ip = ip
        self.port = port
        self.title("🏭 [PC 현장 설비 서버] 휴대폰 Termux 무선 계측/제어 연동 중")
        self.geometry("680x440")
        self.configure(bg="#0f172a", padx=20, pady=16)

        tk.Label(
            self,
            text="📡 PC 현장 설비(PLC/아두이노) 무선 서버 가동 중!",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Malgun Gothic", 14, "bold"),
        ).pack(anchor="w")

        ip_box = tk.Frame(self, bg="#1e293b", padx=16, pady=12, highlightbackground="#f59e0b", highlightthickness=2)
        ip_box.pack(fill=tk.X, pady=12)
        tk.Label(
            ip_box,
            text=f"📱 휴대폰 Termux에서 아래 명령어를 입력하세요:",
            bg="#1e293b",
            fg="#cbd5e1",
            font=("Malgun Gothic", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            ip_box,
            text=f"python termux_1_field_tester.py {self.ip}",
            bg="#1e293b",
            fg="#fef08a",
            font=("Consolas", 14, "bold"),
            pady=4,
        ).pack(anchor="w")

        self.info_lbl = tk.Label(
            self,
            text="",
            bg="#090d16",
            fg="#4ade80",
            font=("Consolas", 11),
            justify=tk.LEFT,
            anchor="w",
            padx=16,
            pady=14,
        )
        self.info_lbl.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(self, bg="#0f172a")
        btn_row.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_row, text="🟢 PC에서 펌프 기동(RUN)", command=lambda: self._local_cmd("RUN"), bg="#059669", fg="#fff", relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="⚪ PC에서 펌프 정지(STOP)", command=lambda: self._local_cmd("STOP"), bg="#475569", fg="#fff", relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="🚨 과압 고장 발생시키기", command=lambda: self._local_cmd("OVERPRESSURE"), bg="#dc2626", fg="#fff", relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="✅ 고장 리셋", command=lambda: self._local_cmd("RESET"), bg="#2563eb", fg="#fff", relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=4)

        self._tick()

    def _local_cmd(self, c):
        if c == "RUN":
            STATE.pump_run = 1
            STATE.elapsed_sec = 0
            STATE.fault_mode = None
            STATE.last_cmd = "💻 PC에서 [펌프 기동(RUN)] 실행"
        elif c == "STOP":
            STATE.pump_run = 0
            STATE.elapsed_sec = 0
            STATE.fault_mode = None
            STATE.last_cmd = "💻 PC에서 [펌프 정지(STOP)] 실행"
        elif c == "OVERPRESSURE":
            STATE.fault_mode = "OVERPRESSURE"
            STATE.last_cmd = "💻 PC에서 [과압 고장] 주입! (휴대폰 Termux 경보 확인!)"
        elif c == "RESET":
            STATE.fault_mode = None
            STATE.last_cmd = "💻 PC에서 [정상 복귀]"

    def _tick(self):
        STATE.step_1sec()
        d = STATE.to_dict()
        txt = (
            f"• 서버 주소       : http://{self.ip}:{self.port}\n"
            f"• 펌프 운전 상태  : {'🟢 RUN (가동중)' if d['pump_run'] else '⚪ STOP (정지)'} (경과: {d['elapsed_sec']}초)\n"
            f"• 토출 압력 (PT)  : {d['pressure_bar']:.2f} bar\n"
            f"• 루프 전류 (mA)  : {d['current_ma']:.2f} mA  (정상: 4.00 ~ 20.00 mA)\n"
            f"• AI 감시 판정    : {d['status_text']}\n"
            f"• 최근 제어 명령  : {d['last_cmd']}"
        )
        self.info_lbl.configure(text=txt)
        self.after(1000, self._tick)


if __name__ == "__main__":
    wifi_ip = get_local_wifi_ip()
    port = 5020
    server = HTTPServer(("0.0.0.0", port), PLCRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"============================================================")
    print(f"📡 PC 현장 설비 서버가 시작되었습니다! (IP: {wifi_ip}, Port: {port})")
    print(f"📱 휴대폰 Termux에서 아래 명령어를 실행하세요:")
    print(f"   python termux_1_field_tester.py {wifi_ip}")
    print(f"============================================================")
    app = PCFieldServerGUI(wifi_ip, port)
    app.mainloop()
