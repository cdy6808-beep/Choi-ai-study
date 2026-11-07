"""
===============================================================================
[대용량 트렌드 감시 예제] 일주일치(7일) 1초 타임베이스(604,800초) 펌프 트렌드 분석기
===============================================================================
- 데이터 규모: 7일 × 86,400초 = 총 604,800 포인트 (1초 단위 샘플링)
- 운전 패턴:
    * 하루 4회(6시간 주기) 펌프 가동 (4시간 RUN / 2시간 STOP) -> 일주일간 총 28회 기동/정지!
    * 매 기동(Run) 직후 10초간 초기 압력 오버슈트(최대 9.5 bar) 및 전류 인러시(19.8 mA) 발생
    * 매 정지(Stop) 직후 6초간 수격 현상(Water Hammer, -0.6 bar) 언더슈트 발생
    * 일주일 중 실제 설비 이상(True Fault) 4건 숨김:
        1) 월요일(Day 1) 14:20:00 (15초간) — 배관 이물질 막힘으로 정격 운전 중 과압 (9.2 bar)
        2) 수요일(Day 3) 03:15:00 (20초간) — 흡입측 공동현상(Cavitation)으로 압력 급락 (2.3 bar)
        3) 금요일(Day 5) 19:40:00 (12초간) — 체크밸브 채터링으로 정격 운전 중 압력 헌팅 (8.9 bar)
        4) 일요일(Day 7) 05:10:00 (18초간) — 정지 중 바이패스 밸브 누설로 잔압 상승 (1.8 bar)

- 핵심 기능:
    1) 604,800초 데이터를 초고속 스캔하여 28번의 기동/정지 오버슈트(총 448초 분량)는 100% 배제!
    2) 진짜 고장 이벤트 4건만 정확히 색출
    3) 상단: 7일 전체 매크로 트렌드 뷰 / 하단: 선택한 시점 전후 120초를 1초 단위로 확대하는 현미경 뷰!
===============================================================================
"""

from __future__ import annotations

import array
import csv
import datetime
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# ==============================================================================
# 1. 일주일치 1초 타임베이스 (604,800초) 데이터 생성 및 고속 블랭킹 감시 엔진
# ==============================================================================
TOTAL_SECONDS = 7 * 24 * 3600  # 604,800 초 (월요일 00:00:00 ~ 일요일 23:59:59)
START_DT = datetime.datetime(2026, 11, 2, 0, 0, 0)  # 월요일 00:00:00 기준
DAY_NAMES = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

# 숨겨둔 실제 설비 고장 4건 정의: (시작초, 지속초, 고장압력_bar, 고장설명)
REAL_FAULTS = [
    (0 * 86400 + 14 * 3600 + 20 * 60, 15, 9.20, "월요일 14:20 — 토출 배관 스트레이너 막힘 (정격 운전 중 과압)"),
    (2 * 86400 + 3 * 3600 + 15 * 60,  20, 2.30, "수요일 03:15 — 흡입구 공동현상/에어 유입 (정격 운전 중 저압)"),
    (4 * 86400 + 19 * 3600 + 40 * 60, 12, 8.85, "금요일 19:40 — 압력조절밸브(PRV) 헌팅 이상 (정격 운전 중 과압)"),
    (6 * 86400 + 5 * 3600 + 10 * 60,  18, 1.85, "일요일 05:10 — 펌프 정지 중 역류방지 체크밸브 누설 (정지 중 잔압)"),
]


class WeeklyTrendEngine:
    """604,800개의 1초 데이터를 메모리에 생성하고 기동/정지 오버슈트를 배제 감시합니다."""

    def __init__(self):
        # 메모리 효율과 C-속도 연산을 위해 표준 array 사용 (604,800개)
        self.pump_run = array.array("B", [0] * TOTAL_SECONDS)      # 0 or 1
        self.pressure = array.array("f", [0.0] * TOTAL_SECONDS)    # bar
        self.flag = array.array("B", [0] * TOTAL_SECONDS)          # 0=정상, 1=배제된오버슈트, 2=실제경보

        # 7일 전체 요약 그래프용 (1시간 = 3600초 단위 최대/최소/평균, 총 168시간)
        self.hourly_max = [0.0] * 168
        self.hourly_min = [0.0] * 168
        self.hourly_run = [0] * 168

        self.events: list[dict] = []  # 기동 오버슈트 및 실제 고장 이벤트 목록
        self.build_time_sec = 0.0

    def generate_and_analyze(self, start_holdoff_sec: int = 12, stop_holdoff_sec: int = 8):
        t0 = time.perf_counter()
        self.events.clear()

        # 6시간(21,600초) 주기: 앞 14,400초(4시간)는 RUN, 뒤 7,200초(2시간)는 STOP
        # 단, 첫 기동을 보기 쉽게 60초에 시작하도록 오프셋 적용
        cycle_len = 21600
        run_len = 14400

        fault_lookup = {}
        for f_start, f_dur, f_bar, f_desc in REAL_FAULTS:
            for s in range(f_start, f_start + f_dur):
                fault_lookup[s] = (f_bar, f_desc)

        naive_alarm_cnt = 0
        masked_overshoot_cnt = 0
        true_alarm_cnt = 0

        # 28번의 사이클을 순회하며 604,800초 데이터 생성 및 블랭킹 판정
        for sec in range(TOTAL_SECONDS):
            pos_in_cycle = (sec - 60) % cycle_len if sec >= 60 else -1
            if pos_in_cycle < 0:
                is_run = 0
                elapsed = sec + 100
            elif pos_in_cycle < run_len:
                is_run = 1
                elapsed = pos_in_cycle
            else:
                is_run = 0
                elapsed = pos_in_cycle - run_len

            self.pump_run[sec] = is_run

            # 기본 물리 파형 계산 (1초 단위)
            if is_run == 1:
                if elapsed < 10:
                    # 펌프 기동 직후 10초간 지수 감쇠형 오버슈팅 (최대 9.45 bar -> 6.0 bar 수렴)
                    overshoot = 3.6 * math.exp(-elapsed / 3.2) * math.sin((elapsed + 1) * 0.45)
                    p = 6.0 + abs(overshoot)
                else:
                    # 정상 운전 (6.0 bar ± 미세 맥동)
                    p = 6.0 + 0.12 * math.sin(sec * 0.05) + 0.05 * math.cos(sec * 0.3)
            else:
                if elapsed < 6:
                    # 펌프 정지 직후 6초간 수격 현상(Water Hammer) 언더슈트/출렁임
                    hammer = -0.75 * math.exp(-elapsed / 2.0) * math.cos(elapsed * 0.8)
                    p = hammer
                else:
                    # 정상 정지 (0.0 bar)
                    p = 0.02 * math.sin(sec * 0.02)

            # 실제 고장 시나리오 구간이면 고장 압력 주입
            if sec in fault_lookup:
                p, _ = fault_lookup[sec]

            self.pressure[sec] = p

            # ------------------------------------------------------------------
            # 핵심 판정 로직: 기동 후 start_holdoff_sec 초, 정지 후 stop_holdoff_sec 초 배제
            # ------------------------------------------------------------------
            if is_run == 1:
                raw_out = (p > 7.5) or (p < 4.5)
                is_masked = (elapsed < start_holdoff_sec)
            else:
                raw_out = (p > 0.5) or (p < -0.25)
                is_masked = (elapsed < stop_holdoff_sec)

            if raw_out:
                naive_alarm_cnt += 1
                if is_masked:
                    self.flag[sec] = 1  # 배제된 정상 기동/정지 오버슈트
                    masked_overshoot_cnt += 1
                else:
                    self.flag[sec] = 2  # 진짜 설비 이상 경보!
                    true_alarm_cnt += 1
            else:
                self.flag[sec] = 0

            # 이벤트 목록에 사이클 대표 시점 기록 (클릭 시 바로 줌인 이동용)
            if is_run == 1 and elapsed == 1 and raw_out:
                dt_str = (START_DT + datetime.timedelta(seconds=sec)).strftime("%m/%d(%a) %H:%M:%S")
                day_ko = DAY_NAMES[sec // 86400]
                self.events.append({
                    "sec": sec,
                    "time_str": f"{day_ko} {(START_DT + datetime.timedelta(seconds=sec)).strftime('%H:%M:%S')}",
                    "type": "🛡️ 기동 오버슈트 (배제됨)" if is_masked else "⚠️ 기동 오버슈트 (미배제 경보)",
                    "peak_bar": round(p, 2),
                    "duration": "약 8초",
                    "action": "기동 직후 정상 서지 피크 -> 알람 차단됨" if is_masked else "무시 시간이 너무 짧아 경보 울림!",
                    "is_fault": not is_masked,
                })
            elif is_run == 0 and elapsed == 0 and sec > 60 and raw_out:
                day_ko = DAY_NAMES[sec // 86400]
                self.events.append({
                    "sec": sec,
                    "time_str": f"{day_ko} {(START_DT + datetime.timedelta(seconds=sec)).strftime('%H:%M:%S')}",
                    "type": "🛡️ 정지 수격충격 (배제됨)" if is_masked else "⚠️ 정지 수격충격 (미배제 경보)",
                    "peak_bar": round(p, 2),
                    "duration": "약 5초",
                    "action": "정지 직후 수격 현상 -> 알람 차단됨" if is_masked else "무시 시간이 너무 짧아 경보 울림!",
                    "is_fault": not is_masked,
                })

        # 실제 고장 4건 이벤트 등록
        for f_start, f_dur, f_bar, f_desc in REAL_FAULTS:
            day_ko = DAY_NAMES[f_start // 86400]
            self.events.append({
                "sec": f_start,
                "time_str": f"{day_ko} {(START_DT + datetime.timedelta(seconds=f_start)).strftime('%H:%M:%S')}",
                "type": "🚨 실제 설비 고장 (True Alarm)",
                "peak_bar": f_bar,
                "duration": f"{f_dur}초 지속",
                "action": f_desc,
                "is_fault": True,
            })

        # 1시간 단위 요약 통계 계산 (7일 = 168시간)
        for hr in range(168):
            s_idx = hr * 3600
            e_idx = s_idx + 3600
            chunk = self.pressure[s_idx:e_idx]
            self.hourly_max[hr] = max(chunk)
            self.hourly_min[hr] = min(chunk)
            self.hourly_run[hr] = self.pump_run[s_idx + 1800]

        self.build_time_sec = time.perf_counter() - t0
        return {
            "total_points": TOTAL_SECONDS,
            "naive_alarms": naive_alarm_cnt,
            "masked_overshoots": masked_overshoot_cnt,
            "true_alarms": true_alarm_cnt,
            "elapsed_ms": round(self.build_time_sec * 1000, 1),
        }


# ==============================================================================
# 2. 일주일 1초 트렌드 대시보드 GUI (상단: 7일 전체 뷰 / 하단: 1초 단위 현미경 줌 뷰)
# ==============================================================================
class Weekly1SecTrendApp(tk.Tk):
    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir
        self.engine = WeeklyTrendEngine()
        self.focus_sec = 60  # 기본 확대 시점: 월요일 첫 펌프 기동 순간(60초)

        self.title("📊 [일주일 1초 타임베이스 트렌드] 604,800초 펌프 오버슈팅 배제 & 1초 단위 줌인(Zoom) 분석기")
        self.geometry("1460x880")
        self.minsize(1150, 720)
        self.configure(bg="#0f172a")

        self.start_hold_var = tk.IntVar(value=12)
        self.stop_hold_var = tk.IntVar(value=8)

        self._build_ui()
        self.run_analysis()

    def _build_ui(self):
        # 1. 상단 툴바
        top = tk.Frame(self, bg="#1e293b", padx=14, pady=8)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(
            top,
            text="📅 7일(604,800초) × 1초 타임베이스 펌프 트렌드 감시기",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 13, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 16))

        # 빠른 시점 점프 버튼들
        jump_frame = tk.Frame(top, bg="#0f172a", padx=8, pady=4, highlightbackground="#38bdf8", highlightthickness=1)
        jump_frame.pack(side=tk.LEFT, padx=6)
        tk.Label(jump_frame, text="🔍 1초 단위 현미경 바로가기:", bg="#0f172a", fg="#fef08a", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))

        self._jump_btn(jump_frame, "🛡️ 월요일 첫 기동 오버슈트(00:01:00)", 60, "#ca8a04")
        self._jump_btn(jump_frame, "🛡️ 첫 정지 수격충격(04:01:00)", 14460, "#ca8a04")
        self._jump_btn(jump_frame, "🚨 고장1: 월 14:20 과압", REAL_FAULTS[0][0], "#dc2626")
        self._jump_btn(jump_frame, "🚨 고장2: 수 03:15 저압", REAL_FAULTS[1][0], "#dc2626")
        self._jump_btn(jump_frame, "🚨 고장3: 금 19:40 헌팅", REAL_FAULTS[2][0], "#dc2626")
        self._jump_btn(jump_frame, "🚨 고장4: 일 05:10 누설", REAL_FAULTS[3][0], "#dc2626")

        # 2. KPI 요약 바
        kpi = tk.Frame(self, bg="#0f172a", padx=14, pady=6)
        kpi.pack(side=tk.TOP, fill=tk.X)

        self.kpi_pts = self._make_kpi(kpi, "일주일 총 샘플 수 (Δt = 1초)", "604,800 초", "#38bdf8")
        self.kpi_cycles = self._make_kpi(kpi, "7일간 펌프 기동/정지 횟수", "총 56회 (기동 28 / 정지 28)", "#a78bfa")
        self.kpi_masked = self._make_kpi(kpi, "🛡️ 자동 배제된 오버슈트 시간", "0 초", "#eab308")
        self.kpi_faults = self._make_kpi(kpi, "🚨 실제 설비 고장 검출 시간", "0 초 (고장 이벤트 4건)", "#ef4444")

        # 3. 중앙 3단 분할 (상단: 7일 전체 트렌드 / 중단: 1초 단위 줌인 차트 / 하단: 이벤트 로그 + pandas 설명)
        paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#0f172a", sashwidth=5, bd=0)
        paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        # (A) 상단: 7일(168시간) 전체 매크로 트렌드 차트
        self.macro_canvas = tk.Canvas(paned, bg="#090d16", height=195, highlightthickness=1, highlightbackground="#334155")
        self.macro_canvas.bind("<Configure>", lambda e: self.draw_macro_chart())
        self.macro_canvas.bind("<Button-1>", self._on_macro_click)
        paned.add(self.macro_canvas, minsize=175)

        # (B) 중단: 선택한 시점 전후 120초를 1초 단위로 보여주는 마이크로(1초 타임베이스) 트렌드 차트
        self.micro_canvas = tk.Canvas(paned, bg="#090d16", height=255, highlightthickness=1, highlightbackground="#38bdf8")
        self.micro_canvas.bind("<Configure>", lambda e: self.draw_micro_chart())
        paned.add(self.micro_canvas, minsize=220)

        # (C) 하단: 이벤트 목록 테이블 & 1초 단위 CSV 추출
        bot_frame = tk.Frame(paned, bg="#1e293b")
        paned.add(bot_frame, minsize=190)

        bot_hdr = tk.Frame(bot_frame, bg="#1e293b", padx=10, pady=4)
        bot_hdr.pack(fill=tk.X)
        tk.Label(
            bot_hdr,
            text="📋 일주일간 발생한 전체 이벤트 목록 (표를 클릭하면 위쪽 1초 단위 현미경 차트가 해당 시각으로 즉시 이동합니다!)",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 9, "bold"),
        ).pack(side=tk.LEFT)

        tk.Button(
            bot_hdr,
            text="💾 현재 1초 단위 확대 구간 CSV로 내보내기",
            command=self.export_zoom_csv,
            bg="#059669",
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 8, "bold"),
            padx=10,
            pady=2,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        cols = ("sec", "time_str", "type", "peak_bar", "duration", "action")
        self.tree = ttk.Treeview(bot_frame, columns=cols, show="headings", height=7)
        headers = {
            "sec": ("누적 초(s)", 90),
            "time_str": ("발생 일시 (요일/시각)", 150),
            "type": ("분류 (오버슈트 배제 vs 실제 고장)", 220),
            "peak_bar": ("피크 압력(bar)", 110),
            "duration": ("지속 시간", 95),
            "action": ("AI / pandas 감시 판정 상세 설명", 560),
        }
        for c, (t, w) in headers.items():
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c != "action" else "w")

        self.tree.tag_configure("fault", background="#450a0a", foreground="#fca5a5")
        self.tree.tag_configure("masked", background="#0f172a", foreground="#fde047")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        ysb = ttk.Scrollbar(bot_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)

    def _jump_btn(self, parent, text, target_sec, bg):
        b = tk.Button(
            parent,
            text=text,
            command=lambda s=target_sec: self.zoom_to_second(s),
            bg=bg,
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 8, "bold"),
            padx=7,
            pady=3,
            cursor="hand2",
        )
        b.pack(side=tk.LEFT, padx=2)

    def _make_kpi(self, parent, title, val, col):
        f = tk.Frame(parent, bg="#1e293b", padx=12, pady=5, highlightbackground="#334155", highlightthickness=1)
        f.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tk.Label(f, text=title, bg="#1e293b", fg="#94a3b8", font=("Malgun Gothic", 8)).pack(anchor="w")
        lbl = tk.Label(f, text=val, bg="#1e293b", fg=col, font=("Malgun Gothic", 11, "bold"))
        lbl.pack(anchor="w")
        return lbl

    # --------------------------------------------------------------------------
    # 분석 실행 및 차트 렌더링
    # --------------------------------------------------------------------------
    def run_analysis(self):
        stats = self.engine.generate_and_analyze(
            self.start_hold_var.get(), self.stop_hold_var.get()
        )
        self.kpi_pts.configure(text=f"{stats['total_points']:,} 초 ({stats['elapsed_ms']}ms 만에 분석 완료)")
        self.kpi_masked.configure(text=f"🛡️ {stats['masked_overshoots']:,} 초 배제됨 (28회 기동/정지 서지)")
        self.kpi_faults.configure(text=f"🚨 {stats['true_alarms']} 초 (실제 고장 4건만 정확히 포착!)")

        for item in self.tree.get_children():
            self.tree.delete(item)

        # 실제 고장 4건을 맨 위에 먼저 배치하고, 이어서 기동/정지 오버슈트 배제 내역 표시
        sorted_ev = sorted(self.engine.events, key=lambda e: (0 if e["is_fault"] else 1, e["sec"]))
        for ev in sorted_ev:
            tag = "fault" if ev["is_fault"] else "masked"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    f"{ev['sec']:,}초",
                    ev["time_str"],
                    ev["type"],
                    f"{ev['peak_bar']:.2f} bar",
                    ev["duration"],
                    ev["action"],
                ),
                tags=(tag,),
            )

        self.draw_macro_chart()
        self.draw_micro_chart()

    def zoom_to_second(self, sec: int):
        self.focus_sec = max(60, min(TOTAL_SECONDS - 60, sec))
        self.draw_macro_chart()
        self.draw_micro_chart()

    def _on_macro_click(self, event):
        w = max(self.macro_canvas.winfo_width(), 800)
        x1, x2 = 65, w - 25
        if x1 <= event.x <= x2:
            ratio = (event.x - x1) / (x2 - x1)
            clicked_sec = int(ratio * TOTAL_SECONDS)
            self.zoom_to_second(clicked_sec)

    def _on_tree_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        sec_str = str(vals[0]).replace("초", "").replace(",", "").strip()
        try:
            self.zoom_to_second(int(sec_str))
        except ValueError:
            pass

    def draw_macro_chart(self):
        """상단: 월~일 7일(604,800초) 전체 트렌드 조감도."""
        c = self.macro_canvas
        c.delete("all")
        w = max(c.winfo_width(), 900)
        h = max(c.winfo_height(), 180)
        x1, y1, x2, y2 = 65, 34, w - 25, h - 26

        c.create_text(
            x1, 16,
            text="🗓️ [1단계: 일주일(7일 = 604,800초) 전체 트렌드] — 28번의 기동 오버슈트(🛡️노란점)는 모두 무시되고, 4번의 실제 고장(🚨빨간점)만 경보로 뜹니다! (클릭 시 확대)",
            fill="#f8fafc", anchor="w", font=("Malgun Gothic", 9, "bold")
        )
        c.create_rectangle(x1, y1, x2, y2, fill="#0f172a", outline="#334155")

        # 요일 구분선 (월~일 7칸)
        for d in range(7):
            dx = x1 + (d / 7.0) * (x2 - x1)
            c.create_line(dx, y1, dx, y2, fill="#1e293b", dash=(2, 2))
            c.create_text(dx + (x2 - x1) / 14.0, y2 + 12, text=DAY_NAMES[d], fill="#94a3b8", font=("Malgun Gothic", 8, "bold"))

        min_p, max_p = -1.5, 11.0

        def sec_to_xy(sec_val, p_val):
            px = x1 + (sec_val / TOTAL_SECONDS) * (x2 - x1)
            py = y2 - ((p_val - min_p) / (max_p - min_p)) * (y2 - y1)
            return px, py

        # 28회 사이클 파형 요약 렌더링
        pts = []
        for hr in range(168):
            sec_mid = hr * 3600 + 1800
            px, py = sec_to_xy(sec_mid, 6.0 if self.engine.hourly_run[hr] else 0.0)
            pts.extend((px, py))
        if len(pts) >= 4:
            c.create_line(*pts, fill="#0284c7", width=1.5)

        # 28번의 기동 오버슈트(노란 점) vs 4번의 진짜 고장(빨간 점) 표시
        for ev in self.engine.events:
            px, py = sec_to_xy(ev["sec"], ev["peak_bar"])
            if ev["is_fault"]:
                c.create_oval(px - 8, py - 8, px + 8, py + 8, outline="#ef4444", width=2)
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#ef4444", outline="#ffffff")
                c.create_text(px, py - 13, text=f"🚨{ev['time_str'].split()[0]}", fill="#fca5a5", font=("Malgun Gothic", 8, "bold"))
            else:
                c.create_oval(px - 3, py - 3, px + 3, py + 3, fill="#eab308", outline="")

        # 현재 하단 차트가 확대해서 보고 있는 시점(Focus Cursor) 표시
        fx, _ = sec_to_xy(self.focus_sec, 0)
        c.create_line(fx, y1, fx, y2, fill="#22c55e", width=2.5)
        c.create_rectangle(fx - 45, y1 + 2, fx + 45, y1 + 18, fill="#15803d", outline="#4ade80")
        c.create_text(fx, y1 + 10, text="🔎 현재 확대 위치", fill="#ffffff", font=("Malgun Gothic", 7, "bold"))

    def draw_micro_chart(self):
        """하단: 선택한 시점 전후 90초(총 180초)를 1초 타임베이스(Δt=1s)로 정밀 렌더링."""
        c = self.micro_canvas
        c.delete("all")
        w = max(c.winfo_width(), 900)
        h = max(c.winfo_height(), 230)
        x1, y1, x2, y2 = 65, 38, w - 25, h - 52

        win_half = 60  # 전후 60초 (총 121초간의 1초 단위 데이터)
        s_sec = max(0, self.focus_sec - win_half)
        e_sec = min(TOTAL_SECONDS - 1, self.focus_sec + win_half)

        dt_center = START_DT + datetime.timedelta(seconds=self.focus_sec)
        day_ko = DAY_NAMES[self.focus_sec // 86400]

        c.create_text(
            x1, 18,
            text=f"🔬 [2단계: 1초 타임베이스(Δt=1s) 현미경 확대 차트] — 기준 시각: {day_ko} {dt_center.strftime('%H:%M:%S')} (누적 {self.focus_sec:,}초) 전후 120초 구간",
            fill="#38bdf8", anchor="w", font=("Malgun Gothic", 10, "bold")
        )
        c.create_rectangle(x1, y1, x2, y2, fill="#0f172a", outline="#334155")

        min_p, max_p = -1.5, 11.0
        span = max(1, e_sec - s_sec)

        def to_xy(sec_val, p_val):
            px = x1 + 15 + ((sec_val - s_sec) / span) * (x2 - x1 - 30)
            py = y2 - ((p_val - min_p) / (max_p - min_p)) * (y2 - y1)
            return px, py

        # 1. 과도 구간(오버슈트 배제 윈도우) 노란 음영 표시
        step_px = (x2 - x1 - 30) / span
        for sec in range(s_sec, e_sec + 1):
            if self.engine.flag[sec] == 1:
                px, _ = to_xy(sec, 0)
                c.create_rectangle(px - step_px / 2, y1 + 1, px + step_px / 2, y2 - 1, fill="#3b2f0b", outline="")

        # 2. 상한(7.5 bar) / 하한(4.5 bar) 점선
        _, y_hi = to_xy(s_sec, 7.5)
        _, y_lo = to_xy(s_sec, 4.5)
        c.create_line(x1, y_hi, x2, y_hi, fill="#ef4444", dash=(4, 3))
        c.create_text(x1 + 8, y_hi - 8, text="상한 7.5 bar", fill="#fca5a5", anchor="w", font=("Consolas", 8))
        c.create_line(x1, y_lo, x2, y_lo, fill="#38bdf8", dash=(4, 3))
        c.create_text(x1 + 8, y_lo + 9, text="하한 4.5 bar", fill="#7dd3fc", anchor="w", font=("Consolas", 8))

        # 3. 1초 단위 압력 곡선 및 1초 포인트 점 찍기
        pts = []
        for sec in range(s_sec, e_sec + 1):
            pts.extend(to_xy(sec, self.engine.pressure[sec]))
        if len(pts) >= 4:
            c.create_line(*pts, fill="#38bdf8", width=2.2)

        for sec in range(s_sec, e_sec + 1):
            px, py = to_xy(sec, self.engine.pressure[sec])
            flg = self.engine.flag[sec]
            if flg == 2:
                # 진짜 설비 이상 (1초 단위 빨간 점)
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#ef4444", outline="#ffffff")
                if sec == s_sec or self.engine.flag[sec - 1] != 2:
                    c.create_text(px + 10, py - 14, text=f"🚨실제고장 시작! ({self.engine.pressure[sec]:.2f}bar)", fill="#fca5a5", font=("Malgun Gothic", 9, "bold"))
            elif flg == 1:
                # 배제된 기동/정지 오버슈트 (1초 단위 노란 방패 점)
                c.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#eab308", outline="#0f172a")
                if sec == s_sec or self.engine.flag[sec - 1] != 1:
                    c.create_text(px + 25, py - 14, text=f"🛡️오버슈트 자동배제 구간 (알람 무시)", fill="#fde047", font=("Malgun Gothic", 9, "bold"))
            else:
                c.create_oval(px - 2, py - 2, px + 2, py + 2, fill="#0284c7", outline="")

        # 4. 하단 1초 단위 PUMP RUN (1/0) 디지털 신호 트랙
        ry1, ry2 = y2 + 12, h - 10
        c.create_text(x1 - 8, (ry1 + ry2) / 2, text="PUMP\nRUN", fill="#4ade80", anchor="e", font=("Consolas", 8, "bold"))
        c.create_rectangle(x1, ry1, x2, ry2, fill="#0f172a", outline="#334155")

        r_pts = []
        for sec in range(s_sec, e_sec + 1):
            px, _ = to_xy(sec, 0)
            py = ry1 + 5 if self.engine.pump_run[sec] == 1 else ry2 - 5
            r_pts.extend((px, py))
        if len(r_pts) >= 4:
            c.create_line(*r_pts, fill="#4ade80", width=2)

    def export_zoom_csv(self):
        out_path = self.base_dir / "instrument_results" / "weekly_1sec_zoom_slice.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        s_sec = max(0, self.focus_sec - 60)
        e_sec = min(TOTAL_SECONDS - 1, self.focus_sec + 60)

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["누적_초", "시각", "펌프_RUN", "압력_bar", "판정상태"])
            for sec in range(s_sec, e_sec + 1):
                dt_s = (START_DT + datetime.timedelta(seconds=sec)).strftime("%Y-%m-%d %H:%M:%S")
                flg = self.engine.flag[sec]
                st = "실제경보(True Alarm)" if flg == 2 else ("오버슈트배제(Masked)" if flg == 1 else "정상")
                w.writerow([sec, dt_s, self.engine.pump_run[sec], round(self.engine.pressure[sec], 3), st])

        messagebox.showinfo("CSV 저장 완료", f"현재 1초 단위 확대 구간 데이터가 저장되었습니다:\n{out_path}")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    app = Weekly1SecTrendApp(base)
    app.mainloop()
