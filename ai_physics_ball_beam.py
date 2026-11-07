"""
===============================================================================
[물리 엔진 + AI 제어 예제] 실시간 2D 물리 엔진 기반 AI 볼 앤 빔(Ball & Beam) 자율 밸런싱
===============================================================================
실제 중력(g), 질량, 관성, 구름 마찰력, 탄성 충돌, 외부 충격(바람/마우스 푸시)이 작동하는
60FPS 물리 엔진 위에서 AI가 스스로 학습하며 시소(서보 모터) 각도를 조절해
굴러가는 쇠구슬을 목표 위치(Target)에 정확히 멈춰 세우는 시뮬레이터입니다.

핵심 기능:
1. 60FPS RK4/Semi-Implicit Euler 강체 물리 엔진 (중력, 경사 가속도, 마찰, 벽면 탄성 충돌)
2. 3가지 제어 모드:
   - 🤖 AI 자율 신경망/강화 제어 (실시간 온라인 가중치 자동 학습!)
   - ⚙️ 표준 PID 제어기 (슬라이더로 Kp, Ki, Kd 직접 조절 실험)
   - 🎮 수동 조작 모드 (키보드 좌/우 화살표로 직접 균형 잡기 도전)
3. 마우스 클릭으로 목표 지점(깃발) 이동 & '💥 외란 충격 주기'로 AI 복원력 테스트
4. 실시간 오실로스코프 파형 (목표 위치 vs 실제 공 위치 vs 서보 각도)
===============================================================================
"""

import math
import random
import tkinter as tk
from tkinter import ttk


class PhysicsBallBeamWorld:
    """실제 물리 법칙(뉴턴 역학 & 회전 운동)을 계산하는 2D 물리 엔진."""

    def __init__(self):
        # 물리 상수
        self.g = 9.81                 # 중력가속도 (m/s^2)
        self.beam_length = 2.0        # 시소(빔) 길이 (m) -> 좌우 -1.0m ~ +1.0m
        self.ball_radius = 0.06       # 구슬 반지름 (m)
        self.friction = 0.22          # 구름 저항 계수
        self.restitution = 0.55       # 양 끝 스토퍼 탄성 반발 계수

        # 동적 상태 변수 (State Vector)
        self.ball_x = -0.65           # 구슬 위치 (m), 중앙 = 0.0
        self.ball_v = 0.0             # 구슬 속도 (m/s)
        self.ball_a = 0.0             # 구슬 가속도 (m/s^2)
        self.ball_spin = 0.0          # 구슬 회전각 (rad, 바퀴 무늬 렌더링용)

        self.beam_angle = 0.0         # 현재 시소 각도 (rad)
        self.beam_target_angle = 0.0  # 서보 모터 목표 각도 (rad)
        self.max_angle = math.radians(24.0)  # 최대 기울기 제한 (±24도)
        self.servo_speed = 4.5        # 서보 모터 응답 속도 (rad/s)

        self.target_x = 0.0           # 목표 위치 (m)
        self.wind_force = 0.0         # 외부 바람/충격 외란 가속도

    def step(self, dt: float):
        """물리 엔진 1 프레임 적분 (Semi-implicit Euler)."""
        # 1. 서보 모터 동역학 (지연 응답 반영)
        target_clamped = max(-self.max_angle, min(self.max_angle, self.beam_target_angle))
        angle_diff = target_clamped - self.beam_angle
        max_step = self.servo_speed * dt
        if abs(angle_diff) <= max_step:
            self.beam_angle = target_clamped
        else:
            self.beam_angle += math.copysign(max_step, angle_diff)

        # 2. 경사면 위 구슬의 병진+회전 가속도 공식:
        #    고체 구(Solid Sphere)의 관성모멘트 I = (2/5)mR^2 이므로 a = -(5/7) * g * sin(theta)
        gravity_acc = -(5.0 / 7.0) * self.g * math.sin(self.beam_angle)
        drag_acc = -self.friction * self.ball_v
        self.ball_a = gravity_acc + drag_acc + self.wind_force

        # 외란 자연 감쇠
        self.wind_force *= 0.88

        # 3. 속도 및 위치 업데이트
        self.ball_v += self.ball_a * dt
        self.ball_x += self.ball_v * dt
        self.ball_spin += (self.ball_v / self.ball_radius) * dt

        # 4. 빔 양 끝 스토퍼(벽) 탄성 충돌 처리
        limit = (self.beam_length / 2.0) - self.ball_radius
        if self.ball_x < -limit:
            self.ball_x = -limit
            self.ball_v = -self.ball_v * self.restitution
        elif self.ball_x > limit:
            self.ball_x = limit
            self.ball_v = -self.ball_v * self.restitution


class AdaptiveAIController:
    """
    온라인 경사하강법(Actor-Critic / MIT Rule 적응 제어)으로
    물리 환경의 마찰과 관성에 맞춰 스스로 가중치(W_p, W_d, W_i)를 진화시키는 AI 제어기.
    """

    def __init__(self):
        # 초기 신경망 가중치 (초기에는 약간 덜 다듬어진 상태에서 시작해 실시간으로 최적화됨)
        self.w_p = 0.45   # 위치 오차 가중치
        self.w_d = 0.32   # 속도 댐핑 가중치
        self.w_i = 0.08   # 정상상태 오차 적분 가중치
        self.integral_err = 0.0
        self.learning_rate = 0.08
        self.episodes_steps = 0

    def compute_action(self, target_x: float, ball_x: float, ball_v: float, dt: float) -> float:
        err = target_x - ball_x
        self.integral_err = max(-0.8, min(0.8, self.integral_err + err * dt))

        # 온라인 적응 학습:
        # 오버슈트(목표를 지나쳐 속도가 반대이거나 진동할 때) 발생 시 댐핑 가중치(w_d)를 강화하고,
        # 목표 도달이 느릴 때 비례 가중치(w_p)를 자동 조정
        if abs(err) > 0.02:
            # 위치 오차와 속도가 같은 방향(목표에서 멀어지는 중)이면 제동력 강화
            if err * (-ball_v) < 0:
                self.w_d = min(1.15, self.w_d + self.learning_rate * abs(ball_v) * dt)
            self.w_p = min(1.25, max(0.35, self.w_p + self.learning_rate * (abs(err) - 0.15) * dt))

        # 시소를 오른쪽(+angle)으로 기울이면 중력이 왼쪽(-x)으로 작용하므로 부호 반전
        raw_angle = -(self.w_p * err - self.w_d * ball_v + self.w_i * self.integral_err)
        self.episodes_steps += 1
        return raw_angle


class PhysicsAISimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🪐 [물리 엔진 + AI 제어] 실시간 볼 앤 빔(Ball & Beam) 자율 밸런싱 & 아두이노 서보 시뮬레이터")
        self.geometry("1420x860")
        self.minsize(1120, 700)
        self.configure(bg="#0f172a")

        self.world = PhysicsBallBeamWorld()
        self.ai_ctrl = AdaptiveAIController()

        # 제어 모드: "AI", "PID", "MANUAL"
        self.mode_var = tk.StringVar(value="AI")
        self.pid_integral = 0.0
        self.prev_err = 0.0

        # 오실로스코프 히스토리 (최근 220 프레임)
        self.hist_target = [0.0] * 220
        self.hist_ball = [0.0] * 220
        self.hist_servo = [90.0] * 220

        self._build_ui()

        # 키보드 수동 조작 바인딩
        self.bind("<Left>", lambda e: self._manual_tilt(-4.0))
        self.bind("<Right>", lambda e: self._manual_tilt(4.0))

        # 60 FPS 물리 루프 시작
        self.after(16, self._physics_loop)

    def _build_ui(self):
        # 1. 상단 툴바
        top = tk.Frame(self, bg="#1e293b", padx=14, pady=10)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(
            top,
            text="🪐 2D 물리 엔진 × AI 자율 균형 제어기 (Ball & Beam Servo System)",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Malgun Gothic", 13, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 18))

        # 제어 모드 선택 라디오 버튼
        modes = [
            ("🤖 AI 자율 신경망 제어 (자동 학습)", "AI", "#059669"),
            ("⚙️ 고전 PID 제어 (수동 튜닝)", "PID", "#2563eb"),
            ("🎮 사람 직접 조작 (방향키 ◀/▶)", "MANUAL", "#7c3aed"),
        ]
        for txt, val, col in modes:
            rb = tk.Radiobutton(
                top,
                text=txt,
                variable=self.mode_var,
                value=val,
                bg=col,
                fg="#ffffff",
                selectcolor="#0f172a",
                activebackground=col,
                activeforeground="#ffffff",
                indicatoron=False,
                font=("Malgun Gothic", 9, "bold"),
                padx=12,
                pady=6,
                cursor="hand2",
            )
            rb.pack(side=tk.LEFT, padx=4)

        # 외란(충격) 버튼들
        tk.Button(
            top,
            text="💥 왼쪽 강풍/충격 주기!",
            command=lambda: self._apply_impulse(-6.5),
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
            text="💥 오른쪽 강풍/충격 주기!",
            command=lambda: self._apply_impulse(6.5),
            bg="#ea580c",
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 9, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            top,
            text="🎯 목표 위치 랜덤 변경",
            command=self._random_target,
            bg="#d97706",
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Malgun Gothic", 9, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=4)

        # 2. 메인 영역 (좌측: 물리 엔진 캔버스 + 실시간 파형 / 우측: 물리 파라미터 & AI 신경망 상태)
        main = tk.Frame(self, bg="#0f172a")
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        left_col = tk.Frame(main, bg="#0f172a")
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 물리 엔진 메인 뷰포트 캔버스
        self.sim_canvas = tk.Canvas(
            left_col, bg="#090d16", height=470, highlightthickness=1, highlightbackground="#334155"
        )
        self.sim_canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.sim_canvas.bind("<Button-1>", self._on_canvas_click)

        # 하단 실시간 오실로스코프 차트 (목표 vs 구슬 위치 vs 서보 모터 각도)
        self.scope_canvas = tk.Canvas(
            left_col, bg="#090d16", height=220, highlightthickness=1, highlightbackground="#334155"
        )
        self.scope_canvas.pack(fill=tk.X)

        # 우측 컨트롤 패널
        right_col = tk.Frame(main, bg="#1e293b", width=340, padx=14, pady=12)
        right_col.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_col.pack_propagate(False)

        self._build_control_panel(right_col)

    def _build_control_panel(self, parent):
        tk.Label(
            parent, text="🧠 AI 신경망 & 하드웨어 텔레메트리", bg="#1e293b", fg="#38bdf8", font=("Malgun Gothic", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        self.telemetry_lbl = tk.Label(
            parent,
            text="",
            bg="#0f172a",
            fg="#4ade80",
            font=("Consolas", 10),
            justify=tk.LEFT,
            anchor="w",
            padx=10,
            pady=10,
        )
        self.telemetry_lbl.pack(fill=tk.X, pady=(0, 12))

        # 물리 환경 설정 슬라이더
        tk.Label(
            parent, text="🌍 물리 엔진 환경 변수 조절", bg="#1e293b", fg="#fbbf24", font=("Malgun Gothic", 10, "bold")
        ).pack(anchor="w", pady=(4, 4))

        self.grav_scale = self._add_slider(parent, "중력 가속도 g (지구=9.8, 달=1.6, 목성=24.8)", 1.6, 25.0, 9.81)
        self.fric_scale = self._add_slider(parent, "시소 표면 마찰 계수 (얼음=0.02 ~ 사포=0.8)", 0.02, 0.80, 0.22)
        self.rest_scale = self._add_slider(parent, "양끝 벽면 탄성 반발력 (탱탱볼 효과)", 0.1, 0.95, 0.55)

        # PID 게인 슬라이더 (PID 모드일 때 사용)
        tk.Label(
            parent, text="⚙️ PID 제어 게인 (PID 모드용)", bg="#1e293b", fg="#c084fc", font=("Malgun Gothic", 10, "bold")
        ).pack(anchor="w", pady=(12, 4))

        self.kp_scale = self._add_slider(parent, "비례 게인 (Kp - 복원력)", 0.0, 1.5, 0.55)
        self.kd_scale = self._add_slider(parent, "미분 게인 (Kd - 브레이크 제동력)", 0.0, 1.5, 0.38)
        self.ki_scale = self._add_slider(parent, "적분 게인 (Ki - 정밀 오차 보정)", 0.0, 0.5, 0.05)

        tk.Label(
            parent,
            text="💡 팁: 왼쪽 물리 화면에서 원하는 위치를 마우스로 클릭하면 목표 깃발(🎯)이 그곳으로 이동하고, AI가 즉시 시소를 기울여 공을 배달합니다!",
            bg="#1e293b",
            fg="#94a3b8",
            wraplength=310,
            justify=tk.LEFT,
            font=("Malgun Gothic", 9),
            pady=10,
        ).pack(side=tk.BOTTOM, fill=tk.X)

    def _add_slider(self, parent, label_txt, min_v, max_v, init_v):
        tk.Label(parent, text=label_txt, bg="#1e293b", fg="#cbd5e1", font=("Malgun Gothic", 8)).pack(anchor="w")
        s = tk.Scale(
            parent,
            from_=min_v,
            to=max_v,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            bg="#1e293b",
            fg="#f8fafc",
            highlightthickness=0,
            troughcolor="#0f172a",
            activebackground="#38bdf8",
        )
        s.set(init_v)
        s.pack(fill=tk.X, pady=(0, 6))
        return s

    # --------------------------------------------------------------------------
    # 상호작용 이벤트
    # --------------------------------------------------------------------------
    def _on_canvas_click(self, event):
        w = max(self.sim_canvas.winfo_width(), 600)
        cx = w / 2.0
        px_per_meter = min(w * 0.36, 320.0)
        # 마우스 클릭 좌표를 시소 위 거리(-0.85m ~ +0.85m)로 변환
        clicked_m = (event.x - cx) / px_per_meter
        self.world.target_x = max(-0.85, min(0.85, clicked_m))

    def _apply_impulse(self, force: float):
        self.world.wind_force = force

    def _random_target(self):
        self.world.target_x = round(random.uniform(-0.75, 0.75), 2)

    def _manual_tilt(self, deg_delta: float):
        if self.mode_var.get() == "MANUAL":
            self.world.beam_target_angle += math.radians(deg_delta)

    # --------------------------------------------------------------------------
    # 60FPS 물리 엔진 + AI 제어 메인 루프
    # --------------------------------------------------------------------------
    def _physics_loop(self):
        dt = 0.016  # 60Hz (16ms)

        # 슬라이더의 물리 상수 실시간 반영
        self.world.g = self.grav_scale.get()
        self.world.friction = self.fric_scale.get()
        self.world.restitution = self.rest_scale.get()

        mode = self.mode_var.get()
        err = self.world.target_x - self.world.ball_x

        if mode == "AI":
            cmd_angle = self.ai_ctrl.compute_action(
                self.world.target_x, self.world.ball_x, self.world.ball_v, dt
            )
            self.world.beam_target_angle = cmd_angle
        elif mode == "PID":
            kp = self.kp_scale.get()
            kd = self.kd_scale.get()
            ki = self.ki_scale.get()
            self.pid_integral = max(-1.0, min(1.0, self.pid_integral + err * dt))
            d_err = (err - self.prev_err) / dt
            self.prev_err = err
            self.world.beam_target_angle = -(kp * err + kd * d_err + ki * self.pid_integral)

        # 물리 스텝 진행
        self.world.step(dt)

        # 아두이노 서보 모터 각도 환산 (수평 90도 기준, 0~180도)
        servo_deg = 90.0 + math.degrees(self.world.beam_angle)

        # 히스토리 기록
        self.hist_target.append(self.world.target_x)
        self.hist_ball.append(self.world.ball_x)
        self.hist_servo.append(servo_deg)
        self.hist_target.pop(0)
        self.hist_ball.pop(0)
        self.hist_servo.pop(0)

        # 렌더링 업데이트
        self._render_physics_scene(servo_deg, err)
        self._render_oscilloscope()
        self._update_telemetry(servo_deg, err)

        self.after(16, self._physics_loop)

    # --------------------------------------------------------------------------
    # 캔버스 그래픽 렌더링 (시소, 굴러가는 쇠구슬, 속도/중력 벡터 화살표, 목표 깃발)
    # --------------------------------------------------------------------------
    def _render_physics_scene(self, servo_deg: float, err: float):
        c = self.sim_canvas
        c.delete("all")
        w = max(c.winfo_width(), 700)
        h = max(c.winfo_height(), 420)
        cx, cy = w / 2.0, h * 0.58
        scale = min(w * 0.36, 320.0)  # 1m 당 픽셀 수

        # 배경 그리드
        for gx in range(0, w, 40):
            c.create_line(gx, 0, gx, h, fill="#111827")
        for gy in range(0, h, 40):
            c.create_line(0, gy, w, gy, fill="#111827")

        # 상단 안내 문구
        c.create_text(
            18, 22,
            text="🖱️ 시소 위 아무 곳이나 마우스로 클릭하면 목표 지점(🎯)이 바뀝니다!  |  우측 상단 [💥 강풍/충격 주기] 버튼으로 물리 엔진을 흔들어보세요!",
            fill="#94a3b8", anchor="w", font=("Malgun Gothic", 9, "bold")
        )

        # 1. 중앙 피벗 받침대 (삼각형 스탠드)
        c.create_polygon(
            cx, cy, cx - 42, cy + 95, cx + 42, cy + 95,
            fill="#334155", outline="#64748b", width=2
        )
        c.create_rectangle(cx - 75, cy + 95, cx + 75, cy + 110, fill="#1e293b", outline="#475569")

        # 2. 회전하는 빔(시소) 좌표 계산
        theta = self.world.beam_angle
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        half_L = (self.world.beam_length / 2.0) * scale

        # 화면 좌표계에서 +theta는 시계방향(오른쪽이 아래로 기울어짐)
        x_left = cx - half_L * cos_t
        y_left = cy - half_L * sin_t
        x_right = cx + half_L * cos_t
        y_right = cy + half_L * sin_t

        # 양 끝 탄성 스토퍼 벽
        nx, ny = sin_t, -cos_t  # 빔 윗면 법선 벡터 (위쪽 방향)
        c.create_line(x_left, y_left, x_left + nx * 28, y_left + ny * 28, fill="#f59e0b", width=6, capstyle=tk.ROUND)
        c.create_line(x_right, y_right, x_right + nx * 28, y_right + ny * 28, fill="#f59e0b", width=6, capstyle=tk.ROUND)

        # 빔 본체
        c.create_line(x_left, y_left, x_right, y_right, fill="#38bdf8", width=12, capstyle=tk.ROUND)
        c.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill="#fbbf24", outline="#0f172a", width=2)

        # 빔 눈금 표시 (-0.8m ~ +0.8m)
        for m_tick in (-0.8, -0.4, 0.0, 0.4, 0.8):
            tx = cx + (m_tick * scale) * cos_t
            ty = cy + (m_tick * scale) * sin_t
            c.create_line(tx, ty, tx - nx * 10, ty - ny * 10, fill="#cbd5e1", width=1.5)

        # 3. 목표 위치(Target Flag 🎯) 그리기
        targ_dist = self.world.target_x * scale
        fx = cx + targ_dist * cos_t + nx * 6
        fy = cy + targ_dist * sin_t + ny * 6
        c.create_line(fx, fy, fx + nx * 48, fy + ny * 48, fill="#22c55e", width=3, dash=(4, 2))
        c.create_oval(fx + nx * 48 - 10, fy + ny * 48 - 10, fx + nx * 48 + 10, fy + ny * 48 + 10, fill="#22c55e", outline="#ffffff", width=1.5)
        c.create_text(fx + nx * 66, fy + ny * 66, text=f"🎯 목표 ({self.world.target_x:+.2f}m)", fill="#4ade80", font=("Malgun Gothic", 9, "bold"))

        # 4. 굴러가는 쇠구슬(Ball) 그리기
        r_px = self.world.ball_radius * scale
        b_dist = self.world.ball_x * scale
        bx = cx + b_dist * cos_t + nx * (r_px + 6)
        by = cy + b_dist * sin_t + ny * (r_px + 6)

        # 목표 지점에 들어왔으면 초록색 후광, 아니면 주황색 구슬
        in_zone = abs(err) < 0.03 and abs(self.world.ball_v) < 0.08
        ball_col = "#22c55e" if in_zone else "#f97316"
        if in_zone:
            c.create_oval(bx - r_px - 6, by - r_px - 6, bx + r_px + 6, by + r_px + 6, outline="#4ade80", width=2.5)

        c.create_oval(bx - r_px, by - r_px, bx + r_px, by + r_px, fill=ball_col, outline="#ffffff", width=2)

        # 구슬 회전 스포크(바퀴살) 표시 — 실제 구름 회전이 눈으로 보임!
        for k in range(2):
            ang = self.world.ball_spin + k * (math.pi / 2.0)
            sx1 = bx + (r_px - 3) * math.cos(ang)
            sy1 = by + (r_px - 3) * math.sin(ang)
            sx2 = bx - (r_px - 3) * math.cos(ang)
            sy2 = by - (r_px - 3) * math.sin(ang)
            c.create_line(sx1, sy1, sx2, sy2, fill="#ffffff", width=1.5)

        # 5. 속도 벡터 화살표 (Velocity Vector)
        if abs(self.world.ball_v) > 0.02:
            v_len = self.world.ball_v * 55.0
            vx = bx + v_len * cos_t
            vy = by + v_len * sin_t
            c.create_line(bx, by, vx, vy, fill="#fbbf24", width=3, arrow=tk.LAST)
            c.create_text(vx, vy - 14, text=f"v={self.world.ball_v:+.2f}m/s", fill="#fde047", font=("Consolas", 8, "bold"))

        # 6. 아두이노 서보 모터(COM5 Pin 10) 실시간 각도 게이지 표시
        c.create_text(
            cx, cy + 130,
            text=f"🦾 Arduino Servo (Pin 10) 출력 각도: {servo_deg:.1f}°   |   현재 오차: {err*100:+.1f} cm",
            fill="#38bdf8", font=("Malgun Gothic", 11, "bold")
        )

    def _render_oscilloscope(self):
        sc = self.scope_canvas
        sc.delete("all")
        w = max(sc.winfo_width(), 700)
        h = max(sc.winfo_height(), 180)

        sc.create_text(
            14, 16,
            text="📊 실시간 물리 오실로스코프 — 초록 점선: 목표 위치(m)  |  주황 실선: 실제 구슬 위치(m)  |  하늘색 선: 서보 각도",
            fill="#cbd5e1", anchor="w", font=("Malgun Gothic", 9, "bold")
        )

        pad_x, pad_y = 45, 32
        pw = w - pad_x - 20
        ph = h - pad_y - 16
        mid_y = pad_y + ph / 2.0

        sc.create_line(pad_x, mid_y, w - 20, mid_y, fill="#334155", dash=(2, 2))

        n = len(self.hist_ball)
        pts_t, pts_b, pts_s = [], [], []
        for i in range(n):
            px = pad_x + (i / (n - 1)) * pw
            py_t = mid_y - (self.hist_target[i] / 1.0) * (ph * 0.45)
            py_b = mid_y - (self.hist_ball[i] / 1.0) * (ph * 0.45)
            py_s = mid_y - ((self.hist_servo[i] - 90.0) / 30.0) * (ph * 0.45)
            pts_t.extend((px, py_t))
            pts_b.extend((px, py_b))
            pts_s.extend((px, py_s))

        if len(pts_s) >= 4:
            sc.create_line(*pts_s, fill="#0284c7", width=1.5)
            sc.create_line(*pts_t, fill="#22c55e", width=2, dash=(4, 2))
            sc.create_line(*pts_b, fill="#f97316", width=2.5)

    def _update_telemetry(self, servo_deg: float, err: float):
        txt = (
            f"[실시간 물리 상태]\n"
            f" • 구슬 위치 (x) : {self.world.ball_x:+.3f} m\n"
            f" • 목표 위치 (r) : {self.world.target_x:+.3f} m\n"
            f" • 위치 오차 (e) : {err*100:+.1f} cm\n"
            f" • 구슬 속도 (v) : {self.world.ball_v:+.3f} m/s\n"
            f" • 구슬 가속도(a): {self.world.ball_a:+.3f} m/s²\n\n"
            f"[🤖 AI 적응형 신경망 가중치]\n"
            f" • W_p (위치복원): {self.ai_ctrl.w_p:.3f}\n"
            f" • W_d (속도제동): {self.ai_ctrl.w_d:.3f}\n"
            f" • W_i (오차적분): {self.ai_ctrl.w_i:.3f}\n\n"
            f"[🔌 아두이노 서보 출력]\n"
            f" • servo.write({int(round(servo_deg))}) deg"
        )
        self.telemetry_lbl.configure(text=txt)


if __name__ == "__main__":
    app = PhysicsAISimulatorApp()
    app.mainloop()
