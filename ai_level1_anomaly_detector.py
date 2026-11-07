"""
===============================================================================
[Level 1 AI 예제] 산업용 계측 CSV 데이터 자동 분석 & AI 이상치(Anomaly) 탐지 리포터
===============================================================================
- 대상 데이터: instrument_results/example_01.csv (4~20mA 압력 트랜스미터 계측 데이터)
              및 시계열 연속 계측 데이터 (instrument_results/sensor_stream_log.csv 자동 생성)
- 핵심 AI 알고리즘: Isolation Forest (비지도 학습 기반 다변량 이상치 탐지) + 물리적 루프 법칙 검증
- 실행 방법:
    python ai_level1_anomaly_detector.py
  (외부 패키지 설치 여부에 상관없이 즉시 실행되며, GUI 진단 대시보드 + 리포트 CSV를 생성합니다!)
===============================================================================
"""

from __future__ import annotations

import csv
import math
import os
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Optional: scikit-learn / pandas / matplotlib가 설치되어 있으면 함께 활용하고,
# 설치되어 있지 않은 환경에서도 100% 동일하게 동작하도록 순수 파이썬 Isolation Forest 엔진 내장!
try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import IsolationForest as SklearnIsolationForest
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ==============================================================================
# 1. 순수 파이썬 Isolation Forest (iForest) 머신러닝 알고리즘 구현체
#    (scikit-learn 미설치 PC에서도 진짜 Isolation Tree 앙상블이 작동합니다)
# ==============================================================================
class PureIsolationTree:
    def __init__(self, height_limit: int, rng: random.Random):
        self.height_limit = height_limit
        self.rng = rng
        self.split_feat = None
        self.split_val = None
        self.left = None
        self.right = None
        self.size = 0
        self.is_leaf = False

    def fit(self, X: list[list[float]], current_height: int = 0):
        self.size = len(X)
        if current_height >= self.height_limit or self.size <= 1:
            self.is_leaf = True
            return self

        n_features = len(X[0])
        feat = self.rng.randrange(n_features)
        col = [row[feat] for row in X]
        min_v, max_v = min(col), max(col)

        if math.isclose(min_v, max_v):
            self.is_leaf = True
            return self

        split_v = self.rng.uniform(min_v, max_v)
        left_X = [row for row in X if row[feat] < split_v]
        right_X = [row for row in X if row[feat] >= split_v]

        if not left_X or not right_X:
            self.is_leaf = True
            return self

        self.split_feat = feat
        self.split_val = split_v
        self.left = PureIsolationTree(self.height_limit, self.rng).fit(left_X, current_height + 1)
        self.right = PureIsolationTree(self.height_limit, self.rng).fit(right_X, current_height + 1)
        return self

    def path_length(self, x: list[float], current_height: int = 0) -> float:
        if self.is_leaf:
            return current_height + _c_factor(self.size)
        if x[self.split_feat] < self.split_val:
            return self.left.path_length(x, current_height + 1)
        return self.right.path_length(x, current_height + 1)


def _c_factor(n: int) -> float:
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    return 2.0 * (math.log(n - 1.0) + 0.5772156649) - (2.0 * (n - 1.0) / n)


class IsolationForestEngine:
    """scikit-learn이 있으면 sklearn을, 없으면 내장 Isolation Forest를 자동 실행하는 하이브리드 AI 엔진."""

    def __init__(self, n_estimators: int = 120, contamination: float = 0.12, seed: int = 42):
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.seed = seed

    def fit_predict(self, features: list[list[float]]) -> tuple[list[int], list[float]]:
        """
        반환:
          labels: 정상 = 1, 이상치(Anomaly) = -1
          scores: 0.0 ~ 1.0 사이의 이상 점수 (높을수록 심각한 이상 징후)
        """
        n = len(features)
        if n == 0:
            return [], []

        if HAS_SKLEARN and n >= 10:
            X_arr = np.array(features, dtype=float)
            model = SklearnIsolationForest(
                n_estimators=self.n_estimators,
                contamination=self.contamination,
                random_state=self.seed,
            )
            preds = model.fit_predict(X_arr).tolist()
            raw_scores = (-model.score_samples(X_arr)).tolist()
            return preds, raw_scores

        # 내장 Pure Isolation Forest 실행
        rng = random.Random(self.seed)
        sample_size = min(n, 64)
        h_limit = max(1, int(math.ceil(math.log2(max(sample_size, 2)))))
        trees: list[PureIsolationTree] = []

        for _ in range(self.n_estimators):
            sub_X = rng.sample(features, sample_size) if n > sample_size else list(features)
            t = PureIsolationTree(h_limit, rng).fit(sub_X)
            trees.append(t)

        c_norm = max(_c_factor(sample_size), 1e-6)
        anomaly_scores = []
        for x in features:
            avg_path = sum(t.path_length(x) for t in trees) / len(trees)
            # Isolation Forest 논문 공식: s(x, n) = 2 ^ (-E(h(x)) / c(n))
            score = math.pow(2.0, -avg_path / c_norm)
            anomaly_scores.append(round(score, 4))

        # 상위 contamination 비율을 이상치(-1)로 판정
        sorted_scores = sorted(anomaly_scores, reverse=True)
        k = max(1, int(round(n * self.contamination)))
        threshold = max(0.55, sorted_scores[min(k - 1, n - 1)])

        labels = [-1 if s >= threshold else 1 for s in anomaly_scores]
        return labels, anomaly_scores


# ==============================================================================
# 2. 산업용 4~20mA 압력 센서 계측 데이터 생성 및 분석기
# ==============================================================================
def ensure_sample_datasets(base_dir: Path) -> tuple[Path, Path]:
    inst_dir = base_dir / "instrument_results"
    inst_dir.mkdir(parents=True, exist_ok=True)

    ex01_path = inst_dir / "example_01.csv"
    stream_path = inst_dir / "sensor_stream_log.csv"

    # 60초간의 연속 계측 시계열 데이터(정상 운전 + 단선/과압/노이즈 스파이크/스케일 드리프트 포함) 생성
    if not stream_path.exists():
        rng = random.Random(2026)
        rows = [["시간_초", "태그", "전류_mA", "압력_bar", "범위밖"]]
        for sec in range(1, 61):
            # 기본 압력 파형: 5.0 bar 주변 완만한 사인파 운전 (정상 전류: 약 12.0 mA)
            true_p = 5.0 + 1.8 * math.sin(sec / 6.0) + rng.uniform(-0.08, 0.08)
            cur_ma = 4.0 + (true_p / 10.0) * 16.0
            meas_p = (cur_ma - 4.0) * 0.625

            # 의도적인 산업 현장 고장/이상치 시나리오 5곳 주입
            if sec == 14:
                # 14초: 루프 단선/언더레인지 징후 (example_01.csv의 PT-104 케이스와 동일!)
                cur_ma = 3.50
                meas_p = -0.3125
            elif sec == 27:
                # 27초: 순간 서지 과압 스파이크 (Over-range > 20mA)
                cur_ma = 21.40
                meas_p = 10.875
            elif sec == 39:
                # 39초: A/D 컨버터 스케일링 오류 (전류는 12mA인데 압력이 9.2bar로 잘못 환산됨!)
                cur_ma = 12.10
                meas_p = 9.20
            elif sec in (48, 49):
                # 48~49초: 배선 접촉 불량으로 전류 급락
                cur_ma = 2.10
                meas_p = -1.1875

            out_of_range = (cur_ma < 4.0) or (cur_ma > 20.0)
            rows.append([
                sec,
                f"PT-10{1 + (sec % 4)}",
                round(cur_ma, 3),
                round(meas_p, 4),
                out_of_range,
            ])

        with open(stream_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    return ex01_path, stream_path


def analyze_csv_with_ai(csv_path: Path) -> list[dict]:
    """
    계측 CSV 파일을 읽어:
      1) 4~20mA 물리 공식 편차(스케일링 오차) 계산
      2) 변화율(dI/dt) 및 Isolation Forest AI 이상 탐지 점수 산출
      3) 구체적인 고장 원인 진단명 자동 부여
    """
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    records = []
    features = []
    prev_ma = None

    for idx, r in enumerate(raw_rows):
        sec = float(r.get("시간_초", idx + 1))
        tag = r.get("태그", f"TAG-{idx+1}")
        ma = float(r.get("전류_mA", 12.0))
        bar = float(r.get("압력_bar", 5.0))

        # 4~20mA <-> 0~10 bar 표준 선형 변환 공식: P_expected = (I - 4.0) * (10.0 / 16.0)
        expected_bar = (ma - 4.0) * 0.625
        formula_err = abs(bar - expected_bar)
        delta_ma = 0.0 if prev_ma is None else abs(ma - prev_ma)
        prev_ma = ma

        # AI 학습용 다변량 피처 벡터: [전류, 압력, 물리공식오차*10, 순간변화량]
        features.append([ma, bar, formula_err * 15.0, delta_ma * 2.0])

        records.append({
            "idx": idx + 1,
            "sec": sec,
            "tag": tag,
            "ma": ma,
            "bar": bar,
            "expected_bar": round(expected_bar, 4),
            "formula_err": round(formula_err, 4),
            "delta_ma": round(delta_ma, 3),
        })

    # Isolation Forest AI 모델 추론
    ai_engine = IsolationForestEngine(n_estimators=120, contamination=0.12, seed=42)
    labels, scores = ai_engine.fit_predict(features)

    for rec, lbl, sc in zip(records, labels, scores):
        ma = rec["ma"]
        ferr = rec["formula_err"]

        # AI 이상 탐지 결과 + 도메인 물리 규칙 결합 진단
        reasons = []
        if ma < 3.8:
            reasons.append("루프 단선/전원 이상 (Under-range < 3.8mA)")
        elif ma < 4.0:
            reasons.append("영점 하한 이탈 (4mA 미만 언더레인지)")
        elif ma > 20.5:
            reasons.append("과압 서지 스파이크 (Over-range > 20.5mA)")
        elif ma > 20.0:
            reasons.append("상한 초과 (20mA 초과)")

        if ferr > 0.35:
            reasons.append(f"전류-압력 환산 스케일 불일치 (기대값 {rec['expected_bar']}bar)")

        if lbl == -1 and not reasons:
            reasons.append("AI 패턴 이상 감지 (급격한 신호 변동)")

        is_anomaly = (lbl == -1) or (len(reasons) > 0)
        rec["ai_score"] = round(sc, 3)
        rec["is_anomaly"] = is_anomaly
        rec["status"] = "🚨 이상 징후" if is_anomaly else "✅ 정상"
        rec["diagnosis"] = " / ".join(reasons) if reasons else "정상 운전 범위 (4~20mA 선형 구간)"

    return records


# ==============================================================================
# 3. 시각화 대시보드 & 빨간 점 이상치 그래프 GUI (Tkinter)
# ==============================================================================
class AnomalyReporterApp(tk.Tk):
    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir
        self.ex01_path, self.stream_path = ensure_sample_datasets(base_dir)
        self.current_csv = self.stream_path
        self.records: list[dict] = []

        engine_tag = "scikit-learn IsolationForest" if HAS_SKLEARN else "Built-in Pure IsolationForest"
        self.title(f"🤖 [AI Level 1] 계측 CSV 데이터 자동 분석 & 이상치(Anomaly) 탐지 리포터  ({engine_tag})")
        self.geometry("1360x840")
        self.minsize(1080, 680)
        self.configure(bg="#0f172a")

        self._build_ui()
        self.run_analysis(self.stream_path)

    def _build_ui(self):
        # 상단 헤더 바
        top = tk.Frame(self, bg="#1e293b", padx=14, pady=10)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(
            top,
            text="🔍 AI 계측 데이터 이상치(Anomaly) 자동 진단 리포터",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 13, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 18))

        self._btn(top, "📂 1. example_01.csv 분석 (원본 4행)", lambda: self.run_analysis(self.ex01_path), "#2563eb")
        self._btn(top, "📈 2. 60초 연속 센서 스트림 분석 (추천)", lambda: self.run_analysis(self.stream_path), "#059669")
        self._btn(top, "📁 다른 CSV 파일 열기...", self.open_custom_csv, "#475569")
        self._btn(top, "💾 AI 진단 리포트 CSV 저장", self.export_report_csv, "#d97706")

        # 요약 KPI 카드 영역
        kpi_frame = tk.Frame(self, bg="#0f172a", padx=14, pady=8)
        kpi_frame.pack(side=tk.TOP, fill=tk.X)

        self.kpi_total = self._make_kpi_card(kpi_frame, "총 계측 샘플 수", "0 건", "#38bdf8")
        self.kpi_normal = self._make_kpi_card(kpi_frame, "정상 데이터", "0 건", "#4ade80")
        self.kpi_anom = self._make_kpi_card(kpi_frame, "🚨 AI 탐지 이상치 (빨간 점)", "0 건", "#f87171")
        self.kpi_sec = self._make_kpi_card(kpi_frame, "이상 발생 구간(초/태그)", "-", "#fbbf24")

        # 중앙 분할 영역: 위쪽=빨간 점 시계열 차트 캔버스, 아래쪽=상세 진단 표
        paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#0f172a", sashwidth=5, bd=0)
        paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        # 1) 시계열 그래프 + 4~20mA 상관관계 스캐터 캔버스
        chart_frame = tk.Frame(paned, bg="#090d16", highlightbackground="#334155", highlightthickness=1)
        self.chart_canvas = tk.Canvas(chart_frame, bg="#090d16", height=360, highlightthickness=0)
        self.chart_canvas.pack(fill=tk.BOTH, expand=True)
        self.chart_canvas.bind("<Configure>", lambda e: self.draw_charts())
        paned.add(chart_frame, minsize=310)

        # 2) 하단 AI 진단 결과 테이블
        table_frame = tk.Frame(paned, bg="#1e293b")
        hdr = tk.Frame(table_frame, bg="#1e293b", padx=8, pady=5)
        hdr.pack(fill=tk.X)
        self.table_title = tk.Label(
            hdr,
            text="📋 구간별 AI 이상치 정밀 진단 리포트 (이상 징후 행은 빨간색으로 강조됩니다)",
            bg="#1e293b",
            fg="#e2e8f0",
            font=("Malgun Gothic", 10, "bold"),
        )
        self.table_title.pack(side=tk.LEFT)

        cols = ("sec", "tag", "ma", "bar", "expected_bar", "ai_score", "status", "diagnosis")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=11)
        headers = {
            "sec": ("시간(초)", 80),
            "tag": ("센서 태그", 95),
            "ma": ("전류 (mA)", 95),
            "bar": ("측정 압력 (bar)", 115),
            "expected_bar": ("정상 기대압력 (bar)", 130),
            "ai_score": ("AI 이상점수", 100),
            "status": ("AI 판정", 110),
            "diagnosis": ("자동 진단 원인 (Isolation Forest + 4~20mA 루프 법칙)", 480),
        }
        for c, (txt, w) in headers.items():
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w, anchor="center" if c != "diagnosis" else "w")

        self.tree.tag_configure("anomaly", background="#450a0a", foreground="#fca5a5")
        self.tree.tag_configure("normal", background="#0f172a", foreground="#cbd5e1")

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)

        paned.add(table_frame, minsize=220)

    def _btn(self, parent, text, cmd, bg):
        b = tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg="#ffffff",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 9, "bold"),
            padx=12,
            pady=5,
            cursor="hand2",
        )
        b.pack(side=tk.LEFT, padx=4)
        return b

    def _make_kpi_card(self, parent, title, val, color):
        card = tk.Frame(parent, bg="#1e293b", padx=14, pady=8, highlightbackground="#334155", highlightthickness=1)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(card, text=title, bg="#1e293b", fg="#94a3b8", font=("Malgun Gothic", 9)).pack(anchor="w")
        lbl = tk.Label(card, text=val, bg="#1e293b", fg=color, font=("Malgun Gothic", 13, "bold"))
        lbl.pack(anchor="w", pady=(2, 0))
        return lbl

    # --------------------------------------------------------------------------
    # 데이터 분석 실행 및 차트 렌더링 (빨간 점 마킹)
    # --------------------------------------------------------------------------
    def run_analysis(self, csv_path: Path):
        self.current_csv = csv_path
        self.records = analyze_csv_with_ai(csv_path)

        total = len(self.records)
        anoms = [r for r in self.records if r["is_anomaly"]]
        normals = total - len(anoms)
        anom_locs = ", ".join(f"{int(r['sec'])}초({r['tag']})" for r in anoms[:6])
        if len(anoms) > 6:
            anom_locs += f" 외 {len(anoms) - 6}건"

        self.kpi_total.configure(text=f"{total} 건")
        self.kpi_normal.configure(text=f"{normals} 건")
        self.kpi_anom.configure(text=f"{len(anoms)} 건 탐지됨!")
        self.kpi_sec.configure(text=anom_locs or "이상 없음")
        self.table_title.configure(text=f"📋 분석 파일: {csv_path.name}  —  이상 징후(빨간 점)가 상단으로 정렬되어 표시됩니다")

        # 테이블 채우기 (이상 징후를 맨 위에 먼저 보여주거나 시간순 표시)
        for item in self.tree.get_children():
            self.tree.delete(item)

        for r in self.records:
            tag_style = "anomaly" if r["is_anomaly"] else "normal"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    f"{int(r['sec'])}초",
                    r["tag"],
                    f"{r['ma']:.2f} mA",
                    f"{r['bar']:.4f} bar",
                    f"{r['expected_bar']:.4f} bar",
                    f"{r['ai_score']:.3f}",
                    r["status"],
                    r["diagnosis"],
                ),
                tags=(tag_style,),
            )

        self.draw_charts()

        # 콘솔에도 깔끔한 요약 리포트 출력
        print(f"\n================ [AI 이상치 진단 리포트: {csv_path.name}] ================")
        print(f"총 데이터: {total}건 | 정상: {normals}건 | 이상 징후: {len(anoms)}건")
        for r in anoms:
            print(f"  🔴 [{int(r['sec'])}초 | {r['tag']}] 전류={r['ma']}mA, 압력={r['bar']}bar -> {r['diagnosis']}")

    def draw_charts(self):
        c = self.chart_canvas
        c.delete("all")
        if not self.records:
            return

        w = max(c.winfo_width(), 900)
        h = max(c.winfo_height(), 320)

        # 왼쪽 62%: 시간에 따른 전류(mA) & 압력 시계열 차트 + 빨간 점(Anomaly) 표시
        # 오른쪽 38%: 전류(mA) vs 압력(bar) 4~20mA 선형성 검증 스캐터 차트
        split_x = int(w * 0.62)
        self._draw_time_series(c, 55, 42, split_x - 30, h - 38)
        self._draw_xy_scatter(c, split_x + 45, 42, w - 30, h - 38)

    def _draw_time_series(self, c: tk.Canvas, x1: int, y1: int, x2: int, y2: int):
        c.create_text(
            x1, y1 - 20,
            text="📈 [차트 1] 시간에 따른 센서 전류(mA) 추이 및 AI 이상 징후 (🔴 빨간 점)",
            fill="#f8fafc", anchor="w", font=("Malgun Gothic", 10, "bold")
        )
        c.create_rectangle(x1, y1, x2, y2, fill="#0f172a", outline="#334155")

        min_y, max_y = 0.0, 24.0
        n = len(self.records)

        def to_xy(idx, val):
            px = x1 + 20 + (idx / max(n - 1, 1)) * (x2 - x1 - 40)
            py = y2 - ((val - min_y) / (max_y - min_y)) * (y2 - y1)
            return px, py

        # 4mA 하한선 & 20mA 상한선 점선 표시
        _, y_4ma = to_xy(0, 4.0)
        _, y_20ma = to_xy(0, 20.0)
        c.create_line(x1, y_20ma, x2, y_20ma, fill="#eab308", dash=(4, 3))
        c.create_text(x1 + 6, y_20ma - 8, text="상한 20.0mA", fill="#eab308", anchor="w", font=("Consolas", 8))

        c.create_line(x1, y_4ma, x2, y_4ma, fill="#eab308", dash=(4, 3))
        c.create_text(x1 + 6, y_4ma + 10, text="하한 4.0mA", fill="#eab308", anchor="w", font=("Consolas", 8))

        # 시계열 선 연결
        pts = []
        for i, r in enumerate(self.records):
            pts.extend(to_xy(i, r["ma"]))
        if len(pts) >= 4:
            c.create_line(*pts, fill="#38bdf8", width=2.2)

        # 각 데이터 포인트 및 이상치 빨간 점 찍기
        for i, r in enumerate(self.records):
            px, py = to_xy(i, r["ma"])
            if r["is_anomaly"]:
                # 빨간색 경고 후광 + 굵은 빨간 점 + 몇 초인지 텍스트 라벨
                c.create_oval(px - 9, py - 9, px + 9, py + 9, fill="", outline="#ef4444", width=2)
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#ef4444", outline="#ffffff", width=1.5)
                c.create_text(
                    px, py - 16,
                    text=f"🚨{int(r['sec'])}초 ({r['ma']}mA)",
                    fill="#fca5a5", font=("Malgun Gothic", 8, "bold")
                )
            else:
                c.create_oval(px - 3, py - 3, px + 3, py + 3, fill="#38bdf8", outline="")

    def _draw_xy_scatter(self, c: tk.Canvas, x1: int, y1: int, x2: int, y2: int):
        c.create_text(
            x1, y1 - 20,
            text="🎯 [차트 2] 4~20mA vs 압력(bar) 물리 법칙 선형성 AI 검증",
            fill="#f8fafc", anchor="w", font=("Malgun Gothic", 10, "bold")
        )
        c.create_rectangle(x1, y1, x2, y2, fill="#0f172a", outline="#334155")

        min_ma, max_ma = 0.0, 24.0
        min_bar, max_bar = -2.0, 12.0

        def to_xy(ma, bar):
            px = x1 + ((ma - min_ma) / (max_ma - min_ma)) * (x2 - x1)
            py = y2 - ((bar - min_bar) / (max_bar - min_bar)) * (y2 - y1)
            return px, py

        # 이상적인 4~20mA -> 0~10bar 정상 직선 그리기
        lx1, ly1 = to_xy(4.0, 0.0)
        lx2, ly2 = to_xy(20.0, 10.0)
        c.create_line(lx1, ly1, lx2, ly2, fill="#4ade80", width=2, dash=(5, 3))
        c.create_text(lx2 - 10, ly2 + 14, text="정상 4~20mA 직선", fill="#4ade80", anchor="e", font=("Malgun Gothic", 8))

        for r in self.records:
            px, py = to_xy(r["ma"], r["bar"])
            if r["is_anomaly"]:
                c.create_oval(px - 6, py - 6, px + 6, py + 6, fill="#ef4444", outline="#ffffff", width=1.5)
                c.create_text(px + 8, py, text=f"{r['tag']}({int(r['sec'])}s)", fill="#fca5a5", anchor="w", font=("Consolas", 8, "bold"))
            else:
                c.create_oval(px - 3, py - 3, px + 3, py + 3, fill="#38bdf8", outline="")

    def open_custom_csv(self):
        path = filedialog.askopenfilename(
            title="계측 CSV 파일 선택",
            initialdir=str(self.base_dir / "instrument_results"),
            filetypes=[("CSV Files", "*.csv")],
        )
        if path:
            self.run_analysis(Path(path))

    def export_report_csv(self):
        out_path = self.base_dir / "instrument_results" / "ai_anomaly_report.csv"
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["시간_초", "태그", "전류_mA", "측정압력_bar", "기대압력_bar", "AI_이상점수", "판정", "진단원인"])
            for r in self.records:
                writer.writerow([
                    int(r["sec"]), r["tag"], r["ma"], r["bar"],
                    r["expected_bar"], r["ai_score"], r["status"], r["diagnosis"]
                ])
        messagebox.showinfo("리포트 저장 완료", f"AI 이상치 진단 결과 리포트가 저장되었습니다:\n{out_path}")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    app = AnomalyReporterApp(base)
    app.mainloop()
