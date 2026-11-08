"""
===============================================================================
⚔️ [미니 스타크래프트 싱글플레이 × AI 실시간 난이도 조절(DDA) 시뮬레이터]
===============================================================================
플레이어(테란: 마린, 메딕, 시즈탱크)의 실시간 실력 지표를 AI 감독(AI Director)이 분석하여,
초보자에게는 역전의 재미를 주고 고수에게는 프로게이머급(AlphaStar) 전술로 맞서는
'동적 난이도 조절(Dynamic Difficulty Adjustment, DDA)' 스타크래프트 전술 게임입니다!

[핵심 AI 난이도 조절(DDA) 메커니즘]
1. 플레이어 실력 실시간 계측 (1초 주기):
   - APM (Actions Per Minute, 분당 마우스/키보드 명령 수)
   - 카이팅(무빙샷) 및 스팀팩 활용도
   - 교전 교환비 (Kill / Death Ratio) 및 자원(미네랄) 운영 효율
2. AI 전술 지능 실시간 진화 (Lv.1 브론즈 ~ Lv.10 AlphaStar):
   - Lv.1~3 (입문/하향 지원): 저글링이 단순 어택땅으로 오며 충원 속도가 느려짐 (역전 유도!)
   - Lv.4~6 (밸런스 교전): 히드라리스크 조합 + 적당한 충원 속도로 팽팽한 긴장감 유지
   - Lv.7~10 (프로게이머/AlphaStar 각성):
     * 저글링 부채꼴 포위 기동(Flanking/Surround)
     * 체력이 가장 낮은 마린/탱크 칼같이 일점사(Focus Fire)
     * 불리할 때 전술적 후퇴 후 울트라리스크 대군 동시 러시!

[조작 방법 (실제 스타크래프트 감성 그대로!)]
- 마우스 드래그 또는 좌클릭 : 내 테란 유닛 선택 (전체 선택 단축키: A 또는 Space)
- 마우스 우클릭            : 이동 또는 적 일점사 공격 (무빙샷 카이팅 가능!)
- 키보드 [T]               : 🔥 스팀팩(Stimpack) 발동! (공격속도/이동속도 1.8배 폭발!)
- 키보드 [M] / [C] / [S]   : 마린(50원) / 메딕(75원) / 시즈탱크(150원) 즉시 생산

[실행 방법]
    python starcraft_ai_dda.py
===============================================================================
"""

from __future__ import annotations

import math
import random
import time
import tkinter as tk
from tkinter import ttk


# ==============================================================================
# 1. 유닛 데이터 클래스 (테란: 마린/메딕/시즈탱크 vs 저그: 저글링/히드라/울트라)
# ==============================================================================
class Unit:
    _next_id = 1

    def __init__(self, team: str, utype: str, x: float, y: float):
        self.id = Unit._next_id
        Unit._next_id += 1
        self.team = team    # "TERRAN" or "ZERG"
        self.utype = utype  # MARINE, MEDIC, TANK / ZERGLING, HYDRA, ULTRA
        self.x = x
        self.y = y
        self.tx = x
        self.ty = y
        self.target_unit: Unit | None = None
        self.selected = (team == "TERRAN")
        self.cooldown = 0.0
        self.stim_timer = 0.0
        self.laser_fx = 0.0
        self.last_hit_pos = None

        # 유닛별 능력치 밸런스
        specs = {
            # (HP, 사거리, 공격력, 공격주기초, 이동속도, 반지름, 색상, 한글명)
            "MARINE":   (45,  145, 7,   0.42, 95,  11, "#3b82f6", "마린"),
            "MEDIC":    (60,  90,  -10, 0.35, 90,  12, "#f8fafc", "메딕"),
            "TANK":     (150, 250, 28,  1.25, 52,  16, "#1d4ed8", "시즈탱크"),
            "ZERGLING": (35,  24,  5,   0.38, 128, 9,  "#b45309", "저글링"),
            "HYDRA":    (80,  140, 10,  0.62, 82,  13, "#a855f7", "히드라"),
            "ULTRA":    (260, 32,  24,  0.75, 105, 19, "#dc2626", "울트라"),
        }
        hp, rng, dmg, cd, spd, rad, col, kname = specs[utype]
        self.max_hp = hp
        self.hp = float(hp)
        self.attack_range = rng
        self.damage = dmg
        self.base_cd = cd
        self.base_speed = spd
        self.radius = rad
        self.color = col
        self.kname = kname


# ==============================================================================
# 2. AI 난이도 자동 조절 감독 (Dynamic Difficulty Adjustment - DDA Director)
# ==============================================================================
class StarcraftAIDirector:
    """
    플레이어의 실시간 APM, 카이팅 컨트롤, 병력 우세도, 킬/데스 비율을 평가하여
    AI 난이도 레벨(1.0 ~ 10.0)을 실시간으로 올리거나 내려 '최적의 몰입감(Flow)'을 유지합니다.
    """

    def __init__(self):
        self.auto_dda = True
        self.ai_level = 4.0            # 1.0 (브론즈) ~ 10.0 (AlphaStar 프로게이머)
        self.player_apm = 0
        self.action_timestamps: list[float] = []
        self.kiting_score = 0.0        # 무빙샷 컨트롤 점수
        self.terran_kills = 0
        self.zerg_kills = 0

        self.spawn_timer = 0.0
        self.ai_decision_log = "🤖 [AI 감독] 플레이어 실력 측정 중... (기본 Lv.4.0 밸런스 모드)"
        self.history_level = [4.0] * 120
        self.history_apm = [0] * 120

    def record_player_action(self, is_micro: bool = False):
        now = time.perf_counter()
        self.action_timestamps.append(now)
        if is_micro:
            self.kiting_score = min(100.0, self.kiting_score + 4.5)

    def update_metrics_and_difficulty(self, terran_units: list[Unit], zerg_units: list[Unit], dt: float):
        now = time.perf_counter()
        # 최근 15초간의 입력을 기준으로 분당 행동수(APM) 환산
        self.action_timestamps = [t for t in self.action_timestamps if now - t <= 15.0]
        self.player_apm = int(len(self.action_timestamps) * 4)
        self.kiting_score = max(0.0, self.kiting_score - 3.0 * dt)

        if not self.auto_dda:
            return

        # 플레이어 전력 vs 저그 전력 계산
        t_power = sum(u.hp * (2.2 if u.utype == "TANK" else 1.0) for u in terran_units)
        z_power = sum(u.hp * (2.0 if u.utype == "ULTRA" else 1.0) for u in zerg_units)
        kd_ratio = (self.terran_kills + 2) / max(1, self.zerg_kills + 2)

        # 목표 AI 난이도 산출:
        # 1) APM이 높고(80+) 카이팅을 잘하며 테란 병력이 압도하면 -> 난이도 급상승 (최대 Lv.10)
        # 2) 테란이 병력을 잃고 밀리면 -> 난이도 즉시 완화 (Lv.1~3으로 낮춰 역전 기회 제공!)
        apm_factor = min(3.5, self.player_apm / 55.0)
        micro_factor = (self.kiting_score / 100.0) * 2.0
        army_ratio = (t_power + 50.0) / (z_power + 100.0)

        target_lv = 2.0 + apm_factor + micro_factor + min(3.5, (army_ratio - 0.6) * 2.5) + min(1.5, (kd_ratio - 1.0) * 0.8)
        target_lv = max(1.0, min(10.0, target_lv))

        # 부드럽게 AI 레벨 수렴
        self.ai_level += (target_lv - self.ai_level) * 1.2 * dt
        self.ai_level = round(max(1.0, min(10.0, self.ai_level)), 2)

        # 현재 AI 전술 상태 텍스트 생성
        if self.ai_level < 3.2:
            self.ai_decision_log = (
                f"🟢 [DDA 하향 지원 | Lv.{self.ai_level:.1f}] 플레이어 위기 감지! "
                f"저그 충원 속도를 늦추고 일점사를 해제하여 역전 찬스를 만듭니다."
            )
        elif self.ai_level < 6.8:
            self.ai_decision_log = (
                f"🟡 [DDA 팽팽한 균형 | Lv.{self.ai_level:.1f}] 플레이어 APM({self.player_apm})에 맞춰 "
                f"저글링+히드라 조합과 적정 타이밍 러시를 수행합니다."
            )
        else:
            self.ai_decision_log = (
                f"🔴 [DDA AlphaStar 각성! | Lv.{self.ai_level:.1f}] 고수 플레이어 감지! "
                f"저그가 부채꼴 포위 기동(Surround) + 빈사 유닛 칼일점사 + 울트라리스크를 투입합니다!"
            )

    def get_tier_name(self) -> str:
        lv = self.ai_level
        if lv < 2.5:
            return "🥉 브론즈 (입문 맞춤형)"
        elif lv < 4.5:
            return "🥈 실버/골드 (표준 교전)"
        elif lv < 6.5:
            return "🥇 플래티넘/다이아 (상급 전술)"
        elif lv < 8.5:
            return "💎 마스터 (고속 마이크로 컨트롤)"
        else:
            return "👑 그랜드마스터 / AlphaStar (프로게이머급)"


# ==============================================================================
# 3. 스타크래프트 전술 시뮬레이터 & AI 대시보드 GUI
# ==============================================================================
class StarcraftDDAApp(tk.Tk):
    MAP_W = 900
    MAP_H = 580

    def __init__(self):
        super().__init__()
        self.title("⚔️ [스타크래프트 싱글플레이 × AI 동적 난이도 조절(DDA)] 실시간 전술 시뮬레이터")
        self.geometry("1460x880")
        self.minsize(1180, 740)
        self.configure(bg="#090d16")

        self.director = StarcraftAIDirector()
        self.units: list[Unit] = []
        self.minerals = 250
        self.drag_rect = None  # (x1, y1, x2, y2)

        self._build_ui()
        self.reset_battle()

        # 단축키 바인딩
        self.bind("t", lambda e: self.use_stimpack())
        self.bind("T", lambda e: self.use_stimpack())
        self.bind("m", lambda e: self.spawn_terran("MARINE", 50))
        self.bind("M", lambda e: self.spawn_terran("MARINE", 50))
        self.bind("c", lambda e: self.spawn_terran("MEDIC", 75))
        self.bind("C", lambda e: self.spawn_terran("MEDIC", 75))
        self.bind("s", lambda e: self.spawn_terran("TANK", 150))
        self.bind("S", lambda e: self.spawn_terran("TANK", 150))
        self.bind("<space>", lambda e: self.select_all_terran())
        self.bind("a", lambda e: self.select_all_terran())

        self.last_time = time.perf_counter()
        self.metric_accum = 0.0
        self.after(25, self._game_loop)

    def _build_ui(self):
        # 1. 상단 스타크래프트 HUD 바
        top = tk.Frame(self, bg="#111827", padx=14, pady=8, highlightbackground="#334155", highlightthickness=1)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(
            top,
            text="⚔️ STARCRAFT : AI DYNAMIC DIFFICULTY DIRECTOR",
            bg="#111827",
            fg="#38bdf8",
            font=("Consolas", 13, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 18))

        self.min_lbl = tk.Label(
            top,
            text="💎 미네랄: 250",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Malgun Gothic", 11, "bold"),
            padx=12,
            pady=4,
        )
        self.min_lbl.pack(side=tk.LEFT, padx=6)

        self.apm_lbl = tk.Label(
            top,
            text="⚡ 내 실시간 APM: 0",
            bg="#0f172a",
            fg="#fef08a",
            font=("Malgun Gothic", 11, "bold"),
            padx=12,
            pady=4,
        )
        self.apm_lbl.pack(side=tk.LEFT, padx=6)

        self.lv_badge = tk.Label(
            top,
            text="🤖 AI 난이도: Lv.4.0 (실버/골드)",
            bg="#1d4ed8",
            fg="#ffffff",
            font=("Malgun Gothic", 11, "bold"),
            padx=14,
            pady=4,
        )
        self.lv_badge.pack(side=tk.LEFT, padx=8)

        tk.Button(
            top, text="🔄 전장 초기화", command=self.reset_battle,
            bg="#475569", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"), padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.RIGHT, padx=4)

        # 2. 메인 영역: 왼쪽=전투 맵 + 테란 커맨드 카드 / 오른쪽=AI 감독(DDA) 실시간 두뇌 분석창
        main = tk.Frame(self, bg="#090d16")
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        left = tk.Frame(main, bg="#090d16")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 전투 지휘 배너
        self.ai_banner = tk.Label(
            left,
            text="🤖 [AI 감독] 플레이어 실력 측정 중...",
            bg="#1e293b",
            fg="#4ade80",
            font=("Malgun Gothic", 10, "bold"),
            anchor="w",
            padx=12,
            pady=6,
        )
        self.ai_banner.pack(fill=tk.X, pady=(0, 4))

        # 메인 전투 전장 캔버스
        self.battle_canvas = tk.Canvas(
            left, bg="#141815", highlightthickness=2, highlightbackground="#334155", cursor="crosshair"
        )
        self.battle_canvas.pack(fill=tk.BOTH, expand=True)
        self.battle_canvas.bind("<ButtonPress-1>", self._on_left_down)
        self.battle_canvas.bind("<B1-Motion>", self._on_left_drag)
        self.battle_canvas.bind("<ButtonRelease-1>", self._on_left_up)
        self.battle_canvas.bind("<Button-3>", self._on_right_click)

        # 하단 테란 생산 & 스킬 커맨드 바
        cmd_bar = tk.Frame(left, bg="#1e293b", padx=12, pady=8, highlightbackground="#475569", highlightthickness=1)
        cmd_bar.pack(fill=tk.X, pady=(6, 0))

        self._cmd_btn(cmd_bar, "🔫 [M] 마린 생산 (50💎)", lambda: self.spawn_terran("MARINE", 50), "#2563eb")
        self._cmd_btn(cmd_bar, "➕ [C] 메딕 생산 (75💎)", lambda: self.spawn_terran("MEDIC", 75), "#0891b2")
        self._cmd_btn(cmd_bar, "🚜 [S] 시즈탱크 생산 (150💎)", lambda: self.spawn_terran("TANK", 150), "#1d4ed8")
        self._cmd_btn(cmd_bar, "🔥 [T] 스팀팩 발동! (공속/이속 폭발)", self.use_stimpack, "#dc2626")
        self._cmd_btn(cmd_bar, "🚩 [Space] 전 병력 선택", self.select_all_terran, "#475569")

        # 3. 우측 패널: AI 난이도 조절(DDA) 텔레메트리 & 수동 오버라이드
        right = tk.Frame(main, bg="#1e293b", width=385, padx=14, pady=12)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)

        self._build_dda_panel(right)

    def _cmd_btn(self, parent, text, cmd, bg):
        b = tk.Button(
            parent, text=text, command=cmd, bg=bg, fg="#ffffff",
            activebackground="#38bdf8", activeforeground="#0f172a",
            relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"), padx=11, pady=6, cursor="hand2"
        )
        b.pack(side=tk.LEFT, padx=4)
        return b

    def _build_dda_panel(self, parent):
        tk.Label(
            parent,
            text="🧠 AI 난이도 자동 조절(DDA) 엔진",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        # 자동 DDA 켜기/끄기 및 수동 난이도 강제 설정
        mode_box = tk.Frame(parent, bg="#0f172a", padx=10, pady=8, highlightbackground="#334155", highlightthickness=1)
        mode_box.pack(fill=tk.X, pady=(0, 10))

        self.auto_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(
            mode_box,
            text="🤖 내 실력(APM/전황)에 맞춰 AI 난이도 자동 조절",
            variable=self.auto_var,
            command=self._toggle_auto_dda,
            bg="#0f172a",
            fg="#4ade80",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#4ade80",
            font=("Malgun Gothic", 9, "bold"),
        )
        chk.pack(anchor="w")

        self.manual_scale = tk.Scale(
            mode_box,
            from_=1.0,
            to=10.0,
            resolution=0.5,
            orient=tk.HORIZONTAL,
            label="수동 난이도 고정 (Lv.1 호구 ~ Lv.10 AlphaStar)",
            bg="#0f172a",
            fg="#cbd5e1",
            highlightthickness=0,
            troughcolor="#1e293b",
            command=self._on_manual_scale,
        )
        self.manual_scale.set(4.0)
        self.manual_scale.pack(fill=tk.X, pady=(4, 0))

        # 실시간 플레이어 평가 및 AI 전술 상태 텍스트
        self.dda_stat_lbl = tk.Label(
            parent,
            text="",
            bg="#090d16",
            fg="#e2e8f0",
            font=("Consolas", 9),
            justify=tk.LEFT,
            anchor="nw",
            padx=10,
            pady=10,
        )
        self.dda_stat_lbl.pack(fill=tk.X, pady=(0, 10))

        # 실시간 APM vs AI 난이도 레벨 변화 트렌드 차트
        tk.Label(
            parent,
            text="📈 실시간 [내 APM(노랑)] vs [AI 난이도(빨강)] 추이",
            bg="#1e293b",
            fg="#fbbf24",
            font=("Malgun Gothic", 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        self.dda_chart = tk.Canvas(parent, bg="#090d16", height=180, highlightthickness=1, highlightbackground="#334155")
        self.dda_chart.pack(fill=tk.X)

        tk.Label(
            parent,
            text="💡 실험 팁:\n"
                 "1) 가만히 손을 놓고 있으면 -> 내 APM이 0이 되고 아군이 밀리므로 AI가 스스로 Lv.1~2(브론즈)로 낮춰줍니다!\n"
                 "2) 마우스 우클릭을 연타하며 무빙샷(카이팅)과 [T] 스팀팩을 쓰면 -> AI가 프로게이머임을 감지하고 Lv.9~10(AlphaStar)으로 각성해 포위 공격과 일점사를 시전합니다!",
            bg="#1e293b",
            fg="#94a3b8",
            wraplength=355,
            justify=tk.LEFT,
            font=("Malgun Gothic", 8),
            pady=8,
        ).pack(side=tk.BOTTOM, fill=tk.X)

    # --------------------------------------------------------------------------
    # 전장 초기화, 유닛 생산, 마우스/키보드 마이크로 컨트롤
    # --------------------------------------------------------------------------
    def reset_battle(self):
        self.units.clear()
        self.minerals = 250
        self.director.terran_kills = 0
        self.director.zerg_kills = 0
        self.director.ai_level = 4.0

        # 초기 테란 분대 (마린 6, 메딕 2, 시즈탱크 1)
        for i in range(6):
            self.units.append(Unit("TERRAN", "MARINE", 180 + (i % 2) * 30, 200 + i * 35))
        self.units.append(Unit("TERRAN", "MEDIC", 140, 250))
        self.units.append(Unit("TERRAN", "MEDIC", 140, 310))
        self.units.append(Unit("TERRAN", "TANK", 110, 280))

        # 초기 저그 분대
        for i in range(6):
            self.units.append(Unit("ZERG", "ZERGLING", 680 + (i % 2) * 30, 180 + i * 40))
        self.units.append(Unit("ZERG", "HYDRA", 750, 250))
        self.units.append(Unit("ZERG", "HYDRA", 750, 330))

    def spawn_terran(self, utype: str, cost: int):
        self.director.record_player_action(is_micro=False)
        if self.minerals < cost:
            return
        self.minerals -= cost
        sy = random.uniform(160, 400)
        u = Unit("TERRAN", utype, 90, sy)
        u.tx, u.ty = 240, sy
        self.units.append(u)

    def use_stimpack(self):
        self.director.record_player_action(is_micro=True)
        for u in self.units:
            if u.team == "TERRAN" and u.selected and u.utype == "MARINE":
                if u.hp > 10:
                    u.hp -= 5
                u.stim_timer = 6.0  # 6초간 공속/이속 1.8배 폭발!

    def select_all_terran(self):
        self.director.record_player_action(is_micro=False)
        for u in self.units:
            if u.team == "TERRAN":
                u.selected = True

    def _toggle_auto_dda(self):
        self.director.auto_dda = self.auto_var.get()

    def _on_manual_scale(self, val):
        if not self.director.auto_dda:
            self.director.ai_level = float(val)

    def _on_left_down(self, event):
        self.director.record_player_action(is_micro=False)
        self.drag_rect = [event.x, event.y, event.x, event.y]

    def _on_left_drag(self, event):
        if self.drag_rect:
            self.drag_rect[2] = event.x
            self.drag_rect[3] = event.y

    def _on_left_up(self, event):
        if not self.drag_rect:
            return
        x1, y1, x2, y2 = self.drag_rect
        self.drag_rect = None
        bx1, bx2 = min(x1, x2), max(x1, x2)
        by1, by2 = min(y1, y2), max(y1, y2)

        if (bx2 - bx1) < 8 and (by2 - by1) < 8:
            # 단일 클릭 선택
            clicked = None
            for u in self.units:
                if u.team == "TERRAN" and math.hypot(u.x - event.x, u.y - event.y) <= u.radius + 8:
                    clicked = u
                    break
            if clicked:
                for u in self.units:
                    if u.team == "TERRAN":
                        u.selected = (u == clicked)
        else:
            # 초록색 드래그 박스(Marquee Selection) 안의 모든 테란 유닛 선택!
            any_in = any(
                u.team == "TERRAN" and bx1 <= u.x <= bx2 and by1 <= u.y <= by2
                for u in self.units
            )
            if any_in:
                for u in self.units:
                    if u.team == "TERRAN":
                        u.selected = (bx1 <= u.x <= bx2 and by1 <= u.y <= by2)

    def _on_right_click(self, event):
        """마우스 우클릭: 적 유닛을 우클릭하면 일점사(Focus Fire), 빈 땅을 우클릭하면 무빙(카이팅)!"""
        self.director.record_player_action(is_micro=True)

        clicked_enemy = None
        for u in self.units:
            if u.team == "ZERG" and math.hypot(u.x - event.x, u.y - event.y) <= u.radius + 10:
                clicked_enemy = u
                break

        sel_units = [u for u in self.units if u.team == "TERRAN" and u.selected]
        for idx, u in enumerate(sel_units):
            if clicked_enemy:
                u.target_unit = clicked_enemy
            else:
                u.target_unit = None
                # 대형 유지를 위한 약간의 산개 오프셋
                angle = (idx / max(1, len(sel_units))) * math.pi * 2
                spread = min(35, len(sel_units) * 4)
                u.tx = event.x + math.cos(angle) * spread
                u.ty = event.y + math.sin(angle) * spread

    # --------------------------------------------------------------------------
    # 메인 게임 물리 & AI 전술 루프 (40 FPS)
    # --------------------------------------------------------------------------
    def _game_loop(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last_time)
        self.last_time = now

        # 미네랄 자동 수급 (초당 18 미네랄)
        self.minerals += 18.0 * dt

        terran_units = [u for u in self.units if u.team == "TERRAN"]
        zerg_units = [u for u in self.units if u.team == "ZERG"]

        # 1. AI 감독(DDA) 난이도 계산 및 저그 웨이브 스폰
        self.director.update_metrics_and_difficulty(terran_units, zerg_units, dt)
        if self.director.auto_dda:
            self.manual_scale.set(round(self.director.ai_level, 1))

        self.metric_accum += dt
        if self.metric_accum >= 0.5:
            self.metric_accum = 0.0
            self.director.history_level.append(self.director.ai_level)
            self.director.history_apm.append(self.director.player_apm)
            self.director.history_level.pop(0)
            self.director.history_apm.pop(0)
            self._draw_dda_chart()

        # AI 레벨에 비례한 저그 증원 속도 및 고급 유닛(히드라/울트라) 비율 결정
        lv = self.director.ai_level
        spawn_interval = max(1.6, 5.2 - lv * 0.34)
        self.director.spawn_timer += dt
        if self.director.spawn_timer >= spawn_interval and len(zerg_units) < 22:
            self.director.spawn_timer = 0.0
            w = max(self.battle_canvas.winfo_width(), 800)
            h = max(self.battle_canvas.winfo_height(), 500)
            sy = random.uniform(80, h - 80)

            # 난이도가 높을수록 히드라리스크와 울트라리스크 등장!
            r_val = random.random()
            if lv >= 7.5 and r_val < 0.22:
                self.units.append(Unit("ZERG", "ULTRA", w - 50, sy))
            elif lv >= 4.0 and r_val < 0.45:
                self.units.append(Unit("ZERG", "HYDRA", w - 50, sy))
            else:
                # 저글링 2기 동시 스폰
                self.units.append(Unit("ZERG", "ZERGLING", w - 50, sy - 15))
                self.units.append(Unit("ZERG", "ZERGLING", w - 50, sy + 15))

        # 테란이 전멸 위기(1기 이하)일 때 AI가 자동 지원군 드랍쉽 투입
        if len(terran_units) <= 1:
            for i in range(4):
                self.units.append(Unit("TERRAN", "MARINE", 100, 200 + i * 35))
            self.units.append(Unit("TERRAN", "MEDIC", 80, 250))

        # 2. 각 유닛 이동, AI 마이크로 컨트롤(포위/일점사/후퇴), 전투 처리
        self._step_units_combat(dt, terran_units, zerg_units)

        # 3. 렌더링 업데이트
        self._render_battlefield()
        self._update_hud_labels(terran_units, zerg_units)

        self.after(25, self._game_loop)

    def _step_units_combat(self, dt: float, terran_units: list[Unit], zerg_units: list[Unit]):
        lv = self.director.ai_level

        for u in self.units:
            u.cooldown = max(0.0, u.cooldown - dt)
            u.stim_timer = max(0.0, u.stim_timer - dt)
            u.laser_fx = max(0.0, u.laser_fx - dt)

            enemies = zerg_units if u.team == "TERRAN" else terran_units
            allies = terran_units if u.team == "TERRAN" else zerg_units

            # 메딕 치료 로직
            if u.utype == "MEDIC":
                wounded = [a for a in allies if a != u and a.hp < a.max_hp and a.utype != "TANK"]
                if wounded:
                    target_ally = min(wounded, key=lambda a: math.hypot(a.x - u.x, a.y - u.y))
                    dist = math.hypot(target_ally.x - u.x, target_ally.y - u.y)
                    if dist <= u.attack_range:
                        if u.cooldown <= 0.0:
                            target_ally.hp = min(float(target_ally.max_hp), target_ally.hp + abs(u.damage))
                            u.cooldown = u.base_cd
                            u.laser_fx = 0.15
                            u.last_hit_pos = (target_ally.x, target_ally.y)
                    else:
                        u.tx, u.ty = target_ally.x - 25, target_ally.y
                self._move_unit_towards(u, u.tx, u.ty, dt)
                continue

            # 저그 AI 전술 의사결정 (AI 난이도 레벨에 따라 행동이 완전히 달라짐!)
            if u.team == "ZERG" and enemies:
                if lv >= 7.0:
                    # [고수용 AlphaStar AI]: 사거리 내 가장 체력이 낮은(빈사 상태) 테란 유닛을 칼같이 일점사!
                    in_range_enemies = [e for e in enemies if math.hypot(e.x - u.x, e.y - u.y) <= u.attack_range + 80]
                    if in_range_enemies:
                        u.target_unit = min(in_range_enemies, key=lambda e: e.hp)
                    else:
                        u.target_unit = min(enemies, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))

                    # 히드라가 체력이 30% 미만이면 뒤로 빼는 카이팅/생존 컨트롤!
                    if u.utype == "HYDRA" and u.hp < u.max_hp * 0.30:
                        u.tx = min(850, u.x + 80)
                        u.ty = u.y
                        self._move_unit_towards(u, u.tx, u.ty, dt)
                        continue
                else:
                    # [일반 AI]: 가장 가까운 적만 공격
                    u.target_unit = min(enemies, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))

                if u.target_unit:
                    # Lv.6 이상 저글링은 위아래 부채꼴로 감싸며 포위(Surround) 기동
                    flank_offset = 0.0
                    if lv >= 6.0 and u.utype == "ZERGLING":
                        flank_offset = ((u.id % 5) - 2) * 22.0
                    u.tx = u.target_unit.x
                    u.ty = u.target_unit.y + flank_offset

            # 공격 사거리 체크 및 발사
            target = u.target_unit
            if target and target.hp <= 0:
                u.target_unit = None
                target = None

            # 테란 유닛이 이동 완료 상태에서 사거리 내 적이 있으면 자동 사격
            dist_to_move = math.hypot(u.tx - u.x, u.ty - u.y)
            if u.team == "TERRAN" and target is None and dist_to_move < 12.0 and enemies:
                near_e = min(enemies, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))
                if math.hypot(near_e.x - u.x, near_e.y - u.y) <= u.attack_range:
                    target = near_e

            if target:
                dist_e = math.hypot(target.x - u.x, target.y - u.y)
                if dist_e <= u.attack_range:
                    if u.cooldown <= 0.0:
                        # AI 레벨에 따른 공격력/공격속도 미세 보정
                        dmg_mult = 1.0
                        if u.team == "ZERG":
                            dmg_mult = 0.75 + (lv / 10.0) * 0.55
                        target.hp -= u.damage * dmg_mult
                        cd = u.base_cd * (0.55 if u.stim_timer > 0 else 1.0)
                        u.cooldown = cd
                        u.laser_fx = 0.12
                        u.last_hit_pos = (target.x, target.y)
                else:
                    self._move_unit_towards(u, target.x, target.y, dt)
            else:
                self._move_unit_towards(u, u.tx, u.ty, dt)

        # 유닛 간 겹침 방지 밀어내기(Separation Physics) 및 사망 처리
        alive = []
        for u in self.units:
            if u.hp > 0:
                alive.append(u)
            else:
                if u.team == "ZERG":
                    self.director.terran_kills += 1
                    self.minerals += 22  # 저그 처치 시 바운티 미네랄 획득!
                else:
                    self.director.zerg_kills += 1
        self.units = alive

        for i in range(len(self.units)):
            for j in range(i + 1, len(self.units)):
                a, b = self.units[i], self.units[j]
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                min_d = a.radius + b.radius + 3
                if 0 < d < min_d:
                    push = (min_d - d) * 0.35
                    nx, ny = dx / d, dy / d
                    a.x -= nx * push
                    a.y -= ny * push
                    b.x += nx * push
                    b.y += ny * push

    def _move_unit_towards(self, u: Unit, tx: float, ty: float, dt: float):
        dx, dy = tx - u.x, ty - u.y
        dist = math.hypot(dx, dy)
        if dist > 4.0:
            spd = u.base_speed * (1.65 if u.stim_timer > 0 else 1.0)
            if u.team == "ZERG":
                spd *= 0.82 + (self.director.ai_level / 10.0) * 0.38
            step = min(dist, spd * dt)
            u.x += (dx / dist) * step
            u.y += (dy / dist) * step

    # --------------------------------------------------------------------------
    # 전장 렌더링 (스타크래프트 초록색 선택 원, 체력바, 레이저/스팀팩 이펙트)
    # --------------------------------------------------------------------------
    def _render_battlefield(self):
        c = self.battle_canvas
        c.delete("all")
        w = max(c.winfo_width(), 800)
        h = max(c.winfo_height(), 500)

        # 지형 그리드 및 중앙 전선 표시
        for gx in range(0, w, 60):
            c.create_line(gx, 0, gx, h, fill="#1c2420")
        for gy in range(0, h, 60):
            c.create_line(0, gy, w, gy, fill="#1c2420")

        c.create_line(w / 2, 0, w / 2, h, fill="#2d3748", dash=(6, 4))
        c.create_text(80, 26, text="🔵 TERRAN BASE (플레이어 진영)", fill="#60a5fa", font=("Malgun Gothic", 10, "bold"))
        c.create_text(w - 110, 26, text="🟣 ZERG HIVE (AI 진영)", fill="#c084fc", font=("Malgun Gothic", 10, "bold"))

        # 공격 레이저 / 치료 빔 렌더링
        for u in self.units:
            if u.laser_fx > 0 and u.last_hit_pos:
                lx, ly = u.last_hit_pos
                if u.utype == "MEDIC":
                    c.create_line(u.x, u.y, lx, ly, fill="#4ade80", width=3)
                elif u.utype == "TANK":
                    c.create_line(u.x, u.y, lx, ly, fill="#fbbf24", width=4)
                    c.create_oval(lx - 18, ly - 18, lx + 18, ly + 18, outline="#f97316", width=2)
                elif u.team == "TERRAN":
                    c.create_line(u.x, u.y, lx, ly, fill="#fde047", width=2)
                else:
                    c.create_line(u.x, u.y, lx, ly, fill="#e879f9", width=2)

        # 유닛 렌더링
        for u in self.units:
            r = u.radius
            # 스타크래프트 특유의 발밑 초록색 선택 원(Selection Circle)!
            if u.team == "TERRAN" and u.selected:
                c.create_oval(u.x - r - 5, u.y - r - 3, u.x + r + 5, u.y + r + 5, outline="#22c55e", width=2)

            # 스팀팩 오라
            if u.stim_timer > 0:
                c.create_oval(u.x - r - 3, u.y - r - 3, u.x + r + 3, u.y + r + 3, outline="#ef4444", width=2)

            # 유닛 본체
            c.create_oval(u.x - r, u.y - r, u.x + r, u.y + r, fill=u.color, outline="#ffffff", width=1.5)
            c.create_text(u.x, u.y, text=u.kname[0], fill="#0f172a" if u.utype == "MEDIC" else "#ffffff", font=("Malgun Gothic", 8, "bold"))

            # 머리 위 스타크래프트 칸칸이 체력바
            bar_w = r * 2.2
            hp_ratio = max(0.0, u.hp / u.max_hp)
            hp_col = "#22c55e" if hp_ratio > 0.5 else ("#eab308" if hp_ratio > 0.25 else "#ef4444")
            bx1, by1 = u.x - bar_w / 2, u.y - r - 10
            c.create_rectangle(bx1, by1, bx1 + bar_w, by1 + 5, fill="#1f2937", outline="#000000")
            c.create_rectangle(bx1, by1, bx1 + bar_w * hp_ratio, by1 + 5, fill=hp_col, outline="")

        # 마우스 드래그 선택 상자 (초록색 스타크래프트 드래그 박스)
        if self.drag_rect:
            x1, y1, x2, y2 = self.drag_rect
            c.create_rectangle(x1, y1, x2, y2, outline="#22c55e", width=2)

    def _update_hud_labels(self, terran_units: list[Unit], zerg_units: list[Unit]):
        self.min_lbl.configure(text=f"💎 미네랄: {int(self.minerals)}")
        self.apm_lbl.configure(text=f"⚡ 내 실시간 APM: {self.director.player_apm}")
        tier = self.director.get_tier_name()
        lv = self.director.ai_level
        bg_col = "#059669" if lv < 3.5 else ("#2563eb" if lv < 7.0 else "#dc2626")
        self.lv_badge.configure(text=f"🤖 AI 난이도: Lv.{lv:.1f} ({tier})", bg=bg_col)
        self.ai_banner.configure(text=self.director.ai_decision_log)

        self.dda_stat_lbl.configure(
            text=(
                f"[실시간 플레이어 실력 분석]\n"
                f" • 손속도 (APM)     : {self.director.player_apm} APM\n"
                f" • 카이팅 마이크로  : {self.director.kiting_score:.0f} / 100 점\n"
                f" • 교전 킬/데스     : {self.director.terran_kills} 킬 / {self.director.zerg_kills} 전사\n"
                f" • 현재 병력 수     : 테란 {len(terran_units)}기 vs 저그 {len(zerg_units)}기\n\n"
                f"[AI 감독(DDA) 실시간 파라미터]\n"
                f" • 측정된 플레이어 티어:\n   {tier}\n"
                f" • 저그 증원 주기   : {max(1.6, 5.2 - lv * 0.34):.1f} 초마다 증원\n"
                f" • 포위/일점사 지능 : {'ON (프로게이머 모드)' if lv >= 7.0 else 'OFF (일반 어택땅)'}"
            )
        )

    def _draw_dda_chart(self):
        c = self.dda_chart
        c.delete("all")
        w = max(c.winfo_width(), 340)
        h = max(c.winfo_height(), 160)
        pad = 20
        n = len(self.director.history_level)

        pts_lv, pts_apm = [], []
        for i in range(n):
            px = pad + (i / (n - 1)) * (w - pad * 2)
            py_lv = h - pad - ((self.director.history_level[i] - 1.0) / 9.0) * (h - pad * 2)
            py_apm = h - pad - (min(250, self.director.history_apm[i]) / 250.0) * (h - pad * 2)
            pts_lv.extend((px, py_lv))
            pts_apm.extend((px, py_apm))

        if len(pts_lv) >= 4:
            c.create_line(*pts_apm, fill="#eab308", width=1.8)
            c.create_line(*pts_lv, fill="#ef4444", width=2.5)


if __name__ == "__main__":
    app = StarcraftDDAApp()
    app.mainloop()
