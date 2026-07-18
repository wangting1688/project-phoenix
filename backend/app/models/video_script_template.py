"""
爆款结构模板库模型

TASK-016.3A.7：AI导演决策增强层

核心表：
1. video_script_templates - 爆款结构模板库
"""

from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Float, Boolean
from app.core.database import Base
from app.core.base_model import BaseModel


class VideoScriptTemplate(Base, BaseModel):
    """
    爆款结构模板库

    预定义经过验证的短视频结构模板，AI导演根据文案内容自动选择最匹配的模板
    """
    __tablename__ = "video_script_templates"

    # 模板基本信息
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # 分类标签
    template_type = Column(String(50), index=True, nullable=False)
    # pain_point - 痛点型
    # story - 故事型
    # expert - 专家型
    # product - 产品型
    # knowledge - 知识型
    # emotion - 情感型

    industry = Column(String(100), nullable=True, index=True)
    # health / beauty / food / finance / education / general

    content_type = Column(String(50), nullable=True)
    # health_warning / personal_experience / expert_explainer / product_demo

    # 结构定义
    structure = Column(JSON, nullable=False)
    # [
    #   {
    #     "role": "hook",
    #     "time_range": "0-3",
    #     "duration": 3,
    #     "purpose": "制造冲突",
    #     "emotion": "疑问",
    #     "required": true,
    #     "tips": "用反问或数据开场"
    #   },
    #   {
    #     "role": "problem",
    #     "time_range": "3-10",
    #     "duration": 7,
    #     "purpose": "描述用户痛苦",
    #     "emotion": "关心",
    #     "required": true,
    #     "tips": "具体描述痛点"
    #   },
    #   ...
    # ]

    # 适用场景
    best_for = Column(Text, nullable=True)
    # "适合青汁、健康食品类产品，目标受众30-50岁女性"

    # 目标受众
    target_audience = Column(String(200), nullable=True)

    # 效果数据
    conversion_rate = Column(Float, default=0.0)  # 历史平均转化率
    completion_rate = Column(Float, default=0.0)  # 历史平均完播率
    usage_count = Column(Integer, default=0)  # 使用次数

    # 评分
    template_score = Column(Integer, default=0)  # 模板综合评分

    # 状态
    is_active = Column(Boolean, default=True, index=True)
    is_preset = Column(Boolean, default=False)  # 是否为系统预置模板

    def __repr__(self):
        return f"<VideoScriptTemplate(name={self.name}, type={self.template_type})>"
