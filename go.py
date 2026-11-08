"""
📱 휴대폰 Termux에서 긴 파일 이름을 칠 필요 없이
딱 `python go.py` 만 치면 모든 실습을 번호로 골라 실행하는 통합 런처입니다!
"""

import os
import subprocess
import sys


def main():
    while True:
        os.system("clear" if os.name != "nt" else "cls")
        print("\033[1;96m====================================================\033[0m")
        print("\033[1;93m 📱 최동열 님의 Termux AI & 자동화 통합 실행기 (go.py)\033[0m")
        print("\033[1;96m====================================================\033[0m")
        print("  [1] 🏭 실습 1: 휴대용 스마트 PLC/4~20mA 필드 진단기")
        print("  [2] 📊 기본 데모: 펌프 기동 오버슈팅 배제 컬러 차트")
        print("  [3] 🔄 GitHub에서 최신 코드 자동 업데이트 받기 (git pull)")
        print("  [q] 종료")
        print("\033[1;96m====================================================\033[0m")
        sel = input("\n👉 실행할 번호(1~3)를 누르고 엔터를 치세요: ").strip().lower()

        if sel == "1":
            subprocess.run([sys.executable, "termux_1_field_tester.py"])
        elif sel == "2":
            subprocess.run([sys.executable, "termux_cli_demo.py"])
        elif sel == "3":
            subprocess.run(["git", "pull"])
            input("\n✅ 업데이트 완료! 엔터를 누르면 메뉴로 돌아갑니다...")
        elif sel == "q":
            break


if __name__ == "__main__":
    main()
