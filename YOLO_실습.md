# 휴대폰 + DroidCam + YOLO

휴대폰 영상을 Windows 가상 카메라로 받아 컴퓨터에서 분석합니다.
영상은 추론 서버로 업로드하지 않으며, S를 누를 때만 결과 사진을 저장합니다.
최초 패키지 설치와 모델 다운로드에는 인터넷이 필요합니다.

## 실행

프로젝트 폴더의 PowerShell 터미널에서:

```powershell
.\.venv-yolo\Scripts\python.exe yolo_droidcam.py
```

다른 카메라가 보이거나 연결 실패 시 번호를 변경합니다.

```powershell
.\.venv-yolo\Scripts\python.exe yolo_droidcam.py --camera 1
.\.venv-yolo\Scripts\python.exe yolo_droidcam.py --camera 2
```

DroidCam 연결은 유지하고, 다른 프로그램에서 카메라 영상을 보고 있다면
그 프로그램의 미리보기를 닫으세요. 카메라를 동시에 사용할 수 없는 경우가 있습니다.

## 실습 순서

1. 전면 카메라에 자신을 비추고 `person` 상자를 확인합니다. 얼굴 인식이나 신원 확인은 아닙니다.
2. 컵, 의자, 휴대폰 등을 비춰 탐지 결과와 숫자를 비교합니다.
3. 결과 창을 클릭하고 S로 사진을 저장합니다. `yolo_results` 폴더에 생성됩니다.
4. Q 또는 ESC로 종료합니다.

사람만 찾으려면:

```powershell
.\.venv-yolo\Scripts\python.exe yolo_droidcam.py --person-only
```

신뢰도 문턱을 바꾸려면:

```powershell
.\.venv-yolo\Scripts\python.exe yolo_droidcam.py --conf 0.6
```

문턱을 높이면 낮은 점수의 탐지는 숨겨집니다. 표시 숫자는 모델의 신뢰도 점수이며
정답 확률을 보장하지 않습니다. 기본 모델은 일반 물체용으로 계기나 밸브 전용 모델이 아닙니다.
FPS는 추론과 상자 그리기 처리 속도이며, Wi-Fi 지연을 포함한 전체 영상 속도는 아닙니다.

VS Code의 실행 버튼을 쓸 때는 인터프리터를 `.venv-yolo\Scripts\python.exe`로 선택하세요.
기존 pandas 실습은 `.venv` 환경을 사용합니다.

공식 사용법: https://docs.ultralytics.com/modes/predict/
