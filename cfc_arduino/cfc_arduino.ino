// Arduino sketch for CFC runtime I/O bridge (COM5).
// Pins: inputs D2,D3,D4 ; outputs D8,D9
const int IN_PINS[] = {2, 3, 4};
const int OUT_PINS[] = {8, 9};
const int NIN = 3, NOUT = 2;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < NIN; i++) pinMode(IN_PINS[i], INPUT_PULLUP);
  for (int i = 0; i < NOUT; i++) { pinMode(OUT_PINS[i], OUTPUT); digitalWrite(OUT_PINS[i], LOW); }
}

void loop() {
  // Send inputs
  Serial.print("I0="); Serial.print(digitalRead(IN_PINS[0]) == LOW ? 1 : 0);
  Serial.print(",I1="); Serial.print(digitalRead(IN_PINS[1]) == LOW ? 1 : 0);
  Serial.print(",I2="); Serial.println(digitalRead(IN_PINS[2]) == LOW ? 1 : 0);

  // Read outputs if available
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    // parse "O0=1,O1=0"
    int idx = 0;
    while (idx < line.length()) {
      int eq = line.indexOf('=', idx);
      if (eq < 0) break;
      int comma = line.indexOf(',', eq);
      if (comma < 0) comma = line.length();
      String key = line.substring(idx, eq);
      int val = line.substring(eq + 1, comma).toInt();
      int pin = key.substring(1).toInt();
      if (pin >= 0 && pin < NOUT) digitalWrite(OUT_PINS[pin], val ? HIGH : LOW);
      idx = comma + 1;
    }
  }
  delay(50);
}
