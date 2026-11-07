"""
===============================================================================
📱 [실습 1 - 휴대폰 Termux용] 휴대용 스마트 필드 진단기 & 원격 제어 단말기
===============================================================================
스마트폰 Termux에서 실행하여 현장의 PLC/계측기/아두이노 데이터를 실시간 수집하고,
4~20mA 루프 무결성 진단, 펌프 기동/정지 오버슈팅 자동 배제 감시, 원격 제어를 수행합니다!

[사용 방법]
1. 단독 데모 모드 (설비 서버 없이 휴대폰 혼자서 현장 진단 + 원격 제어 실습):
    python termux_1_field_tester.py

2. PC 설비 서버와 실시간 Wi-Fi 연동 모드 (PC에서 pc_plc_field_server.py 실행 시):
    python termux_1_field_tester.py <PC의_IP주소>
===============================================================================
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.request

# ANSI 터미널 컬러
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_GRAY = "\033[90m"


class LocalPumpSim:
    """PC 서버 주소를 입력하지 않았을 때도 휴대폰 단독으로 모든 기능을 실습할 수 있는 내장 시뮬레이터."""

    def __init__(self):
        self.pump_run = 1
        self.elapsed_sec = 0
        self.fault_mode = None
        self.last_cmd = "휴대폰 내장 시뮬레이터 가동 중"

    def send_cmd(self, cmd: str):
        cmd = cmd.upper()
        if cmd == "RUN":
            self.pump_run = 1
            self.elapsed_sec = 0
            self.fault_mode = None
            self.last_cmd = "📱 [기동(RUN)] 명령 실행 -> 초기 오버슈트 자동 배제 작동!"
        elif cmd == "STOP":
            self.pump_run = 0
            self.elapsed_sec = 0
            self.fault_mode = None
            self.last_cmd = "📱 [정지(STOP)] 명령 실행 -> 수격 현상 자동 배제 작동!"
        elif cmd == "OVERPRESSURE":
            self.fault_mode = "OVERPRESSURE"
            self.last_cmd = "🚨 [과압 고장 테스트] 배관 막힘 9.25 bar 주입!"
        elif cmd == "CAVITATION":
            self.fault_mode = "CAVITATION"
            self.last_cmd = "🚨 [저압 고장 테스트] 공동현상 2.10 bar 주입!"
        elif cmd == "WIRE_BREAK":
            self.fault_mode = "WIRE_BREAK"
            self.last_cmd = "🚨 [4mA 루프 단선 테스트] 3.45 mA 단선 신호 주입!"
        elif cmd == "RESET":
            self.fault_mode = None
            self.last_cmd = "✅ [고장 해제] 정상 운전 상태로 복구 완료!"

    def poll(self) -> dict:
        self.elapsed_sec += 1
        if self.pump_run == 1:
            if self.elapsed_sec <= 4:
                overshoot = [3.1, 3.5, 2.1, 0.8][self.elapsed_sec - 1]
                p = 6.0 + overshoot
            else:
                p = 6.0 + random.uniform(-0.12, 0.12)
        else:
            if self.elapsed_sec <= 3:
                hammer = [-0.6, 1.2, 0.3][self.elapsed_sec - 1]
                p = hammer
            else:
                p = 0.0 + random.uniform(-0.02, 0.02)

        if self.fault_mode == "OVERPRESSURE":
            p = 9.25 + random.uniform(-0.05, 0.05)
        elif self.fault_mode == "CAVITATION":
            p = 2.10 + random.uniform(-0.05, 0.05)

        ma = 3.45 if self.fault_mode == "WIRE_BREAK" else round(4.0 + (p / 10.0) * 16.0, 2)
        p = round(p, 2)

        if self.pump_run == 1:
            raw_out = (p > 7.5) or (p < 4.5) or (ma < 4.0)
            is_masked = (self.elapsed_sec <= 5) and (self.fault_mode is None)
        else:
            raw_out = (p > 0.5) or (p < -0.25) or (ma < 4.0)
            is_masked = (self.elapsed_sec <= 3) and (self.fault_mode is None)

        if raw_out and is_masked:
            code = "MASKED"
            txt = f"🛡️ 기동/정지 과도구간 ({self.elapsed_sec}초차 오버슈트 자동배제)"
        elif raw_out and not is_masked:
            code = "ALARM"
            if ma < 4.0:
                txt = "🚨 [경보] 4~20mA 루프 단선 감지! (전류 < 4.0mA)"
            elif p > 7.5:
                txt = "🚨 [경보] 정격 운전 중 비정상 과압 발생!"
            else:
                txt = "🚨 [경보] 정격 운전 중 저압/공동현상 발생!"
        else:
            code = "NORMAL"
            txt = "✅ 정상 운전 중" if self.pump_run else "⚪ 펌프 대기(STOP)"

        return {
            "pump_run": self.pump_run,
            "elapsed_sec": self.elapsed_sec,
            "pressure_bar": p,
            "current_ma": ma,
            "status_code": code,
            "status_text": txt,
            "last_cmd": self.last_cmd,
        }


def fetch_from_pc(pc_ip: str, cmd: str | None = None) -> dict | None:
    path = f"/cmd/{cmd}" if cmd else "/status"
    url = f"http://{pc_ip}:5020{path}"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def render_handheld_screen(data: dict, mode_title: str, history: list[dict]):
    os.system("clear" if os.name != "nt" else "cls")
    p = data["pressure_bar"]
    ma = data["current_ma"]
    run = data["pump_run"]
    code = data["status_code"]

    if code == "ALARM":
        s_col = C_RED
    elif code == "MASKED":
        s_col = C_YELLOW
    else:
        s_col = C_GREEN if run else C_GRAY

    pct = max(0.0, min(100.0, ((ma - 4.0) / 16.0) * 100.0))
    bar_fill = max(0, min(24, int(round((p / 10.0) * 24))))
    gauge = "█" * bar_fill + "░" * (24 - bar_fill)

    print(f"{C_BOLD}{C_CYAN}╔════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║ 📱 SIEMENS/HART 휴대용 스마트 필드 진단기 (Termux v1.0)    ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╠════════════════════════════════════════════════════════════╣{C_RESET}")
    print(f"  📡 연결 모드 : {C_MAGENTA}{mode_title}{C_RESET}")
    print(f"  ⚙️ 펌프 상태 : {C_GREEN + '🟢 RUN (가동중)' if run else C_GRAY + '⚪ STOP (정지중)'}{C_RESET}  (상태 경과: {data['elapsed_sec']}초)")
    print(f"  🔌 루프 전류 : {s_col}{C_BOLD}{ma:6.2f} mA{C_RESET}   (4~20mA 스팬: {pct:5.1f}%)")
    print(f"  💧 토출 압력 : {s_col}{C_BOLD}{p:6.2f} bar{C_RESET}  [{s_col}{gauge}{C_RESET}]")
    print(f"  🤖 AI 판정   : {s_col}{C_BOLD}{data['status_text']}{C_RESET}")
    print(f"  💬 최근 명령 : {data['last_cmd']}")
    print(f"{C_BOLD}{C_CYAN}╠════════════════════════════════════════════════════════════╣{C_RESET}")
    print(f"  📊 {C_BOLD}최근 8초 실시간 트렌드 (1초 타임베이스){C_RESET}")
    for h in history[-8:]:
        hc = C_RED if h["status_code"] == "ALARM" else (C_YELLOW if h["status_code"] == "MASKED" else C_GREEN)
        b_len = max(0, min(20, int(round(h["pressure_bar"] * 2.0))))
        print(f"   [{h['elapsed_sec']:03d}s] {hc}{h['pressure_bar']:5.2f}bar ({h['current_ma']:5.2f}mA) {'━'*b_len:<20} {h['status_text'][:18]}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╚════════════════════════════════════════════════════════════╝{C_RESET}")


def main():
    pc_ip = sys.argv[1] if len(sys.argv) > 1 else None
    local_sim = LocalPumpSim()
    history: list[dict] = []

    while True:
        # 5초 연속 실시간 계측 스트리밍 후 원격 제어 메뉴 표시
        for _ in range(5):
            if pc_ip:
                d = fetch_from_pc(pc_ip)
                if d is None:
                    mode_title = f"⚠️ PC({pc_ip}) 연결 대기중 -> 내장 시뮬레이터로 자동 전환됨"
                    d = local_sim.poll()
                else:
                    mode_title = f"🟢 PC 현장 설비 서버({pc_ip}:5020) 실시간 Wi-Fi 직결됨"
            else:
                mode_title = "📱 휴대폰 단독 현장 진단 시뮬레이터 모드"
                d = local_sim.poll()

            history.append(d)
            render_handheld_screen(d, mode_title, history)
            time.sleep(0.8)

        print(f"\n{C_BOLD}{C_YELLOW}[🎛️ 휴대폰 원격 제어 & 고장 진단 메뉴]{C_RESET}")
        print("  [Enter] 5초 연속 감시 계속하기")
        print("  [1] 🟢 펌프 원격 기동 (RUN)  -> 초기 기동 오버슈트 자동 배제 확인!")
        print("  [2] ⚪ 펌프 원격 정지 (STOP) -> 정지 수격 현상 자동 배제 확인!")
        print("  [3] 🚨 배관 막힘 과압 고장 주입 (9.25 bar) -> AI 실제 경보 확인!")
        print("  [4] 🚨 4~20mA 신호선 단선 주입 (3.45 mA)  -> 루프 단선 경보 확인!")
        print("  [5] ✅ 고장 리셋 (정상 복귀)")
        print("  [q] 종료")
        choice = input(f"\n👉 번호를 선택하고 엔터를 누르세요: ").strip().lower()

        cmd_map = {
            "1": "RUN",
            "2": "STOP",
            "3": "OVERPRESSURE",
            "4": "WIRE_BREAK",
            "5": "RESET",
        }
        if choice == "q":
            print("진단기를 종료합니다.")
            break
        elif choice in cmd_map:
            cmd = cmd_map[choice]
            if pc_ip:
                res = fetch_from_pc(pc_ip, cmd)
                if res:
                    history.append(res)
            local_sim.send_cmd(cmd)


if __name__ == "__main__":
    main()
