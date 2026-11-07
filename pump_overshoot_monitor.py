"""
===============================================================================
[산업용 펌프 감시 AI/데이터 분석] 펌프 기동(Run) / 정지(Stop) 오버슈팅 자동 배제 감시기
===============================================================================
핵심 원리 (Transient Blanking / Hold-Off Window):
1. 펌프 기동(0 -> 1) 직후 N초(예: 5초) 동안 발생하는 초기 압력/전류 오버슈팅(Surge/Inrush)은
   물리적으로 당연한 현상이므로 '과도 구간(Transient Mask)'으로 지정하여 경보에서 자동 배제합니다.
2. 펌프 정지(1 -> 0) 직후 M초(예: 4초) 동안 발생하는 수격 현상(Water Hammer / 언더슈트)도
   경보에서 자동 배제합니다.
3. 안정화 시간(Hold-off)이 지난 '정상 운전 구간(Steady-State)'에서 발생하는 이상 피크나
   배관 막힘/공동 현상(Cavitation)만 정확히 '🚨 실제 설비 이상(True Alarm)'으로 잡아냅니다!

실행 방법:
    python pump_overshoot_monitor.py
===============================================================================
"""

import csv
import math
import random
import tkinter as tk
from tkinter import ttk
from pathlib import Path

# pandas가 설치된 환경에서는 pandas 벡터 연산 코드를 그대로 보여주고,
# 미설치 환경에서도 즉시 동작하도록 하이브리드 처리
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ==============================================================================
# 1. 현실적인 펌프 운전 로그 CSV 생성 (기동 오버슈트 + 정지 언더슈트 + 실제 고장 포함)
# ==============================================================================
def generate_pump_log_csv(csv_path: Path) -> list[dict]:
    rng = random.Random(42)
    rows = []

    # 80초 시나리오:
    # - 01~09초: 펌프 정지 상태 (0 bar, 4.0 mA)
    # - 10초   : 펌프 1차 기동(RUN)! -> 10~13초 동안 초기 오버슈팅 발생 (최대 9.4 bar까지 치솟았다가 6.0 bar로 안정화) -> [정상 오버슈트: 배제 대상!]
    # - 14~34초: 안정 운전 구간 (약 6.0 bar)
    #   * 단, 24~25초에 배관 이물질로 인한 비정상 과압 스파이크(9.1 bar) 발생! -> [🚨 진짜 경보 대상!]
    # - 35초   : 펌프 1차 정지(STOP)! -> 35~37초 동안 수격 현상 언더슈트(-0.6 bar) 발생 -> [정상 정지 충격: 배제 대상!]
    # - 38~49초: 정지 상태 유지
    # - 50초   : 펌프 2차 기동(RUN)! -> 50~53초 초기 기동 오버슈팅(9.2 bar) -> [정상 오버슈트: 배제 대상!]
    # - 54~80초: 안정 운전 구간
    #   * 단, 66~68초에 임펠러 공회전/에어포켓으로 압력 급락(2.1 bar) 발생! -> [🚨 진짜 경보 대상!]

    for sec in range(1, 81):
        pump_run = 1 if (10 <= sec <= 34 or 50 <= sec <= 80) else 0

        if pump_run == 1:
            # 기동 후 경과 시간
            elapsed_run = (sec - 10) if sec < 40 else (sec - 50)
            if elapsed_run == 0:
                pressure = 8.9   # 기동 직후 서지 피크
                current_ma = 19.2
            elif elapsed_run == 1:
                pressure = 9.4   # 최대 오버슈트 (상한 8.0 bar 초과하지만 정상 기동 현상!)
                current_ma = 19.8
            elif elapsed_run == 2:
                pressure = 7.9
                current_ma = 16.5
            elif elapsed_run == 3:
                pressure = 6.5
                current_ma = 14.3
            else:
                # 정상 정격 운전 (6.0 bar, 13.6 mA 부근)
                pressure = 6.0 + rng.uniform(-0.15, 0.15)
                current_ma = 4.0 + (pressure / 10.0) * 16.0

            # 실제 운전 중 발생한 진짜 이상 징후 2건 주입!
            if sec in (24, 25):
                # 정상 운전 중 갑자기 배관 막힘으로 압력 급등
                pressure = 9.15
                current_ma = 18.6
            elif sec in (66, 67, 68):
                # 정상 운전 중 공동현상(Cavitation)/누수로 압력 급락
                pressure = 2.15
                current_ma = 7.4
        else:
            # 정지 상태
            elapsed_stop = sec - 35
            if 0 <= elapsed_stop <= 1:
                # 정지 직후 수격 현상(언더슈트/진동)
                pressure = -0.55 if elapsed_stop == 0 else 1.45
                current_ma = 3.2 if elapsed_stop == 0 else 6.3
            elif elapsed_stop == 2:
                pressure = 0.45
                current_ma = 4.7
            else:
                pressure = 0.0 + rng.uniform(-0.03, 0.03)
                current_ma = 4.0 + rng.uniform(-0.05, 0.05)

        rows.append({
            "sec": sec,
            "pump_run": pump_run,
            "pressure_bar": round(pressure, 3),
            "current_ma": round(current_ma, 2),
        })

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["sec", "pump_run", "pressure_bar", "current_ma"])
        writer.writeheader()
        writer.writerows(rows)

    return rows


# ==============================================================================
# 2. 펌프 기동/정지 과도 구간(Overshoot) 배제 감시 알고리즘
# ==============================================================================
def analyze_pump_with_blanking(
    rows: list[dict],
    start_holdoff_sec: int = 5,
    stop_holdoff_sec: int = 4,
    run_high_limit: float = 7.5,
    run_low_limit: float = 4.5,
    stop_high_limit: float = 0.4,
) -> list[dict]:
    """
    - start_holdoff_sec: 펌프 기동(0->1) 후 오버슈팅을 무시할 블랭킹 시간(초)
    - stop_holdoff_sec : 펌프 정지(1->0) 후 수격/언더슈트를 무시할 블랭킹 시간(초)
    """
    results = []
    last_start_sec = -999
    last_stop_sec = -999
    prev_run = rows[0]["pump_run"] if rows else 0

    for r in rows:
        sec = int(r["sec"])
        run = int(r["pump_run"])
        p = float(r["pressure_bar"])
        ma = float(r["current_ma"])

        # 1) Rising Edge (기동 순간: 0 -> 1) & Falling Edge (정지 순간: 1 -> 0) 검출
        if run == 1 and prev_run == 0:
            last_start_sec = sec
        elif run == 0 and prev_run == 1:
            last_stop_sec = sec
        prev_run = run

        # 2) 단순 임계치 판정 (오버슈트를 배제하지 않았을 때 울리는 기존 단순 경보)
        if run == 1:
            naive_alarm = (p > run_high_limit) or (p < run_low_limit)
        else:
            naive_alarm = (p > stop_high_limit) or (p < -0.2)

        # 3) 과도 구간(Transient Window) 여부 판정
        is_start_transient = (run == 1) and (0 <= (sec - last_start_sec) < start_holdoff_sec)
        is_stop_transient = (run == 0) and (0 <= (sec - last_stop_sec) < stop_holdoff_sec)
        is_masked = is_start_transient or is_stop_transient

        # 4) 스마트 판정: 과도 구간이 아닐 때 발생한 이탈만 진짜 경보(True Alarm)로 인정!
        true_alarm = naive_alarm and (not is_masked)

        if true_alarm:
            if p > run_high_limit:
                status = "🚨 실제 이상 (정격중 과압)"
                reason = f"기동 안정화 완료 후 비정상 과압 ({p:.2f} > {run_high_limit} bar)"
            elif p < run_low_limit:
                status = "🚨 실제 이상 (정격중 저압/공동)"
                reason = f"기동 안정화 완료 후 비정상 압력 급락 ({p:.2f} < {run_low_limit} bar)"
            else:
                status = "🚨 실제 이상 (정지중 잔압)"
                reason = f"정지 안정화 완료 후 비정상 압력 감지 ({p:.2f} bar)"
        elif naive_alarm and is_start_transient:
            status = "🛡️ 정상 기동 오버슈트 (배제됨)"
            reason = f"펌프 기동 후 {sec - last_start_sec + 1}초차 초기 서지 피크 -> 경보 자동 무시"
        elif naive_alarm and is_stop_transient:
            status = "🛡️ 정상 정지 수격충격 (배제됨)"
            reason = f"펌프 정지 후 {sec - last_stop_sec + 1}초차 압력 출렁임 -> 경보 자동 무시"
        else:
            status = "✅ 정상 운전" if run == 1 else "⚪ 정상 대기(정지)"
            reason = "안정 상태 정상 범위"

        results.append({
            "sec": sec,
            "pump_run": run,
            "pressure_bar": p,
            "current_ma": ma,
            "naive_alarm": naive_alarm,
            "is_masked": is_masked,
            "true_alarm": true_alarm,
            "status": status,
            "reason": reason,
        })

    return results


# ==============================================================================
# 3. pandas 핵심 레시피 문자열 (화면에 바로 표시 및 복사 가능)
# ==============================================================================
PANDAS_RECIPE_CODE = """# [핵심 pandas 코드] 펌프 기동(Run) / 정지(Stop) 오버슈팅 배제 감시 레시피
import pandas as pd

df = pd.read_csv("instrument_results/pump_operation_log.csv")

# 1. 펌프 상태 변화(Edge) 검출: diff()가 +1이면 기동(Run), -1이면 정지(Stop)
df["state_change"] = df["pump_run"].diff().fillna(0)

# 2. 각 운전/정지 사이클 번호(group)를 매기고, 상태가 바뀐 뒤 몇 초가 지났는지(elapsed_sec) 계산
df["cycle_id"] = (df["state_change"] != 0).cumsum()
df["elapsed_sec"] = df.groupby("cycle_id").cumcount()

# 3. 과도 구간(Transient Mask) 정의: 기동 후 5초 미만 또는 정지 후 4초 미만은 True
df["transient_mask"] = (
    ((df["pump_run"] == 1) & (df["elapsed_sec"] < 5)) |
    ((df["pump_run"] == 0) & (df["elapsed_sec"] < 4))
)

# 4. 원시 임계치 이탈 여부 (운전 중 4.5~7.5 bar 이탈)
df["raw_out_of_bounds"] = (
    ((df["pump_run"] == 1) & ~df["pressure_bar"].between(4.5, 7.5)) |
    ((df["pump_run"] == 0) & ~df["pressure_bar"].between(-0.2, 0.4))
)

# 5. 최종 실제 경보(True Alarm): 임계치를 벗어났지만 과도 구간(오버슈트)이 아닌 경우만 선택!
df["true_alarm"] = df["raw_out_of_bounds"] & (~df["transient_mask"])
print(df[df["true_alarm"]])  # 가짜 기동 오버슈트는 모두 빠지고 진짜 고장 행만 출력됩니다!
"""


# ==============================================================================
# 4. 시각화 대시보드 GUI (오버슈트 배제 구간 노란 음영 vs 실제 경보 빨간 점)
# ==============================================================================
class PumpOvershootMonitorApp(tk.Tk):
    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir
        self.csv_path = base_dir / "instrument_results" / "pump_operation_log.csv"
        self.raw_rows = generate_pump_log_csv(self.csv_path)
        self.results = []

        self.title("🛡️ [펌프 오버슈팅 배제 감시기] Pump Run/Stop 과도 구간 자동 마스킹 & 이상 감시 대시보드")
        self.geometry("1420x860")
        self.minsize(1100, 700)
        self.configure(bg="#0f172a")

        self.start_hold_var = tk.IntVar(value=5)
        self.stop_hold_var = tk.IntVar(value=4)

        self._build_ui()
        self.recalculate()

    def _build_ui(self):
        # 상단 컨트롤 바
        top = tk.Frame(self, bg="#1e293b", padx=14, pady=10)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(
            top,
            text="🛡️ 펌프 기동/정지 오버슈팅 자동 배제(Blanking) 감시 시스템",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 13, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 20))

        # 기동/정지 배제 시간(초) 실시간 조절 스핀박스/슬라이더
        ctrl = tk.Frame(top, bg="#0f172a", padx=10, pady=4, highlightbackground="#38bdf8", highlightthickness=1)
        ctrl.pack(side=tk.LEFT)

        tk.Label(ctrl, text="⏱️ 기동(Run) 후 오버슈트 무시 시간(초):", bg="#0f172a", fg="#fef08a", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT)
        s1 = tk.Scale(
            ctrl, from_=0, to=10, orient=tk.HORIZONTAL, variable=self.start_hold_var,
            command=lambda _: self.recalculate(), bg="#0f172a", fg="#ffffff", highlightthickness=0, length=110
        )
        s1.pack(side=tk.LEFT, padx=(4, 14))

        tk.Label(ctrl, text="⏱️ 정지(Stop) 후 수격충격 무시 시간(초):", bg="#0f172a", fg="#fef08a", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT)
        s2 = tk.Scale(
            ctrl, from_=0, to=10, orient=tk.HORIZONTAL, variable=self.stop_hold_var,
            command=lambda _: self.recalculate(), bg="#0f172a", fg="#ffffff", highlightthickness=0, length=110
        )
        s2.pack(side=tk.LEFT, padx=4)

        tk.Button(
            top,
            text="⚠️ 비교체험: 무시시간 0초로 끄기 (가짜경보 폭주)",
            command=self._set_zero_blanking,
            bg="#dc2626",
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 9, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            top,
            text="🛡️ 권장 설정 (기동 5초 / 정지 4초 배제)",
            command=self._set_recommended_blanking,
            bg="#059669",
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 9, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=4)

        # KPI 요약 카드
        kpi_bar = tk.Frame(self, bg="#0f172a", padx=14, pady=6)
        kpi_bar.pack(side=tk.TOP, fill=tk.X)

        self.card_naive = self._make_card(kpi_bar, "단순 임계치 감시 시 총 알람 수", "0 건", "#94a3b8")
        self.card_masked = self._make_card(kpi_bar, "🛡️ 자동 배제된 기동/정지 오버슈트", "0 건 (가짜경보 차단!)", "#eab308")
        self.card_true = self._make_card(kpi_bar, "🚨 최종 검출된 진짜 설비 이상", "0 건", "#ef4444")

        # 메인 상하 분할
        paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#0f172a", sashwidth=5, bd=0)
        paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        # 상단: 시계열 파형 그래프 (펌프 RUN 신호 + 압력 파형 + 노란색 배제 구간 + 빨간색 진짜 경보)
        self.canvas = tk.Canvas(paned, bg="#090d16", height=370, highlightthickness=1, highlightbackground="#334155")
        self.canvas.bind("<Configure>", lambda e: self.draw_chart())
        paned.add(self.canvas, minsize=320)

        # 하단 좌우 분할: 왼쪽=이벤트 로그 테이블, 오른쪽=핵심 pandas 코드
        bottom_pane = tk.PanedWindow(paned, orient=tk.HORIZONTAL, bg="#0f172a", sashwidth=5, bd=0)
        paned.add(bottom_pane, minsize=230)

        # 왼쪽 표
        tbl_frame = tk.Frame(bottom_pane, bg="#1e293b")
        cols = ("sec", "run", "bar", "ma", "status", "reason")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=10)
        spec = {
            "sec": ("시간(초)", 65),
            "run": ("펌프상태", 80),
            "bar": ("토출압력(bar)", 100),
            "ma": ("전류(mA)", 85),
            "status": ("감시 판정 결과", 190),
            "reason": ("상세 분석 사유", 360),
        }
        for c, (t, w) in spec.items():
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c != "reason" else "w")

        self.tree.tag_configure("true_alarm", background="#450a0a", foreground="#fca5a5")
        self.tree.tag_configure("masked_overshoot", background="#422006", foreground="#fde047")
        self.tree.tag_configure("normal", background="#0f172a", foreground="#94a3b8")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        bottom_pane.add(tbl_frame, minsize=680)

        # 오른쪽 pandas 레시피 코드뷰
        code_frame = tk.Frame(bottom_pane, bg="#090d16")
        tk.Label(
            code_frame,
            text="💻 실무 pandas 구현 코드 (diff + groupby cumcount 마스킹 기법)",
            bg="#1e293b",
            fg="#38bdf8",
            anchor="w",
            padx=10,
            pady=4,
            font=("Malgun Gothic", 9, "bold"),
        ).pack(fill=tk.X)
        txt = tk.Text(code_frame, bg="#090d16", fg="#e2e8f0", font=("Consolas", 9), relief=tk.FLAT, padx=8, pady=6)
        txt.insert("1.0", PANDAS_RECIPE_CODE)
        txt.pack(fill=tk.BOTH, expand=True)
        bottom_pane.add(code_frame, minsize=400)

    def _make_card(self, parent, title, val, col):
        f = tk.Frame(parent, bg="#1e293b", padx=14, pady=6, highlightbackground="#334155", highlightthickness=1)
        f.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tk.Label(f, text=title, bg="#1e293b", fg="#cbd5e1", font=("Malgun Gothic", 9)).pack(anchor="w")
        lbl = tk.Label(f, text=val, bg="#1e293b", fg=col, font=("Malgun Gothic", 12, "bold"))
        lbl.pack(anchor="w")
        return lbl

    def _set_zero_blanking(self):
        self.start_hold_var.set(0)
        self.stop_hold_var.set(0)
        self.recalculate()

    def _set_recommended_blanking(self):
        self.start_hold_var.set(5)
        self.stop_hold_var.set(4)
        self.recalculate()

    def recalculate(self):
        s_hold = self.start_hold_var.get()
        e_hold = self.stop_hold_var.get()
        self.results = analyze_pump_with_blanking(self.raw_rows, s_hold, e_hold)

        naive_cnt = sum(1 for r in self.results if r["naive_alarm"])
        masked_cnt = sum(1 for r in self.results if r["naive_alarm"] and r["is_masked"])
        true_cnt = sum(1 for r in self.results if r["true_alarm"])

        self.card_naive.configure(text=f"총 {naive_cnt} 건 (오버슈트 포함)")
        self.card_masked.configure(text=f"🛡️ {masked_cnt} 건 자동 배제됨 (기동/정지 과도구간)")
        self.card_true.configure(text=f"🚨 {true_cnt} 건 (24~25초 과압, 66~68초 저압)")

        # 테이블에는 이벤트(오버슈트 배제 건 + 실제 알람 건)를 우선 눈에 띄게 표시하고 나머지 표시
        for item in self.tree.get_children():
            self.tree.delete(item)

        sorted_for_table = sorted(
            self.results,
            key=lambda x: (0 if x["true_alarm"] else (1 if (x["naive_alarm"] and x["is_masked"]) else 2), x["sec"]),
        )
        for r in sorted_for_table:
            if r["true_alarm"]:
                tag = "true_alarm"
            elif r["naive_alarm"] and r["is_masked"]:
                tag = "masked_overshoot"
            else:
                tag = "normal"

            self.tree.insert(
                "",
                tk.END,
                values=(
                    f"{r['sec']}초",
                    "🟢 RUN" if r["pump_run"] else "⚪ STOP",
                    f"{r['pressure_bar']:.2f} bar",
                    f"{r['current_ma']:.1f} mA",
                    r["status"],
                    r["reason"],
                ),
                tags=(tag,),
            )

        self.draw_chart()

    def draw_chart(self):
        c = self.canvas
        c.delete("all")
        if not self.results:
            return

        w = max(c.winfo_width(), 900)
        h = max(c.winfo_height(), 340)
        x1, y1, x2, y2 = 65, 42, w - 30, h - 75

        c.create_text(
            x1, 18,
            text="📈 펌프 토출 압력(bar) 감시 파형 — 🟨 노란 음영: 기동/정지 과도 배제 구간 (🛡️ 노란점=무시된 오버슈트)  |  🔴 빨간점: 실제 설비 이상 경보!",
            fill="#f8fafc", anchor="w", font=("Malgun Gothic", 10, "bold")
        )
        c.create_rectangle(x1, y1, x2, y2, fill="#0f172a", outline="#334155")

        min_p, max_p = -1.5, 11.0
        n = len(self.results)

        def to_xy(idx, p_val):
            px = x1 + 15 + (idx / max(n - 1, 1)) * (x2 - x1 - 30)
            py = y2 - ((p_val - min_p) / (max_p - min_p)) * (y2 - y1)
            return px, py

        # 1. 과도 구간(Transient Blanking Window) 노란색 보호 영역 기둥 그리기
        step_w = (x2 - x1 - 30) / max(n - 1, 1)
        for i, r in enumerate(self.results):
            if r["is_masked"]:
                px, _ = to_xy(i, 0)
                c.create_rectangle(
                    px - step_w / 2, y1 + 1, px + step_w / 2, y2 - 1,
                    fill="#2e2308", outline=""
                )

        # 2. 운전 중 정상 상한(7.5 bar) 및 하한(4.5 bar) 가이드선
        _, y_hi = to_xy(0, 7.5)
        _, y_lo = to_xy(0, 4.5)
        c.create_line(x1, y_hi, x2, y_hi, fill="#ef4444", dash=(4, 3))
        c.create_text(x1 + 6, y_hi - 8, text="운전 상한 (7.5 bar)", fill="#fca5a5", anchor="w", font=("Malgun Gothic", 8))

        c.create_line(x1, y_lo, x2, y_lo, fill="#38bdf8", dash=(4, 3))
        c.create_text(x1 + 6, y_lo + 9, text="운전 하한 (4.5 bar)", fill="#7dd3fc", anchor="w", font=("Malgun Gothic", 8))

        # 3. 압력 곡선 그리기
        pts = []
        for i, r in enumerate(self.results):
            pts.extend(to_xy(i, r["pressure_bar"]))
        if len(pts) >= 4:
            c.create_line(*pts, fill="#38bdf8", width=2.2)

        # 4. 포인트 마킹:
        #    - 노란색 방패 점(🛡️): 오버슈트가 발생했으나 기동/정지 직후라서 똑똑하게 무시(배제)된 점
        #    - 빨간색 경보 점(🚨): 안정화 이후에 발생한 진짜 고장 점
        for i, r in enumerate(self.results):
            px, py = to_xy(i, r["pressure_bar"])
            if r["true_alarm"]:
                c.create_oval(px - 9, py - 9, px + 9, py + 9, outline="#ef4444", width=2)
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#ef4444", outline="#ffffff", width=1.5)
                c.create_text(px, py - 15, text=f"🚨{r['sec']}s({r['pressure_bar']}bar)", fill="#fca5a5", font=("Consolas", 8, "bold"))
            elif r["naive_alarm"] and r["is_masked"]:
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#eab308", outline="#0f172a", width=1.5)
                if r["pressure_bar"] > 9.0 or r["pressure_bar"] < -0.3:
                    c.create_text(px + 6, py - 12, text=f"🛡️배제됨({r['sec']}s)", fill="#fde047", font=("Malgun Gothic", 8, "bold"))

        # 5. 하단 펌프 RUN / STOP 상태 타임라인 바
        ry1, ry2 = y2 + 16, h - 14
        c.create_text(x1 - 8, (ry1 + ry2) / 2, text="PUMP\nRUN", fill="#4ade80", anchor="e", font=("Consolas", 8, "bold"))
        c.create_rectangle(x1, ry1, x2, ry2, fill="#0f172a", outline="#334155")

        run_pts = []
        for i, r in enumerate(self.results):
            px, _ = to_xy(i, 0)
            py = ry1 + 6 if r["pump_run"] == 1 else ry2 - 6
            run_pts.extend((px, py))
        if len(run_pts) >= 4:
            c.create_line(*run_pts, fill="#4ade80", width=2.5)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    app = PumpOvershootMonitorApp(base)
    app.mainloop()
