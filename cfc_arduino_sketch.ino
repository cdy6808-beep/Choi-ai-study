// ============================================================================
// [어린이 아두이노 CFC 스튜디오]에서 자동 생성된 아두이노 코드입니다.
// 지멘스 PLC의 CFC 차트처럼 매 순간 모든 블록이 동시에 똑똑하게 작동합니다!
// ============================================================================
#include <Arduino.h>

long B1_OUT = 0; // 🔢 숫자 상수 출력
bool B2_Q = 0; // ✨ 깜빡깜빡 신호기 출력
unsigned long B2_timer = 0;
bool B3_Q = 0; // 💡 LED 전구 켜기 출력

void setup() {
  pinMode(13, OUTPUT); // 출력 핀 13번
}

void loop() {
  unsigned long now = millis();

  // [1번 블록] 🔢 숫자 상수
  B1_OUT = 50;

  // [2번 블록] ✨ 깜빡깜빡 신호기
  if (B1_OUT) {
    if (now - B2_timer >= 500) {
      B2_Q = !B2_Q;
      B2_timer = now;
    }
  } else { B2_Q = false; }

  // [3번 블록] 💡 LED 전구 켜기
  B3_Q = B2_Q;
  digitalWrite(13, B3_Q ? HIGH : LOW);

}