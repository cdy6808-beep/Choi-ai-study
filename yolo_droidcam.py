"""DroidCam 영상에서 물체 탐지: Q/ESC 종료, S 결과 화면 저장."""

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
from time import perf_counter

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent


def check_video(frame):
    """읽기 성공이어도 가상 카메라의 단색 초록 출력일 수 있습니다."""
    pixels = frame[::16, ::16].astype("float32")
    blue, green, red = pixels.mean(axis=(0, 1))
    if green > 60 and green > red + 50 and green > blue + 50 and pixels.std(axis=(0, 1)).max() < 5:
        raise RuntimeError(
            "가상 카메라가 단색 초록 화면을 보내고 있습니다. YOLO를 종료한 뒤 "
            "DroidCam의 File > Exit로 완전히 종료하고 다시 실행·연결하세요. "
            "그다음 YOLO를 다시 실행하세요. 계속되면 --camera 1로 확인하세요.")


def open_camera(index):
    # 가상 카메라 드라이버마다 지원하는 Windows 영상 API가 다릅니다.
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            # 가상 카메라의 기본 해상도를 유지해 출력 형식 재협상을 피합니다.
            ok, frame = cap.read()
            if ok:
                return cap, frame
        cap.release()
    raise RuntimeError(f"카메라 {index}의 영상을 읽지 못했습니다. --camera 1 또는 2로 시도하세요. "
                       "DroidCam 연결을 확인하고 카메라를 사용하는 다른 앱의 미리보기를 닫으세요.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="카메라 번호 (기본 0)")
    parser.add_argument("--conf", type=float, default=0.4, help="탐지 신뢰도 문턱 (0~1)")
    parser.add_argument("--person-only", action="store_true", help="사람만 탐지")
    parser.add_argument("--check", action="store_true", help="화면 없이 한 프레임 탐지 후 종료")
    args = parser.parse_args()
    if not 0 < args.conf <= 1:
        parser.error("--conf는 0 초과 1 이하로 지정하세요.")

    print("YOLO11 nano 모델을 준비합니다. 최초 실행 시 모델을 다운로드합니다.", flush=True)
    model = YOLO(str(ROOT / "yolo11n.pt"))
    cap = None
    try:
        cap, frame = open_camera(args.camera)
        check_video(frame)
        print(f"카메라 {args.camera} 연결 완료. 화면을 클릭한 뒤 Q로 종료, S로 저장.", flush=True)
        while True:
            start = perf_counter()
            # CPU와 작은 입력 크기를 사용해 GPU 없이 실습합니다.
            result = model.predict(frame, imgsz=320, conf=args.conf, device="cpu",
                                   classes=[0] if args.person_only else None, verbose=False)[0]
            counts = Counter(result.names[int(c)] for c in result.boxes.cls.tolist())
            if args.check:
                print(f"한 프레임 탐지 성공: {dict(counts)}", flush=True)
                break
            annotated = result.plot()
            fps = 1 / max(perf_counter() - start, 1e-6)
            # OpenCV 기본 글꼴이 지원하는 영문으로 화면 표시.
            label = f"Inference FPS: {fps:.1f} | " + ", ".join(f"{k}: {v}" for k, v in counts.items())
            cv2.putText(annotated, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (0, 255, 0), 2)
            cv2.imshow("DroidCam YOLO - Q: quit / S: save", annotated)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if cv2.getWindowProperty("DroidCam YOLO - Q: quit / S: save", cv2.WND_PROP_VISIBLE) < 1:
                break
            if key in (ord("s"), ord("S")):
                folder = ROOT / "yolo_results"
                folder.mkdir(exist_ok=True)
                path = folder / f"capture_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
                # 한글 경로에서도 저장되도록 imwrite 대신 인코딩 후 저장.
                ok, encoded = cv2.imencode(".jpg", annotated)
                if not ok:
                    raise RuntimeError("결과 이미지 인코딩 실패")
                encoded.tofile(str(path))
                print(f"저장: {path}", flush=True)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("영상 연결이 끊어졌습니다. 휴대폰과 DroidCam 연결을 확인하세요.")
            check_video(frame)
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n종료했습니다.")
    except (RuntimeError, OSError, cv2.error) as exc:
        raise SystemExit(f"실행 오류: {exc}")
