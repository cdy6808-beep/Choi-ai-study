"""
===============================================================================
📱 휴대폰 Termux(터묵스) 전용 — 펌프 트렌드 & AI 이상치 터미널 분석기 (CLI 버전)
===============================================================================
휴대폰 Termux 환경(창이 없는 검은색 터미널 화면)에서도 화려한 컬러와
텍스트 그래프(ASCII Chart)로 펌프 오버슈팅 배제와 AI 이상치 탐지를 실행할 수 있는 파일입니다!

[휴대폰 Termux에서 실행 방법]
    python termux_cli_demo.py
===============================================================================
"""

import math
import random
import time

# 터미널 컬러 코드 (ANSI Escape)
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_GRAY = "\033[90m"


def run_termux_demo():
    print(f"{C_BOLD}{C_CYAN}============================================================{C_RESET}")
    print(f"{C_BOLD}{C_CYAN} 📱 [Termux 모바일 버전] 펌프 오버슈팅 배제 & AI 이상 감시기{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}============================================================{C_RESET}")
    print("시간(초) | 펌프 | 압력(bar) | 막대 그래프 (0 ~ 10 bar)      | AI 감시 판정")
    print("------------------------------------------------------------")

    rng = random.Random(42)
    start_holdoff = 4  # 기동 후 4초간 오버슈트 무시
    masked_count = 0
    alarm_count = 0

    for sec in range(1, 26):
        is_run = 1 if sec >= 4 else 0
        elapsed = sec - 4 if is_run else sec

        if not is_run:
            p = 0.0
        elif elapsed == 0:
            p = 9.1  # 기동 직후 오버슈트 피크!
        elif elapsed == 1:
            p = 9.5  # 기동 2초차 최대 오버슈트!
        elif elapsed == 2:
            p = 8.1  # 기동 3초차 오버슈트 수렴 중
        elif sec in (14, 15):
            p = 9.3  # 🚨 안정 운전 중 발생한 실제 배관 막힘 과압 고장!
        elif sec in (21, 22):
            p = 2.1  # 🚨 안정 운전 중 발생한 실제 공동현상(저압) 고장!
        else:
            p = 6.0 + rng.uniform(-0.15, 0.15)

        # 판정 로직
        raw_out = (p > 7.5 or p < 4.5) if is_run else (p > 0.5)
        is_masked = is_run and (elapsed < start_holdoff)

        bar_len = max(0, min(25, int(round(p * 2.5))))
        if raw_out and is_masked:
            masked_count += 1
            color = C_YELLOW
            status = "🛡️ 기동 오버슈트 (자동 배제)"
            bar_str = "█" * bar_len
        elif raw_out and not is_masked:
            alarm_count += 1
            color = C_RED
            status = "🚨 실제 설비 이상 경보!"
            bar_str = "▓" * bar_len
        else:
            color = C_GREEN if is_run else C_GRAY
            status = "✅ 정상 운전" if is_run else "⚪ 대기(STOP)"
            bar_str = "━" * bar_len

        run_str = f"{C_GREEN}RUN {C_RESET}" if is_run else f"{C_GRAY}STOP{C_RESET}"
        print(
            f"  {sec:02d}초   | {run_str} | {color}{p:6.2f} bar{C_RESET} | "
            f"{color}{bar_str:<25}{C_RESET} | {color}{status}{C_RESET}"
        )
        time.sleep(0.08)

    print("------------------------------------------------------------")
    print(f"{C_YELLOW}🛡️ 자동 배제된 기동 오버슈트 : {masked_count} 건 (가짜 알람 완벽 차단!){C_RESET}")
    print(f"{C_RED}🚨 최종 검출된 진짜 설비 고장: {alarm_count} 건 (14~15초 과압, 21~22초 저압){C_RESET}")
    print(f"{C_BOLD}{C_CYAN}============================================================{C_RESET}")


if __name__ == "__main__":
    run_termux_demo()
