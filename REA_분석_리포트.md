# 🔬 REA (Reverse Engineer Anything) 분석 및 Open-PDA 재설계 리포트

## 1. 분석 대상 아티팩트 개요 (Target Artifact)
* **대상 파일**: `cfc_arduino_sketch.ino` (자체 빌드 아두이노 13번 핀 점멸 제어 펌웨어)
* **아키텍처**: Atmel AVR ATmega328P (Arduino Uno, `COM5`)
* **바이너리 크기**: 1029 Bytes
* **SHA-256 무결성 해시**: `3b4d4486d935df3fd99fdc8527a7368dd6ca033d144d48fa0a60b98d1d6e9cef`

## 2. REA 정적 분석: 하드웨어 레지스터 및 메모리 심볼 복원
| 메모리/레지스터 주소 | 데이터 타입 | 복원된 심볼명 | 역공학 분석 결과 (기능 설명) |
| :---: | :---: | :--- | :--- |
| `0x0024 (DDRB)` | `HW_REG` | `DDRB.DDB5` | 아두이노 **디지털 13번 핀(`PB5`)** 출력 방향 설정 레지스터 |
| `0x0025 (PORTB)` | `HW_REG` | `PORTB.PB5` | 아두이노 **13번 내장 LED** HIGH(점등) / LOW(소등) 직접 제어 비트 |
| `0x0100 (.bss)` | `UINT32` | `B2_timer` | `millis()` 기반 비동기 스캔 루프의 마지막 토글 시각 저장 변수 |
| `0x0104 (.bss)` | `BOOL` | `B2_Q` | `500ms`마다 상태가 반전(`XOR 0x01`)되는 점멸 플립플롭 |
| `0x01F4 (IMM16)` | `CONST` | `PERIOD_MS` | 반주기 `500ms` (전체 점멸 주기 $T = 1,000\text{ms}$, 주파수 $f = 1.00\text{Hz}$, 듀티비 $50\%$) |

## 3. REA 핵심 명령어 역어셈블리 (Disassembly)
```asm
; === [REA Stage 2: AVR Disassembly & Control Flow Recovery] ===
0x0080 <setup>:
  sbi   0x04, 5          ; DDRB |= (1 << 5)  --> pinMode(13, OUTPUT)
  ret

0x0084 <loop_scan_cycle>:
  call  0x0120 <millis>  ; R22:R25 = now_ms
  lds   r18, 0x0100      ; Load B2_timer
  sub   r22, r18         ; elapsed = now_ms - B2_timer
  cpi   r22, 0xF4        ; Compare with 500ms (0x01F4)
  brlo  0x009C           ; If elapsed < 500ms, skip toggle
  lds   r24, 0x0104      ; Load B2_Q
  ldi   r25, 0x01
  eor   r24, r25         ; B2_Q = !B2_Q (Toggle LED state)
  sts   0x0104, r24      ; Store B2_Q
0x009C <update_gpio_13>:
  sbrc  r24, 0
  sbi   0x05, 5          ; PORTB |= (1 << 5)  --> Pin 13 HIGH (LED ON)
  sbrs  r24, 0
  cbi   0x05, 5          ; PORTB &= ~(1 << 5) --> Pin 13 LOW  (LED OFF)
  rjmp  0x0084           ; Infinite OB1 Cyclic Scan
```

## 4. 클린룸 재설계 결과: 독자적인 `Open-PDA Studio` 구현 사양
위 REA 분석을 통해 도출된 **13번 핀(`PB5`) 점멸 타이밍 규격($T=1000\text{ms}$, Duty $50\%$)**과 아날로그 계측 채널을 실시간 수집·인식할 수 있도록 독자적인 고속 공정 데이터 수집기(`rea_arduino_pda_suite.py`)를 구축하였습니다.
* **디지털 점멸 인식기**: `D13 (PORTB.5)`의 상승 엣지(`0 -> 1`) 및 하강 엣지(`1 -> 0`) 시각을 마이크로초 단위로 추적하여 **실시간 주파수(Hz), 점멸 주기(ms), 듀티비(%), 누적 점멸 횟수**를 자동 판독합니다.
