"""계장정비 pandas 실습 10선. 모든 데이터와 판정 기준은 교육용 가상 값입니다.

실행: .venv/Scripts/python.exe instrument_examples.py 1
전체 실행: .venv/Scripts/python.exe instrument_examples.py all
설비 연결이나 제어 명령 없이 표와 CSV만 생성합니다.
"""

import sys
from pathlib import Path

import pandas as pd

OUTPUT = Path(__file__).resolve().parent / "instrument_results"


def example_01():
    """초급: 4~20 mA 신호를 압력으로 환산하기."""
    df = pd.DataFrame({"태그": ["PT-101", "PT-102", "PT-103", "PT-104"],
                       "전류_mA": [4.0, 12.0, 20.0, 3.5]})
    # 가상 압력 범위: 0~10 bar. 범위 밖 신호도 그대로 환산해 이상을 드러냅니다.
    df["압력_bar"] = (df["전류_mA"] - 4) / 16 * 10
    df["범위밖"] = ~df["전류_mA"].between(4, 20)
    return df


def example_02():
    """초급: 압력계 5점 교정 오차 판정하기."""
    df = pd.DataFrame({"기준_bar": [0, 2.5, 5, 7.5, 10],
                       "지시_bar": [0.01, 2.52, 5.08, 7.53, 10.02]})
    # 교육용 허용오차: ±0.5% of span, span=10 bar → ±0.05 bar.
    df["오차_bar"] = df["지시_bar"] - df["기준_bar"]
    df["오차_pct_span"] = df["오차_bar"] / 10 * 100
    df["합격"] = df["오차_bar"].abs().le(0.05 + 1e-9)
    return df


def example_03():
    """초급: 교정 기한이 지난 계기 찾기."""
    df = pd.DataFrame({"태그": ["PT-101", "TT-201", "FT-301"],
                       "교정기한": ["2026-11-01", "2026-11-10", "2026-12-05"]})
    # 같은 실습 결과를 얻도록 기준일을 고정했습니다. 오늘 기준은 pd.Timestamp.today().normalize().
    reference = pd.Timestamp("2026-11-06")
    df["교정기한"] = pd.to_datetime(df["교정기한"])
    df["남은일수"] = (df["교정기한"] - reference).dt.days
    df["기한경과"] = df["남은일수"] < 0
    return df.sort_values("남은일수")


def example_04():
    """초급: 반복 고장 태그 순위 만들기."""
    df = pd.DataFrame({"태그": ["PT-101", "TT-201", "PT-101", "FV-301", "PT-101", "FV-301"],
                       "정비시간_h": [1, 2, 1.5, 3, 2, 1]})
    return (df.groupby("태그", as_index=False)
            .agg(고장건수=("태그", "size"), 총정비시간_h=("정비시간_h", "sum"))
            .sort_values("고장건수", ascending=False))


def example_05():
    """초급: 예비품 부족분과 구매 예상액 계산하기."""
    df = pd.DataFrame({"품목": ["압력전송기", "솔레노이드", "리미트스위치"],
                       "현재고": [1, 5, 0], "최소재고": [3, 2, 2],
                       "단가_원": [350000, 80000, 50000]})
    df["부족수량"] = (df["최소재고"] - df["현재고"]).clip(lower=0)
    df["구매예상액_원"] = df["부족수량"] * df["단가_원"]
    return df


def example_06():
    """중급: 1분 온도 이력을 5분 통계로 요약하기."""
    df = pd.DataFrame({"시각": pd.date_range("2026-11-06 09:00", periods=15, freq="min"),
                       "온도_C": [70, 71, 70, 72, 71, 73, 74, 90, 76, 75, 74, 73, 72, 71, 70]})
    return (df.set_index("시각").resample("5min")["온도_C"]
            .agg(["mean", "min", "max"]).reset_index()
            .rename(columns={"mean": "평균_C", "min": "최저_C", "max": "최고_C"}))


def example_07():
    """중급: 알람 로그에 계기 정보를 붙이고 다발 알람 찾기."""
    alarms = pd.DataFrame({"태그": ["PT-101", "TT-201", "PT-101", "XX-999", "PT-101"],
                           "종류": ["HIGH", "HIGH", "HIGH", "BAD", "HIGH"]})
    master = pd.DataFrame({"태그": ["PT-101", "TT-201"],
                           "설비": ["급수펌프", "열교환기"], "담당": ["계장1반", "계장2반"]})
    joined = alarms.merge(master, on="태그", how="left", validate="many_to_one")
    joined[["설비", "담당"]] = joined[["설비", "담당"]].fillna("미등록")
    return (joined.groupby(["태그", "설비", "담당", "종류"], as_index=False)
            .size().rename(columns={"size": "알람건수"})
            .sort_values("알람건수", ascending=False))


def example_08():
    """중급: 밸브 명령과 피드백 차이가 3회 연속 큰 구간 찾기."""
    df = pd.DataFrame({"시각": pd.date_range("2026-11-06 10:00", periods=8, freq="s"),
                       "명령_pct": [0, 20, 40, 60, 80, 80, 80, 80],
                       "피드백_pct": [0, 18, 25, 42, 61, 70, 79, 80]})
    df["편차_pctp"] = df["명령_pct"] - df["피드백_pct"]
    df["큰편차"] = df["편차_pctp"].abs() > 10
    # 1초 간격이므로 3개 연속 표본을 확인합니다. 실제 고착 진단은 아닙니다.
    df["점검후보"] = df["큰편차"].rolling(3, min_periods=3).sum().eq(3)
    return df


def example_09():
    """고급: 과거 정상 구간의 이동 통계로 센서 이상 후보 찾기."""
    values = [50, 50.1, 49.9, 50.2, 49.8, 50, 50.1, 49.9, 50, 50.1, 54, 50, 49.9, 50.1, 50]
    df = pd.DataFrame({"시각": pd.date_range("2026-11-06 11:00", periods=len(values), freq="min"),
                       "압력_bar": values})
    # shift(1): 판정할 현재 값을 기준 통계에 포함하지 않습니다.
    past = df["압력_bar"].shift(1).rolling(5, min_periods=5)
    df["과거평균"] = past.mean()
    df["과거표준편차"] = past.std()
    # 일정한 신호에서 0으로 나누거나 작은 잡음을 과대평가하지 않도록 하한 설정.
    df["이상점수"] = (df["압력_bar"] - df["과거평균"]).abs() / df["과거표준편차"].clip(lower=0.05)
    df["판정가능"] = df["과거평균"].notna()
    df["이상후보"] = df["판정가능"] & df["이상점수"].gt(3)
    return df


def example_10():
    """고급: 고장 이력과 설비 중요도를 결합해 점검 우선순위 만들기."""
    assets = pd.DataFrame({"태그": ["PT-101", "TT-201", "FV-301", "LT-401"],
                           "중요도": [5, 2, 5, 3]})
    failures = pd.DataFrame({"태그": ["PT-101", "PT-101", "TT-201", "FV-301"],
                             "발생일": pd.to_datetime(["2026-11-01", "2026-10-20", "2026-10-15", "2026-11-03"]),
                             "정지시간_h": [2, 3, 1, 8]})
    reference = pd.Timestamp("2026-11-06")
    # 기준일 직전 30일: 10/08 00:00 이상, 11/07 00:00 미만.
    recent = failures.loc[(failures["발생일"] >= reference - pd.Timedelta(days=29))
                          & (failures["발생일"] < reference + pd.Timedelta(days=1))]
    stats = recent.groupby("태그", as_index=False).agg(
        최근30일고장건수=("태그", "size"), 정지시간_h=("정지시간_h", "sum"))
    df = assets.merge(stats, on="태그", how="left", validate="one_to_one").fillna(0)
    # 교육용 임의 가중치입니다. 실제 정비 의사결정 기준이 아닙니다.
    df["점검점수"] = df["중요도"] * (df["최근30일고장건수"] * 2 + df["정지시간_h"])
    return df.sort_values("점검점수", ascending=False)


EXAMPLES = [example_01, example_02, example_03, example_04, example_05,
            example_06, example_07, example_08, example_09, example_10]


def main():
    choice = sys.argv[1] if len(sys.argv) > 1 else "list"
    if choice == "list":
        for number, function in enumerate(EXAMPLES, 1):
            print(f"{number:02d}. {function.__doc__}")
        print("\n실행하려면 파일명 뒤에 1~10 또는 all을 붙이세요.")
        return
    if choice != "all" and choice not in {str(n) for n in range(1, 11)}:
        raise SystemExit("예제 번호는 1~10 또는 all을 입력하세요.")
    selected = range(1, 11) if choice == "all" else [int(choice)]
    OUTPUT.mkdir(exist_ok=True)
    for number in selected:
        function = EXAMPLES[number - 1]
        result = function()
        print(f"\n[{number:02d}] {function.__doc__}")
        print(result.to_string(index=False))
        result.to_csv(OUTPUT / f"example_{number:02d}.csv", index=False, encoding="utf-8-sig")
    print(f"\nCSV 저장 폴더: {OUTPUT}")


if __name__ == "__main__":
    main()
