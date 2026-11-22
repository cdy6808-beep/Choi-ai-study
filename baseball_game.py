"""
===============================================================================
⚾ [올인원 야구 슈퍼 스튜디오] (Baseball Super Studio)
===============================================================================
두 가지 최고 인기 야구 게임을 하나의 세련된 GUI 프로그램으로 즐길 수 있습니다!

[모드 1: 실전 배팅 & 9이닝 아케이드 (Real Action Batting Game)]
- 투수의 다양한 구종 (150km/h 직구, 슬라이더, 커브, 체인지업, 포크볼)
- 실제 물리 법칙 기반 타격: 스윙 타이밍(밀어치기/당겨치기)과 타구 발사각 계산
- 비거리(m) 및 타구 속도(km/h) 측정, 장타/단타/플라이/땅볼/홈런(Home Run!) 판정
- 1루, 2루, 3루 주자 진루 다이아몬드 미니맵 연동
- 전광판 B-S-O(볼/스트라이크/아웃) 카운트 및 9이닝 정규 스코어보드
- 타격음, 포구음, 홈런 팡파르 효과음 (Windows winsound 스레딩 지원)

[모드 2: 두뇌 추리 숫자야구 (Number Baseball AI Battle)]
- 3자리 / 4자리 선택 가능
- 1인 도전 모드 & 🤖 AI 실시간 대결 모드 (플레이어 vs 영리한 AI)
- AI 논리 필터링 알고리즘: 이전 힌트를 바탕으로 후보군을 좁혀가며 추리
- 온스크린 키패드 & 키보드 숫자 입력 지원, 컬러 뱃지 판정 로그

[조작법]
- 배팅 스윙: [스페이스바] 또는 [마우스 좌클릭]
- 다음 투구: [P] 또는 [투구 시작] 버튼
- 번트: [B]

[실행 방법]
    python baseball_game.py
===============================================================================
"""

from __future__ import annotations

import itertools
import math
import os
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

# 효과음 모듈 (Windows 환경 지원)
try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False


def play_sound(sound_type: str):
    """UI를 멈추지 않도록 별도 스레드에서 효과음 재생."""
    if not HAS_SOUND:
        return

    def _worker():
        try:
            if sound_type == "hit":          # 호쾌한 타격음
                winsound.Beep(920, 60)
                winsound.Beep(1400, 90)
            elif sound_type == "homerun":     # 홈런 축하 팡파르
                notes = [(523, 100), (659, 100), (784, 120), (1046, 280)]
                for freq, dur in notes:
                    winsound.Beep(freq, dur)
            elif sound_type == "strike":      # 스트라이크 징
                winsound.Beep(420, 110)
            elif sound_type == "out":         # 아웃 버저
                winsound.Beep(260, 220)
            elif sound_type == "ball":        # 볼 띡
                winsound.Beep(680, 70)
            elif sound_type == "cheer":       # 안타 환호
                winsound.Beep(784, 90)
                winsound.Beep(988, 140)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


# ==============================================================================
# 1. 모드 1: 실전 배팅 아케이드 엔진 & 그래픽
# ==============================================================================
class BattingArcadeTab(tk.Frame):
    CANVAS_W = 860
    CANVAS_H = 540

    PITCH_TYPES = [
        ("직구 (Four-seam)", 148, 156, "#ef4444", 0.0, 0.0),
        ("슬라이더 (Slider)", 134, 142, "#f59e0b", 28.0, 12.0),
        ("커브 (Curveball)", 116, 126, "#10b981", -22.0, 36.0),
        ("체인지업 (Changeup)", 125, 133, "#06b6d4", 0.0, 22.0),
        ("포크볼 (Forkball)", 128, 138, "#8b5cf6", 0.0, 48.0),
    ]

    def __init__(self, master):
        super().__init__(master, bg="#0f172a")

        # 게임 상태
        self.inning = 1
        self.is_top = False  # False: 말(플레이어 공격), True: 초(수비/AI)
        self.score_away = 0
        self.score_home = 0
        self.balls = 0
        self.strikes = 0
        self.outs = 0
        self.hits_total = 0
        self.home_runs_total = 0

        # 주자 상태 (1루, 2루, 3루)
        self.runners = [False, False, False]

        # 투구 & 타격 물리 상태
        self.pitch_state = "IDLE"  # "IDLE", "WINDUP", "FLIGHT", "HIT_FLY", "RESOLVED"
        self.cur_pitch_name = "-"
        self.cur_speed_kmh = 0
        self.flight_progress = 0.0  # 0.0 (투수 손) ~ 1.0 (홈플레이트 통과)
        self.flight_duration = 0.65  # 초
        self.pitch_start_t = 0.0
        self.pitch_break_x = 0.0
        self.pitch_break_y = 0.0
        self.target_cross_t = 0.0

        # 타구 비행 상태
        self.hit_flight_t = 0.0
        self.hit_flight_dur = 1.8
        self.hit_start_pos = (0, 0)
        self.hit_target_pos = (0, 0)
        self.hit_peak_h = 100
        self.hit_distance_m = 0
        self.hit_exit_speed = 0
        self.hit_commentary = "경기가 시작되었습니다! [스페이스바]로 스윙하세요!"

        # 배트 스윙 애니메이션
        self.swinging = False
        self.swing_progress = 0.0
        self.swing_time = 0.0

        self._build_ui()
        self.after(20, self._render_loop)

    def _build_ui(self):
        # 상단 전광판 (Scoreboard)
        board = tk.Frame(self, bg="#111827", padx=12, pady=6, highlightbackground="#334155", highlightthickness=1)
        board.pack(fill=tk.X, padx=10, pady=(8, 4))

        # 이닝 / 팀 점수
        left_box = tk.Frame(board, bg="#111827")
        left_box.pack(side=tk.LEFT, padx=6)

        self.inning_lbl = tk.Label(
            left_box, text="1회말 ▼ 공격", bg="#1f2937", fg="#38bdf8",
            font=("Malgun Gothic", 11, "bold"), padx=10, pady=4
        )
        self.inning_lbl.pack(side=tk.LEFT, padx=4)

        self.score_lbl = tk.Label(
            left_box, text="원정 AI  0  :  0  홈(YOU)", bg="#111827", fg="#f8fafc",
            font=("Consolas", 14, "bold"), padx=8
        )
        self.score_lbl.pack(side=tk.LEFT, padx=6)

        # BSO 카운트 (LED 램프 스타일)
        bso_box = tk.Frame(board, bg="#0f172a", padx=10, pady=3, highlightbackground="#374151", highlightthickness=1)
        bso_box.pack(side=tk.LEFT, padx=12)

        tk.Label(bso_box, text="B", bg="#0f172a", fg="#10b981", font=("Consolas", 10, "bold")).grid(row=0, column=0, padx=2)
        self.ball_leds = [self._led(bso_box, 0, c + 1, "#10b981") for c in range(3)]

        tk.Label(bso_box, text="S", bg="#0f172a", fg="#f59e0b", font=("Consolas", 10, "bold")).grid(row=1, column=0, padx=2)
        self.strike_leds = [self._led(bso_box, 1, c + 1, "#f59e0b") for c in range(2)]

        tk.Label(bso_box, text="O", bg="#0f172a", fg="#ef4444", font=("Consolas", 10, "bold")).grid(row=2, column=0, padx=2)
        self.out_leds = [self._led(bso_box, 2, c + 1, "#ef4444") for c in range(2)]

        # 우측: 구속 / 구종 표시 & 버튼
        right_box = tk.Frame(board, bg="#111827")
        right_box.pack(side=tk.RIGHT)

        self.pitch_info_lbl = tk.Label(
            right_box, text="투수 대기 중...", bg="#1e293b", fg="#fbbf24",
            font=("Malgun Gothic", 10, "bold"), padx=10, pady=4
        )
        self.pitch_info_lbl.pack(side=tk.LEFT, padx=6)

        tk.Button(
            right_box, text="⚾ 투구 시작 [P]", command=self.trigger_pitch,
            bg="#2563eb", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"),
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            right_box, text="🔄 경기 리셋", command=self.reset_match,
            bg="#475569", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"),
            padx=8, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=3)

        # 메인 전장 캔버스
        canvas_frame = tk.Frame(self, bg="#090d16")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        self.canvas = tk.Canvas(
            canvas_frame, bg="#0d141e", width=self.CANVAS_W, height=self.CANVAS_H,
            highlightthickness=1, highlightbackground="#334155"
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 캔버스 클릭 시 스윙
        self.canvas.bind("<Button-1>", lambda e: self.swing_bat())

        # 하단 중계 자막 & 안내 티커
        bottom_bar = tk.Frame(self, bg="#1e293b", padx=12, pady=6)
        bottom_bar.pack(fill=tk.X, padx=10, pady=(2, 8))

        self.commentary_lbl = tk.Label(
            bottom_bar, text="📢 중계: " + self.hit_commentary, bg="#1e293b", fg="#4ade80",
            font=("Malgun Gothic", 10, "bold"), anchor="w"
        )
        self.commentary_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.stat_bar_lbl = tk.Label(
            bottom_bar, text="안타: 0개 | 홈런: 0개 | 최고비거리: 0m", bg="#1e293b", fg="#94a3b8",
            font=("Malgun Gothic", 9)
        )
        self.stat_bar_lbl.pack(side=tk.RIGHT)

    def _led(self, parent, r, c, on_color):
        lbl = tk.Label(parent, text="●", bg="#0f172a", fg="#374151", font=("Consolas", 10))
        lbl.grid(row=r, column=c, padx=1)
        lbl.on_color = on_color
        return lbl

    def _update_leds(self):
        for i, led in enumerate(self.ball_leds):
            led.configure(fg=led.on_color if i < self.balls else "#374151")
        for i, led in enumerate(self.strike_leds):
            led.configure(fg=led.on_color if i < self.strikes else "#374151")
        for i, led in enumerate(self.out_leds):
            led.configure(fg=led.on_color if i < self.outs else "#374151")

    # --------------------------------------------------------------------------
    # 투구 및 타격 메커니즘
    # --------------------------------------------------------------------------
    def trigger_pitch(self):
        if self.pitch_state in ("WINDUP", "FLIGHT"):
            return
        self.pitch_state = "WINDUP"
        self.pitch_info_lbl.configure(text="투수 와인드업 중...", fg="#fef08a")

        # 0.4초 후 투수 손에서 공 발사
        def _release():
            ptype = random.choice(self.PITCH_TYPES)
            name, spd_min, spd_max, col, brk_x, brk_y = ptype
            spd = random.randint(spd_min, spd_max)

            self.cur_pitch_name = name
            self.cur_speed_kmh = spd
            self.pitch_break_x = brk_x + random.uniform(-6, 6)
            self.pitch_break_y = brk_y + random.uniform(-6, 6)
            # 구속에 따른 실제 비행 시간 (150km/h: 약 0.52초, 120km/h: 약 0.65초)
            self.flight_duration = 0.50 + (160 - spd) * 0.0038
            self.flight_progress = 0.0
            self.pitch_start_t = time.perf_counter()
            self.target_cross_t = self.pitch_start_t + self.flight_duration
            self.pitch_state = "FLIGHT"
            self.pitch_info_lbl.configure(text=f"{name} ({spd} km/h)", fg=col)

        self.after(350, _release)

    def swing_bat(self):
        if self.swinging:
            return
        self.swinging = True
        self.swing_progress = 0.0
        self.swing_time = time.perf_counter()

        # 공이 날아오는 중이면 타격 판정
        if self.pitch_state == "FLIGHT":
            dt = self.swing_time - self.target_cross_t
            # |dt| <= 0.045s -> 정타 (Perfect)
            # -0.11 <= dt < -0.045s -> 당겨치기 (Early)
            # 0.045 < dt <= 0.11s -> 밀어치기 (Late)
            # 그 외: 헛스윙 (Swing & Miss)
            if abs(dt) <= 0.11:
                self._resolve_hit(dt)
            else:
                self._resolve_swing_miss()
        else:
            # 공이 없을 때 헛스윙 연습
            play_sound("strike")

    def _resolve_swing_miss(self):
        play_sound("strike")
        self.strikes += 1
        self.set_commentary("헛스윙! 배트가 허공을 가릅니다!")
        self._check_count()

    def _resolve_hit(self, dt: float):
        self.pitch_state = "HIT_FLY"
        self.hit_flight_t = 0.0
        play_sound("hit")

        # 타이밍 기반 방향 및 발사각
        # dt < 0 : 당겨치기 (좌측으로 비구)
        # dt > 0 : 밀어치기 (우측으로 비구)
        spray_angle_deg = -dt * 360.0  # -40도 (좌익수) ~ +40도 (우익수)
        timing_accuracy = 1.0 - (abs(dt) / 0.11)  # 0.0 ~ 1.0

        # 발사각과 타구속도 (최대 175 km/h)
        self.hit_exit_speed = int(115 + timing_accuracy * 55 + random.randint(-5, 8))
        launch_quality = random.random() * 0.4 + timing_accuracy * 0.6

        cx = self.CANVAS_W / 2
        cy = self.CANVAS_H * 0.82
        self.hit_start_pos = (cx, cy)

        # 비거리 계산 (m)
        if launch_quality >= 0.82:
            # 대형 홈런 가능성!
            self.hit_distance_m = int(108 + (launch_quality - 0.82) * 120 + random.randint(-2, 8))
            self.hit_peak_h = 160
            self.hit_flight_dur = 2.2
            target_x = cx + math.sin(math.radians(spray_angle_deg)) * (self.CANVAS_W * 0.44)
            target_y = 60 + random.randint(-25, 20)
            self.hit_target_pos = (target_x, target_y)

            if self.hit_distance_m >= 105:
                # 홈런!
                self._on_home_run(self.hit_distance_m)
            else:
                # 펜스 맞는 2루타 / 3루타
                self._on_extra_base_hit(2 if random.random() < 0.75 else 3, "펜스를 직격하는 장타!")
        elif launch_quality >= 0.52:
            # 안타 (Single / Double)
            self.hit_distance_m = int(68 + launch_quality * 42)
            self.hit_peak_h = 95
            self.hit_flight_dur = 1.5
            target_x = cx + math.sin(math.radians(spray_angle_deg)) * (self.CANVAS_W * 0.32)
            target_y = 150 + random.randint(0, 45)
            self.hit_target_pos = (target_x, target_y)
            self._on_single_hit("외야수 앞에 떨어지는 깨끗한 안타!")
        elif launch_quality >= 0.28:
            # 외야 뜬공 아웃 (Fly out)
            self.hit_distance_m = int(75 + launch_quality * 28)
            self.hit_peak_h = 130
            self.hit_flight_dur = 1.7
            target_x = cx + math.sin(math.radians(spray_angle_deg)) * (self.CANVAS_W * 0.28)
            target_y = 130 + random.randint(0, 30)
            self.hit_target_pos = (target_x, target_y)
            self._on_out("외야수가 침착하게 포구, 뜬공 아웃!")
        else:
            # 내야 땅볼 아웃 또는 파울
            if abs(spray_angle_deg) > 35:
                self.hit_distance_m = int(45 + random.randint(0, 20))
                self.hit_peak_h = 40
                self.hit_flight_dur = 0.9
                target_x = cx + (1 if spray_angle_deg > 0 else -1) * (self.CANVAS_W * 0.42)
                target_y = 300
                self.hit_target_pos = (target_x, target_y)
                self._on_foul()
            else:
                self.hit_distance_m = int(25 + random.randint(0, 15))
                self.hit_peak_h = 25
                self.hit_flight_dur = 0.9
                target_x = cx + math.sin(math.radians(spray_angle_deg)) * (self.CANVAS_W * 0.16)
                target_y = 320
                self.hit_target_pos = (target_x, target_y)
                self._on_out("내야수 정면 땅볼, 1루에서 아웃!")

    def _on_home_run(self, dist_m: int):
        self.home_runs_total += 1
        self.hits_total += 1
        runs = 1 + sum(1 for r in self.runners if r)
        self.score_home += runs
        self.runners = [False, False, False]
        self.balls = 0
        self.strikes = 0
        play_sound("homerun")
        self.set_commentary(f"💥 쾅!! 넘어갔습니다! {dist_m}m 대형 홈런! ({runs}점 득점!) 🏆")
        self._update_all_views()

    def _on_single_hit(self, desc: str):
        self.hits_total += 1
        scored = 1 if self.runners[2] else 0
        self.score_home += scored
        self.runners[2] = self.runners[1]
        self.runners[1] = self.runners[0]
        self.runners[0] = True
        self.balls = 0
        self.strikes = 0
        play_sound("cheer")
        msg = f"⚾ {desc} (비거리 {self.hit_distance_m}m, {self.hit_exit_speed}km/h)"
        if scored:
            msg += " 3루 주자 홈인! 1득점!"
        self.set_commentary(msg)
        self._update_all_views()

    def _on_extra_base_hit(self, bases: int, desc: str):
        self.hits_total += 1
        scored = 0
        for b in range(3):
            if self.runners[b]:
                if b + bases >= 3:
                    scored += 1
        self.score_home += scored
        new_runners = [False, False, False]
        if bases == 2:
            new_runners[1] = True
            if self.runners[0]:
                new_runners[2] = True
        elif bases == 3:
            new_runners[2] = True
        self.runners = new_runners
        self.balls = 0
        self.strikes = 0
        play_sound("cheer")
        msg = f"🚀 {desc} {bases}루타! (비거리 {self.hit_distance_m}m)"
        if scored:
            msg += f" {scored}명 홈인! {scored}득점!"
        self.set_commentary(msg)
        self._update_all_views()

    def _on_foul(self):
        play_sound("strike")
        if self.strikes < 2:
            self.strikes += 1
        self.set_commentary(f"파울! 관중석으로 들어가는 파울 타구입니다. (비거리 {self.hit_distance_m}m)")
        self._update_leds()

    def _on_out(self, desc: str):
        play_sound("out")
        self.outs += 1
        self.balls = 0
        self.strikes = 0
        self.set_commentary(f"아웃! {desc}")
        self._check_count()

    def _on_called_ball_or_strike(self):
        # 타자가 스윙 안 했을 때 투구 궤적 최종 판정
        in_zone = abs(self.pitch_break_x) <= 22 and abs(self.pitch_break_y) <= 25
        if in_zone:
            play_sound("strike")
            self.strikes += 1
            self.set_commentary(f"스트라이크 콜! 한가운데 꽂히는 {self.cur_pitch_name}!")
        else:
            play_sound("ball")
            self.balls += 1
            self.set_commentary(f"볼! 존을 약간 벗어난 {self.cur_pitch_name}.")
        self._check_count()

    def _check_count(self):
        if self.strikes >= 3:
            play_sound("out")
            self.outs += 1
            self.strikes = 0
            self.balls = 0
            self.set_commentary("삼진 아웃! 배트가 나오지 못했습니다!")
        elif self.balls >= 4:
            # 포볼 (볼넷)
            self.balls = 0
            self.strikes = 0
            scored = 0
            if self.runners[0] and self.runners[1] and self.runners[2]:
                scored = 1
                self.score_home += 1
            elif self.runners[0] and self.runners[1]:
                self.runners[2] = True
            elif self.runners[0]:
                self.runners[1] = True
            self.runners[0] = True
            play_sound("cheer")
            msg = "볼넷(Walk)! 침착하게 1루로 걸어나갑니다."
            if scored:
                msg += " 밀어내기 1득점!"
            self.set_commentary(msg)

        if self.outs >= 3:
            self._end_half_inning()

        self._update_all_views()

    def _end_half_inning(self):
        self.outs = 0
        self.strikes = 0
        self.balls = 0
        self.runners = [False, False, False]
        # 공수 교대 시뮬레이션
        if not self.is_top:
            self.is_top = True
            # AI 원정팀 득점 시뮬레이션 (0~2점 무작위)
            ai_scored = random.choice([0, 0, 1, 0, 2])
            self.score_away += ai_scored
            self.set_commentary(f"3아웃 공수 교대! AI 원정팀이 {ai_scored}점을 내고 이닝이 바뀝니다.")
            # 바로 플레이어 공격 회차로 복귀
            self.is_top = False
            self.inning += 1
            if self.inning > 9:
                self._finish_game()
        self._update_all_views()

    def _finish_game(self):
        msg = f"경기 종료! 최종 스코어 {self.score_away} : {self.score_home}\n"
        if self.score_home > self.score_away:
            msg += "🏆 축하합니다! 승리하셨습니다!"
        elif self.score_home < self.score_away:
            msg += "아쉽게 패배했습니다. 다음 경기에 설욕하세요!"
        else:
            msg += "무승부로 경기가 끝났습니다!"
        messagebox.showinfo("Game Over", msg, parent=self)
        self.reset_match()

    def reset_match(self):
        self.inning = 1
        self.is_top = False
        self.score_away = 0
        self.score_home = 0
        self.balls = 0
        self.strikes = 0
        self.outs = 0
        self.hits_total = 0
        self.home_runs_total = 0
        self.runners = [False, False, False]
        self.pitch_state = "IDLE"
        self.set_commentary("새로운 경기가 시작되었습니다! [P] 키나 [투구 시작] 버튼을 누르세요.")
        self._update_all_views()

    def set_commentary(self, msg: str):
        self.hit_commentary = msg
        self.commentary_lbl.configure(text="📢 중계: " + msg)

    def _update_all_views(self):
        top_str = "초 ▲ 수비" if self.is_top else "말 ▼ 공격"
        self.inning_lbl.configure(text=f"{self.inning}회{top_str}")
        self.score_lbl.configure(text=f"원정 AI  {self.score_away}  :  {self.score_home}  홈(YOU)")
        self._update_leds()
        self.stat_bar_lbl.configure(
            text=f"안타: {self.hits_total}개 | 홈런: {self.home_runs_total}개 | 최고비거리: {self.hit_distance_m}m"
        )

    # --------------------------------------------------------------------------
    # 캔버스 실시간 렌더링 루프 (그라운드, 투수, 공 궤적, 배트, 다이아몬드 미니맵)
    # --------------------------------------------------------------------------
    def _render_loop(self):
        now = time.perf_counter()
        c = self.canvas
        c.delete("all")
        w, h = self.CANVAS_W, self.CANVAS_H
        cx = w / 2

        # 1. 스타디움 그라운드 배경 원근감 렌더링
        # 외야 관중석 / 밤하늘
        c.create_rectangle(0, 0, w, h * 0.38, fill="#0f172a", outline="")
        # 외야 조명탑 불빛
        for lx in (w * 0.15, w * 0.35, w * 0.65, w * 0.85):
            c.create_oval(lx - 25, 20, lx + 25, 34, fill="#fef08a", outline="")

        # 외야 펜스 녹색 벽
        c.create_polygon(
            0, h * 0.38, w, h * 0.38, w, h * 0.45, 0, h * 0.45,
            fill="#14532d", outline="#166534"
        )
        c.create_text(w * 0.16, h * 0.415, text="LEFT 99M", fill="#86efac", font=("Consolas", 8, "bold"))
        c.create_text(w * 0.50, h * 0.415, text="CENTER 120M", fill="#fde047", font=("Consolas", 9, "bold"))
        c.create_text(w * 0.84, h * 0.415, text="RIGHT 99M", fill="#86efac", font=("Consolas", 8, "bold"))

        # 천연잔디 그라운드 (원근감 사다리꼴)
        c.create_polygon(
            0, h * 0.45, w, h * 0.45, w * 1.1, h, -w * 0.1, h,
            fill="#15803d", outline=""
        )

        # 내야 흙 마운드 및 파울 라인
        mound_x, mound_y = cx, h * 0.48
        plate_x, plate_y = cx, h * 0.84

        c.create_line(plate_x, plate_y, 40, h * 0.45, fill="#ffffff", width=2)
        c.create_line(plate_x, plate_y, w - 40, h * 0.45, fill="#ffffff", width=2)

        # 투수 마운드 (타원)
        c.create_oval(mound_x - 38, mound_y - 12, mound_x + 38, mound_y + 12, fill="#78350f", outline="#92400e")
        c.create_rectangle(mound_x - 8, mound_y - 2, mound_x + 8, mound_y + 2, fill="#ffffff", outline="")

        # 투수 실루엣
        c.create_oval(mound_x - 7, mound_y - 36, mound_x + 7, mound_y - 22, fill="#f8fafc", outline="#000")
        c.create_rectangle(mound_x - 9, mound_y - 22, mound_x + 9, mound_y - 4, fill="#1d4ed8", outline="")

        # 홈플레이트 (오각형)
        c.create_polygon(
            plate_x - 22, plate_y,
            plate_x + 22, plate_y,
            plate_x + 22, plate_y + 16,
            plate_x, plate_y + 28,
            plate_x - 22, plate_y + 16,
            fill="#ffffff", outline="#000", width=1.5
        )

        # 스트라이크 존 가이드 박스 (반투명 점선 사각 프레임)
        sz_w, sz_h = 70, 85
        sz_y = plate_y - 48
        c.create_rectangle(
            plate_x - sz_w / 2, sz_y - sz_h / 2,
            plate_x + sz_w / 2, sz_y + sz_h / 2,
            outline="#38bdf8", width=2, dash=(4, 3)
        )

        # 2. 공 궤적 애니메이션
        ball_draw_x, ball_draw_y, ball_r = None, None, 0

        if self.pitch_state == "FLIGHT":
            p = (now - self.pitch_start_t) / max(0.01, self.flight_duration)
            self.flight_progress = min(1.15, p)

            # 공의 3D 원근 투영: 투수 손 -> 홈플레이트
            bx = mound_x + (plate_x - mound_x) * p + (self.pitch_break_x * (p ** 2))
            by = (mound_y - 24) + ((plate_y - 40) - (mound_y - 24)) * p + (self.pitch_break_y * (p ** 2))
            # 크기: 4px -> 26px
            br = 4 + 22 * (p ** 1.3)

            # 그림자
            c.create_oval(bx - br * 0.7, by + br * 0.8, bx + br * 0.7, by + br * 1.2, fill="#064e3b", outline="")
            # 야구공 본체
            c.create_oval(bx - br, by - br, bx + br, by + br, fill="#ffffff", outline="#991b1b", width=1.5)
            # 실밥 무늬
            c.create_arc(bx - br * 0.8, by - br * 0.8, bx + br * 0.8, by + br * 0.8, start=45, extent=90, style=tk.ARC, outline="#dc2626")

            # 홈플레이트를 완전히 지나쳤는데 스윙을 안 했을 경우 자동 볼/스트라이크 판정
            if p >= 1.08:
                self.pitch_state = "RESOLVED"
                self._on_called_ball_or_strike()

        elif self.pitch_state == "HIT_FLY":
            self.hit_flight_t += 0.025
            p = min(1.0, self.hit_flight_t / self.hit_flight_dur)

            # 포물선 궤적
            sx, sy = self.hit_start_pos
            tx, ty = self.hit_target_pos
            bx = sx + (tx - sx) * p
            arc_y = -4 * self.hit_peak_h * p * (1 - p)
            by = sy + (ty - sy) * p + arc_y
            br = max(3, int(20 * (1 - p * 0.7)))

            # 타구 잔상 선
            c.create_line(sx, sy, bx, by, fill="#fde047", width=2, dash=(3, 2))
            c.create_oval(bx - br, by - br, bx + br, by + br, fill="#ffffff", outline="#ea580c", width=1.5)

            if p >= 1.0:
                self.pitch_state = "IDLE"

        # 3. 타자 배트 스윙 애니메이션
        swing_angle = -35.0  # 기본 대기 각도
        if self.swinging:
            self.swing_progress += 0.14
            if self.swing_progress <= 1.0:
                # 스윙 휘두르기 (각도 -35도 -> +95도)
                swing_angle = -35.0 + 130.0 * math.sin(self.swing_progress * math.pi / 2.0)
            else:
                self.swinging = False

        # 우타자 배트 그리기
        pivot_x = plate_x - 38
        pivot_y = plate_y - 20
        bat_len = 54
        rad = math.radians(swing_angle)
        tip_x = pivot_x + math.cos(rad) * bat_len
        tip_y = pivot_y + math.sin(rad) * bat_len

        # 배트 손잡이 & 몸통
        c.create_line(pivot_x, pivot_y, tip_x, tip_y, fill="#f59e0b", width=7, capstyle=tk.ROUND)
        c.create_line(pivot_x, pivot_y, pivot_x + (tip_x - pivot_x) * 0.3, pivot_y + (tip_y - pivot_y) * 0.3, fill="#78350f", width=5)

        # 타자 헬멧 실루엣
        c.create_oval(pivot_x - 14, pivot_y - 42, pivot_x + 14, pivot_y - 14, fill="#1d4ed8", outline="#000")

        # 4. 우측 상단 다이아몬드 주자 현황 미니맵
        dx, dy = w - 85, 80
        ds = 28
        c.create_rectangle(dx - 55, dy - 55, dx + 55, dy + 55, fill="#0f172a", outline="#374151")
        c.create_polygon(dx, dy - ds, dx + ds, dy, dx, dy + ds, dx - ds, dy, fill="#1e293b", outline="#475569")

        # 각 베이스 램프 (홈, 1루, 2루, 3루)
        # 홈 (dy + ds)
        c.create_rectangle(dx - 5, dy + ds - 5, dx + 5, dy + ds + 5, fill="#ffffff", outline="#000")
        # 1루 (dx + ds, dy)
        c.create_rectangle(dx + ds - 6, dy - 6, dx + ds + 6, dy + 6, fill="#ef4444" if self.runners[0] else "#475569", outline="#000")
        # 2루 (dx, dy - ds)
        c.create_rectangle(dx - 6, dy - ds - 6, dx + 6, dy - ds + 6, fill="#ef4444" if self.runners[1] else "#475569", outline="#000")
        # 3루 (dx - ds, dy)
        c.create_rectangle(dx - ds - 6, dy - 6, dx - ds + 6, dy + 6, fill="#ef4444" if self.runners[2] else "#475569", outline="#000")
        c.create_text(dx, dy - 64, text="DIAMOND BASES", fill="#94a3b8", font=("Consolas", 8, "bold"))

        self.after(20, self._render_loop)


# ==============================================================================
# 2. 모드 2: 두뇌 추리 숫자야구 (Number Baseball AI Battle)
# ==============================================================================
class NumberBaseballTab(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg="#0f172a")

        self.digits_count = 3  # 3자리 or 4자리
        self.game_mode = "VS_AI"  # "VS_AI" or "SOLO"
        self.secret_target = ""
        self.ai_secret_target = ""
        self.attempts_history = []
        self.ai_candidates = []
        self.ai_history = []
        self.current_input = ""
        self.turn = "PLAYER"  # "PLAYER" or "AI"
        self.game_over = False

        self._build_ui()
        self.start_new_game()

    def _build_ui(self):
        # 상단 설정 바
        top_bar = tk.Frame(self, bg="#1e293b", padx=14, pady=10)
        top_bar.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(
            top_bar, text="🧠 두뇌 추리 숫자야구", bg="#1e293b", fg="#38bdf8",
            font=("Malgun Gothic", 13, "bold")
        ).pack(side=tk.LEFT, padx=(0, 16))

        # 자리수 선택 (3자리 / 4자리)
        tk.Label(top_bar, text="자리수:", bg="#1e293b", fg="#cbd5e1", font=("Malgun Gothic", 9)).pack(side=tk.LEFT)
        self.digits_var = tk.IntVar(value=3)
        for d in (3, 4):
            tk.Radiobutton(
                top_bar, text=f"{d}자리", variable=self.digits_var, value=d,
                bg="#1e293b", fg="#f8fafc", selectcolor="#0f172a",
                command=self.start_new_game, font=("Malgun Gothic", 9, "bold")
            ).pack(side=tk.LEFT, padx=4)

        # 게임 모드 (AI 대결 / 혼자 풀기)
        tk.Label(top_bar, text=" | 모드:", bg="#1e293b", fg="#cbd5e1", font=("Malgun Gothic", 9)).pack(side=tk.LEFT, padx=(8, 2))
        self.mode_var = tk.StringVar(value="VS_AI")
        tk.Radiobutton(
            top_bar, text="🤖 AI 실시간 대결", variable=self.mode_var, value="VS_AI",
            bg="#1e293b", fg="#a78bfa", selectcolor="#0f172a",
            command=self.start_new_game, font=("Malgun Gothic", 9, "bold")
        ).pack(side=tk.LEFT, padx=3)
        tk.Radiobutton(
            top_bar, text="👤 혼자 도전", variable=self.mode_var, value="SOLO",
            bg="#1e293b", fg="#38bdf8", selectcolor="#0f172a",
            command=self.start_new_game, font=("Malgun Gothic", 9, "bold")
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            top_bar, text="🔄 새 게임 시작", command=self.start_new_game,
            bg="#059669", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"),
            padx=12, pady=4, cursor="hand2"
        ).pack(side=tk.RIGHT)

        # 메인 좌우 분할
        main_pane = tk.Frame(self, bg="#0f172a")
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # 왼쪽: 입력 디스플레이 & 가상 키패드
        left_box = tk.Frame(main_pane, bg="#1e293b", width=340, padx=14, pady=12)
        left_box.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_box.pack_propagate(False)

        tk.Label(
            left_box, text="🎯 숫자 입력 & 키패드", bg="#1e293b", fg="#fde047",
            font=("Malgun Gothic", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        # 입력 표시창
        self.display_var = tk.StringVar(value="_ _ _")
        self.display_lbl = tk.Label(
            left_box, textvariable=self.display_var, bg="#090d16", fg="#38bdf8",
            font=("Consolas", 24, "bold"), pady=12, highlightbackground="#334155", highlightthickness=1
        )
        self.display_lbl.pack(fill=tk.X, pady=(0, 10))

        # 가상 키패드 (1~9, 0, C, 제출)
        key_frame = tk.Frame(left_box, bg="#1e293b")
        key_frame.pack(fill=tk.X)

        keys = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("지움", 3, 0), ("0", 3, 1), ("전송", 3, 2),
        ]
        for txt, r, c in keys:
            bg_col = "#2563eb" if txt.isdigit() else ("#dc2626" if txt == "지움" else "#059669")
            cmd = (lambda t=txt: self._on_key(t))
            btn = tk.Button(
                key_frame, text=txt, command=cmd, bg=bg_col, fg="#ffffff",
                relief=tk.FLAT, font=("Consolas", 12, "bold"), width=6, height=2, cursor="hand2"
            )
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
        key_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # 규칙 안내 박스
        rule_box = tk.Frame(left_box, bg="#090d16", padx=10, pady=8)
        rule_box.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        tk.Label(
            rule_box,
            text="[규칙 설명]\n"
                 "• 중복 없는 0~9 서로 다른 숫자\n"
                 "• 🟡 스트라이크: 숫자와 자리가 모두 일치\n"
                 "• 🟢 볼: 숫자는 맞지만 자리가 다름\n"
                 "• 🔴 아웃: 맞는 숫자가 하나도 없음",
            bg="#090d16", fg="#94a3b8", font=("Malgun Gothic", 9), justify=tk.LEFT
        ).pack(anchor="w")

        # 오른쪽: 판정 로그 테이블 (플레이어 시도 vs AI 시도)
        right_box = tk.Frame(main_pane, bg="#1e293b", padx=12, pady=10)
        right_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.status_banner = tk.Label(
            right_box, text="게임 진행 중...", bg="#0f172a", fg="#4ade80",
            font=("Malgun Gothic", 10, "bold"), padx=10, pady=6, anchor="w"
        )
        self.status_banner.pack(fill=tk.X, pady=(0, 6))

        # 테이블
        cols = ("round", "who", "guess", "result", "desc")
        self.tree = ttk.Treeview(right_box, columns=cols, show="headings", height=14)
        headers = {
            "round": ("회차", 60),
            "who": ("도전자", 90),
            "guess": ("입력 숫자", 100),
            "result": ("판정 결과", 120),
            "desc": ("상세 분석", 320),
        }
        for col_name, (txt, w) in headers.items():
            self.tree.heading(col_name, text=txt)
            self.tree.column(col_name, width=w, anchor="center" if col_name != "desc" else "w")

        self.tree.tag_configure("player", background="#1e293b", foreground="#f8fafc")
        self.tree.tag_configure("ai", background="#090d16", foreground="#c084fc")
        self.tree.tag_configure("win", background="#14532d", foreground="#86efac")

        sb = ttk.Scrollbar(right_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_key(self, key: str):
        if self.game_over:
            return
        if key == "지움":
            if self.current_input:
                self.current_input = self.current_input[:-1]
        elif key == "전송":
            self.submit_player_guess()
            return
        else:
            if len(self.current_input) < self.digits_count:
                if key not in self.current_input:
                    self.current_input += key

        # 디스플레이 갱신
        chars = list(self.current_input) + ["_"] * (self.digits_count - len(self.current_input))
        self.display_var.set(" ".join(chars))

    def start_new_game(self):
        self.digits_count = self.digits_var.get()
        self.game_mode = self.mode_var.get()
        self.current_input = ""
        self.game_over = False
        self.turn = "PLAYER"

        # 플레이어가 맞혀야 할 비밀 숫자 생성
        digits_pool = list("0123456789")
        random.shuffle(digits_pool)
        self.secret_target = "".join(digits_pool[:self.digits_count])

        # AI가 맞혀야 할 비밀 숫자 (AI 대결 모드 시)
        random.shuffle(digits_pool)
        self.ai_secret_target = "".join(digits_pool[:self.digits_count])

        # AI의 초기 추리 후보군 전체 생성 (3자리: 10*9*8 = 720개)
        all_perms = ["".join(p) for p in itertools.permutations("0123456789", self.digits_count)]
        self.ai_candidates = list(all_perms)
        self.attempts_history = []
        self.ai_history = []

        for item in self.tree.get_children():
            self.tree.delete(item)

        chars = ["_"] * self.digits_count
        self.display_var.set(" ".join(chars))

        mode_desc = f"🤖 AI와의 1:1 두뇌 대결! (목표: {self.digits_count}자리)" if self.game_mode == "VS_AI" else f"👤 혼자 도전 모드 ({self.digits_count}자리)"
        self.status_banner.configure(text=f"새 게임 시작! {mode_desc} — 중복 없는 숫자를 입력하세요!")

    @staticmethod
    def evaluate(secret: str, guess: str) -> tuple[int, int]:
        """스트라이크, 볼 판정."""
        strikes = sum(1 for s, g in zip(secret, guess) if s == g)
        balls = sum(1 for g in guess if g in secret) - strikes
        return strikes, balls

    def submit_player_guess(self):
        if len(self.current_input) != self.digits_count:
            messagebox.showwarning("입력 오류", f"{self.digits_count}자리 숫자를 모두 입력해주세요!", parent=self)
            return

        guess = self.current_input
        self.current_input = ""
        self.display_var.set(" ".join(["_"] * self.digits_count))

        strikes, balls = self.evaluate(self.secret_target, guess)
        round_num = len(self.attempts_history) + 1
        res_str = self._format_result(strikes, balls)

        if strikes == self.digits_count:
            self.tree.insert("", tk.END, values=(round_num, "👤 플레이어", guess, res_str, "🎉 정답! 홈런입니다!!"), tags=("win",))
            self.status_banner.configure(text=f"🏆 축하합니다! {round_num}회 만에 정답 [{guess}]을 맞히셨습니다!")
            play_sound("homerun")
            self.game_over = True
            return

        self.attempts_history.append((guess, strikes, balls))
        self.tree.insert("", tk.END, values=(round_num, "👤 플레이어", guess, res_str, f"S:{strikes} B:{balls}"), tags=("player",))
        self.tree.yview_moveto(1.0)

        if self.game_mode == "VS_AI":
            self.after(500, self._ai_turn)

    def _ai_turn(self):
        if self.game_over:
            return

        # AI의 영리한 추리 알고리즘:
        # 남아 있는 후보군 중 하나를 선택하여 추리
        if not self.ai_candidates:
            ai_guess = "".join(random.sample("0123456789", self.digits_count))
        else:
            # 후보군이 많을 때는 랜덤 추출, 좁혀지면 최적 후보 선택
            ai_guess = random.choice(self.ai_candidates)

        strikes, balls = self.evaluate(self.ai_secret_target, ai_guess)
        round_num = len(self.ai_history) + 1
        res_str = self._format_result(strikes, balls)

        # AI 후보군 필터링 (새로운 S, B 판정과 일치하지 않는 후보는 제거)
        self.ai_candidates = [
            c for c in self.ai_candidates
            if self.evaluate(c, ai_guess) == (strikes, balls)
        ]

        if strikes == self.digits_count:
            self.tree.insert(
                "", tk.END,
                values=(round_num, "🤖 AI", ai_guess, res_str, f"AI가 정답을 맞혔습니다! (비밀번호: {self.ai_secret_target})"),
                tags=("win",)
            )
            self.status_banner.configure(text=f"🤖 AI가 {round_num}회 만에 정답 [{ai_guess}]을 맞혔습니다! AI 승리!")
            play_sound("out")
            self.game_over = True
            return

        self.ai_history.append((ai_guess, strikes, balls))
        desc = f"후보군 {len(self.ai_candidates)}개 압축"
        self.tree.insert("", tk.END, values=(round_num, "🤖 AI", ai_guess, res_str, desc), tags=("ai",))
        self.tree.yview_moveto(1.0)
        self.status_banner.configure(text=f"플레이어 턴입니다! (AI 남은 후보군: {len(self.ai_candidates)}개)")

    @staticmethod
    def _format_result(strikes: int, balls: int) -> str:
        if strikes == 0 and balls == 0:
            return "🔴 OUT"
        parts = []
        if strikes > 0:
            parts.append(f"{strikes}S")
        if balls > 0:
            parts.append(f"{balls}B")
        return " ".join(parts)


# ==============================================================================
# 3. 메인 야구 슈퍼 스튜디오 윈도우
# ==============================================================================
class BaseballGameApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚾ [올인원 야구 슈퍼 스튜디오] 배팅 아케이드 & 두뇌 숫자야구 AI")
        self.geometry("1100x780")
        self.minsize(980, 680)
        self.configure(bg="#0f172a")

        self._setup_style()

        # 탭 뷰 (1: 실전 배팅 아케이드 / 2: 두뇌 숫자야구)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.tab_batting = BattingArcadeTab(self.nb)
        self.tab_number = NumberBaseballTab(self.nb)

        self.nb.add(self.tab_batting, text="⚾ 실전 배팅 & 9이닝 아케이드 (타격/홈런)")
        self.nb.add(self.tab_number, text="🧠 두뇌 추리 숫자야구 (AI 대결)")

        # 키보드 스페이스바 전역 바인딩 (배팅 탭일 때 스윙)
        self.bind("<space>", self._on_space)
        self.bind("p", lambda e: self.tab_batting.trigger_pitch())
        self.bind("P", lambda e: self.tab_batting.trigger_pitch())

        # 숫자키 입력 지원 (숫자야구 탭용)
        for i in range(10):
            self.bind(str(i), lambda e, digit=str(i): self._on_digit_key(digit))
        self.bind("<BackSpace>", lambda e: self.tab_number._on_key("지움"))
        self.bind("<Return>", lambda e: self.tab_number._on_key("전송"))

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#0f172a", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1e293b", foreground="#cbd5e1", padding=(16, 8), font=("Malgun Gothic", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])

    def _on_space(self, event):
        cur_tab = self.nb.select()
        if self.nb.index(cur_tab) == 0:
            self.tab_batting.swing_bat()

    def _on_digit_key(self, digit: str):
        cur_tab = self.nb.select()
        if self.nb.index(cur_tab) == 1:
            self.tab_number._on_key(digit)


# ==============================================================================
# 4. 터미널 콘솔(CLI) 모드 (모바일 Termux 및 무헤드 환경 완벽 지원)
# ==============================================================================
def _cli_number_baseball():
    print("\n" + "=" * 50)
    print("🧠 [두뇌 추리 숫자야구] CLI 모드")
    print("=" * 50)
    print("  [1] 1인 도전 모드 (컴퓨터의 비밀번호 맞히기)")
    print("  [2] 🤖 AI 1:1 대결 모드 (플레이어 vs 영리한 AI 턴제 추리)")
    mode = input("👉 모드 선택 (1 or 2): ").strip()

    digits = 3
    d_in = input("👉 자릿수 선택 (3 or 4, 기본: 3): ").strip()
    if d_in == "4":
        digits = 4

    pool = [str(i) for i in range(10)]

    def calc_sb(secret: str, guess: str):
        s = sum(1 for a, b in zip(secret, guess) if a == b)
        b = sum(1 for a in guess if a in secret) - s
        return s, b

    if mode == "2":
        print(f"\n[AI 대결 모드] AI가 맞힐 당신의 {digits}자리 비밀번호(중복 없는 숫자)를 마음속으로 정하세요.")
        while True:
            user_target = input(f"👉 AI에게 출제할 당신의 {digits}자리 비밀번호: ").strip()
            if len(user_target) == digits and user_target.isdigit() and len(set(user_target)) == digits:
                break
            print(f"⚠️ 중복 없는 {digits}자리 숫자를 입력하세요!")

        ai_target = "".join(random.sample(pool, digits))
        ai_candidates = ["".join(p) for p in itertools.permutations(pool, digits)]

        round_num = 1
        print("\n🚀 AI와의 치열한 숫자야구 대결 시작!")
        while True:
            print(f"\n--- [Round {round_num}] ---")
            # 플레이어 턴
            while True:
                user_guess = input(f"👤 당신의 추측 ({digits}자리): ").strip()
                if len(user_guess) == digits and user_guess.isdigit() and len(set(user_guess)) == digits:
                    break
                print(f"⚠️ 서로 다른 {digits}자리 숫자를 입력하세요.")

            s, b = calc_sb(ai_target, user_guess)
            res_str = "OUT" if (s == 0 and b == 0) else f"{s}S {b}B"
            print(f"   결과 ➔ \033[1;93m[{res_str}]\033[0m")

            if s == digits:
                print(f"\n🎉 축하합니다! {round_num}회 만에 AI의 비밀번호 [{ai_target}]를 맞혀 승리하셨습니다!")
                play_sound("homerun")
                break

            # AI 턴
            ai_guess = random.choice(ai_candidates)
            ai_s, ai_b = calc_sb(user_target, ai_guess)
            ai_res = "OUT" if (ai_s == 0 and ai_b == 0) else f"{ai_s}S {ai_b}B"
            print(f"🤖 AI의 추측: [{ai_guess}] ➔ \033[1;96m[{ai_res}]\033[0m (남은 AI 후보군: {len(ai_candidates)}개)")

            if ai_s == digits:
                print(f"\n🤖 아쉽습니다! AI가 {round_num}회 만에 당신의 번호 [{user_target}]를 맞혔습니다. AI 승리!")
                play_sound("out")
                break

            # AI 필터링
            ai_candidates = [cand for cand in ai_candidates if calc_sb(cand, ai_guess) == (ai_s, ai_b)]
            round_num += 1

    else:
        # 1인 모드
        target = "".join(random.sample(pool, digits))
        tries = 0
        print(f"\n🎯 컴퓨터가 서로 다른 {digits}자리 비밀번호를 생성했습니다! 맞춰보세요.")
        while True:
            tries += 1
            while True:
                guess = input(f"[{tries}회차] 추측 ({digits}자리): ").strip()
                if len(guess) == digits and guess.isdigit() and len(set(guess)) == digits:
                    break
                print(f"⚠️ 서로 다른 {digits}자리 숫자를 입력하세요.")

            s, b = calc_sb(target, guess)
            if s == digits:
                print(f"\n🎉 정답입니다! [{target}]을(를) {tries}번 만에 맞히셨습니다!")
                play_sound("homerun")
                break
            elif s == 0 and b == 0:
                print("   ➔ 🔴 \033[1;91m아웃 (OUT)\033[0m")
                play_sound("ball")
            else:
                print(f"   ➔ 🟢 \033[1;92m{s} 스트라이크\033[0m / 🟡 \033[1;93m{b} 볼\033[0m")
                play_sound("hit")

    input("\n엔터를 누르면 메뉴로 돌아갑니다...")


def _cli_batting_game():
    print("\n" + "=" * 50)
    print("🏟️ [실전 타격 9이닝 아케이드] CLI 시뮬레이터")
    print("=" * 50)

    pitches = [
        ("152km/h 불꽃 직구", 0.65),
        ("138km/h 고속 슬라이더", 0.55),
        ("122km/h 폭포수 커브", 0.50),
        ("128km/h 체인지업", 0.52),
        ("135km/h 낙차 포크볼", 0.48),
    ]

    score_player = 0
    score_ai = 0
    max_innings = 3  # 콘솔 모드는 3이닝 스피드 매치

    print("⚡ 3이닝 스피드 매치로 진행됩니다. 플레이어 공격(말 공격)!")

    for inn in range(1, max_innings + 1):
        # AI 초 공격 시뮬레이션
        ai_runs = random.choices([0, 1, 2, 3], weights=[50, 30, 15, 5])[0]
        score_ai += ai_runs
        print(f"\n📢 [{inn}회초] 원정팀(AI) 공격 종료 ➔ {ai_runs}점 획득 (원정 {score_ai} : 홈 {score_player})")

        print(f"\n🔔 [{inn}회말] 당신의 타석입니다! (홈팀 공격)")
        outs = 0
        strikes = 0
        balls = 0
        bases = [False, False, False]  # 1루, 2루, 3루

        while outs < 3:
            pitch_name, base_hit_prob = random.choice(pitches)
            is_zone = random.random() < 0.65  # 65% 확률로 스트라이크 존 투구

            runners_str = "".join(["[3루]" if bases[2] else "", "[2루]" if bases[1] else "", "[1루]" if bases[0] else ""])
            if not runners_str:
                runners_str = "주자 없음"

            print(f"\n⚾ 현재 카운트: {balls}B - {strikes}S | {outs}아웃 | 주자: {runners_str}")
            print(f"투수가 와인드업에 들어갔습니다...")
            print("  [1] 적극 스윙 (타격 노리기)")
            print("  [2] 공 지켜보기 (볼 카운트 싸움)")
            print("  [3] 기습 번트")
            choice = input("👉 당신의 선택: ").strip()

            print(f"⚾ 투구: \033[1;96m{pitch_name}\033[0m")
            time.sleep(0.4)

            if choice == "2":  # 지켜보기
                if is_zone:
                    strikes += 1
                    print("  ➔ 🔴 꽉 찬 스트라이크 존으로 들어옵니다! (루킹 스트라이크)")
                    play_sound("strike")
                else:
                    balls += 1
                    print("  ➔ 🟢 존을 크게 벗어납니다! (볼)")
                    play_sound("ball")

                if balls == 4:
                    print("  🎉 포볼(볼넷) 출루!")
                    balls = 0
                    strikes = 0
                    # 밀어내기 진루
                    if bases[0] and bases[1] and bases[2]:
                        score_player += 1
                        print("  ⭐ 만루 밀어내기 득점! +1점")
                    elif bases[0] and bases[1]:
                        bases[2] = True
                    elif bases[0]:
                        bases[1] = True
                    else:
                        bases[0] = True

                elif strikes == 3:
                    print("  💀 3구 삼진 아웃!")
                    play_sound("out")
                    outs += 1
                    strikes = 0
                    balls = 0

            elif choice == "3":  # 번트
                if is_zone and random.random() < 0.6:
                    print("  👟 완벽한 3루선상 세이프티 번트 성공! 내야 안타!")
                    play_sound("hit")
                    strikes = 0
                    balls = 0
                    if bases[2]:
                        score_player += 1
                        bases[2] = False
                    bases[2], bases[1], bases[0] = bases[1], bases[0], True
                else:
                    print("  ❌ 번트 타구가 포수 뜬공으로 처리됩니다! (아웃)")
                    play_sound("out")
                    outs += 1
                    strikes = 0
                    balls = 0

            else:  # 스윙
                if not is_zone and random.random() < 0.45:
                    print("  💨 유인구에 방망이가 헛돕니다! (헛스윙)")
                    play_sound("strike")
                    strikes += 1
                else:
                    roll = random.random()
                    hit_prob = base_hit_prob + (0.1 if is_zone else -0.2)
                    if roll < hit_prob:
                        play_sound("hit")
                        # 안타 종류 결정
                        hit_roll = random.random()
                        if hit_roll < 0.15:  # 홈런
                            play_sound("homerun")
                            runs = 1 + sum(bases)
                            score_player += runs
                            bases = [False, False, False]
                            print(f"  🚀 깡---!! 담장을 훌쩍 넘어가는 대형 홈런(HOME RUN)!! (+{runs}점)")
                        elif hit_roll < 0.35:  # 2루타
                            runs = sum(bases[1:])
                            score_player += runs
                            bases[2] = bases[0]
                            bases[1] = True
                            bases[0] = False
                            print(f"  🔥 좌중간을 가르는 통렬한 2루타! (+{runs}점)")
                        else:  # 1루타
                            runs = 1 if bases[2] else 0
                            score_player += runs
                            bases[2] = bases[1]
                            bases[1] = bases[0]
                            bases[0] = True
                            print(f"  ✨ 시원한 중전 안타 출루! (+{runs}점)")

                        strikes = 0
                        balls = 0
                    else:
                        # 범타
                        if random.random() < 0.5:
                            print("  🧤 높게 뜬 타구가 야수 정면 플라이 아웃!")
                        else:
                            print("  🧤 빗맞은 땅볼 타구, 1루에서 아웃!")
                        play_sound("out")
                        outs += 1
                        strikes = 0
                        balls = 0

                if strikes >= 3:
                    print("  💀 헛스윙 삼진 아웃!")
                    play_sound("out")
                    outs += 1
                    strikes = 0
                    balls = 0

    print("\n" + "=" * 50)
    print(f"🏁 경기 종료! 최종 스코어 ➔ 홈팀(당신): {score_player} vs 원정팀(AI): {score_ai}")
    if score_player > score_ai:
        print("🏆 승리를 축하합니다! 오늘의 MVP!")
        play_sound("homerun")
    elif score_player < score_ai:
        print("😢 아쉽게 패배했습니다. 다음 경기에 설욕하세요!")
    else:
        print("🤝 팽팽한 명승부 끝에 무승부로 끝났습니다!")
    print("=" * 50)
    input("\n엔터를 누르면 메뉴로 돌아갑니다...")


def run_cli_mode():
    """GUI가 없는 터미널/Termux 환경에서 자동 실행되는 CLI 모드."""
    while True:
        os.system("clear" if os.name != "nt" else "cls")
        print("\033[1;96m====================================================\033[0m")
        print("\033[1;93m ⚾ [올인원 야구 슈퍼 스튜디오] 터미널 콘솔 에디션\033[0m")
        print("\033[1;96m====================================================\033[0m")
        print("  [1] 🧠 두뇌 추리 숫자야구 (솔로 & AI 1:1 대결)")
        print("  [2] 🏟️ 실전 타격 시뮬레이터 (3이닝 스피드 매치)")
        print("  [q] 종료")
        print("\033[1;96m====================================================\033[0m")
        choice = input("👉 선택하세요 (1, 2, q): ").strip().lower()
        if choice == "1":
            _cli_number_baseball()
        elif choice == "2":
            _cli_batting_game()
        elif choice == "q":
            print("\n게임을 종료합니다. 즐거운 하루 되세요!")
            break


if __name__ == "__main__":
    import sys
    if "--cli" in sys.argv:
        run_cli_mode()
    else:
        try:
            app = BaseballGameApp()
            app.mainloop()
        except (tk.TclError, ImportError, Exception) as e:
            print(f"⚠️ GUI 창을 띄울 수 없어 콘솔(CLI) 모드로 자동 전환합니다. ({e})\n")
            run_cli_mode()
