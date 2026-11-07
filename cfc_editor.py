"""
쉬운 아두이노 CFC 스튜디오 (Kids-Friendly Siemens CFC Visual Coding & COM5 Uploader)
=============================================================================
초등학생도 레고 블록처럼 꺼내서 선만 연결하면 아두이노(COM5)로 바로 업로드되는
지멘스 SIMATIC CFC 스타일 그래픽 코딩 프로그램입니다.

주요 특징:
1. 초등학생 눈높이의 친절한 한글 블록 (버튼, 센서, 깜빡이, 타이머, 그리고/또는, LED, 부저, 서보모터 등)
2. 부드러운 둥근 블록 캔버스 + 마우스 드래그 직각(Manhattan) 자동 배선 + 핀 수치 클릭 즉시 변경
3. 실시간 시뮬레이션 모드: 아두이노 없이도 화면에서 버튼을 눌러보며 전기가 흐르는(초록색 선) 것을 눈으로 확인!
4. 원클릭 아두이노(COM5) 업로드: arduino-cli / Arduino IDE /avr-gcc 자동 감지 및 원클릭 컴파일·업로드 지원
"""

import json
import os
import shutil
import subprocess
import threading
import urllib.request
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# ==============================================================================
# 1. 초등학생도 한눈에 이해하는 쉬운 CFC 블록 사전
# ==============================================================================
# 핀 형식: (핀코드, 화면표시이름, 타입, 기본값, 설명)

EASY_BLOCKS = {
    "1. 입력 (센서와 버튼)": {
        "BUTTON": {
            "title": "🔘 버튼 스위치",
            "sub": "디지털 입력 (DI)",
            "color": "#0284c7",
            "bg": "#e0f2fe",
            "ins": [("PIN", "아두이노 핀", "pin", "2")],
            "outs": [("Q", "신호(켜짐/꺼짐)", "bool")],
            "help": "버튼을 누르면 1(켜짐), 떼면 0(꺼짐) 신호가 나와요.",
        },
        "SENSOR_LIGHT": {
            "title": "☀️ 빛/가변저항 센서",
            "sub": "아날로그 입력 (0~1023)",
            "color": "#0891b2",
            "bg": "#cffafe",
            "ins": [("PIN", "아날로그 핀(A)", "apin", "0")],
            "outs": [("VAL", "측정값(0~1023)", "int")],
            "help": "밝기나 다이얼 값을 0부터 1023까지의 숫자로 읽어와요.",
        },
        "NUMBER": {
            "title": "🔢 숫자 상수",
            "sub": "고정된 숫자/스위치",
            "color": "#4f46e5",
            "bg": "#e0e7ff",
            "ins": [("VAL", "숫자 값", "int", "1")],
            "outs": [("OUT", "출력 값", "int")],
            "help": "원하는 숫자(예: 1, 0, 1000)를 내보내는 블록이에요.",
        },
    },
    "2. 생각하기 (논리와 판단)": {
        "AND": {
            "title": "🤝 둘 다 켜지면 (AND)",
            "sub": "논리곱 블록",
            "color": "#2563eb",
            "bg": "#dbeafe",
            "ins": [("IN1", "입력 1", "bool", "0"), ("IN2", "입력 2", "bool", "0")],
            "outs": [("Q", "결과", "bool")],
            "help": "입력 1과 입력 2가 모두 켜졌을 때만 결과가 켜져요!",
        },
        "OR": {
            "title": "🙌 하나만 켜져도 (OR)",
            "sub": "논리합 블록",
            "color": "#2563eb",
            "bg": "#dbeafe",
            "ins": [("IN1", "입력 1", "bool", "0"), ("IN2", "입력 2", "bool", "0")],
            "outs": [("Q", "결과", "bool")],
            "help": "입력 1이나 입력 2 중 하나라도 켜지면 결과가 켜져요!",
        },
        "NOT": {
            "title": "🔄 청개구리 반대로 (NOT)",
            "sub": "반전 블록",
            "color": "#1d4ed8",
            "bg": "#dbeafe",
            "ins": [("IN", "입력", "bool", "0")],
            "outs": [("Q", "반대 결과", "bool")],
            "help": "켜짐(1)이 들어오면 꺼짐(0)으로, 꺼짐(0)이 들어오면 켜짐(1)으로 바꿔요.",
        },
        "LATCH": {
            "title": "📌 한번 누르면 계속 켜짐",
            "sub": "RS 기억 스위치",
            "color": "#7c3aed",
            "bg": "#ede9fe",
            "ins": [("S", "켜기(Set)", "bool", "0"), ("R", "끄기(Reset)", "bool", "0")],
            "outs": [("Q", "기억 상태", "bool")],
            "help": "'켜기'에 신호가 오면 손을 떼도 계속 켜져 있고, '끄기'를 누르면 꺼져요.",
        },
        "COMPARE": {
            "title": "⚖️ 누가 더 클까? (비교)",
            "sub": "값 > 기준값",
            "color": "#9333ea",
            "bg": "#f3e8ff",
            "ins": [("VAL", "비교할 값", "int", "0"), ("REF", "기준 숫자", "int", "500")],
            "outs": [("Q", "더 크면 켜짐", "bool")],
            "help": "센서 값이 기준 숫자보다 크면 1(켜짐) 신호를 내보내요.",
        },
    },
    "3. 시간과 횟수 (타이머/카운터)": {
        "BLINK": {
            "title": "✨ 깜빡깜빡 신호기",
            "sub": "주기적 펄스 (PULSE)",
            "color": "#059669",
            "bg": "#d1fae5",
            "ins": [("EN", "작동 스위치", "bool", "1"), ("MS", "깜빡임 시간(ms)", "int", "500")],
            "outs": [("Q", "깜빡 신호", "bool")],
            "help": "작동 스위치가 켜지면 정해진 시간(1000=1초)마다 켜졌다 꺼졌다 반복해요.",
        },
        "TIMER_ON": {
            "title": "⏱️ 기다렸다 켜기 (TON)",
            "sub": "켜짐 지연 타이머",
            "color": "#0d9488",
            "bg": "#ccfbf1",
            "ins": [("IN", "시작 신호", "bool", "0"), ("MS", "기다릴 시간(ms)", "int", "1000")],
            "outs": [("Q", "완료 신호", "bool")],
            "help": "신호가 들어오고 정해진 시간(예: 1000=1초) 동안 유지되면 켜져요.",
        },
        "COUNTER": {
            "title": "🔢 횟수 세기 (CTU)",
            "sub": "카운터 블록",
            "color": "#0f766e",
            "bg": "#ccfbf1",
            "ins": [
                ("CU", "숫자 올리기", "bool", "0"),
                ("R", "0으로 초기화", "bool", "0"),
                ("GOAL", "목표 횟수", "int", "5"),
            ],
            "outs": [("Q", "목표 달성!", "bool"), ("CV", "현재 횟수", "int")],
            "help": "버튼을 누를 때마다 횟수를 세고, 목표 횟수에 도달하면 완료 신호가 켜져요.",
        },
    },
    "4. 출력 (불빛과 움직임)": {
        "LED": {
            "title": "💡 LED 전구 켜기",
            "sub": "디지털 출력 (DO)",
            "color": "#e11d48",
            "bg": "#ffe4e6",
            "ins": [("IN", "켜기 신호", "bool", "0"), ("PIN", "아두이노 핀", "pin", "13")],
            "outs": [("Q", "현재 상태", "bool")],
            "help": "켜기 신호에 1이 들어오면 아두이노 핀에 연결된 LED에 불이 들어와요! (13번은 보드 내장 LED)",
        },
        "PWM_LED": {
            "title": "🌈 밝기/속도 조절 (PWM)",
            "sub": "아날로그 출력 (0~255)",
            "color": "#db2777",
            "bg": "#fce7f3",
            "ins": [("VAL", "밝기/속도(0~255)", "int", "128"), ("PIN", "PWM 핀(~)", "pin", "9")],
            "outs": [],
            "help": "0부터 255 사이의 숫자로 LED 밝기나 모터 속도를 부드럽게 조절해요.",
        },
        "BUZZER": {
            "title": "🎵 삐- 소리 부저",
            "sub": "멜로디 출력 (tone)",
            "color": "#ea580c",
            "bg": "#ffedd5",
            "ins": [
                ("EN", "소리 켜기", "bool", "0"),
                ("FREQ", "음높이(Hz)", "int", "523"),
                ("PIN", "아두이노 핀", "pin", "8"),
            ],
            "outs": [],
            "help": "소리 켜기가 1이면 부저에서 소리가 나요! (도=523, 레=587, 미=659, 솔=784)",
        },
        "SERVO": {
            "title": "🦾 서보 모터 각도",
            "sub": "0도 ~ 180도 회전",
            "color": "#d97706",
            "bg": "#fef3c7",
            "ins": [("ANGLE", "회전 각도(0~180)", "int", "90"), ("PIN", "서보 핀", "pin", "10")],
            "outs": [],
            "help": "서보 모터의 팔을 0도에서 180도 사이 원하는 각도로 움직여요.",
        },
    },
}

FLAT_BLOCKS = {}
for _cat, _items in EASY_BLOCKS.items():
    for _k, _v in _items.items():
        FLAT_BLOCKS[_k] = _v

# 초등학생을 위한 프리셋 예제들
PRESET_EXAMPLES = {
    "예제 1: [기초] 0.5초마다 깜빡이는 보드 LED (13번 핀)": "blink",
    "예제 2: [버튼] 2번 핀 버튼을 누르면 LED 켜고 부저 울리기": "button_led",
    "예제 3: [기억+타이머] 한번 누르면 계속 깜빡이고 5번 깜빡이면 부저": "smart_counter",
}


# ==============================================================================
# 2. 메인 그래픽 에디터 클래스
# ==============================================================================

class KidsArduinoCFCApp(tk.Tk):
    BLOCK_W = 195
    HEADER_H = 42
    PIN_STEP = 28
    PIN_R = 7

    def __init__(self):
        super().__init__()
        self.title("🎨 지멘스 CFC 스타일 — 어린이 아두이노 그림 코딩 스튜디오 (COM5 직결)")
        self.geometry("1460x880")
        self.minsize(1150, 700)
        self.configure(bg="#0f172a")

        # 데이터 모델
        self.blocks = {}       # bid -> dict
        self.wires = []        # list of {src_id, src_pin, dst_id, dst_pin}
        self.next_id = 1

        # 마우스 상호작용 상태
        self.selected_block = None
        self.selected_wire = None
        self.drag_info = None      # (bid, dx, dy)
        self.wiring_from = None    # (bid, kind, pin_name, x, y)
        self.mouse_pos = (0, 0)
        self.hover_pin = None      # (bid, kind, pin_name)
        self.hover_badge = None    # (bid, pin_name)

        # 하드웨어 설정 (기본 COM5, Arduino Uno)
        self.port_var = tk.StringVar(value="COM5")
        self.board_var = tk.StringVar(value="Arduino Uno (arduino:avr:uno)")

        # 시뮬레이션 상태
        self.sim_active = False
        self.sim_ms = 0
        self.sim_mem = {}

        self._build_top_bar()
        self._build_main_workspace()
        self._build_status_bar()

        self.bind("<Delete>", lambda e: self.delete_selected())
        self.bind("<BackSpace>", lambda e: self.delete_selected())
        self.bind("<Escape>", lambda e: self._cancel_wire())

        # 첫 실행 시 가장 직관적인 깜빡이+버튼 예제 로드
        self.load_example("blink")
        self.after(200, self.refresh_com_ports)

    # --------------------------------------------------------------------------
    # 상단 툴바 (아두이노 COM5 업로드 & 예제 선택)
    # --------------------------------------------------------------------------
    def _build_top_bar(self):
        top = tk.Frame(self, bg="#1e293b", height=60, padx=14, pady=8)
        top.pack(side=tk.TOP, fill=tk.X)

        # 로고 타이틀
        title_box = tk.Frame(top, bg="#1e293b")
        title_box.pack(side=tk.LEFT, padx=(0, 16))
        tk.Label(
            title_box,
            text="⚡ 아두이노 CFC 블록 스튜디오",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="블록을 꺼내고 점과 점을 선으로 이어보세요!",
            bg="#1e293b",
            fg="#94a3b8",
            font=("Malgun Gothic", 9),
        ).pack(anchor="w")

        # 예제 불러오기 드롭다운
        ex_frame = tk.Frame(top, bg="#334155", padx=8, pady=4)
        ex_frame.pack(side=tk.LEFT, padx=6)
        tk.Label(ex_frame, text="📚 따라하기 예제:", bg="#334155", fg="#f8fafc", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.example_cb = ttk.Combobox(
            ex_frame,
            values=list(PRESET_EXAMPLES.keys()),
            width=40,
            state="readonly",
            font=("Malgun Gothic", 9),
        )
        self.example_cb.current(0)
        self.example_cb.pack(side=tk.LEFT)
        self.example_cb.bind("<<ComboboxSelected>>", self._on_example_selected)

        # 지우기 / 삭제 버튼
        self._create_btn(top, "🗑️ 선택 삭제", self.delete_selected, "#dc2626")
        self._create_btn(top, "📄 새 도화지", self.clear_all, "#475569")

        # 시뮬레이션 버튼
        self.sim_btn = self._create_btn(
            top, "▶️ 화면에서 미리 작동해보기", self.toggle_simulation, "#059669"
        )

        # 우측: 아두이노 COM5 업로드 영역
        hw_frame = tk.Frame(top, bg="#0f172a", padx=10, pady=5, highlightbackground="#38bdf8", highlightthickness=1)
        hw_frame.pack(side=tk.RIGHT, padx=4)

        tk.Label(hw_frame, text="🔌 포트:", bg="#0f172a", fg="#38bdf8", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT)
        self.port_cb = ttk.Combobox(hw_frame, textvariable=self.port_var, values=["COM5", "COM3", "COM4", "COM6"], width=8, font=("Consolas", 10, "bold"))
        self.port_cb.pack(side=tk.LEFT, padx=4)

        tk.Button(
            hw_frame,
            text="🔄",
            command=self.refresh_com_ports,
            bg="#1e293b",
            fg="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(hw_frame, text="보드:", bg="#0f172a", fg="#cbd5e1", font=("Malgun Gothic", 9)).pack(side=tk.LEFT)
        self.board_cb = ttk.Combobox(
            hw_frame,
            textvariable=self.board_var,
            values=[
                "Arduino Uno (arduino:avr:uno)",
                "Arduino Nano (arduino:avr:nano)",
                "Arduino Mega (arduino:avr:mega)",
            ],
            width=24,
            state="readonly",
            font=("Consolas", 9),
        )
        self.board_cb.pack(side=tk.LEFT, padx=6)

        self.upload_btn = tk.Button(
            hw_frame,
            text="🚀 아두이노(COM5)로 바로 업로드!",
            command=self.upload_to_arduino,
            bg="#f59e0b",
            fg="#0f172a",
            activebackground="#fbbf24",
            activeforeground="#000000",
            relief=tk.FLAT,
            font=("Malgun Gothic", 10, "bold"),
            padx=14,
            pady=4,
            cursor="hand2",
        )
        self.upload_btn.pack(side=tk.LEFT, padx=(6, 0))

    def _create_btn(self, parent, text, cmd, bg):
        btn = tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg="#ffffff",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 9, "bold"),
            padx=11,
            pady=6,
            cursor="hand2",
        )
        btn.pack(side=tk.LEFT, padx=4)
        return btn

    # --------------------------------------------------------------------------
    # 메인 3단 화면 (왼쪽: 블록 상자 / 가운데: 고급 CFC 캔버스 / 오른쪽: 아두이노 코드 & 로그)
    # --------------------------------------------------------------------------
    def _build_main_workspace(self):
        pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg="#0f172a", sashwidth=5, bd=0)
        pane.pack(fill=tk.BOTH, expand=True)

        # 1. 왼쪽: 쉬운 블록 상자
        left = tk.Frame(pane, bg="#1e293b", width=265)
        self._build_block_toolbox(left)
        pane.add(left, minsize=245)

        # 2. 가운데: 고급 CFC 그래픽 캔버스
        center = tk.Frame(pane, bg="#f8fafc")
        self._build_cfc_canvas(center)
        pane.add(center, minsize=620)

        # 3. 오른쪽: 친절한 설명 + 자동 생성 아두이노 코드 + 업로드 창
        right = tk.Frame(pane, bg="#0f172a", width=390)
        self._build_right_panel(right)
        pane.add(right, minsize=320)

    def _build_block_toolbox(self, parent):
        tk.Label(
            parent,
            text="🧰 블록 상자 (클릭해서 꺼내세요)",
            bg="#0f172a",
            fg="#fbbf24",
            font=("Malgun Gothic", 10, "bold"),
            pady=9,
        ).pack(fill=tk.X)

        c = tk.Canvas(parent, bg="#1e293b", highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=c.yview)
        inner = tk.Frame(c, bg="#1e293b")

        inner.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        c.create_window((0, 0), window=inner, anchor="nw", width=248)
        c.configure(yscrollcommand=sb.set)

        c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for cat_title, items in EASY_BLOCKS.items():
            tk.Label(
                inner,
                text=cat_title,
                bg="#334155",
                fg="#38bdf8",
                anchor="w",
                padx=10,
                pady=5,
                font=("Malgun Gothic", 9, "bold"),
            ).pack(fill=tk.X, pady=(8, 3), padx=4)

            for btype, bdef in items.items():
                card = tk.Frame(inner, bg="#0f172a", padx=4, pady=3)
                card.pack(fill=tk.X, padx=6, pady=2)

                btn = tk.Button(
                    card,
                    text=f"{bdef['title']}   ➕",
                    bg=bdef["color"],
                    fg="#ffffff",
                    activebackground="#38bdf8",
                    activeforeground="#0f172a",
                    relief=tk.FLAT,
                    anchor="w",
                    padx=10,
                    pady=5,
                    font=("Malgun Gothic", 9, "bold"),
                    cursor="hand2",
                    command=lambda t=btype: self.spawn_block(t),
                )
                btn.pack(fill=tk.X)

                tk.Label(
                    card,
                    text=bdef["help"],
                    bg="#0f172a",
                    fg="#94a3b8",
                    anchor="w",
                    justify=tk.LEFT,
                    wraplength=225,
                    font=("Malgun Gothic", 8),
                    pady=2,
                ).pack(fill=tk.X, padx=4)

    def _build_cfc_canvas(self, parent):
        # 상단 안내 배너
        self.guide_banner = tk.Label(
            parent,
            text="💡 사용법: ① 왼쪽 블록을 클릭해 꺼내세요  ② 블록의 오른쪽 파란 점(출력)을 드래그해서 다른 블록의 왼쪽 점(입력)에 연결하세요  ③ 회색 숫자 상자를 클릭하면 핀 번호나 시간을 바꿀 수 있어요!",
            bg="#e0f2fe",
            fg="#0369a1",
            font=("Malgun Gothic", 9, "bold"),
            pady=7,
            padx=10,
            anchor="w",
        )
        self.guide_banner.pack(side=tk.TOP, fill=tk.X)

        self.canvas = tk.Canvas(parent, bg="#f8fafc", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

    def _build_right_panel(self, parent):
        # 1. 선택된 블록 쉬운 설정창
        prop_box = tk.Frame(parent, bg="#1e293b", padx=12, pady=10)
        prop_box.pack(fill=tk.X, padx=6, pady=6)

        tk.Label(
            prop_box,
            text="⚙️ 선택한 블록 설정",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X)

        self.inspector_body = tk.Frame(prop_box, bg="#1e293b", pady=6)
        self.inspector_body.pack(fill=tk.X)

        # 2. 실시간 생성된 아두이노 코드 (.ino)
        code_hdr = tk.Frame(parent, bg="#0f172a", padx=10, pady=4)
        code_hdr.pack(fill=tk.X)
        tk.Label(
            code_hdr,
            text="💻 자동 번역된 아두이노 코드 (.ino)",
            bg="#0f172a",
            fg="#fbbf24",
            font=("Malgun Gothic", 10, "bold"),
        ).pack(side=tk.LEFT)

        tk.Button(
            code_hdr,
            text="💾 .ino 파일 저장",
            command=self.save_ino_file,
            bg="#334155",
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 8, "bold"),
            padx=8,
            pady=2,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=2)

        tk.Button(
            code_hdr,
            text="📋 코드 복사",
            command=self.copy_code,
            bg="#334155",
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 8, "bold"),
            padx=8,
            pady=2,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=2)

        self.code_view = tk.Text(
            parent,
            bg="#090d16",
            fg="#e2e8f0",
            font=("Consolas", 9),
            height=18,
            relief=tk.FLAT,
            padx=10,
            pady=8,
            wrap=tk.NONE,
        )
        self.code_view.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        # 3. 아두이노 업로드 진행 상태 콘솔
        tk.Label(
            parent,
            text="📡 아두이노(COM5) 업로드 상태창",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Malgun Gothic", 9, "bold"),
            anchor="w",
            padx=10,
        ).pack(fill=tk.X)

        self.log_view = tk.Text(
            parent,
            bg="#020617",
            fg="#4ade80",
            font=("Consolas", 9),
            height=8,
            relief=tk.FLAT,
            padx=10,
            pady=6,
        )
        self.log_view.pack(fill=tk.X, padx=6, pady=(2, 8))
        self.log("준비 완료! 오른쪽 위 [🚀 아두이노(COM5)로 바로 업로드!] 버튼을 누르면 업로드가 시작됩니다.")

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="환영합니다! 왼쪽 블록을 클릭해서 추가하거나, 오른쪽 위 [🚀 아두이노로 바로 업로드] 버튼을 눌러보세요.")
        bar = tk.Label(
            self,
            textvariable=self.status_var,
            bg="#020617",
            fg="#94a3b8",
            anchor="w",
            padx=14,
            pady=5,
            font=("Malgun Gothic", 9),
        )
        bar.pack(side=tk.BOTTOM, fill=tk.X)

    # --------------------------------------------------------------------------
    # 캔버스 그래픽 렌더링 (고급 둥근 카드 + 지멘스 CFC 번호표 + 직각 배선)
    # --------------------------------------------------------------------------
    def create_rounded_rect(self, x1, y1, x2, y2, r=10, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        # 1. 모눈종이 배경 (도트 & 그리드)
        step = 24
        for gx in range(0, w, step):
            col = "#cbd5e1" if gx % (step * 4) == 0 else "#e2e8f0"
            self.canvas.create_line(gx, 0, gx, h, fill=col)
        for gy in range(0, h, step):
            col = "#cbd5e1" if gy % (step * 4) == 0 else "#e2e8f0"
            self.canvas.create_line(0, gy, w, gy, fill=col)

        # 2. 연결된 전선 (Wires) 그리기
        for idx, wire in enumerate(self.wires):
            if wire["src_id"] not in self.blocks or wire["dst_id"] not in self.blocks:
                continue
            sb = self.blocks[wire["src_id"]]
            db = self.blocks[wire["dst_id"]]
            x1, y1 = self.get_pin_pos(wire["src_id"], "out", wire["src_pin"])
            x2, y2 = self.get_pin_pos(wire["dst_id"], "in", wire["dst_pin"])
            pts = self.route_orthogonal(x1, y1, x2, y2, sb, db)

            is_sel = (self.selected_wire == idx)
            w_col = "#ef4444" if is_sel else "#334155"
            w_thick = 4.0 if is_sel else 3.0

            # 시뮬레이션 중 전기가 통하면 밝은 초록색으로 빛남!
            if self.sim_active:
                sig = self.sim_mem.get(f"out_{wire['src_id']}_{wire['src_pin']}", 0)
                if sig > 0:
                    w_col = "#16a34a"
                    w_thick = 4.2

            # 전선 외곽 그림자 + 본선
            self.canvas.create_line(*pts, fill="#cbd5e1", width=w_thick + 2, capstyle=tk.ROUND, joinstyle=tk.ROUND)
            self.canvas.create_line(*pts, fill=w_col, width=w_thick, capstyle=tk.ROUND, joinstyle=tk.ROUND)

            # 화살표 끝
            self.canvas.create_polygon(
                x2 - 2, y2, x2 - 11, y2 - 5, x2 - 11, y2 + 5, fill=w_col, outline=w_col
            )

        # 마우스로 현재 긋고 있는 임시 선
        if self.wiring_from:
            _, _, _, x1, y1 = self.wiring_from
            x2, y2 = self.mouse_pos
            pts = self.route_orthogonal(x1, y1, x2, y2)
            self.canvas.create_line(*pts, fill="#2563eb", width=3.5, dash=(6, 4), capstyle=tk.ROUND)

        # 3. 모든 CFC 블록 그리기
        for bid, b in self.blocks.items():
            self._draw_cfc_block(bid, b)

    def _draw_cfc_block(self, bid, b):
        bdef = FLAT_BLOCKS[b["type"]]
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        is_sel = (self.selected_block == bid)

        # 부드러운 그림자
        self.create_rounded_rect(x + 4, y + 5, x + w + 4, y + h + 5, r=12, fill="#cbd5e1", outline="")

        # 블록 몸통 배경
        border_col = "#f59e0b" if is_sel else bdef["color"]
        border_w = 3.5 if is_sel else 2.0
        self.create_rounded_rect(x, y, x + w, y + h, r=12, fill=bdef["bg"], outline=border_col, width=border_w)

        # 상단 컬러 헤더
        self.create_rounded_rect(x, y, x + w, y + self.HEADER_H, r=10, fill=bdef["color"], outline="")
        self.canvas.create_rectangle(x, y + self.HEADER_H - 10, x + w, y + self.HEADER_H, fill=bdef["color"], outline="")

        # 블록 제목과 부제목
        self.canvas.create_text(
            x + 10, y + 14, text=bdef["title"], anchor="w", fill="#ffffff", font=("Malgun Gothic", 10, "bold")
        )
        self.canvas.create_text(
            x + 10, y + 31, text=f"{b['name']}  ({bdef['sub']})", anchor="w", fill="#e2e8f0", font=("Malgun Gothic", 8)
        )

        # 지멘스 CFC 실행 순서 번호표 (우측 상단 노란 뱃지)
        bx1, by1, bx2, by2 = x + w - 34, y + 7, x + w - 7, y + 27
        self.create_rounded_rect(bx1, by1, bx2, by2, r=5, fill="#fef08a", outline="#ca8a04", width=1)
        self.canvas.create_text(
            (bx1 + bx2) / 2, (by1 + by2) / 2, text=str(b["order"]), fill="#713f12", font=("Consolas", 9, "bold")
        )

        # 왼쪽 입력 핀(Input Pins) 및 숫자 상자(Parameter Badges)
        wired_inputs = {(w_["dst_id"], w_["dst_pin"]) for w_ in self.wires}

        for idx, (pcode, plabel, ptype, pdef) in enumerate(bdef["ins"]):
            px, py = self.get_pin_pos(bid, "in", pcode)
            is_pin_hover = (self.hover_pin == (bid, "in", pcode))

            # 하드웨어 핀 설정(PIN)은 선 연결 대신 클릭해서 숫자를 바꾸는 배지로 표시
            if ptype in ("pin", "apin"):
                val_str = str(b["params"].get(pcode, pdef))
                disp = f"A{val_str}" if ptype == "apin" else f"핀 {val_str}번"
                self.create_rounded_rect(
                    x + 10, py - 10, x + w - 10, py + 10, r=6, fill="#ffffff", outline="#94a3b8", width=1.2
                )
                self.canvas.create_text(
                    x + w / 2, py, text=f"🔌 {plabel}: {disp} (클릭변경)", fill="#0f172a", font=("Malgun Gothic", 8, "bold")
                )
                continue

            # 일반 입력 단자 동그라미
            r = self.PIN_R + (2 if is_pin_hover else 0)
            p_col = "#22c55e" if is_pin_hover else ("#2563eb" if ptype == "bool" else "#ea580c")
            self.canvas.create_oval(px - r, py - r, px + r, py + r, fill=p_col, outline="#ffffff", width=2)
            self.canvas.create_text(px + 12, py, text=plabel, anchor="w", fill="#0f172a", font=("Malgun Gothic", 9, "bold"))

            # 선이 연결되지 않은 입력 핀은 왼쪽 바깥에 클릭 가능한 상수 값 배지 표시
            if (bid, pcode) not in wired_inputs:
                val_str = str(b["params"].get(pcode, pdef))
                bw = max(len(val_str) * 8 + 18, 36)
                is_b_hover = (self.hover_badge == (bid, pcode))
                b_bg = "#fef08a" if is_b_hover else "#ffffff"
                b_out = "#f59e0b" if is_b_hover else "#64748b"

                self.canvas.create_line(px - self.PIN_R, py, px - 14, py, fill="#64748b", width=2)
                self.create_rounded_rect(
                    px - 14 - bw, py - 11, px - 14, py + 11, r=6, fill=b_bg, outline=b_out, width=1.5
                )
                self.canvas.create_text(
                    px - 14 - bw / 2, py, text=val_str, fill="#0f172a", font=("Consolas", 9, "bold")
                )

        # 오른쪽 출력 핀(Output Pins)
        for idx, (pcode, plabel, ptype) in enumerate(bdef["outs"]):
            px, py = self.get_pin_pos(bid, "out", pcode)
            is_pin_hover = (self.hover_pin == (bid, "out", pcode))
            r = self.PIN_R + (2 if is_pin_hover else 0)
            p_col = "#22c55e" if is_pin_hover else ("#2563eb" if ptype == "bool" else "#ea580c")

            self.canvas.create_oval(px - r, py - r, px + r, py + r, fill=p_col, outline="#ffffff", width=2)
            self.canvas.create_text(px - 12, py, text=plabel, anchor="e", fill="#0f172a", font=("Malgun Gothic", 9, "bold"))

            # 시뮬레이션 중일 때 출력 값 표시등
            if self.sim_active:
                v = self.sim_mem.get(f"out_{bid}_{pcode}", 0)
                lamp_bg = "#22c55e" if v > 0 else "#cbd5e1"
                lamp_fg = "#ffffff" if v > 0 else "#475569"
                self.create_rounded_rect(px + 12, py - 10, px + 54, py + 10, r=6, fill=lamp_bg, outline="")
                self.canvas.create_text(px + 33, py, text=str(v), fill=lamp_fg, font=("Consolas", 9, "bold"))

        # 시뮬레이션 중 LED / 부저 시각 효과 표시
        if self.sim_active and b["type"] == "LED":
            led_on = self.sim_mem.get(f"out_{bid}_Q", 0) > 0
            glow_col = "#fde047" if led_on else "#94a3b8"
            txt = "🌟 반짝반짝 켜짐!" if led_on else "⚫ 꺼짐"
            self.create_rounded_rect(x + 20, y + h + 4, x + w - 20, y + h + 26, r=8, fill=glow_col, outline="#ca8a04")
            self.canvas.create_text(x + w / 2, y + h + 15, text=txt, fill="#0f172a", font=("Malgun Gothic", 9, "bold"))

    # --------------------------------------------------------------------------
    # 좌표 계산 및 마우스 이벤트
    # --------------------------------------------------------------------------
    def spawn_block(self, btype, x=None, y=None, name=None, params=None):
        bdef = FLAT_BLOCKS[btype]
        bid = self.next_id
        self.next_id += 1

        n_rows = max(len(bdef["ins"]), len(bdef["outs"]), 1)
        h = self.HEADER_H + n_rows * self.PIN_STEP + 14

        if x is None or y is None:
            offset = (len(self.blocks) % 7) * 28
            x = 140 + offset
            y = 90 + offset

        p_dict = {p[0]: p[3] for p in bdef["ins"]}
        if params:
            p_dict.update(params)

        self.blocks[bid] = {
            "id": bid,
            "type": btype,
            "name": name or f"{btype}_{bid}",
            "x": x,
            "y": y,
            "w": self.BLOCK_W,
            "h": h,
            "order": len(self.blocks) + 1,
            "params": p_dict,
        }
        self.selected_block = bid
        self.auto_order_blocks()
        self.refresh_inspector()
        self.refresh_all()
        return bid

    def get_pin_pos(self, bid, kind, pin_code):
        b = self.blocks[bid]
        bdef = FLAT_BLOCKS[b["type"]]
        pins = bdef["ins"] if kind == "in" else bdef["outs"]
        for idx, p in enumerate(pins):
            if p[0] == pin_code:
                py = b["y"] + self.HEADER_H + 18 + idx * self.PIN_STEP
                px = b["x"] if kind == "in" else b["x"] + b["w"]
                return px, py
        return b["x"], b["y"]

    def route_orthogonal(self, x1, y1, x2, y2, sb=None, db=None):
        stub = 22
        if x2 >= x1 + stub:
            mx = (x1 + x2) / 2
            return [x1, y1, mx, y1, mx, y2, x2, y2]
        else:
            top_y = min(y1, y2) - 55
            if sb and db:
                top_y = min(sb["y"], db["y"]) - 30
            return [x1, y1, x1 + stub, y1, x1 + stub, top_y, x2 - stub, top_y, x2 - stub, y2, x2, y2]

    def hit_test_pin(self, x, y):
        r_sq = 13 ** 2
        for bid, b in self.blocks.items():
            bdef = FLAT_BLOCKS[b["type"]]
            for p in bdef["ins"]:
                if p[2] in ("pin", "apin"):
                    continue
                px, py = self.get_pin_pos(bid, "in", p[0])
                if (x - px) ** 2 + (y - py) ** 2 <= r_sq:
                    return (bid, "in", p[0], px, py)
            for p in bdef["outs"]:
                px, py = self.get_pin_pos(bid, "out", p[0])
                if (x - px) ** 2 + (y - py) ** 2 <= r_sq:
                    return (bid, "out", p[0], px, py)
        return None

    def hit_test_badge(self, x, y):
        wired_inputs = {(w_["dst_id"], w_["dst_pin"]) for w_ in self.wires}
        for bid, b in self.blocks.items():
            bdef = FLAT_BLOCKS[b["type"]]
            for pcode, plabel, ptype, pdef in bdef["ins"]:
                px, py = self.get_pin_pos(bid, "in", pcode)
                if ptype in ("pin", "apin"):
                    if b["x"] + 8 <= x <= b["x"] + b["w"] - 8 and py - 11 <= y <= py + 11:
                        return (bid, pcode, plabel)
                elif (bid, pcode) not in wired_inputs:
                    val_str = str(b["params"].get(pcode, pdef))
                    bw = max(len(val_str) * 8 + 18, 36)
                    if px - 14 - bw <= x <= px - 14 and py - 12 <= y <= py + 12:
                        return (bid, pcode, plabel)
        return None

    def hit_test_block(self, x, y):
        for bid in reversed(list(self.blocks.keys())):
            b = self.blocks[bid]
            if b["x"] <= x <= b["x"] + b["w"] and b["y"] <= y <= b["y"] + b["h"]:
                return bid
        return None

    def on_mouse_down(self, event):
        x, y = event.x, event.y

        # 1. 핀 클릭 (선 연결 시작 또는 완료)
        pin_hit = self.hit_test_pin(x, y)
        if pin_hit:
            bid, kind, pcode, px, py = pin_hit
            if kind == "out":
                self.wiring_from = (bid, kind, pcode, px, py)
                self.mouse_pos = (x, y)
                self.status_var.set("선 연결 중... 연결하고 싶은 다른 블록의 왼쪽 파란 점(입력)에 놓아주세요!")
                self.redraw()
                return
            elif kind == "in" and self.wiring_from:
                self._complete_wire(bid, pcode)
                return

        # 2. 핀 번호 / 상수 배지 클릭 -> 즉시 값 수정 팝업!
        badge_hit = self.hit_test_badge(x, y)
        if badge_hit and not self.sim_active:
            bid, pcode, plabel = badge_hit
            self.selected_block = bid
            self.refresh_inspector()
            self._prompt_pin_value(bid, pcode, plabel)
            return

        # 3. 블록 클릭
        bid = self.hit_test_block(x, y)
        if bid is not None:
            # 시뮬레이션 중 버튼이나 숫자 블록을 클릭하면 스위치 ON/OFF 토글!
            if self.sim_active and self.blocks[bid]["type"] in ("BUTTON", "NUMBER"):
                b = self.blocks[bid]
                if b["type"] == "BUTTON":
                    cur = self.sim_mem.get(f"btn_{bid}", 0)
                    self.sim_mem[f"btn_{bid}"] = 0 if cur else 1
                else:
                    cur = int(b["params"].get("VAL", "0"))
                    b["params"]["VAL"] = "0" if cur else "1"
                self.redraw()
                return

            self.selected_block = bid
            self.selected_wire = None
            b = self.blocks[bid]
            self.drag_info = (bid, x - b["x"], y - b["y"])
            self.refresh_inspector()
            self.redraw()
            return

        # 4. 전선 선택
        self.selected_wire = self._find_wire_near(x, y)
        self.selected_block = None
        self._cancel_wire()
        self.refresh_inspector()
        self.redraw()

    def on_mouse_drag(self, event):
        if self.wiring_from:
            self.mouse_pos = (event.x, event.y)
            self.redraw()
        elif self.drag_info:
            bid, dx, dy = self.drag_info
            nx = max(50, round((event.x - dx) / 12) * 12)
            ny = max(20, round((event.y - dy) / 12) * 12)
            self.blocks[bid]["x"] = nx
            self.blocks[bid]["y"] = ny
            self.redraw()

    def on_mouse_up(self, event):
        if self.wiring_from:
            pin_hit = self.hit_test_pin(event.x, event.y)
            if pin_hit and pin_hit[1] == "in":
                self._complete_wire(pin_hit[0], pin_hit[2])
            else:
                self._cancel_wire()
        if self.drag_info:
            self.auto_order_blocks()
            self.refresh_all()
        self.drag_info = None

    def on_mouse_move(self, event):
        pin_hit = self.hit_test_pin(event.x, event.y)
        new_pin = (pin_hit[0], pin_hit[1], pin_hit[2]) if pin_hit else None
        badge_hit = self.hit_test_badge(event.x, event.y)
        new_badge = (badge_hit[0], badge_hit[1]) if badge_hit else None

        if new_pin != self.hover_pin or new_badge != self.hover_badge:
            self.hover_pin = new_pin
            self.hover_badge = new_badge
            self.redraw()

    def on_double_click(self, event):
        bid = self.hit_test_block(event.x, event.y)
        if bid is not None:
            b = self.blocks[bid]
            bdef = FLAT_BLOCKS[b["type"]]
            if bdef["ins"]:
                pcode, plabel, _, _ = bdef["ins"][0]
                self._prompt_pin_value(bid, pcode, plabel)

    def on_right_click(self, event):
        w_idx = self._find_wire_near(event.x, event.y)
        if w_idx is not None:
            del self.wires[w_idx]
            self.selected_wire = None
            self.refresh_all()

    def _complete_wire(self, dst_id, dst_pin):
        src_id, _, src_pin, _, _ = self.wiring_from
        if src_id == dst_id:
            self._cancel_wire()
            return
        self.wires = [w for w in self.wires if not (w["dst_id"] == dst_id and w["dst_pin"] == dst_pin)]
        self.wires.append({"src_id": src_id, "src_pin": src_pin, "dst_id": dst_id, "dst_pin": dst_pin})
        self.wiring_from = None
        self.auto_order_blocks()
        self.refresh_inspector()
        self.refresh_all()
        self.status_var.set("🎉 선 연결 성공! 오른쪽 코드 창에 아두이노 코드가 자동으로 만들어졌어요.")

    def _cancel_wire(self):
        self.wiring_from = None
        self.redraw()

    def _prompt_pin_value(self, bid, pcode, plabel):
        b = self.blocks[bid]
        cur = b["params"].get(pcode, "0")
        ans = simpledialog.askstring(
            "값 바꾸기",
            f"[{b['name']}] 블록의 '{plabel}' 값을 입력하세요:\n(예: 핀 번호 2~13, 시간 1000=1초)",
            initialvalue=str(cur),
            parent=self,
        )
        if ans is not None and ans.strip() != "":
            b["params"][pcode] = ans.strip()
            self.refresh_inspector()
            self.refresh_all()

    def _find_wire_near(self, x, y):
        for idx, wire in enumerate(self.wires):
            if wire["src_id"] not in self.blocks or wire["dst_id"] not in self.blocks:
                continue
            sb = self.blocks[wire["src_id"]]
            db = self.blocks[wire["dst_id"]]
            x1, y1 = self.get_pin_pos(wire["src_id"], "out", wire["src_pin"])
            x2, y2 = self.get_pin_pos(wire["dst_id"], "in", wire["dst_pin"])
            pts = self.route_orthogonal(x1, y1, x2, y2, sb, db)
            for i in range(0, len(pts) - 2, 2):
                ax, ay, bx, by = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
                dx, dy = bx - ax, by - ay
                if dx == 0 and dy == 0:
                    continue
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
                px, py = ax + t * dx, ay + t * dy
                if ((x - px) ** 2 + (y - py) ** 2) ** 0.5 <= 7.0:
                    return idx
        return None

    def delete_selected(self):
        if self.selected_block is not None and self.selected_block in self.blocks:
            bid = self.selected_block
            del self.blocks[bid]
            self.wires = [w for w in self.wires if w["src_id"] != bid and w["dst_id"] != bid]
            self.selected_block = None
            self.auto_order_blocks()
            self.refresh_inspector()
            self.refresh_all()
        elif self.selected_wire is not None and 0 <= self.selected_wire < len(self.wires):
            del self.wires[self.selected_wire]
            self.selected_wire = None
            self.refresh_all()

    # --------------------------------------------------------------------------
    # 우측 블록 속성창 업데이트
    # --------------------------------------------------------------------------
    def refresh_inspector(self):
        for w in self.inspector_body.winfo_children():
            w.destroy()

        if self.selected_block is None or self.selected_block not in self.blocks:
            tk.Label(
                self.inspector_body,
                text="캔버스에서 블록을 클릭하면 여기서 핀 번호나 시간을 쉽게 바꿀 수 있어요!",
                bg="#1e293b",
                fg="#94a3b8",
                wraplength=340,
                justify=tk.LEFT,
                font=("Malgun Gothic", 9),
            ).pack(anchor="w")
            return

        b = self.blocks[self.selected_block]
        bdef = FLAT_BLOCKS[b["type"]]

        tk.Label(
            self.inspector_body,
            text=f"{bdef['title']}  —  {bdef['help']}",
            bg="#1e293b",
            fg="#e2e8f0",
            wraplength=340,
            justify=tk.LEFT,
            font=("Malgun Gothic", 9),
        ).pack(anchor="w", pady=(0, 8))

        entries = {}
        wired_inputs = {(w_["dst_id"], w_["dst_pin"]) for w_ in self.wires}

        for pcode, plabel, ptype, pdef in bdef["ins"]:
            row = tk.Frame(self.inspector_body, bg="#1e293b", pady=2)
            row.pack(fill=tk.X)
            tk.Label(row, text=f"• {plabel}:", bg="#1e293b", fg="#38bdf8", width=16, anchor="w", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT)

            if (b["id"], pcode) in wired_inputs and ptype not in ("pin", "apin"):
                tk.Label(row, text="🔗 다른 블록과 선으로 연결됨", bg="#1e293b", fg="#4ade80", font=("Malgun Gothic", 9)).pack(side=tk.LEFT)
            else:
                ent = tk.Entry(row, bg="#0f172a", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT, font=("Consolas", 10))
                ent.insert(0, str(b["params"].get(pcode, pdef)))
                ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
                entries[pcode] = ent

        def save_params():
            for k, ent in entries.items():
                b["params"][k] = ent.get().strip()
            self.refresh_all()
            self.status_var.set(f"✅ [{bdef['title']}] 블록 설정이 변경되었습니다.")

        if entries:
            tk.Button(
                self.inspector_body,
                text="✔️ 설정 값 적용하기",
                command=save_params,
                bg="#2563eb",
                fg="#ffffff",
                relief=tk.FLAT,
                font=("Malgun Gothic", 9, "bold"),
                pady=4,
                cursor="hand2",
            ).pack(fill=tk.X, pady=(8, 0))

    # --------------------------------------------------------------------------
    # 지멘스 CFC 실행 순서 자동 정렬 & 아두이노 C++ 코드 생성기
    # --------------------------------------------------------------------------
    def auto_order_blocks(self):
        ordered = sorted(self.blocks.values(), key=lambda b: (b["x"], b["y"], b["id"]))
        for idx, b in enumerate(ordered, start=1):
            b["order"] = idx

    def generate_ino_code(self):
        sorted_blocks = sorted(self.blocks.values(), key=lambda b: (b["order"], b["id"]))
        uses_servo = any(b["type"] == "SERVO" for b in sorted_blocks)

        lines = [
            "// ============================================================================",
            "// [어린이 아두이노 CFC 스튜디오]에서 자동 생성된 아두이노 코드입니다.",
            "// 지멘스 PLC의 CFC 차트처럼 매 순간 모든 블록이 동시에 똑똑하게 작동합니다!",
            "// ============================================================================",
            "#include <Arduino.h>",
        ]
        if uses_servo:
            lines.append("#include <Servo.h>")
        lines.append("")

        wire_map = {}
        for w in self.wires:
            if w["src_id"] in self.blocks and w["dst_id"] in self.blocks:
                wire_map[(w["dst_id"], w["dst_pin"])] = f"B{w['src_id']}_{w['src_pin']}"

        setup_lines = []
        for b in sorted_blocks:
            bid = b["id"]
            bt = b["type"]
            bdef = FLAT_BLOCKS[bt]

            for pcode, _, ptype in bdef["outs"]:
                ctype = "bool" if ptype == "bool" else "long"
                lines.append(f"{ctype} B{bid}_{pcode} = 0; // {bdef['title']} 출력")

            if bt == "BLINK":
                lines.append(f"unsigned long B{bid}_timer = 0;")
            elif bt == "TIMER_ON":
                lines.append(f"unsigned long B{bid}_start = 0;")
                lines.append(f"bool B{bid}_active = false;")
            elif bt == "COUNTER":
                lines.append(f"bool B{bid}_prev = false;")
            elif bt == "SERVO":
                lines.append(f"Servo servo_{bid};")

            # 핀 모드 설정
            if bt == "BUTTON":
                pin = b["params"].get("PIN", "2")
                setup_lines.append(f"  pinMode({pin}, INPUT_PULLUP); // 버튼 핀 {pin}번")
            elif bt in ("LED", "PWM_LED", "BUZZER"):
                pin = b["params"].get("PIN", "13")
                setup_lines.append(f"  pinMode({pin}, OUTPUT); // 출력 핀 {pin}번")
            elif bt == "SERVO":
                pin = b["params"].get("PIN", "10")
                setup_lines.append(f"  servo_{bid}.attach({pin}); // 서보모터 핀 {pin}번")

        lines.append("")
        lines.append("void setup() {")
        if setup_lines:
            lines.extend(setup_lines)
        else:
            lines.append("  // 설정된 입출력 핀이 없습니다.")
        lines.append("}")
        lines.append("")
        lines.append("void loop() {")
        lines.append("  unsigned long now = millis();")
        lines.append("")

        def val_of(b, pcode):
            if (b["id"], pcode) in wire_map:
                return wire_map[(b["id"], pcode)]
            return str(b["params"].get(pcode, "0"))

        for b in sorted_blocks:
            bid = b["id"]
            bt = b["type"]
            bdef = FLAT_BLOCKS[bt]
            lines.append(f"  // [{b['order']}번 블록] {bdef['title']}")

            if bt == "BUTTON":
                pin = val_of(b, "PIN")
                lines.append(f"  B{bid}_Q = (digitalRead({pin}) == LOW); // 버튼 스위치 읽기 (누르면 ON)")
            elif bt == "SENSOR_LIGHT":
                apin = val_of(b, "PIN")
                lines.append(f"  B{bid}_VAL = analogRead(A{apin});")
            elif bt == "NUMBER":
                lines.append(f"  B{bid}_OUT = {val_of(b, 'VAL')};")
            elif bt == "AND":
                lines.append(f"  B{bid}_Q = ({val_of(b, 'IN1')}) && ({val_of(b, 'IN2')});")
            elif bt == "OR":
                lines.append(f"  B{bid}_Q = ({val_of(b, 'IN1')}) || ({val_of(b, 'IN2')});")
            elif bt == "NOT":
                lines.append(f"  B{bid}_Q = !({val_of(b, 'IN')});")
            elif bt == "LATCH":
                lines.append(f"  if ({val_of(b, 'R')}) B{bid}_Q = false;")
                lines.append(f"  else if ({val_of(b, 'S')}) B{bid}_Q = true;")
            elif bt == "COMPARE":
                lines.append(f"  B{bid}_Q = ({val_of(b, 'VAL')}) > ({val_of(b, 'REF')});")
            elif bt == "BLINK":
                en = val_of(b, "EN")
                ms = val_of(b, "MS")
                lines.append(f"  if ({en}) {{")
                lines.append(f"    if (now - B{bid}_timer >= {ms}) {{")
                lines.append(f"      B{bid}_Q = !B{bid}_Q;")
                lines.append(f"      B{bid}_timer = now;")
                lines.append("    }")
                lines.append(f"  }} else {{ B{bid}_Q = false; }}")
            elif bt == "TIMER_ON":
                in_v = val_of(b, "IN")
                ms = val_of(b, "MS")
                lines.append(f"  if ({in_v}) {{")
                lines.append(f"    if (!B{bid}_active) {{ B{bid}_active = true; B{bid}_start = now; }}")
                lines.append(f"    if (now - B{bid}_start >= {ms}) B{bid}_Q = true;")
                lines.append(f"  }} else {{ B{bid}_active = false; B{bid}_Q = false; }}")
            elif bt == "COUNTER":
                cu = val_of(b, "CU")
                r = val_of(b, "R")
                goal = val_of(b, "GOAL")
                lines.append(f"  if ({r}) B{bid}_CV = 0;")
                lines.append(f"  else if (({cu}) && !B{bid}_prev) B{bid}_CV++;")
                lines.append(f"  B{bid}_prev = {cu};")
                lines.append(f"  B{bid}_Q = (B{bid}_CV >= {goal});")
            elif bt == "LED":
                in_v = val_of(b, "IN")
                pin = val_of(b, "PIN")
                lines.append(f"  B{bid}_Q = {in_v};")
                lines.append(f"  digitalWrite({pin}, B{bid}_Q ? HIGH : LOW);")
            elif bt == "PWM_LED":
                val = val_of(b, "VAL")
                pin = val_of(b, "PIN")
                lines.append(f"  analogWrite({pin}, constrain({val}, 0, 255));")
            elif bt == "BUZZER":
                en = val_of(b, "EN")
                freq = val_of(b, "FREQ")
                pin = val_of(b, "PIN")
                lines.append(f"  if ({en}) tone({pin}, {freq});")
                lines.append(f"  else noTone({pin});")
            elif bt == "SERVO":
                ang = val_of(b, "ANGLE")
                lines.append(f"  servo_{bid}.write(constrain({ang}, 0, 180));")

            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    def refresh_all(self):
        self.redraw()
        code = self.generate_ino_code()
        self.code_view.delete("1.0", tk.END)
        self.code_view.insert("1.0", code)

    # --------------------------------------------------------------------------
    # 실시간 시뮬레이션 모드 (아두이노 없이 화면에서 작동 확인)
    # --------------------------------------------------------------------------
    def toggle_simulation(self):
        self.sim_active = not self.sim_active
        if self.sim_active:
            self.sim_btn.configure(text="⏹️ 시뮬레이션 멈추기", bg="#dc2626")
            self.guide_banner.configure(
                bg="#dcfce7",
                fg="#15803d",
                text="🟢 [화면 작동 테스트 중!] 캔버스의 '🔘 버튼 스위치'나 '🔢 숫자 상수' 블록을 마우스로 클릭해보세요! 전기가 흐르는 길은 초록색으로 빛납니다!",
            )
            self._sim_loop()
        else:
            self.sim_btn.configure(text="▶️ 화면에서 미리 작동해보기", bg="#059669")
            self.guide_banner.configure(
                bg="#e0f2fe",
                fg="#0369a1",
                text="💡 사용법: ① 왼쪽 블록을 클릭해 꺼내세요  ② 블록의 오른쪽 파란 점(출력)을 드래그해서 다른 블록의 왼쪽 점(입력)에 연결하세요  ③ 회색 숫자 상자를 클릭하면 핀 번호나 시간을 바꿀 수 있어요!",
            )
            self.redraw()

    def _sim_loop(self):
        if not self.sim_active:
            return
        self.sim_ms += 100

        wire_map = {(w["dst_id"], w["dst_pin"]): (w["src_id"], w["src_pin"]) for w in self.wires}

        def get_in(b, pcode):
            if (b["id"], pcode) in wire_map:
                sid, spin = wire_map[(b["id"], pcode)]
                return int(self.sim_mem.get(f"out_{sid}_{spin}", 0))
            try:
                return int(float(b["params"].get(pcode, "0")))
            except ValueError:
                return 0

        for b in sorted(self.blocks.values(), key=lambda x: (x["order"], x["id"])):
            bid = b["id"]
            bt = b["type"]

            if bt == "BUTTON":
                self.sim_mem[f"out_{bid}_Q"] = int(self.sim_mem.get(f"btn_{bid}", 1))
            elif bt == "SENSOR_LIGHT":
                self.sim_mem[f"out_{bid}_VAL"] = 600
            elif bt == "NUMBER":
                self.sim_mem[f"out_{bid}_OUT"] = get_in(b, "VAL")
            elif bt == "AND":
                self.sim_mem[f"out_{bid}_Q"] = 1 if (get_in(b, "IN1") and get_in(b, "IN2")) else 0
            elif bt == "OR":
                self.sim_mem[f"out_{bid}_Q"] = 1 if (get_in(b, "IN1") or get_in(b, "IN2")) else 0
            elif bt == "NOT":
                self.sim_mem[f"out_{bid}_Q"] = 0 if get_in(b, "IN") else 1
            elif bt == "LATCH":
                if get_in(b, "R"):
                    self.sim_mem[f"out_{bid}_Q"] = 0
                elif get_in(b, "S"):
                    self.sim_mem[f"out_{bid}_Q"] = 1
            elif bt == "COMPARE":
                self.sim_mem[f"out_{bid}_Q"] = 1 if get_in(b, "VAL") > get_in(b, "REF") else 0
            elif bt == "BLINK":
                if get_in(b, "EN"):
                    ms = max(200, get_in(b, "MS"))
                    self.sim_mem[f"out_{bid}_Q"] = (self.sim_ms // ms) % 2
                else:
                    self.sim_mem[f"out_{bid}_Q"] = 0
            elif bt == "TIMER_ON":
                if get_in(b, "IN"):
                    el = self.sim_mem.get(f"tmr_{bid}", 0) + 100
                    self.sim_mem[f"tmr_{bid}"] = el
                    self.sim_mem[f"out_{bid}_Q"] = 1 if el >= max(100, get_in(b, "MS")) else 0
                else:
                    self.sim_mem[f"tmr_{bid}"] = 0
                    self.sim_mem[f"out_{bid}_Q"] = 0
            elif bt == "COUNTER":
                cu = 1 if get_in(b, "CU") else 0
                prev = self.sim_mem.get(f"prev_{bid}", 0)
                cv = self.sim_mem.get(f"out_{bid}_CV", 0)
                if get_in(b, "R"):
                    cv = 0
                elif cu and not prev:
                    cv += 1
                self.sim_mem[f"prev_{bid}"] = cu
                self.sim_mem[f"out_{bid}_CV"] = cv
                self.sim_mem[f"out_{bid}_Q"] = 1 if cv >= get_in(b, "GOAL") else 0
            elif bt == "LED":
                self.sim_mem[f"out_{bid}_Q"] = 1 if get_in(b, "IN") else 0

        self.redraw()
        self.after(100, self._sim_loop)

    # --------------------------------------------------------------------------
    # 프리셋 예제 불러오기
    # --------------------------------------------------------------------------
    def _on_example_selected(self, *_):
        key = PRESET_EXAMPLES.get(self.example_cb.get(), "blink")
        self.load_example(key)

    def clear_all(self):
        self.blocks.clear()
        self.wires.clear()
        self.next_id = 1
        self.selected_block = None
        self.selected_wire = None
        self.refresh_inspector()
        self.refresh_all()

    def load_example(self, key):
        self.clear_all()
        if key == "blink":
            b1 = self.spawn_block("NUMBER", 110, 140, name="항상켜짐", params={"VAL": "1"})
            b2 = self.spawn_block("BLINK", 380, 130, name="깜빡이", params={"MS": "500"})
            b3 = self.spawn_block("LED", 670, 130, name="보드LED", params={"PIN": "13"})
            self.wires = [
                {"src_id": b1, "src_pin": "OUT", "dst_id": b2, "dst_pin": "EN"},
                {"src_id": b2, "src_pin": "Q", "dst_id": b3, "dst_pin": "IN"},
            ]
        elif key == "button_led":
            b1 = self.spawn_block("BUTTON", 100, 110, name="시작버튼", params={"PIN": "2"})
            b2 = self.spawn_block("LED", 430, 80, name="불빛LED", params={"PIN": "13"})
            b3 = self.spawn_block("BUZZER", 430, 220, name="멜로디부저", params={"PIN": "8", "FREQ": "523"})
            self.wires = [
                {"src_id": b1, "src_pin": "Q", "dst_id": b2, "dst_pin": "IN"},
                {"src_id": b1, "src_pin": "Q", "dst_id": b3, "dst_pin": "EN"},
            ]
        elif key == "smart_counter":
            b_on = self.spawn_block("BUTTON", 80, 80, name="시작버튼", params={"PIN": "2"})
            b_off = self.spawn_block("BUTTON", 80, 220, name="정지버튼", params={"PIN": "3"})
            b_lat = self.spawn_block("LATCH", 330, 110, name="기억스위치")
            b_blk = self.spawn_block("BLINK", 580, 90, name="깜빡이", params={"MS": "400"})
            b_led = self.spawn_block("LED", 840, 80, name="LED전구", params={"PIN": "13"})
            b_cnt = self.spawn_block("COUNTER", 580, 250, name="5번세기", params={"GOAL": "5"})
            b_buz = self.spawn_block("BUZZER", 840, 240, name="알람부저", params={"PIN": "8", "FREQ": "784"})
            self.wires = [
                {"src_id": b_on, "src_pin": "Q", "dst_id": b_lat, "dst_pin": "S"},
                {"src_id": b_off, "src_pin": "Q", "dst_id": b_lat, "dst_pin": "R"},
                {"src_id": b_lat, "src_pin": "Q", "dst_id": b_blk, "dst_pin": "EN"},
                {"src_id": b_blk, "src_pin": "Q", "dst_id": b_led, "dst_pin": "IN"},
                {"src_id": b_blk, "src_pin": "Q", "dst_id": b_cnt, "dst_pin": "CU"},
                {"src_id": b_off, "src_pin": "Q", "dst_id": b_cnt, "dst_pin": "R"},
                {"src_id": b_cnt, "src_pin": "Q", "dst_id": b_buz, "dst_pin": "EN"},
            ]

        self.auto_order_blocks()
        self.refresh_inspector()
        self.refresh_all()

    # --------------------------------------------------------------------------
    # 아두이노 COM5 감지 & 원클릭 자동 컴파일/업로드 엔진
    # --------------------------------------------------------------------------
    def log(self, msg):
        self.log_view.insert(tk.END, msg + "\n")
        self.log_view.see(tk.END)

    def refresh_com_ports(self):
        ports = ["COM5"]
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "[System.IO.Ports.SerialPort]::getportnames()"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=3,
            ).decode("utf-8", errors="ignore")
            found = [p.strip() for p in out.splitlines() if p.strip()]
            if found:
                ports = found
                if "COM5" in found:
                    self.port_var.set("COM5")
                else:
                    self.port_var.set(found[0])
        except Exception:
            pass
        self.port_cb["values"] = ports

    def find_arduino_cli(self):
        # 1. 워크스페이스 내 설치된 포터블 arduino-cli 확인
        local_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "arduino-cli.exe")
        if os.path.exists(local_cli):
            return local_cli

        # 2. 시스템 PATH 확인
        which_cli = shutil.which("arduino-cli")
        if which_cli:
            return which_cli

        # 3. 기본 설치 경로들 탐색
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Arduino15\arduino-cli.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def upload_to_arduino(self):
        port = self.port_var.get().strip() or "COM5"
        board_str = self.board_var.get()
        fqbn = "arduino:avr:uno"
        if "(" in board_str and ")" in board_str:
            fqbn = board_str.split("(")[-1].split(")")[0].strip()

        # 스케치 폴더 저장
        sketch_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfc_arduino_sketch")
        os.makedirs(sketch_dir, exist_ok=True)
        sketch_file = os.path.join(sketch_dir, "cfc_arduino_sketch.ino")
        with open(sketch_file, "w", encoding="utf-8") as f:
            f.write(self.generate_ino_code())

        self.upload_btn.configure(state=tk.DISABLED, text="⏳ 업로드 중...")
        self.log(f"\n==========================================")
        self.log(f"🚀 [{port}] 포트로 아두이노 업로드를 시작합니다!")
        self.log(f"📁 스케치 저장됨: {sketch_file}")

        threading.Thread(target=self._upload_worker, args=(sketch_dir, port, fqbn), daemon=True).start()

    def _run_cli(self, args):
        """UTF-8 및 한글 윈도우(CP949) 인코딩 충돌 없이 안전하게 명령어를 실행합니다."""
        proc = subprocess.run(
            args,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        return proc.returncode, stdout, stderr

    def _upload_worker(self, sketch_dir, port, fqbn):
        try:
            cli_path = self.find_arduino_cli()
            if not cli_path:
                self._ui_log("📦 아두이노 업로더(arduino-cli)가 없어서 자동으로 준비하고 있어요 (최초 1회)...")
                cli_path = self._download_portable_arduino_cli()

            if not cli_path:
                self._ui_log("⚠️ arduino-cli 자동 준비 실패. 스케치 파일(.ino)은 정상 저장되었습니다.")
                return

            # 코어 확인 및 설치 (arduino:avr)
            self._ui_log(f"🔧 컴파일러 점검 중 ({os.path.basename(cli_path)})...")
            rc, out, err = self._run_cli([cli_path, "core", "list"])
            if "arduino:avr" not in out:
                self._ui_log("📥 아두이노 AVR 보드 코어를 설치하고 있습니다 (최초 1회, 약 30초 소요)...")
                self._run_cli([cli_path, "core", "update-index"])
                rc_inst, out_inst, err_inst = self._run_cli([cli_path, "core", "install", "arduino:avr"])
                if rc_inst != 0:
                    self._ui_log("⚠️ 코어 설치 메시지:\n" + (err_inst or out_inst))

            # 서보 모터 블록 사용 시 Servo 라이브러리 자동 확인/설치
            code_txt = self.generate_ino_code()
            if "#include <Servo.h>" in code_txt:
                self._ui_log("🦾 서보 모터(Servo) 라이브러리 확인 중...")
                self._run_cli([cli_path, "lib", "install", "Servo"])

            # 1단계: 컴파일
            self._ui_log(f"⚙️ [1/2] 그림을 아두이노 기계어로 번역(컴파일)하는 중... ({fqbn})")
            rc_comp, out_comp, err_comp = self._run_cli([cli_path, "compile", "--fqbn", fqbn, sketch_dir])
            if rc_comp != 0:
                self._ui_log("❌ 컴파일 오류:\n" + (err_comp or out_comp))
                return

            self._ui_log("✅ 번역(컴파일) 성공!")

            # 2단계: COM5 업로드
            self._ui_log(f"⚡ [2/2] {port} 포트의 아두이노 보드로 프로그램을 전송하는 중...")
            rc_up, out_up, err_up = self._run_cli([cli_path, "upload", "-p", port, "--fqbn", fqbn, sketch_dir])
            if rc_up != 0:
                self._ui_log(f"❌ [{port}] 업로드 실패:\n" + (err_up or out_up))
                self._ui_log("💡 팁: 아두이노 USB 케이블이 연결되어 있는지, 다른 프로그램(시리얼 모니터 등)이 COM5를 사용 중이지 않은지 확인해주세요!")
                return

            self._ui_log(f"🎉 축하합니다! [{port}] 아두이노 보드에 업로드가 완료되었습니다! 지금 보드를 확인해보세요!")
        except Exception as e:
            self._ui_log(f"⚠️ 오류 발생: {e}")
        finally:
            self.after(0, lambda: self.upload_btn.configure(state=tk.NORMAL, text="🚀 아두이노(COM5)로 바로 업로드!"))

    def _download_portable_arduino_cli(self):
        tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
        os.makedirs(tools_dir, exist_ok=True)
        zip_path = os.path.join(tools_dir, "arduino-cli.zip")
        url = "https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip"
        try:
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tools_dir)
            cli_exe = os.path.join(tools_dir, "arduino-cli.exe")
            return cli_exe if os.path.exists(cli_exe) else None
        except Exception as e:
            self._ui_log(f"업로더 다운로드 실패: {e}")
            return None

    def _ui_log(self, msg):
        self.after(0, lambda: self.log(msg))

    def copy_code(self):
        self.clipboard_clear()
        self.clipboard_append(self.generate_ino_code())
        self.status_var.set("📋 아두이노 코드가 클립보드에 복사되었습니다!")

    def save_ino_file(self):
        path = filedialog.asksaveasfilename(
            title="아두이노 코드 저장",
            defaultextension=".ino",
            filetypes=[("Arduino Sketch", "*.ino")],
            initialfile="cfc_arduino_sketch.ino",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.generate_ino_code())
            self.status_var.set(f"💾 저장 완료: {path}")


if __name__ == "__main__":
    app = KidsArduinoCFCApp()
    app.mainloop()
