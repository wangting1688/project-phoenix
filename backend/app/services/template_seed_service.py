"""
爆款结构模板预置数据

TASK-016.3A.7：AI导演决策增强层

预置经过验证的6种爆款短视频结构模板
"""

from typing import List, Dict
from app.core.database import SessionLocal
from app.models import VideoScriptTemplate


PRESET_TEMPLATES: List[Dict] = [
    {
        "name": "痛点型-健康焦虑",
        "description": "适合健康类产品，用痛点切入引发焦虑，再给出解决方案",
        "template_type": "pain_point",
        "industry": "health",
        "content_type": "health_warning",
        "structure": [
            {"role": "hook", "time_range": "0-3", "duration": 3, "purpose": "制造冲突", "emotion": "疑问", "required": True, "tips": "用反问或数据开场，如'40岁以后你有没有发现...'"},
            {"role": "problem", "time_range": "3-10", "duration": 7, "purpose": "描述用户痛苦", "emotion": "关心", "required": True, "tips": "具体描述痛点，让观众觉得'说的就是我'"},
            {"role": "explain", "time_range": "10-20", "duration": 10, "purpose": "解释原因", "emotion": "认真", "required": True, "tips": "用专业知识解释为什么会出现这个问题"},
            {"role": "trust", "time_range": "20-30", "duration": 10, "purpose": "建立信任", "emotion": "真诚", "required": True, "tips": "分享个人经验或案例"},
            {"role": "product", "time_range": "30-40", "duration": 10, "purpose": "自然引入产品", "emotion": "自然", "required": False, "tips": "产品是解决方案的一部分，不是硬广"},
            {"role": "ending", "time_range": "40-45", "duration": 5, "purpose": "引导咨询", "emotion": "微笑", "required": True, "tips": "引导关注或私信咨询"},
        ],
        "best_for": "适合青汁、健康食品、保健品类产品，目标受众30-50岁女性",
        "target_audience": "30-50岁女性",
        "conversion_rate": 0.045,
        "completion_rate": 0.52,
        "template_score": 92,
    },
    {
        "name": "故事型-个人经历",
        "description": "用主播真实经历讲故事，建立情感连接后自然推荐",
        "template_type": "story",
        "industry": "general",
        "content_type": "personal_experience",
        "structure": [
            {"role": "hook", "time_range": "0-3", "duration": 3, "purpose": "以前的我", "emotion": "感慨", "required": True, "tips": "展示过去的状态，引发好奇"},
            {"role": "problem", "time_range": "3-10", "duration": 7, "purpose": "出现问题", "emotion": "苦恼", "required": True, "tips": "描述遇到的困难和挫折"},
            {"role": "emotion", "time_range": "10-20", "duration": 10, "purpose": "情感转折", "emotion": "真诚", "required": True, "tips": "分享心路历程，触动情感"},
            {"role": "trust", "time_range": "20-30", "duration": 10, "purpose": "发现方法", "emotion": "开心", "required": True, "tips": "展示改变的过程和效果"},
            {"role": "product", "time_range": "30-38", "duration": 8, "purpose": "推荐给别人", "emotion": "亲切", "required": False, "tips": "因为自己受益所以推荐"},
            {"role": "ending", "time_range": "38-42", "duration": 4, "purpose": "引导关注", "emotion": "微笑", "required": True, "tips": "关注了解更多"},
        ],
        "best_for": "适合所有品类，特别适合建立主播个人IP和信任感",
        "target_audience": "25-50岁大众",
        "conversion_rate": 0.038,
        "completion_rate": 0.58,
        "template_score": 88,
    },
    {
        "name": "专家型-知识科普",
        "description": "以专家身份纠正错误认知，用科学依据建立权威",
        "template_type": "expert",
        "industry": "health",
        "content_type": "expert_explainer",
        "structure": [
            {"role": "hook", "time_range": "0-3", "duration": 3, "purpose": "错误认知", "emotion": "严肃", "required": True, "tips": "提出一个常见的错误认知"},
            {"role": "explain", "time_range": "3-18", "duration": 15, "purpose": "专业解释", "emotion": "认真", "required": True, "tips": "用专业知识解释正确做法"},
            {"role": "trust", "time_range": "18-28", "duration": 10, "purpose": "科学依据", "emotion": "专业", "required": True, "tips": "引用研究或数据支持"},
            {"role": "product", "time_range": "28-38", "duration": 10, "purpose": "建议方法", "emotion": "自然", "required": False, "tips": "产品作为建议方案之一"},
            {"role": "ending", "time_range": "38-42", "duration": 4, "purpose": "行动引导", "emotion": "微笑", "required": True, "tips": "引导收藏或咨询"},
        ],
        "best_for": "适合健康、护肤、营养品类，主播有专业知识背景",
        "target_audience": "28-45岁注重健康人群",
        "conversion_rate": 0.042,
        "completion_rate": 0.48,
        "template_score": 85,
    },
    {
        "name": "产品型-种草推荐",
        "description": "快速切入产品卖点，适合已经有认知基础的产品",
        "template_type": "product",
        "industry": "general",
        "content_type": "product_demo",
        "structure": [
            {"role": "hook", "time_range": "0-3", "duration": 3, "purpose": "产品亮点", "emotion": "开心", "required": True, "tips": "直接展示产品最吸引人的点"},
            {"role": "product", "time_range": "3-15", "duration": 12, "purpose": "使用展示", "emotion": "自然", "required": True, "tips": "展示使用过程和效果"},
            {"role": "trust", "time_range": "15-25", "duration": 10, "purpose": "真实体验", "emotion": "真诚", "required": True, "tips": "分享个人使用感受"},
            {"role": "emotion", "time_range": "25-32", "duration": 7, "purpose": "改变展示", "emotion": "开心", "required": False, "tips": "展示使用前后的变化"},
            {"role": "ending", "time_range": "32-35", "duration": 3, "purpose": "促单引导", "emotion": "微笑", "required": True, "tips": "引导下单或咨询"},
        ],
        "best_for": "适合有实物展示的产品，如护肤品、食品、日用品",
        "target_audience": "25-45岁女性",
        "conversion_rate": 0.052,
        "completion_rate": 0.42,
        "template_score": 80,
    },
    {
        "name": "知识型-干货分享",
        "description": "纯知识输出，建立专业形象，适合知识付费引流",
        "template_type": "knowledge",
        "industry": "education",
        "content_type": "expert_explainer",
        "structure": [
            {"role": "hook", "time_range": "0-3", "duration": 3, "purpose": "提出问题", "emotion": "疑问", "required": True, "tips": "用一个常见问题开场"},
            {"role": "explain", "time_range": "3-20", "duration": 17, "purpose": "知识讲解", "emotion": "认真", "required": True, "tips": "分点讲解，清晰有条理"},
            {"role": "trust", "time_range": "20-28", "duration": 8, "purpose": "经验分享", "emotion": "真诚", "required": True, "tips": "结合个人经验增加可信度"},
            {"role": "ending", "time_range": "28-32", "duration": 4, "purpose": "引导关注", "emotion": "微笑", "required": True, "tips": "引导关注获取更多干货"},
        ],
        "best_for": "适合知识类、教育类内容，建立专业IP",
        "target_audience": "25-40岁学习型人群",
        "conversion_rate": 0.028,
        "completion_rate": 0.55,
        "template_score": 78,
    },
    {
        "name": "情感型-共鸣触动",
        "description": "用情感故事引发共鸣，适合品牌传播和粉丝增长",
        "template_type": "emotion",
        "industry": "general",
        "content_type": "personal_experience",
        "structure": [
            {"role": "hook", "time_range": "0-3", "duration": 3, "purpose": "情感开场", "emotion": "感慨", "required": True, "tips": "用一句话触动情感"},
            {"role": "emotion", "time_range": "3-15", "duration": 12, "purpose": "故事展开", "emotion": "真诚", "required": True, "tips": "讲述真实故事，引发共鸣"},
            {"role": "problem", "time_range": "15-25", "duration": 10, "purpose": "困境描述", "emotion": "感慨", "required": True, "tips": "描述遇到的困难和挣扎"},
            {"role": "trust", "time_range": "25-35", "duration": 10, "purpose": "转折改变", "emotion": "开心", "required": True, "tips": "展示如何走出困境"},
            {"role": "ending", "time_range": "35-40", "duration": 5, "purpose": "鼓励互动", "emotion": "微笑", "required": True, "tips": "鼓励观众分享自己的故事"},
        ],
        "best_for": "适合品牌传播、粉丝增长，建立情感连接",
        "target_audience": "25-50岁大众",
        "conversion_rate": 0.022,
        "completion_rate": 0.62,
        "template_score": 75,
    },
]


def seed_preset_templates():
    """预置模板数据到数据库"""
    db = SessionLocal()
    try:
        # 检查是否已有预置模板
        existing = db.query(VideoScriptTemplate).filter(
            VideoScriptTemplate.is_preset == True
        ).count()

        if existing > 0:
            return f"已有 {existing} 个预置模板，跳过"

        for tpl_data in PRESET_TEMPLATES:
            template = VideoScriptTemplate(
                name=tpl_data["name"],
                description=tpl_data["description"],
                template_type=tpl_data["template_type"],
                industry=tpl_data["industry"],
                content_type=tpl_data["content_type"],
                structure=tpl_data["structure"],
                best_for=tpl_data["best_for"],
                target_audience=tpl_data["target_audience"],
                conversion_rate=tpl_data["conversion_rate"],
                completion_rate=tpl_data["completion_rate"],
                template_score=tpl_data["template_score"],
                is_active=True,
                is_preset=True,
            )
            db.add(template)

        db.commit()
        return f"成功预置 {len(PRESET_TEMPLATES)} 个爆款模板"
    finally:
        db.close()
