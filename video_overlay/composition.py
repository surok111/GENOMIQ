"""Overlay timeline for Timur's GENOMIQ pitch.

The picture is a vertical talking-head take (720×1590, 50.6 s).
Each scene is timed to the spoken phrase in `speech`. The converter in
`convert.py` paints these scenes on top of the original recording.

Speech anchors (Russian, recognised from the soundtrack):

  0–5    Здравствуйте, меня зовут Тимур, я основатель проекта Genomic,
         софт для интерпретации генетических…
  5–8    …данных. Лаборатории в России, 10 генетиков
  ~8     200 пациентов в месяц
  ~10    9 часов ручной курации на каждого
  ~13    это непомерная нагрузка
  ~16    неточность и усталость равно судебный иск
  ~20    и потеря пациента
  ~21    наше решение — инструмент, сокращающий время анализа
  ~24    с медианы восьми часов до 40 минут
  ~28    инструмент интегрируется в медицинское ПО
  ~32    и не требует ручного сопровождения
  ~35    в рабочем процессе Genomic забирает всю рутинную работу
  ~38    врачу остаётся только проверить и поставить печать
  ~41    база знаний валидирована специалистами из разных стран
  ~45    продукт успешно проходит первые тесты
  ~47    HealthNet станет важным этапом в развитии Genomiq
  ~50    спасибо

Heard-as corrections kept in the on-screen copy:
  «9:00» → «9 часов»
  «медицинское по / право» → «медицинское ПО»
  «10 генетики» → «10 генетиков»
  «Валентина / Валиди специалистами» → «валидирована специалистами»
  «медианах» → «медианы»
  closing «джено…» → Genomiq
"""

from __future__ import annotations

WIDTH = 720
HEIGHT = 1590
FPS = 30
DURATION = 50.633333

# Shirt starts near y=1080; wall above the hair ends near y=330.
# Cards stay on the shirt. Marker chips stay on the wall.
WALL_BOTTOM = 330
CARD_MIN_TOP = 1096
CARD_BOTTOM_MARGIN = 72

# Tones used by cards, chips, and icons.
TONES = {
    "teal": {"bar": (15, 138, 132, 255), "ink": (16, 42, 48, 255), "soft": (226, 244, 241, 255)},
    "gold": {"bar": (196, 132, 42, 255), "ink": (62, 40, 12, 255), "soft": (255, 244, 224, 255)},
    "danger": {"bar": (184, 48, 58, 255), "ink": (72, 16, 22, 255), "soft": (255, 232, 232, 255)},
    "ink": {"bar": (20, 32, 40, 255), "ink": (20, 32, 40, 255), "soft": (238, 236, 230, 255)},
}


# kind:
#   hero      big title
#   stats     counting tiles, each item pops at `at` seconds into the scene
#   alert     single warning
#   equation  chips that add up to a consequence
#   compare   before → after
#   checks    rows that tick in
#   flow      routine vs what the doctor still does, plus a stamp
#   trust     validation line
#   finale    tests, HealthNet, thanks
#
# item keys vary by kind; `at` is delay from scene start, in seconds.
SCENES: list[dict] = [
    {
        "start": 0.12,
        "end": 2.90,
        "section": "Знакомство",
        "tone": "gold",
        "kind": "hero",
        "icon": "marker",
        "kicker": "Здравствуйте",
        "title": "Тимур",
        "subtitle": "основатель проекта",
        "speech": "Меня зовут Тимур. Я основатель проекта.",
    },
    {
        "start": 2.55,
        "end": 6.95,
        "section": "Продукт",
        "tone": "teal",
        "kind": "hero",
        "icon": "dna",
        "kicker": "GENOMIQ",
        "title": "Интерпретация\nгенетических данных",
        "subtitle": "софт для лабораторий",
        "speech": "Софт для интерпретации генетических данных.",
        "note_at": 5.05,
        "note": "Лаборатории в России",
        "note_icon": "pin",
    },
    {
        "start": 6.55,
        "end": 12.35,
        "section": "Проблема",
        "tone": "ink",
        "kind": "stats",
        "kicker": "Лаборатории в России",
        "speech": "10 генетиков. 200 пациентов в месяц. 9 часов курации на каждого.",
        "items": (
            {"value": 10, "text": "10", "label": "генетиков", "icon": "people", "at": 0.05},
            {"value": 200, "text": "200", "label": "пациентов\nв месяц", "icon": "calendar", "at": 1.45},
            {"value": 9, "text": "9 ч", "label": "ручная\nкурация", "icon": "clock", "at": 3.05},
        ),
    },
    {
        "start": 12.05,
        "end": 15.90,
        "section": "Проблема",
        "tone": "danger",
        "kind": "alert",
        "icon": "warning",
        "kicker": "На каждого пациента",
        "title": "Непомерная\nнагрузка",
        "subtitle": "ручная курация не масштабируется",
        "speech": "Это непомерная нагрузка.",
    },
    {
        "start": 15.55,
        "end": 21.40,
        "section": "Проблема",
        "tone": "danger",
        "kind": "equation",
        "kicker": "Цена ошибки",
        "speech": "Неточность и усталость — это судебный иск и потеря пациента.",
        "items": (
            {"text": "Неточность", "icon": "alert", "at": 0.15},
            {"text": "Усталость", "icon": "clock", "at": 0.85},
        ),
        "results": (
            {"text": "Судебный иск", "icon": "gavel", "at": 2.35},
            {"text": "Потеря пациента", "icon": "user_x", "at": 4.15},
        ),
    },
    {
        "start": 21.05,
        "end": 28.45,
        "section": "Решение",
        "tone": "teal",
        "kind": "compare",
        "icon": "spark",
        "kicker": "Наше решение",
        "title": "Время анализа",
        "speech": "Инструмент сокращает медиану с 8 часов до 40 минут.",
        "before": {"value": "8 ч", "label": "было", "at": 2.70},
        "after": {"value": "40 мин", "label": "стало", "at": 3.55},
    },
    {
        "start": 28.10,
        "end": 34.75,
        "section": "Решение",
        "tone": "teal",
        "kind": "checks",
        "kicker": "Как это встаёт в клинику",
        "speech": "Интегрируется в медицинское ПО и не требует ручного сопровождения.",
        "items": (
            {"text": "Интеграция в медицинское ПО", "icon": "plug", "at": 0.20},
            {"text": "Без ручного сопровождения", "icon": "check", "at": 3.55},
        ),
    },
    {
        "start": 34.40,
        "end": 41.75,
        "section": "Решение",
        "tone": "gold",
        "kind": "flow",
        "kicker": "Рабочий процесс",
        "speech": "Genomic забирает рутину. Врачу остаётся проверить и поставить печать.",
        "lead": "Genomic забирает всю рутинную работу",
        "lead_at": 0.25,
        "steps": (
            {"text": "Проверить", "at": 3.15},
            {"text": "Поставить печать", "at": 3.90},
        ),
        "stamp_at": 3.70,
    },
    {
        "start": 41.40,
        "end": 46.05,
        "section": "Доверие",
        "tone": "teal",
        "kind": "trust",
        "icon": "globe",
        "kicker": "База знаний",
        "title": "Валидирована\nспециалистами",
        "subtitle": "из разных стран",
        "speech": "База знаний валидирована специалистами из разных стран.",
    },
    {
        "start": 45.70,
        "end": 50.64,
        "section": "Доверие",
        "tone": "gold",
        "kind": "finale",
        "speech": "Продукт проходит первые тесты. HealthNet — этап развития Genomiq.",
        "items": (
            {"text": "Первые тесты пройдены", "icon": "check", "at": 0.25},
            {"text": "HealthNet", "icon": "heart", "at": 1.15, "badge": True},
            {"text": "Этап развития GENOMIQ", "icon": "dna", "at": 2.15},
        ),
        "thanks_at": 3.85,
        "thanks": "Спасибо",
    },
]


# Short chips on the grey wall, synced tighter than the cards.
MARKERS: list[dict] = [
    {"start": 0.35, "end": 2.85, "text": "Тимур", "icon": "marker", "tone": "gold"},
    {"start": 2.70, "end": 6.70, "text": "Генетические данные", "icon": "dna", "tone": "teal"},
    {"start": 5.05, "end": 7.15, "text": "Россия", "icon": "pin", "tone": "teal"},
    {"start": 6.70, "end": 8.35, "text": "10 генетиков", "icon": "people", "tone": "ink"},
    {"start": 8.00, "end": 9.85, "text": "200 пациентов", "icon": "calendar", "tone": "ink"},
    {"start": 9.60, "end": 12.30, "text": "9 часов", "icon": "clock", "tone": "gold"},
    {"start": 12.20, "end": 15.70, "text": "Нагрузка", "icon": "warning", "tone": "danger"},
    {"start": 15.70, "end": 18.15, "text": "Неточность", "icon": "alert", "tone": "danger"},
    {"start": 16.50, "end": 18.90, "text": "Усталость", "icon": "clock", "tone": "danger"},
    {"start": 17.90, "end": 20.40, "text": "Судебный иск", "icon": "gavel", "tone": "danger"},
    {"start": 19.70, "end": 21.45, "text": "Потеря пациента", "icon": "user_x", "tone": "danger"},
    {"start": 21.20, "end": 24.10, "text": "Решение", "icon": "spark", "tone": "teal"},
    {"start": 23.80, "end": 28.30, "text": "8 ч  →  40 мин", "icon": "arrow", "tone": "teal"},
    {"start": 28.20, "end": 31.90, "text": "Медицинское ПО", "icon": "plug", "tone": "teal"},
    {"start": 31.70, "end": 34.60, "text": "Без ручного труда", "icon": "check", "tone": "teal"},
    {"start": 34.60, "end": 37.90, "text": "Рутина на Genomic", "icon": "layers", "tone": "gold"},
    {"start": 37.80, "end": 41.60, "text": "Печать врача", "icon": "stamp", "tone": "gold"},
    {"start": 41.50, "end": 45.80, "text": "Валидация", "icon": "globe", "tone": "teal"},
    {"start": 45.80, "end": 48.40, "text": "Первые тесты", "icon": "check", "tone": "gold"},
    {"start": 47.00, "end": 50.40, "text": "HealthNet", "icon": "heart", "tone": "gold"},
]
