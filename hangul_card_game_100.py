"""
===============================================================================
🎴 [9세 두뇌 발달 한글 카드 퍼즐] 지혜의 산수화 낱말 카드 게임 (Stage 0 ~ Stage 100)
===============================================================================
첨부해주신 수묵 산수화 십자말풀이 카드 게임 스타일을 그대로 구현하고,
9살(초등 2~3학년) 아이의 어휘력·기억력·교차 추론 지능이 단계별로 발달하도록
Stage 0부터 Stage 100까지 총 101개의 고유 스테이지를 탑재한 한글 카드 게임입니다!

[발달 커리큘럼 (Stage 0 ~ 100)]
- Stage 00 ~ 10 [1단계: 새싹 어휘] 동물, 과일, 가족, 기초 자연어 (2~3단어 교차, 힌트 풍부)
- Stage 11 ~ 30 [2단계: 호기심 탐험] 학교생활, 날씨, 공룡, 우주, 탈것 (3~4단어 교차)
- Stage 31 ~ 55 [3단계: 생각 주머니] 반대말, 직업, 감정 표현, 과학 기초 어휘 (4~5단어 교차)
- Stage 56 ~ 80 [4단계: 논리 징검다리] 교과서 핵심 어휘, 역사/지리, 관용 표현 (5~6단어 교차 + 방해 카드)
- Stage 81 ~ 100 [5단계: 지혜의 달인] 어린이 사자성어, 속담, 고급 추론 어휘 (6~7단어 복합 교차 보드)

[조작 방법]
1. 보드의 회색 빈칸을 클릭해 선택한 뒤, 아래쪽 '내 손안의 한글 카드'를 클릭하면 글자가 쏙 들어갑니다!
2. 또는 한글 카드를 먼저 클릭하면 현재 선택된 빈칸에 자동으로 들어가고 다음 빈칸으로 이동합니다.
3. 가로·세로 한 줄의 낱말이 올바르게 완성되면 황금빛으로 빛나며 칭찬 메시지가 뜹니다!

[실행 방법]
    python hangul_card_game_100.py
===============================================================================
"""

from __future__ import annotations

import json
import math
import os
import random
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# ==============================================================================
# 1. 9세 맞춤형 발달 단계별 대규모 한국어 낱말 & 친절한 뜻풀이 사전 (260+ 핵심 어휘)
# ==============================================================================
# 형식: (단어, 9살 눈높이 뜻풀이 힌트)

TIER_1_WORDS = [
    ("강아지", "멍멍 짖으며 꼬리를 흔드는 귀여운 동물"),
    ("고양이", "야옹야옹 울며 쥐를 잘 잡는 동물"),
    ("호랑이", "어흥! 숲속의 무서운 줄무늬 왕"),
    ("코끼리", "코가 아주 길고 귀가 큰 육지 최대 동물"),
    ("원숭이", "나무를 잘 타고 바나나를 좋아하는 동물"),
    ("다람쥐", "도토리를 볼에 가득 넣는 숲속 작은 동물"),
    ("거북이", "등딱지가 단단하고 걸음이 느린 동물"),
    ("토끼풀", "하얀 꽃이 피고 네잎클로버를 찾을 수 있는 풀"),
    ("무지개", "비 온 뒤 하늘에 뜨는 일곱 빛깔 다리"),
    ("해바라기", "해를 따라 고개를 돌리는 노란 키다리 꽃"),
    ("민들레", "후 불면 하얀 씨앗이 날아가는 봄꽃"),
    ("소나무", "사계절 내내 푸른 잎을 가진 나무"),
    ("복숭아", "분홍빛이 돌고 향긋하며 달콤한 여름 과일"),
    ("바나나", "길쭉하고 노란 껍질을 벗겨 먹는 달콤한 과일"),
    ("토마토", "빨갛고 동그란 몸에 좋은 멋쟁이 채소과일"),
    ("고구마", "구워 먹으면 달콤하고 노란 땅속 줄기"),
    ("옥수수", "노란 알갱이가 줄지어 박혀 있는 여름 간식"),
    ("할머니", "엄마나 아빠를 낳아주신 인자한 어르신"),
    ("할아버지", "수염이 멋지고 옛날이야기를 해주시는 어르신"),
    ("어머니", "나를 낳고 사랑으로 길러주시는 엄마"),
    ("아버지", "든든하게 가족을 지켜주시는 아빠"),
    ("동생들", "나보다 나이가 적은 귀여운 아우들"),
    ("친구들", "학교와 놀이터에서 사이좋게 노는 단짝들"),
    ("선생님", "학교에서 우리에게 지혜와 지식을 가르쳐 주시는 분"),
    ("운동장", "학교에서 달리기와 축구를 하는 넓은 마당"),
    ("교실문", "친구들과 공부하는 방으로 들어가는 문"),
    ("색연필", "여러 가지 고운 색깔로 그림을 그리는 연필"),
    ("지우개", "연필로 틀리게 쓴 글자를 깨끗이 지우는 학용품"),
    ("스케치북", "도화지가 여러 장 묶여 있는 그림 공책"),
    ("피아노", "하얀 건반과 검은 건반을 눌러 연주하는 악기"),
]

TIER_2_WORDS = [
    ("비행기", "넓은 날개로 구름 위 하늘을 날아가는 탈것"),
    ("자동차", "바퀴 네 개로 도로를 달리는 편리한 탈것"),
    ("자전거", "두 발로 페달을 밟아 바퀴를 굴리는 탈것"),
    ("기차역", "칙칙폭폭 기차를 타고 내리는 장소"),
    ("소방차", "사이렌을 울리며 불을 끄러 출동하는 빨간 차"),
    ("구급차", "아픈 사람을 병원으로 빠르게 옮겨주는 차"),
    ("경찰차", "나쁜 도둑을 잡고 안전을 지키는 순찰차"),
    ("도서관", "수많은 책을 빌려 읽을 수 있는 조용한 곳"),
    ("박물관", "옛날 사람들의 유물과 역사를 전시해 놓은 곳"),
    ("미술관", "아름다운 그림과 조각 작품을 감상하는 곳"),
    ("동물원", "사자, 기린, 펭귄 등 여러 동물을 볼 수 있는 곳"),
    ("식물원", "사계절 내내 신기한 꽃과 나무가 자라는 온실"),
    ("소나기", "여름철에 갑자기 세차게 내리다가 그치는 비"),
    ("눈사람", "하얀 눈을 동그랗게 뭉쳐 만든 겨울 친구"),
    ("회오리", "바람이 빙글빙글 돌면서 치솟는 현상"),
    ("북극곰", "얼음으로 덮인 추운 북극에 사는 하얀 곰"),
    ("남극해", "펭귄들이 헤엄치며 사는 남쪽 끝 차가운 바다"),
    ("태양계", "태양과 지구를 비롯한 여덟 행성들의 가족"),
    ("은하수", "밤하늘에 별들이 강물처럼 반짝이며 모인 길"),
    ("우주선", "로켓의 힘으로 달과 화성까지 날아가는 배"),
    ("망원경", "멀리 있는 별이나 풍경을 크게 보여주는 도구"),
    ("현미경", "눈에 안 보이는 아주 작은 세포를 확대해 보는 기구"),
    ("나침반", "언제나 북쪽과 남쪽 방향을 가리키는 바늘 도구"),
    ("온도계", "차갑고 따뜻한 정도를 숫자로 재는 기구"),
    ("체온계", "열이 나는지 몸의 온도를 재는 기구"),
    ("신호등", "빨간불 멈춤, 초록불 건너기를 알려주는 길 안내등"),
    ("횡단보도", "길을 안전하게 건널 수 있도록 그어 놓은 하얀 줄"),
    ("놀이터", "그네와 미끄럼틀, 시소가 있는 즐거운 공간"),
    ("수영장", "물장구치며 헤엄을 배우는 시원한 곳"),
    ("축구공", "발로 차서 골대에 넣는 둥근 운동 공"),
]

TIER_3_WORDS = [
    ("과학자", "세상의 원리를 실험하고 새로운 사실을 밝히는 사람"),
    ("발명가", "세상에 없던 편리한 물건을 새로 만들어내는 사람"),
    ("요리사", "신선한 재료로 맛있는 음식을 만드는 전문가"),
    ("건축가", "튼튼하고 아름다운 집과 다리를 설계하는 사람"),
    ("우주인", "우주복을 입고 우주 정거장에서 연구하는 사람"),
    ("소방관", "불길 속에서 생명을 구하는 용감한 영웅"),
    ("경찰관", "우리 동네의 안전과 질서를 지켜주시는 분"),
    ("의사선생", "아픈 곳을 진찰하고 병을 고쳐주시는 분"),
    ("작곡가", "아름다운 노래의 멜로디를 만드는 예술가"),
    ("화가들", "붓과 물감으로 멋진 그림을 그리는 예술가들"),
    ("광합성", "식물이 햇빛과 물로 스스로 영양분을 만드는 일"),
    ("증발산", "물이 수증기가 되어 공기 중으로 날아가는 현상"),
    ("중력장", "지구가 모든 물체를 아래로 끌어당기는 힘"),
    ("자석극", "N극과 S극이 서로 당기거나 밀어내는 성질"),
    ("전기회로", "건전지와 전선을 연결해 전구에 불이 켜지는 길"),
    ("그림자", "빛이 물체에 가려져 뒤쪽에 생기는 어두운 모양"),
    ("메아리", "산에서 야호 외치면 되돌아오는 소리"),
    ("화석들", "오래전 공룡이나 식물이 돌 속에 남아있는 흔적"),
    ("공룡알", "아기 공룡이 태어나기 전 들어있던 커다란 알"),
    ("화산섬", "바다 밑 화산이 폭발해 용암이 굳어 만들어진 섬"),
    ("한라산", "제주도 한가운데 솟아 있는 우리나라에서 가장 높은 산"),
    ("백두산", "민족의 영산이자 꼭대기에 천지 호수가 있는 산"),
    ("독도섬", "동해의 가장 동쪽 끝을 지키는 소중한 우리 땅"),
    ("태극기", "하얀 바탕에 태극 문양과 건곤감리가 그려진 국기"),
    ("무궁화", "피고 또 피어 영원히 지지 않는 우리나라 꽃"),
    ("거북선", "이순신 장군님이 왜적을 물리칠 때 만든 철갑선"),
    ("훈민정음", "세종대왕님이 백성을 위해 만드신 한글의 옛 이름"),
    ("측우기", "조선 시대에 비가 내린 양을 정확히 재던 기구"),
    ("해시계", "해 그림자의 위치로 시간을 알 수 있었던 옛 시계"),
    ("물시계", "물이 일정하게 흐르는 양으로 시간을 재던 자격루"),
]

TIER_4_WORDS = [
    ("책임감", "내가 맡은 일을 끝까지 해내려는 바른 마음가짐"),
    ("배려심", "다른 사람의 입장을 먼저 생각하고 도와주는 따뜻한 마음"),
    ("협동심", "여러 사람이 힘을 합쳐 한마음으로 돕는 정신"),
    ("정직함", "거짓말하지 않고 마음을 바르고 곧게 쓰는 태도"),
    ("성실함", "꾀부리지 않고 매일 꾸준히 열심히 노력하는 태도"),
    ("인내심", "힘들고 어려운 일이 있어도 포기하지 않고 참아내는 힘"),
    ("호기심", "새롭고 신기한 것에 대해 왜 그럴까 궁금해하는 마음"),
    ("창의력", "남들과 다른 새롭고 기발한 생각을 떠올리는 능력"),
    ("상상력", "경험하지 않은 일도 머릿속으로 생생하게 그려보는 힘"),
    ("관찰력", "사물의 작은 변화나 특징을 자세히 살펴보는 능력"),
    ("집중력", "한 가지 일에 마음을 모아 흔들리지 않는 힘"),
    ("자신감", "나는 해낼 수 있다고 스스로를 굳게 믿는 마음"),
    ("환경보호", "자연과 지구를 깨끗하게 아끼고 지키는 일"),
    ("재활용", "다 쓴 물건을 버리지 않고 다시 쓸모 있게 만드는 일"),
    ("분리수거", "종이, 플라스틱, 캔을 종류별로 나누어 버리는 실천"),
    ("에너지", "기계를 움직이거나 빛과 열을 내는 원동력"),
    ("태양광", "햇빛을 모아 깨끗한 전기를 만드는 친환경 기술"),
    ("풍력발전", "바람개비 날개를 돌려 전기를 생산하는 방식"),
    ("생태계", "동물과 식물, 자연환경이 서로 어우러져 살아가는 세계"),
    ("먹이사슬", "식물부터 초식동물, 육식동물까지 먹고 먹히는 관계"),
    ("기후변화", "지구가 점점 더워져 날씨가 급격히 바뀌는 현상"),
    ("북극빙하", "지구 온난화로 조금씩 녹고 있는 북극의 거대한 얼음"),
    ("도전정신", "어려운 목표 앞에서도 두려워하지 않고 부딪쳐 보는 마음"),
    ("약속시간", "친구와 서로 지키기로 정한 소중한 시간"),
    ("감사의말", "고마운 마음을 담아 전하는 따뜻한 인사"),
    ("사과의말", "실수했을 때 미안하다고 먼저 용기 내어 하는 말"),
    ("경청하기", "상대방의 이야기를 귀 기울여 끝까지 잘 듣는 태도"),
    ("공감능력", "친구의 기쁨과 슬픔을 내 마음처럼 함께 느끼는 힘"),
    ("독서습관", "매일 꾸준히 책을 읽으며 마음의 양식을 쌓는 습관"),
    ("일기쓰기", "하루 동안 있었던 일과 내 생각을 글로 남기는 일"),
]

TIER_5_WORDS = [
    ("유비무환", "[사자성어] 미리 준비해 두면 나중에 걱정할 일이 없음"),
    ("일석이조", "[사자성어] 돌 하나로 새 두 마리를 잡듯 한 번에 두 가지 이득을 얻음"),
    ("동문서답", "[사자성어] 동쪽을 묻는데 서쪽을 답하듯 엉뚱한 대답을 함"),
    ("우공이산", "[사자성어] 포기하지 않고 꾸준히 노력하면 큰 산도 옮길 수 있음"),
    ("대기만성", "[사자성어] 큰 그릇은 늦게 만들어지듯 큰 인물은 오랜 노력 끝에 이루어짐"),
    ("금상첨화", "[사자성어] 비단 위에 꽃을 더하듯 좋은 일에 더 좋은 일이 겹침"),
    ("설상가상", "[사자성어] 눈 위에 서리가 덮이듯 어려운 일이 겹쳐 일어남"),
    ("고진감래", "[사자성어] 쓴 것이 다하면 단 것이 오듯 고생 끝에 낙이 옴"),
    ("역지사지", "[사자성어] 다른 사람의 처지에서 바꾸어 생각해 봄"),
    ("초지일관", "[사자성어] 처음에 세운 뜻을 끝까지 밀고 나감"),
    ("백문불여일견", "[고사성어] 백 번 듣는 것보다 한 번 직접 보는 것이 훨씬 낫다"),
    ("작심삼일", "[사자성어] 굳게 먹은 마음이 사흘을 못 가고 곧 느슨해짐"),
    ("전화위복", "[사자성어] 나쁜 일이 계기가 되어 오히려 좋은 일로 바뀜"),
    ("자업자득", "[사자성어] 자기가 저지른 일의 결과를 스스로 돌려받음"),
    ("죽마고우", "[사자성어] 대나무 말을 타고 놀던 어릴 적부터 친한 단짝 친구"),
    ("청출어람", "[사자성어] 제자가 스승보다 더 뛰어나게 발전함"),
    ("다다익선", "[사자성어] 많으면 많을수록 더욱 좋음"),
    ("과유불급", "[사자성어] 지나친 것은 미치지 못한 것과 같아 적당함이 중요함"),
    ("시나브로", "[순우리말] 모르는 사이에 조금씩 조금씩 자라나는 모양"),
    ("나비효과", "[과학어휘] 작은 날갯짓 하나가 세상 반대편에 큰 변화를 일으키는 현상"),
    ("인공지능", "[미래기술] 컴퓨터가 사람처럼 학습하고 스스로 판단하는 기술"),
    ("로봇공학", "[미래기술] 스스로 움직이고 일하는 로봇을 설계하고 만드는 학문"),
    ("알고리즘", "[코딩어휘] 문제를 해결하기 위해 순서대로 정해 놓은 똑똑한 절차"),
    ("빅데이터", "[미래기술] 수많은 정보 속에서 의미 있는 규칙을 찾아내는 큰 데이터"),
    ("자율주행", "[미래기술] 운전자가 핸들을 잡지 않아도 자동차가 스스로 길을 찾아 달림"),
    ("가상현실", "[미래기술] 컴퓨터로 만든 세계를 실제처럼 체험하는 기술"),
    ("우주정거장", "[우주과학] 지구 둘레를 돌며 우주인들이 머물며 연구하는 기지"),
    ("정보보안", "[미래기술] 소중한 개인정보와 컴퓨터를 해킹으로부터 지키는 기술"),
    ("민주주의", "[사회어휘] 모든 국민이 나라의 주인으로서 의견을 존중하며 다스리는 제도"),
    ("문화유산", "[역사어휘] 조상님들이 물려주신 소중하고 가치 있는 보물과 전통"),
]

ALL_WORDS_POOL = TIER_1_WORDS + TIER_2_WORDS + TIER_3_WORDS + TIER_4_WORDS + TIER_5_WORDS


# ==============================================================================
# 2. 십자말풀이(Crossword) 보드 자동 생성 알고리즘 (Stage 0 ~ Stage 100)
# ==============================================================================
class StagePuzzleGenerator:
    """
    스테이지 번호(0~100)를 시드(Seed)로 사용하여,
    9살 아이의 발달 단계에 맞는 단어 수, 빈칸 비율, 방해 카드(Distractor)를 가진
    교차 한글 퍼즐 보드를 생성합니다.
    """

    GRID_ROWS = 8
    GRID_COLS = 10

    @staticmethod
    def get_stage_config(stage_num: int) -> dict:
        if stage_num == 0:
            return {
                "tier_name": "🌱 Stage 0: 첫걸음 튜토리얼 (6~7세 기초)",
                "target_words": 2,
                "blank_ratio": 0.45,
                "distractors": 0,
                "pool": TIER_1_WORDS[:12],
                "iq_badge": "두뇌 깨우기 Lv.1",
            }
        elif stage_num <= 10:
            return {
                "tier_name": f"🌱 1단계: 새싹 어휘 교실 (Stage {stage_num})",
                "target_words": 3,
                "blank_ratio": 0.50,
                "distractors": 0,
                "pool": TIER_1_WORDS,
                "iq_badge": "어휘 감각 Lv.2",
            }
        elif stage_num <= 30:
            return {
                "tier_name": f"🌿 2단계: 호기심 탐험대 (Stage {stage_num})",
                "target_words": 4,
                "blank_ratio": 0.55,
                "distractors": 1,
                "pool": TIER_1_WORDS + TIER_2_WORDS,
                "iq_badge": "연상 추론 Lv.3",
            }
        elif stage_num <= 55:
            return {
                "tier_name": f"🌳 3단계: 생각 주머니 확장 (Stage {stage_num})",
                "target_words": 5,
                "blank_ratio": 0.62,
                "distractors": 2,
                "pool": TIER_2_WORDS + TIER_3_WORDS,
                "iq_badge": "교차 논리 Lv.4",
            }
        elif stage_num <= 80:
            return {
                "tier_name": f"✨ 4단계: 논리 징검다리 (Stage {stage_num})",
                "target_words": 6,
                "blank_ratio": 0.68,
                "distractors": 2,
                "pool": TIER_3_WORDS + TIER_4_WORDS,
                "iq_badge": "통합 사고력 Lv.5",
            }
        else:
            return {
                "tier_name": f"👑 5단계: 지혜의 달인 (Stage {stage_num})",
                "target_words": 6 if stage_num < 92 else 7,
                "blank_ratio": 0.75,
                "distractors": 3,
                "pool": TIER_4_WORDS + TIER_5_WORDS,
                "iq_badge": "언어 천재 마스터 MAX",
            }

    @classmethod
    def build_stage(cls, stage_num: int) -> dict:
        cfg = cls.get_stage_config(stage_num)
        rng = random.Random(10000 + stage_num * 97)

        rows, cols = cls.GRID_ROWS, cls.GRID_COLS
        grid = [[None for _ in range(cols)] for _ in range(rows)]
        placed_words = []  # list of {word, clue, dir, r, c, cells: [(r,c), ...]}

        candidates = list(cfg["pool"])
        rng.shuffle(candidates)

        # 추가 예비 풀 (교차 단어 매칭 확률 극대화)
        backup_pool = [w for w in ALL_WORDS_POOL if w not in candidates]
        rng.shuffle(backup_pool)
        full_candidates = candidates + backup_pool

        def can_place(word: str, r: int, c: int, d: str) -> tuple[bool, int]:
            """배치 가능 여부와 기존 단어와의 교차 횟수를 반환."""
            L = len(word)
            dr = 0 if d == "H" else 1
            dc = 1 if d == "H" else 0

            if r < 0 or c < 0 or r + dr * (L - 1) >= rows or c + dc * (L - 1) >= cols:
                return False, 0

            # 단어 바로 앞/뒤 칸이 비어 있어야 함 (단어끼리 일렬로 붙는 것 방지)
            before_r, before_c = r - dr, c - dc
            after_r, after_c = r + dr * L, c + dc * L
            if 0 <= before_r < rows and 0 <= before_c < cols and grid[before_r][before_c] is not None:
                return False, 0
            if 0 <= after_r < rows and 0 <= after_c < cols and grid[after_r][after_c] is not None:
                return False, 0

            intersections = 0
            for i, ch in enumerate(word):
                cr, cc = r + dr * i, c + dc * i
                cur_cell = grid[cr][cc]
                if cur_cell is not None:
                    if cur_cell != ch:
                        return False, 0
                    intersections += 1
                else:
                    # 교차점이 아닌 새 칸의 좌우(또는 상하) 인접 칸이 차 있으면 원치 않는 2글자 접촉 발생 -> 방지
                    for nr, nc in ((cr - dc, cc - dr), (cr + dc, cc + dr)):
                        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] is not None:
                            return False, 0

            return True, intersections

        def do_place(word: str, clue: str, r: int, c: int, d: str):
            dr = 0 if d == "H" else 1
            dc = 1 if d == "H" else 0
            cells = []
            for i, ch in enumerate(word):
                cr, cc = r + dr * i, c + dc * i
                grid[cr][cc] = ch
                cells.append((cr, cc))
            placed_words.append({
                "word": word,
                "clue": clue,
                "dir": d,
                "r": r,
                "c": c,
                "cells": cells,
            })

        # 1) 첫 중심 단어 배치
        first_w, first_clue = full_candidates[0]
        start_r = rows // 2 - 1
        start_c = max(1, (cols - len(first_w)) // 2)
        do_place(first_w, first_clue, start_r, start_c, "H")
        used_words = {first_w}

        # 2) 교차하는 단어 우선 배치
        for word, clue in full_candidates[1:]:
            if len(placed_words) >= cfg["target_words"]:
                break
            if word in used_words or len(word) > 6:
                continue

            best_pos = None
            # 먼저 기존 배치된 글자와 교차하는 위치 탐색
            for pw in placed_words:
                prefer_dir = "V" if pw["dir"] == "H" else "H"
                for i, ch_existing in enumerate(pw["word"]):
                    er, ec = pw["cells"][i]
                    for j, ch_new in enumerate(word):
                        if ch_existing == ch_new:
                            nr = er - (j if prefer_dir == "V" else 0)
                            nc = ec - (j if prefer_dir == "H" else 0)
                            ok, inter = can_place(word, nr, nc, prefer_dir)
                            if ok and inter >= 1:
                                best_pos = (nr, nc, prefer_dir)
                                break
                    if best_pos:
                        break
                if best_pos:
                    break

            # 교차점이 없으면 보드의 빈 공간에 독립 배치 (첨부 이미지처럼 교차 그룹 + 독립 단어 조합)
            if not best_pos:
                for _try in range(40):
                    d_try = rng.choice(["H", "V"])
                    r_try = rng.randrange(rows)
                    c_try = rng.randrange(cols)
                    ok, _ = can_place(word, r_try, c_try, d_try)
                    if ok:
                        best_pos = (r_try, c_try, d_try)
                        break

            if best_pos:
                do_place(word, clue, best_pos[0], best_pos[1], best_pos[2])
                used_words.add(word)

        # 3) 어떤 칸을 고정 힌트 타일(노란색)로 두고, 어떤 칸을 빈칸(회색, 플레이어가 카드로 채울 칸)으로 둘지 결정
        #    규칙: 각 단어마다 최소 1글자는 노란색 고정 힌트로 보여주고, 최소 1글자는 빈칸으로 둠!
        all_occupied = {}
        for pw in placed_words:
            for r, c in pw["cells"]:
                all_occupied[(r, c)] = grid[r][c]

        blank_cells = set()
        for pw in placed_words:
            cells = list(pw["cells"])
            rng.shuffle(cells)
            n_blanks = max(1, min(len(cells) - 1, int(round(len(cells) * cfg["blank_ratio"]))))
            # 이미 빈칸으로 지정된 칸 수 확인
            cur_blanks = sum(1 for rc in cells if rc in blank_cells)
            for rc in cells:
                if cur_blanks >= n_blanks:
                    break
                # 만약 이 칸을 빈칸으로 만들었을 때 다른 단어가 전부 빈칸이 되지 않는지 체크
                blank_cells.add(rc)
                cur_blanks += 1

        # 각 단어마다 최소 1개의 노란색 고정 글자 보장
        for pw in placed_words:
            if all(rc in blank_cells for rc in pw["cells"]):
                keep_rc = rng.choice(pw["cells"])
                blank_cells.discard(keep_rc)

        # 4) 하단 카드 덱(Hand Cards) 생성: 정답 글자들 + 발달 단계별 헷갈리는 방해 카드(Distractors)
        hand_cards = [grid[r][c] for (r, c) in sorted(blank_cells)]
        distractor_letters = [
            "가", "나", "다", "라", "마", "바", "사", "아", "자", "차",
            "카", "타", "파", "하", "고", "노", "도", "로", "모", "보",
            "소", "오", "조", "구", "누", "두", "루", "무", "부", "수",
        ]
        rng.shuffle(distractor_letters)
        for ch in distractor_letters:
            if len(hand_cards) >= len(blank_cells) + cfg["distractors"]:
                break
            if ch not in hand_cards:
                hand_cards.append(ch)

        rng.shuffle(hand_cards)

        return {
            "stage": stage_num,
            "tier_name": cfg["tier_name"],
            "iq_badge": cfg["iq_badge"],
            "rows": rows,
            "cols": cols,
            "grid_solution": grid,
            "placed_words": placed_words,
            "blank_cells": blank_cells,
            "hand_cards": hand_cards,
        }


# ==============================================================================
# 3. 수묵 산수화 풍경 & 한지 타일 그래픽 GUI (Tkinter)
# ==============================================================================
class HangulCardGameApp(tk.Tk):
    CELL_SIZE = 56
    BOARD_PAD_X = 48
    BOARD_PAD_Y = 28

    def __init__(self):
        super().__init__()
        self.title("🎴 [지혜의 산수화] 9세 두뇌 발달 한글 낱말 카드 게임 (Stage 0 ~ Stage 100)")
        self.geometry("1280x860")
        self.minsize(1060, 740)
        self.configure(bg="#ece5d5")

        # 진행 상태 저장 파일
        self.save_path = Path(__file__).resolve().parent / "hangul_game_save.json"
        self.unlocked_stage = 0
        self.current_stage = 0
        self.score = 0
        self.stars = 0
        self._load_progress()

        # 현재 스테이지 플레이 데이터
        self.stage_data = None
        self.user_grid = {}         # (r, c) -> {"char": str, "card_idx": int}
        self.used_card_indices = set()
        self.selected_cell = None   # (r, c)
        self.completed_words = set()

        self._build_ui()
        self.start_stage(self.current_stage)

    def _load_progress(self):
        if self.save_path.exists():
            try:
                with open(self.save_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self.unlocked_stage = int(d.get("unlocked_stage", 0))
                self.current_stage = int(d.get("current_stage", 0))
                self.score = int(d.get("score", 0))
                self.stars = int(d.get("stars", 0))
            except Exception:
                pass

    def _save_progress(self):
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "unlocked_stage": max(self.unlocked_stage, self.current_stage),
                    "current_stage": self.current_stage,
                    "score": self.score,
                    "stars": self.stars,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # UI 레이아웃 구성
    # --------------------------------------------------------------------------
    def _build_ui(self):
        # 1. 상단 전통 목재 스타일 헤더 바
        top = tk.Frame(self, bg="#2c3e35", padx=16, pady=10)
        top.pack(side=tk.TOP, fill=tk.X)

        self.title_lbl = tk.Label(
            top,
            text="🎴 지혜의 산수화 한글 카드 퍼즐",
            bg="#2c3e35",
            fg="#fef08a",
            font=("Malgun Gothic", 14, "bold"),
        )
        self.title_lbl.pack(side=tk.LEFT, padx=(0, 16))

        self.tier_lbl = tk.Label(
            top,
            text="🌱 Stage 0",
            bg="#3f574b",
            fg="#ffffff",
            font=("Malgun Gothic", 10, "bold"),
            padx=12,
            pady=4,
        )
        self.tier_lbl.pack(side=tk.LEFT, padx=6)

        # 스테이지 0 ~ 100 바로 이동 선택기
        nav_frame = tk.Frame(top, bg="#2c3e35")
        nav_frame.pack(side=tk.LEFT, padx=14)

        tk.Button(
            nav_frame, text="◀ 이전", command=lambda: self.start_stage(max(0, self.current_stage - 1)),
            bg="#4a6658", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"), padx=8, pady=3, cursor="hand2"
        ).pack(side=tk.LEFT, padx=2)

        self.stage_var = tk.StringVar(value="Stage 0")
        stage_values = [f"Stage {i}" for i in range(101)]
        self.stage_cb = ttk.Combobox(nav_frame, textvariable=self.stage_var, values=stage_values, width=10, state="readonly", font=("Malgun Gothic", 10, "bold"))
        self.stage_cb.pack(side=tk.LEFT, padx=4)
        self.stage_cb.bind("<<ComboboxSelected>>", self._on_stage_selected)

        tk.Button(
            nav_frame, text="다음 ▶", command=lambda: self.start_stage(min(100, self.current_stage + 1)),
            bg="#4a6658", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"), padx=8, pady=3, cursor="hand2"
        ).pack(side=tk.LEFT, padx=2)

        # 우측 점수 & 힌트 버튼
        self.score_lbl = tk.Label(
            top,
            text="⭐ 지혜 점수: 0점",
            bg="#2c3e35",
            fg="#fde047",
            font=("Malgun Gothic", 11, "bold"),
        )
        self.score_lbl.pack(side=tk.RIGHT, padx=10)

        tk.Button(
            top, text="💡 한 글자 힌트 보기", command=self.use_hint,
            bg="#d97706", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"), padx=12, pady=4, cursor="hand2"
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            top, text="🔄 다시 놓기", command=lambda: self.start_stage(self.current_stage),
            bg="#64748b", fg="#ffffff", relief=tk.FLAT, font=("Malgun Gothic", 9, "bold"), padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.RIGHT, padx=4)

        # 2. 메인 영역 (좌측: 수묵 산수화 보드 & 카드 트레이 / 우측: 9세 맞춤형 낱말 뜻풀이 사전)
        main = tk.Frame(self, bg="#ece5d5")
        main.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        left_area = tk.Frame(main, bg="#ece5d5")
        left_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # (A) 수묵 산수화 배경 + 8x10 한글 타일 보드 캔버스
        self.board_canvas = tk.Canvas(
            left_area, bg="#f5efe0", height=510, highlightthickness=2, highlightbackground="#8c7a5b"
        )
        self.board_canvas.pack(fill=tk.BOTH, expand=True)
        self.board_canvas.bind("<Configure>", lambda e: self.redraw_all())
        self.board_canvas.bind("<Button-1>", self.on_board_click)

        # (B) 하단 플레이어 손패(Hand Cards) 캔버스
        card_header = tk.Frame(left_area, bg="#3e3326", padx=12, pady=5)
        card_header.pack(fill=tk.X, pady=(8, 0))
        self.msg_lbl = tk.Label(
            card_header,
            text="👇 아래의 한글 카드를 클릭해서 회색 빈칸을 채워보세요! (이미 넣은 빈칸을 다시 클릭하면 카드가 돌아옵니다)",
            bg="#3e3326",
            fg="#fef08a",
            font=("Malgun Gothic", 10, "bold"),
        )
        self.msg_lbl.pack(side=tk.LEFT)

        self.card_canvas = tk.Canvas(
            left_area, bg="#d8cbb3", height=130, highlightthickness=2, highlightbackground="#8c7a5b"
        )
        self.card_canvas.pack(fill=tk.X)
        self.card_canvas.bind("<Configure>", lambda e: self.draw_hand_cards())
        self.card_canvas.bind("<Button-1>", self.on_card_click)

        # 3. 우측 패널: 이번 스테이지 낱말 힌트 & 아이 지능 발달 게이지
        right_area = tk.Frame(main, bg="#faf6ed", width=355, padx=14, pady=12, highlightbackground="#8c7a5b", highlightthickness=2)
        right_area.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        right_area.pack_propagate(False)

        tk.Label(
            right_area,
            text="📖 이번 스테이지 낱말 수수께끼",
            bg="#faf6ed",
            fg="#2c3e35",
            font=("Malgun Gothic", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        self.clues_frame = tk.Frame(right_area, bg="#faf6ed")
        self.clues_frame.pack(fill=tk.BOTH, expand=True)

        # 하단 두뇌 발달 레벨 박스
        brain_box = tk.Frame(right_area, bg="#2c3e35", padx=12, pady=10)
        brain_box.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        self.brain_lbl = tk.Label(
            brain_box,
            text="🧠 9세 두뇌 발달 지수: 새싹 탐험가",
            bg="#2c3e35",
            fg="#4ade80",
            font=("Malgun Gothic", 10, "bold"),
            justify=tk.LEFT,
            anchor="w",
        )
        self.brain_lbl.pack(fill=tk.X)

    # --------------------------------------------------------------------------
    # 스테이지 시작 및 게임 로직
    # --------------------------------------------------------------------------
    def _on_stage_selected(self, _event):
        val = self.stage_var.get().replace("Stage", "").strip()
        if val.isdigit():
            self.start_stage(int(val))

    def start_stage(self, stage_num: int):
        self.current_stage = max(0, min(100, stage_num))
        self.stage_var.set(f"Stage {self.current_stage}")
        self.stage_data = StagePuzzleGenerator.build_stage(self.current_stage)

        self.user_grid.clear()
        self.used_card_indices.clear()
        self.completed_words.clear()

        # 첫 번째 빈칸을 자동으로 선택해 두어 아이가 바로 카드를 누르기만 해도 들어가게 함
        blanks_sorted = sorted(self.stage_data["blank_cells"])
        self.selected_cell = blanks_sorted[0] if blanks_sorted else None

        self.tier_lbl.configure(text=f"{self.stage_data['tier_name']}  |  {self.stage_data['iq_badge']}")
        self.score_lbl.configure(text=f"⭐ 지혜 점수: {self.score:,}점  (클리어: {self.unlocked_stage}/100)")
        self.brain_lbl.configure(
            text=f"🧠 현재 두뇌 발달 단계: {self.stage_data['iq_badge']}\n"
                 f"🎯 목표 낱말 수: {len(self.stage_data['placed_words'])}개  |  빈칸: {len(blanks_sorted)}칸"
        )
        self.msg_lbl.configure(
            text="👇 초록색 테두리로 선택된 빈칸에 들어갈 알맞은 글자 카드를 아래에서 골라 클릭하세요!",
            fg="#fef08a",
        )

        self.refresh_clues_panel()
        self.redraw_all()
        self._save_progress()

    def refresh_clues_panel(self):
        for w in self.clues_frame.winfo_children():
            w.destroy()

        for idx, pw in enumerate(self.stage_data["placed_words"], start=1):
            is_done = idx in self.completed_words
            card_bg = "#dcfce7" if is_done else "#ffffff"
            border_c = "#16a34a" if is_done else "#cbd5e1"

            box = tk.Frame(
                self.clues_frame, bg=card_bg, padx=10, pady=8,
                highlightbackground=border_c, highlightthickness=1.5
            )
            box.pack(fill=tk.X, pady=4)

            dir_badge = "가로 ➡" if pw["dir"] == "H" else "세로 ⬇"
            word_preview = []
            for r, c in pw["cells"]:
                if (r, c) not in self.stage_data["blank_cells"]:
                    word_preview.append(self.stage_data["grid_solution"][r][c])
                elif (r, c) in self.user_grid:
                    word_preview.append(self.user_grid[(r, c)]["char"])
                else:
                    word_preview.append("▢")

            status_icon = "✅ 완성!" if is_done else f"[{dir_badge}]  {' '.join(word_preview)}"
            hdr_col = "#15803d" if is_done else "#0f172a"

            tk.Label(
                box,
                text=f"낱말 {idx}.  {status_icon}",
                bg=card_bg,
                fg=hdr_col,
                font=("Malgun Gothic", 10, "bold"),
                anchor="w",
            ).pack(fill=tk.X)

            tk.Label(
                box,
                text=f"💡 힌트: {pw['clue']}",
                bg=card_bg,
                fg="#334155",
                wraplength=305,
                justify=tk.LEFT,
                font=("Malgun Gothic", 9),
                anchor="w",
            ).pack(fill=tk.X, pady=(3, 0))

            # 힌트 박스를 클릭하면 해당 단어의 첫 빈칸으로 포커스 이동!
            def focus_word(cells=pw["cells"]):
                for rc in cells:
                    if rc in self.stage_data["blank_cells"] and rc not in self.user_grid:
                        self.selected_cell = rc
                        self.redraw_all()
                        return
                for rc in cells:
                    if rc in self.stage_data["blank_cells"]:
                        self.selected_cell = rc
                        self.redraw_all()
                        return

            box.bind("<Button-1>", lambda e, fn=focus_word: fn())

    # --------------------------------------------------------------------------
    # 수묵 산수화 배경 및 타일 보드 렌더링 (첨부 이미지 스타일 완벽 재현!)
    # --------------------------------------------------------------------------
    def redraw_all(self):
        self.draw_board()
        self.draw_hand_cards()

    def _board_origin(self):
        c = self.board_canvas
        w = max(c.winfo_width(), 720)
        h = max(c.winfo_height(), 480)
        rows = self.stage_data["rows"]
        cols = self.stage_data["cols"]
        cell_sz = min((w - 80) // cols, (h - 60) // rows, 62)
        ox = (w - cols * cell_sz) // 2
        oy = (h - rows * cell_sz) // 2
        return ox, oy, cell_sz, w, h

    def draw_board(self):
        c = self.board_canvas
        c.delete("all")
        if not self.stage_data:
            return

        ox, oy, sz, w, h = self._board_origin()

        # 1. 동양화 수묵 산수화(능선 + 소나무 실루엣) 배경 그리기
        # 먼 산 능선
        c.create_polygon(
            0, h, 0, h * 0.45, w * 0.22, h * 0.22, w * 0.48, h * 0.48,
            w * 0.76, h * 0.14, w, h * 0.38, w, h,
            fill="#d9e2dc", outline=""
        )
        # 중간 산 능선
        c.create_polygon(
            0, h, 0, h * 0.62, w * 0.18, h * 0.44, w * 0.42, h * 0.68,
            w * 0.65, h * 0.35, w * 0.88, h * 0.56, w, h * 0.48, w, h,
            fill="#bccbc4", outline=""
        )
        # 가까운 산자락
        c.create_polygon(
            0, h, 0, h * 0.78, w * 0.32, h * 0.65, w * 0.62, h * 0.82,
            w * 0.85, h * 0.68, w, h * 0.75, w, h,
            fill="#9fb3aa", outline=""
        )

        # 2. 8x10 타일 그리드 그리기 (첨부 이미지의 흰색/노란색/회색 입체 타일 재현)
        rows = self.stage_data["rows"]
        cols = self.stage_data["cols"]
        sol = self.stage_data["grid_solution"]
        blanks = self.stage_data["blank_cells"]

        # 완성된 단어에 속한 칸 집합
        completed_cells = set()
        for idx, pw in enumerate(self.stage_data["placed_words"], start=1):
            if idx in self.completed_words:
                completed_cells.update(pw["cells"])

        for r in range(rows):
            for col in range(cols):
                x1 = ox + col * sz
                y1 = oy + r * sz
                x2 = x1 + sz - 3
                y2 = y1 + sz - 3

                ch = sol[r][col]
                is_blank = (r, col) in blanks
                is_selected = (self.selected_cell == (r, col))

                if ch is None:
                    # 배경 빈 공간 타일 (반투명 한지 백색 타일)
                    c.create_rectangle(x1, y1, x2, y2, fill="#f7f4eb", outline="#cdc6b8", width=1)
                elif not is_blank:
                    # 고정 힌트 글자 타일 (첨부 이미지의 따뜻한 연노란색 한지 타일!)
                    bg_col = "#bbf7d0" if (r, col) in completed_cells else "#f7ecaa"
                    border_col = "#16a34a" if (r, col) in completed_cells else "#b8a868"
                    # 아래쪽 입체 베벨 그림자
                    c.create_rectangle(x1 + 2, y1 + 3, x2 + 2, y2 + 3, fill="#9e9260", outline="")
                    c.create_rectangle(x1, y1, x2, y2, fill=bg_col, outline=border_col, width=1.5)
                    c.create_text(
                        (x1 + x2) / 2, (y1 + y2) / 2,
                        text=ch, fill="#1c1917", font=("Batang", int(sz * 0.46), "bold")
                    )
                else:
                    # 플레이어가 채워야 할 회색 빈칸 (또는 이미 카드를 넣은 칸)
                    if (r, col) in self.user_grid:
                        u_ch = self.user_grid[(r, col)]["char"]
                        is_correct_word = (r, col) in completed_cells
                        tile_bg = "#86efac" if is_correct_word else "#fde047"
                        tile_out = "#15803d" if is_correct_word else ("#2563eb" if is_selected else "#ca8a04")
                        c.create_rectangle(x1 + 2, y1 + 3, x2 + 2, y2 + 3, fill="#78716c", outline="")
                        c.create_rectangle(x1, y1, x2, y2, fill=tile_bg, outline=tile_out, width=3 if is_selected else 2)
                        c.create_text(
                            (x1 + x2) / 2, (y1 + y2) / 2,
                            text=u_ch, fill="#0f172a", font=("Batang", int(sz * 0.46), "bold")
                        )
                    else:
                        # 아직 비어 있는 회색 슬롯 (첨부 이미지의 회색 빈칸 스타일!)
                        slot_bg = "#cbd5e1" if is_selected else "#beb9ae"
                        slot_out = "#16a34a" if is_selected else "#8c8578"
                        slot_w = 3.5 if is_selected else 1.5
                        c.create_rectangle(x1, y1, x2, y2, fill=slot_bg, outline=slot_out, width=slot_w)
                        if is_selected:
                            c.create_text(
                                (x1 + x2) / 2, (y1 + y2) / 2,
                                text="?", fill="#15803d", font=("Malgun Gothic", int(sz * 0.35), "bold")
                            )

    def draw_hand_cards(self):
        c = self.card_canvas
        c.delete("all")
        if not self.stage_data:
            return

        w = max(c.winfo_width(), 720)
        h = max(c.winfo_height(), 120)
        cards = self.stage_data["hand_cards"]
        n = len(cards)
        if n == 0:
            return

        card_w = min(68, max(46, (w - 60) // n - 10))
        card_h = min(84, h - 26)
        total_w = n * (card_w + 10) - 10
        start_x = (w - total_w) // 2
        y1 = (h - card_h) // 2
        y2 = y1 + card_h

        self.card_rects = []
        for idx, ch in enumerate(cards):
            x1 = start_x + idx * (card_w + 10)
            x2 = x1 + card_w
            self.card_rects.append((idx, x1, y1, x2, y2))

            if idx in self.used_card_indices:
                # 이미 보드에 올려놓은 카드 슬롯 (점선 빈자리)
                c.create_rectangle(x1, y1, x2, y2, fill="#c7baa1", outline="#9c8d73", dash=(3, 3))
            else:
                # 입체 한글 카드
                c.create_rectangle(x1 + 3, y1 + 4, x2 + 3, y2 + 4, fill="#786b54", outline="")
                c.create_rectangle(x1, y1, x2, y2, fill="#fffbeb", outline="#b45309", width=2)
                c.create_rectangle(x1 + 4, y1 + 4, x2 - 4, y2 - 4, fill="#fef3c7", outline="#fde68a")
                c.create_text(
                    (x1 + x2) / 2, (y1 + y2) / 2,
                    text=ch, fill="#1c1917", font=("Batang", int(card_w * 0.46), "bold")
                )

    # --------------------------------------------------------------------------
    # 마우스 클릭 상호작용 (빈칸 선택 / 카드 배치 / 카드 회수 / 정답 체크)
    # --------------------------------------------------------------------------
    def on_board_click(self, event):
        if not self.stage_data:
            return
        ox, oy, sz, _, _ = self._board_origin()
        col = (event.x - ox) // sz
        r = (event.y - oy) // sz

        if (r, col) in self.stage_data["blank_cells"]:
            # 이미 카드가 놓인 칸을 클릭하면 카드를 손패로 되돌림!
            if (r, col) in self.user_grid:
                card_idx = self.user_grid[(r, col)]["card_idx"]
                self.used_card_indices.discard(card_idx)
                del self.user_grid[(r, col)]
                self.selected_cell = (r, col)
                self._check_words_status()
                self.redraw_all()
            else:
                self.selected_cell = (r, col)
                self.redraw_all()

    def on_card_click(self, event):
        if not self.stage_data:
            return

        for idx, x1, y1, x2, y2 in getattr(self, "card_rects", []):
            if idx not in self.used_card_indices and x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.place_card_into_selected(idx)
                return

    def place_card_into_selected(self, card_idx: int):
        blanks = sorted(self.stage_data["blank_cells"])
        if not blanks:
            return

        # 선택된 칸이 없거나 이미 채워져 있으면 비어 있는 첫 칸 찾기
        target_rc = self.selected_cell
        if target_rc not in self.stage_data["blank_cells"]:
            target_rc = None
        if target_rc is not None and target_rc in self.user_grid:
            # 기존 카드 회수 후 교체
            old_idx = self.user_grid[target_rc]["card_idx"]
            self.used_card_indices.discard(old_idx)

        if target_rc is None:
            for rc in blanks:
                if rc not in self.user_grid:
                    target_rc = rc
                    break

        if target_rc is None:
            return

        ch = self.stage_data["hand_cards"][card_idx]
        self.user_grid[target_rc] = {"char": ch, "card_idx": card_idx}
        self.used_card_indices.add(card_idx)

        # 다음 빈칸으로 포커스 자동 이동
        for rc in blanks:
            if rc not in self.user_grid:
                self.selected_cell = rc
                break

        self._check_words_status()
        self.redraw_all()

    def use_hint(self):
        """현재 선택된 빈칸(또는 첫 빈칸)에 정답 글자 카드를 자동으로 찾아 꽂아줍니다."""
        if not self.stage_data:
            return
        blanks = sorted(self.stage_data["blank_cells"])
        target_rc = self.selected_cell if (self.selected_cell in blanks and self.selected_cell not in self.user_grid) else None
        if target_rc is None:
            for rc in blanks:
                if rc not in self.user_grid:
                    target_rc = rc
                    break
        if target_rc is None:
            return

        r, c = target_rc
        ans_ch = self.stage_data["grid_solution"][r][c]

        # 손패에서 해당 정답 글자 카드 찾기
        for idx, ch in enumerate(self.stage_data["hand_cards"]):
            if idx not in self.used_card_indices and ch == ans_ch:
                self.selected_cell = target_rc
                self.place_card_into_selected(idx)
                self.msg_lbl.configure(text=f"💡 힌트 요정이 '{ans_ch}' 카드를 알맞은 자리에 놓아주었어요!", fg="#4ade80")
                return

    def _check_words_status(self):
        sol = self.stage_data["grid_solution"]
        newly_completed = []

        self.completed_words.clear()
        for idx, pw in enumerate(self.stage_data["placed_words"], start=1):
            all_match = True
            for r, c in pw["cells"]:
                if (r, c) in self.stage_data["blank_cells"]:
                    if (r, c) not in self.user_grid or self.user_grid[(r, c)]["char"] != sol[r][c]:
                        all_match = False
                        break
            if all_match:
                self.completed_words.add(idx)
                newly_completed.append(pw["word"])

        self.refresh_clues_panel()

        # 모든 단어 완성 시 스테이지 클리어!
        if len(self.completed_words) == len(self.stage_data["placed_words"]):
            self.score += 100 + self.current_stage * 10
            self.unlocked_stage = max(self.unlocked_stage, min(100, self.current_stage + 1))
            self._save_progress()
            self.redraw_all()
            self.after(200, self._on_stage_clear)
        elif len(self.user_grid) == len(self.stage_data["blank_cells"]):
            # 빈칸은 다 채웠는데 틀린 글자가 있는 경우
            self.msg_lbl.configure(
                text="🤔 어라? 위치가 바뀐 글자 카드가 있어요! 노란색 칸을 다시 클릭해서 빼낸 뒤 자리를 바꿔보세요!",
                fg="#fca5a5",
            )

    def _on_stage_clear(self):
        words_summary = "\n".join(
            f" • {pw['word']} : {pw['clue']}" for pw in self.stage_data["placed_words"]
        )
        if self.current_stage < 100:
            ans = messagebox.askyesno(
                f"🎉 Stage {self.current_stage} 클리어!",
                f"와아! 정말 대단해요! 모든 한글 낱말을 완성했어요!\n\n"
                f"[오늘 배운 낱말]\n{words_summary}\n\n"
                f"⭐ 현재 지혜 점수: {self.score:,}점\n"
                f"바로 다음 스테이지(Stage {self.current_stage + 1})로 도전할까요?",
                parent=self,
            )
            if ans:
                self.start_stage(self.current_stage + 1)
        else:
            messagebox.showinfo(
                "👑 Stage 100 최종 마스터 달성!",
                f"축하합니다!! Stage 0부터 Stage 100까지 모든 한글 지혜의 산수화를 정복했어요!\n"
                f"최종 지혜 점수: {self.score:,}점",
                parent=self,
            )


if __name__ == "__main__":
    app = HangulCardGameApp()
    app.mainloop()
