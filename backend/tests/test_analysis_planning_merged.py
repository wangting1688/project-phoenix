"""合并后的“分析与策划”提示词应同时返回内容字段与策划字段。"""

from app.experts.ai_expert import AIExpertService, MockAIProvider


def test_merged_mock_returns_both_sections():
    svc = AIExpertService(ai_provider=MockAIProvider())
    result = svc.analysis_planning_expert("更年期失眠怎么改善")
    assert result.get("title")
    assert result.get("style")
    assert result.get("structure")
    assert result.get("opening_hook")
    assert result.get("duration") == 60
