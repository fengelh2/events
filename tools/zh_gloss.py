"""Rough English gloss for Chinese event titles.

WHY A DICTIONARY AND NOT A TRANSLATION API: the nightly build is a
deterministic pipeline with no API keys and no network budget beyond the
scrapes themselves. A translation service would add a per-run cost, a new
failure mode in CI, and non-reproducible output. A term dictionary is free,
deterministic, and degrades gracefully — an unknown word simply stays in
Chinese rather than the whole row failing.

WHAT THIS IS NOT: it is not a translation. It is a term-substitution gloss,
so word order stays Chinese and particles are dropped. "親子星空探索之旅"
glosses as "parent-child stargazing journey", which is the point — enough for
a parent scanning a calendar to decide whether to click. The original title is
always kept alongside it, because that is what you need to search for or quote
when booking.

The vocabulary was built from the ACTUAL Chinese titles rendering on the
hk-kids page (32 of them on 2026-09-09), not from a generic word list, so it
covers the terms this calendar really produces.
"""

from __future__ import annotations

import re

# Ordered LONGEST-FIRST at match time. Multi-character terms must win over
# their own substrings: 水上樂園 (water park) must be tried before 樂園
# (park), and 親子 (parent-child) before 子.
_TERMS: dict[str, str] = {
    # ── venues & places ────────────────────────────────────────────────
    "大尾篤": "Tai Mei Tuk", "美荷樓": "Mei Ho House", "九龍城寨": "Kowloon Walled City",
    "嘉道理農場暨植物園": "Kadoorie Farm & Botanic Garden", "嘉道理農場": "Kadoorie Farm",
    "香港話劇團": "HK Repertory Theatre", "舞蹈中心": "Dance Centre",
    "國際廣場": "Plaza", "朗壹廣場": "One North", "圖書館": "library",
    "博物館": "museum", "劇場": "theatre", "農場": "farm", "廣場": "plaza",
    "海岸公園": "Marine Park", "公園": "park", "大埔": "Tai Po", "香港": "Hong Kong",
    "星光大道": "Avenue of Stars", "六廠": "CHAT Mills",
    # ── audience ───────────────────────────────────────────────────────
    "親子": "parent-child", "兒童": "children", "幼兒": "toddler", "嬰兒": "baby",
    "小朋友": "kids", "青少年": "youth", "寶寶": "baby", "小小": "little",
    "家庭": "family", "合家歡": "family fun",
    # ── activity types ─────────────────────────────────────────────────
    "水上樂園": "water park", "遊樂場": "playground", "工作坊": "workshop",
    "體驗營": "experience camp", "嘉年華": "carnival", "同樂日": "fun day",
    "綵燈會": "lantern carnival", "巡迴展覽": "touring exhibition",
    "展覽": "exhibition", "音樂會": "concert", "歌劇": "opera", "戲劇": "drama",
    "舞蹈": "dance", "音樂": "music", "課程": "course", "課": "class",
    "故事": "story", "繪本": "picture book", "電影": "film", "放映": "screening",
    "健身": "fitness", "探索": "exploration", "之旅": "journey",
    "大冒險": "big adventure", "冒險": "adventure", "碰碰船": "bumper boats",
    "恐龍": "dinosaur", "星空": "stargazing", "感官": "sensory",
    "玩具": "toy", "小卡車": "little truck", "馬術": "equestrian",
    "規劃師": "planner", "鐵路": "railway", "漫畫": "comics", "南瓜": "Pumpkin",
    "聖誕": "Christmas", "中秋": "Mid-Autumn", "週末": "weekend",
    "好去處": "things to do", "預約": "booking", "報名": "registration",
    "免費": "free", "入園": "admission", "登記": "register",
    "早鳥優惠": "early-bird", "優惠": "offer", "週年": "anniversary", "周年": "anniversary",
    "成立": "founded", "第四期": "phase 4", "展期": "run extended",
    "小馬": "pony", "大本營": "base camp", "夏日": "summer", "仲夏": "midsummer",
    "奇幻": "fantasy", "秘密": "secret", "人魚島": "Mermaid Island",
    "怪獸": "monster", "育成計劃": "nurture programme", "光影": "light & shadow",
    "綜合": "integrated", "啟蒙": "introductory", "音樂家": "musician",
    "手製": "handmade", "我的": "my", "聖誕樹": "Christmas tree",
    "織": "weaving", "藤": "rattan", "花": "flower", "式": "style",
    "工業": "industry", "留聲": "sound", "星期六": "Saturday", "星期日": "Sunday",
    "逢三": "every Wed", "歲": "yrs", "米闊": "m wide", "巨型": "giant",
    "第": "no.", "期": "term", "季": "season", "上課日期": "class dates",
}

# Punctuation that carries no meaning in the gloss.
_STRIP = "《》「」『』【】〈〉（）()·・、，,：:！!？?︕｜|～~"

_CJK = re.compile(r"[㐀-䶿一-鿿]")


def has_chinese(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def gloss(title: str) -> str | None:
    """Return a rough English gloss, or None when it would not help.

    None is returned when the title has no Chinese at all, or when too little
    of it could be glossed — a string that is still mostly Chinese characters
    is not an English gloss, and showing it would be worse than showing
    nothing.
    """
    if not title or not has_chinese(title):
        return None

    # Chinese dates first: "6月9日" -> "9 Jun". Without this the term pass
    # strips 月/日 and leaves the bare digits glued together ("69").
    _MON = ("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
    def _date(m):
        mo, dy = int(m.group(1)), m.group(2)
        return f" {dy} {_MON[mo-1]} " if 1 <= mo <= 12 else m.group(0)
    out = re.sub(r"(\d{1,2})月(\d{1,2})日", _date, title)
    out = re.sub(r"(\d{1,2})月", lambda m: f" {_MON[int(m.group(1))-1]} "
                 if 1 <= int(m.group(1)) <= 12 else m.group(0), out)
    for term in sorted(_TERMS, key=len, reverse=True):
        if term in out:
            out = out.replace(term, f" {_TERMS[term]} ")

    for ch in _STRIP:
        out = out.replace(ch, " ")
    out = re.sub(r"\s+", " ", out).strip()

    # Refuse to emit a half-Chinese string. If more than a quarter of what is
    # left is still CJK, the dictionary did not cover this title.
    remaining = len(_CJK.findall(out))
    if remaining and remaining > max(1, len(out.replace(" ", "")) * 0.25):
        return None
    # Drop any residual CJK so the gloss reads as English.
    out = _CJK.sub("", out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s*/\s*$", "", out).strip(" -–—:|/")
    if len(out) < 4:
        return None
    return out
