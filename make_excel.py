"""최동열 예제.xlsx 생성 스크립트 (외부 패키지 없이 순수 표준 라이브러리로 정식 OpenXML .xlsx 생성)."""
import os
import shutil
import zipfile
from xml.sax.saxutils import escape


def col_letter(n):
    """1-based column index to Excel column letter (1 -> A, 2 -> B, ...)."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def build_xlsx(filepath):
    # (row_idx, [(col_idx, type, value_or_formula, style_id), ...])
    # style_id: 0=기본, 1=타이틀, 2=테이블헤더, 3=수식결과강조(노랑), 4=데이터셀(테두리)
    rows_data = [
        (1, [(1, "s", "📊 최동열 님을 위한 실무 핵심 엑셀 함수 예제 10선", 1)]),
        (2, [(1, "s", "아래 샘플 데이터(B4:F8)를 바탕으로 10가지 핵심 엑셀 함수가 실제 수식으로 적용되어 있습니다.", 0)]),
        (4, [
            (1, "s", "사번", 2),
            (2, "s", "이름", 2),
            (3, "s", "부서", 2),
            (4, "s", "실적점수", 2),
            (5, "s", "매출액(만원)", 2),
            (6, "s", "목표달성여부", 2),
        ]),
        (5, [(1, "s", "EMP-01", 4), (2, "s", "최동열", 4), (3, "s", "자동화팀", 4), (4, "n", 95, 4), (5, "n", 1500, 4), (6, "f", 'IF(D5>=80,"우수","보통")', 4)]),
        (6, [(1, "s", "EMP-02", 4), (2, "s", "김철수", 4), (3, "s", "제어팀", 4), (4, "n", 78, 4), (5, "n", 920, 4), (6, "f", 'IF(D6>=80,"우수","보통")', 4)]),
        (7, [(1, "s", "EMP-03", 4), (2, "s", "이영희", 4), (3, "s", "자동화팀", 4), (4, "n", 88, 4), (5, "n", 1350, 4), (6, "f", 'IF(D7>=80,"우수","보통")', 4)]),
        (8, [(1, "s", "EMP-04", 4), (2, "s", "박민수", 4), (3, "s", "AI개발팀", 4), (4, "n", 92, 4), (5, "n", 1420, 4), (6, "f", 'IF(D8>=80,"우수","보통")', 4)]),
        (9, [(1, "s", "EMP-05", 4), (2, "s", "정수진", 4), (3, "s", "제어팀", 4), (4, "n", 65, 4), (5, "n", 750, 4), (6, "f", 'IF(D9>=80,"우수","보통")', 4)]),

        (11, [
            (1, "s", "번호", 2),
            (2, "s", "함수명", 2),
            (3, "s", "기능 설명", 2),
            (4, "s", "실제 계산 결과 (수식 적용됨)", 2),
            (5, "s", "적용된 수식 예시", 2),
        ]),
        (12, [
            (1, "n", 1, 4),
            (2, "s", "SUM (합계)", 4),
            (3, "s", "전체 직원의 매출액 총합계 구하기", 4),
            (4, "f", "SUM(E5:E9)", 3),
            (5, "s", "=SUM(E5:E9)", 4),
        ]),
        (13, [
            (1, "n", 2, 4),
            (2, "s", "AVERAGE (평균)", 4),
            (3, "s", "전체 직원의 실적점수 평균 구하기", 4),
            (4, "f", "AVERAGE(D5:D9)", 3),
            (5, "s", "=AVERAGE(D5:D9)", 4),
        ]),
        (14, [
            (1, "n", 3, 4),
            (2, "s", "MAX / MIN (최대값)", 4),
            (3, "s", "가장 높은 최고 실적점수 찾기", 4),
            (4, "f", "MAX(D5:D9)", 3),
            (5, "s", "=MAX(D5:D9)", 4),
        ]),
        (15, [
            (1, "n", 4, 4),
            (2, "s", "IF (조건문)", 4),
            (3, "s", "최동열 님의 점수가 90점 이상이면 'S등급', 아니면 'A등급'", 4),
            (4, "f", 'IF(D5>=90,"S등급","A등급")', 3),
            (5, "s", '=IF(D5>=90,"S등급","A등급")', 4),
        ]),
        (16, [
            (1, "n", 5, 4),
            (2, "s", "COUNTIF (조건부 개수)", 4),
            (3, "s", "'자동화팀' 소속 직원이 몇 명인지 세기", 4),
            (4, "f", 'COUNTIF(C5:C9,"자동화팀")', 3),
            (5, "s", '=COUNTIF(C5:C9,"자동화팀")', 4),
        ]),
        (17, [
            (1, "n", 6, 4),
            (2, "s", "SUMIF (조건부 합계)", 4),
            (3, "s", "'자동화팀'의 매출액 합계만 더하기", 4),
            (4, "f", 'SUMIF(C5:C9,"자동화팀",E5:E9)', 3),
            (5, "s", '=SUMIF(C5:C9,"자동화팀",E5:E9)', 4),
        ]),
        (18, [
            (1, "n", 7, 4),
            (2, "s", "VLOOKUP (값 찾기)", 4),
            (3, "s", "사번 'EMP-01'(최동열)로 매출액(5번째 열) 찾아오기", 4),
            (4, "f", 'VLOOKUP("EMP-01",A5:F9,5,FALSE)', 3),
            (5, "s", '=VLOOKUP("EMP-01",A5:F9,5,FALSE)', 4),
        ]),
        (19, [
            (1, "n", 8, 4),
            (2, "s", "INDEX + MATCH (고급 검색)", 4),
            (3, "s", "이름이 '최동열'인 직원의 소속 부서 찾아오기", 4),
            (4, "f", 'INDEX(C5:C9,MATCH("최동열",B5:B9,0))', 3),
            (5, "s", '=INDEX(C5:C9,MATCH("최동열",B5:B9,0))', 4),
        ]),
        (20, [
            (1, "n", 9, 4),
            (2, "s", "RANK (순위 구하기)", 4),
            (3, "s", "최동열 님의 실적점수(D5)가 전체 중 몇 등인지 계산", 4),
            (4, "f", "RANK(D5,D5:D9)", 3),
            (5, "s", "=RANK(D5,D5:D9)", 4),
        ]),
        (21, [
            (1, "n", 10, 4),
            (2, "s", "LEFT / CONCAT (텍스트 결합)", 4),
            (3, "s", "부서명과 이름을 합쳐서 '[자동화팀] 최동열' 형태로 만들기", 4),
            (4, "f", '"["&C5&"] "&B5', 3),
            (5, "s", '="["&C5&"] "&B5', 4),
        ]),
    ]

    sheet_rows_xml = []
    for r_idx, cells in rows_data:
        c_xml = []
        for c_idx, c_type, val, style_id in cells:
            ref = f"{col_letter(c_idx)}{r_idx}"
            if c_type == "s":
                c_xml.append(
                    f'<c r="{ref}" s="{style_id}" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>'
                )
            elif c_type == "n":
                c_xml.append(f'<c r="{ref}" s="{style_id}"><v>{val}</v></c>')
            elif c_type == "f":
                c_xml.append(f'<c r="{ref}" s="{style_id}"><f>{escape(str(val))}</f></c>')
        sheet_rows_xml.append(f'<row r="{r_idx}" ht="22" customHeight="1">{"".join(c_xml)}</row>')

    worksheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cols>
    <col min="1" max="1" width="12" customWidth="1"/>
    <col min="2" max="2" width="24" customWidth="1"/>
    <col min="3" max="3" width="48" customWidth="1"/>
    <col min="4" max="4" width="28" customWidth="1"/>
    <col min="5" max="5" width="34" customWidth="1"/>
    <col min="6" max="6" width="18" customWidth="1"/>
  </cols>
  <sheetData>
    {"".join(sheet_rows_xml)}
  </sheetData>
</worksheet>"""

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="4">
    <font><sz val="11"/><name val="맑은 고딕"/></font>
    <font><b/><sz val="15"/><color rgb="FF1E3A8A"/><name val="맑은 고딕"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
    <font><b/><sz val="11"/><color rgb="FF991B1B"/><name val="맑은 고딕"/></font>
  </fonts>
  <fills count="4">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1E3A8A"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFEF08A"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFCBD5E1"/></left>
      <right style="thin"><color rgb="FFCBD5E1"/></right>
      <top style="thin"><color rgb="FFCBD5E1"/></top>
      <bottom style="thin"><color rgb="FFCBD5E1"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="5">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">
      <alignment vertical="center"/>
    </xf>
  </cellXfs>
</styleSheet>"""

    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="엑셀함수10선_최동열" sheetId="1" r:id="rId1"/>
  </sheets>
  <calcPr fullCalcOnLoad="1"/>
</workbook>"""

    wb_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels_xml)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)


if __name__ == "__main__":
    local_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "최동열 예제.xlsx")
    build_xlsx(local_out)
    print("생성 완료:", local_out)
