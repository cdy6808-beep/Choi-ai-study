"""pandas 입문: 카페의 하루 매출 분석.

설치: py -m pip install pandas
실행: py pandas_example.py
"""

from pathlib import Path

import pandas as pd


# 1. 표 만들기: 딕셔너리의 키는 열 이름, 리스트는 각 열의 데이터입니다.
df = pd.DataFrame({
    "메뉴": ["아메리카노", "라떼", "아메리카노", "차", "라떼"],
    "수량": [2, 1, 3, 2, 2],
    "단가": [3000, 4000, 3000, 3500, 4000],
})

# 2. 열끼리 계산하면 모든 행에 한 번에 적용됩니다.
df["매출"] = df["수량"] * df["단가"]
print("[전체 주문]")
print(df.to_string(index=False))

# 3. 조건에 맞는 행만 골라봅니다.
print("\n[매출이 8,000원 이상인 주문]")
print(df.loc[df["매출"] >= 8000].to_string(index=False))

# 4. 같은 메뉴끼리 묶어 합계를 구하고, 매출이 높은 순으로 정렬합니다.
summary = (
    df.groupby("메뉴", as_index=False)[["수량", "매출"]]
    .sum()
    .sort_values("매출", ascending=False)
)
print("\n[메뉴별 판매 실적]")
print(summary.to_string(index=False))
print(f"\n총매출: {df['매출'].sum():,}원")

# 5. 엑셀에서도 열 수 있도록 CSV로 저장합니다.
output_path = Path(__file__).resolve().parent / "cafe_sales_summary.csv"
summary.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"저장 완료: {output_path}")

# 연습: 위 데이터에 메뉴 한 행을 추가하고, 총매출이 어떻게 바뀌는지 확인해 보세요.
