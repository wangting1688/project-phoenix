"""H3 字幕生成单元测试：无标点、底部对齐、最多两行、时间不重叠。"""

import re

from app.services.h3_pipeline import _build_subtitle_ass, _strip_punct, split_sentences


def _parse_events(ass: str):
    events = []
    for line in ass.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        m = re.match(r"Dialogue:\s*\d+,([\d:.]+),([\d:.]+),Default,.*?,,(.*)$", line)
        assert m, f"无法解析字幕行: {line}"

        def ts(s):
            h, mm, sec = s.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(sec)

        events.append((ts(m.group(1)), ts(m.group(2)), m.group(3)))
    return events


def _plain(text: str) -> str:
    """去掉 ASS 样式标签和换行标记，只留显示文字。"""
    return re.sub(r"\{[^}]*\}", "", text).replace("\\N", "")


def test_strip_punct_removes_cn_and_en_punctuation():
    text = "大家好，今天！怎么样？很好；真的:测试,OK！"
    cleaned = _strip_punct(text)
    assert "，" not in cleaned and "！" not in cleaned and "：" not in cleaned
    assert "大家" in cleaned and "测试" in cleaned and "OK" in cleaned


def test_subtitle_ass_bottom_no_punct_no_overlap():
    specs = [
        {"text": "大家好，今天分享更年期失眠怎么改善的方法。", "dur": 4.0},
        {"text": "第一，睡前放下手机；第二，喝杯温水。", "dur": 5.0},
    ]
    ass = _build_subtitle_ass(specs, 512, 960)

    assert re.search(r"Style: Default,.*?,2,", ass), "字幕未配置底部居中(Alignment=2)"
    assert "PlayResX: 512" in ass and "PlayResY: 960" in ass

    events = _parse_events(ass)
    assert events, "应生成至少一条字幕"
    prev_end = -1.0
    for start, end, text in events:
        display = _plain(text)
        assert _strip_punct(display) == display, f"字幕仍带标点: {text}"
        assert text.count("\\N") <= 1, f"超过两行: {text}"
        assert start >= prev_end - 0.001, f"字幕时间重叠: {start} < {prev_end}"
        prev_end = max(prev_end, end)


def test_first_hook_line_has_big_font():
    specs = [{"text": "为什么很多女性到了40岁以后睡眠会变差。", "dur": 4.0}]
    ass = _build_subtitle_ass(specs, 512, 960)
    events = _parse_events(ass)
    assert events and events[0][2].startswith("{\\fs"), "首句未使用大字钩子样式"


def test_split_sentences_filters_punct_only():
    sents = split_sentences("血脂高不是不能吃肉，是看你吃的是什么。。")
    assert len(sents) == 1
    assert sents[0].strip("。") == "血脂高不是不能吃肉，是看你吃的是什么"


def test_subtitle_does_not_split_digit_run():
    specs = [{"text": "为什么很多女性到了40岁以后睡眠会变差。", "dur": 4.0}]
    ass = _build_subtitle_ass(specs, 512, 960)
    events = _parse_events(ass)
    for _, _, text in events:
        assert "4\\N0" not in text, f"数字被拆开: {text}"
        lines = text.split("\\N")
        assert not (len(lines) > 1 and lines[-1].isdigit() and lines[-2][-1].isdigit())
