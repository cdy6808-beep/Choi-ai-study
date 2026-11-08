# 📱 최동열 님의 AI & 자동화 통합 실습 저장소 (`Choi-ai-study`)

휴대폰 인터넷 브라우저에서 **이 페이지(`github.com/cdy6808-beep/Choi-ai-study`)**를 열면, 아래 코드 상자 오른쪽 위의 **[복사(📋) 아이콘]**을 터치 한 번만 해서 **Termux**에 바로 붙여넣기(`Paste`) 하실 수 있습니다!

---

## 🚀 1. 휴대폰 Termux 최초 설치 & 실행 (오른쪽 위 📋 버튼 터치 후 Termux에 붙여넣기!)

```bash
pkg update -y && pkg install git python -y && rm -rf Choi-ai-study && git clone https://github.com/cdy6808-beep/Choi-ai-study.git && cd Choi-ai-study && python go.py
```

---

## 🔄 2. 휴대폰 Termux에서 최신 코드로 업데이트 후 실행하기

```bash
cd ~/Choi-ai-study && git pull && python go.py
```

---

## 💻 3. 수록된 전체 프로그램 목록 (PC & 모바일)

| 파일명 | 설명 |
| :--- | :--- |
| **`cfc_editor.py`** | 🎨 지멘스 SIMATIC CFC 스타일 아두이노(`COM5`) 시각 코딩 스튜디오 |
| **`ai_level1_anomaly_detector.py`** | 🤖 [AI Level 1] 계측 CSV 데이터 Isolation Forest 이상치 탐지 리포터 |
| **`ai_physics_ball_beam.py`** | 🪐 60FPS 2D 물리 엔진 + AI 볼 앤 빔(Ball & Beam) 자율 밸런싱 시뮬레이터 |
| **`pump_overshoot_monitor.py`** | 🛡️ 펌프 기동(Run)/정지(Stop) 오버슈팅 자동 배제(Blanking) 감시기 |
| **`weekly_1sec_pump_trend.py`** | 📅 일주일(604,800초) 1초 타임베이스 펌프 트렌드 현미경 분석기 |
| **`pc_plc_field_server.py`** | 🏭 PC 현장 설비 무선 서버 (휴대폰 Termux 실시간 연동용) |
| **`termux_1_field_tester.py`** | 📱 휴대폰 Termux용 스마트 PLC/4~20mA 필드 진단기 |
| **`hangul_card_game_100.py`** | 🎴 9세 두뇌 발달 수묵 산수화 한글 낱말 카드 게임 (Stage 0 ~ 100) |
| **`ibapda_arduino_bridge.py`** | 🔌 `COM5` 아두이노 ➔ `ibaPDA` 실시간 연동 브릿지 (Modbus TCP & UDP) |
| **`rea_arduino_pda_suite.py`** | 🔬 REA 역공학 분석 워크벤치 & 아두이노 13번 LED 점멸 실시간 인식 Open-PDA |
| **`starcraft_ai_dda.py`** | ⚔️ 스타크래프트 싱글플레이 × AI 동적 난이도 조절(DDA) 전술 시뮬레이터 |
| **`REA_분석_리포트.md`** | 📄 아두이노 13번 핀 점멸 펌웨어 REA 역공학 분석 및 재설계 리포트 |
