"""
视频剪辑编排层模型

TASK-016.3A.6：AI剪辑素材编排层

核心表：
1. video_edit_plans - AI剪辑计划（导演分镜）
2. video_edit_segments - 剪辑片段关联（镜头→素材片段映射）
"""

from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Float, DateTime, Boolean
from app.core.database import Base
from app.core.base_model import BaseModel


class VideoEditPlan(Base, BaseModel):
    """
    AI剪辑计划表 - 导演分镜方案

    AI导演根据文案+主播画像+素材库生成的完整剪辑方案
    """
    __tablename__ = "video_edit_plans"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    video_project_id = Column(Integer, ForeignKey("video_projects.id"), index=True, nullable=True)
    script_id = Column(Integer, ForeignKey("content_versions.id"), nullable=True)

    # 计划信息
    title = Column(String(200), nullable=False)
    total_duration = Column(Integer, default=60)  # 总时长（秒）
    editing_strategy = Column(String(50), default="standard")
    # standard - 标准型（hook+explain+ending）
    # story - 故事型（problem+emotion+trust+ending）
    # product - 产品型（hook+problem+product+ending）
    # knowledge - 知识型（hook+explain+trust+ending）

    business_stage = Column(String(50), default="growth", index=True)
    # growth - 涨粉期
    # relationship - 信任建立期
    # conversion - 成交期

    # 文案内容
    script_content = Column(Text, nullable=True)
    script_sections = Column(JSON, nullable=True)
    # [{"section": "hook", "text": "40岁以后为什么容易疲惫？", "duration": 3}, ...]

    # AI导演分析
    director_analysis = Column(JSON, nullable=True)
    # {
    #   "target_audience": "30-50岁女性",
    #   "emotion_flow": ["疑问", "认真", "真诚", "亲切"],
    #   "key_message": "青汁补充膳食纤维",
    #   "conversion_point": "引导咨询",
    #   "recommended_style": "聊天式",
    # }

    # 素材匹配状态
    match_status = Column(String(50), default="pending", index=True)
    # pending - 待匹配
    # matched - 已匹配
    # partial - 部分匹配（有缺失素材）
    # failed - 匹配失败

    # 匹配统计
    total_shots = Column(Integer, default=0)
    matched_shots = Column(Integer, default=0)
    missing_shots = Column(Integer, default=0)

    # 补拍建议
    shooting_suggestions = Column(JSON, nullable=True)
    # [{"role": "product", "required": true, "description": "手拿青汁包装", "duration": 10}, ...]

    # 预测效果
    predicted_completion_rate = Column(Float, default=0.0)
    predicted_conversion_rate = Column(Float, default=0.0)

    # TASK-016.3A.7: 导演评分机制
    director_score = Column(Integer, default=0)  # 导演方案综合评分 0-100
    score_breakdown = Column(JSON, nullable=True)
    # {
    #   "template_match": {"score": 28, "max": 30, "reason": "模板匹配度高"},
    #   "asset_quality": {"score": 22, "max": 25, "reason": "素材质量优秀"},
    #   "creator_fit": {"score": 18, "max": 20, "reason": "匹配主播最佳情绪"},
    #   "conversion": {"score": 13, "max": 15, "reason": "产品镜头+结尾完整"},
    #   "originality": {"score": 9, "max": 10, "reason": "结构有新意"},
    # }
    score_reasons = Column(JSON, nullable=True)
    # ["+ 主播情绪匹配", "+ hook素材强", "- 产品出现稍早"]

    # 模板关联
    template_id = Column(Integer, ForeignKey("video_script_templates.id"), nullable=True)

    # 补拍任务关联
    shooting_task_ids = Column(JSON, nullable=True)
    # 生成的asset_collection_tasks的ID列表

    # 状态
    status = Column(String(50), default="draft", index=True)
    # draft - 草稿
    # reviewed - 已审核
    # approved - 已批准
    # editing - 剪辑中
    # completed - 已完成

    def __repr__(self):
        return f"<VideoEditPlan(title={self.title}, status={self.status}, matched={self.matched_shots}/{self.total_shots})>"


class VideoEditSegment(Base, BaseModel):
    """
    剪辑片段关联表 - 镜头→素材片段映射

    一个剪辑计划包含多个镜头，每个镜头对应一个素材片段
    """
    __tablename__ = "video_edit_segments"

    edit_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), index=True, nullable=False)
    asset_segment_id = Column(Integer, ForeignKey("asset_segments.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 镜头信息
    sequence = Column(Integer, nullable=False)  # 镜头序号
    role = Column(String(50), nullable=False, index=True)
    # hook / problem / explain / trust / emotion / product / ending / transition

    # 时间安排
    start_time = Column(Float, default=0.0)  # 在最终视频中的开始时间
    end_time = Column(Float, default=0.0)  # 在最终视频中的结束时间
    duration = Column(Float, default=0.0)  # 时长

    # 素材片段信息（冗余，方便查询）
    asset_id = Column(Integer, nullable=True)
    source_start_time = Column(Float, nullable=True)  # 原素材片段开始时间
    source_end_time = Column(Float, nullable=True)  # 原素材片段结束时间

    # 剪辑指令
    transition = Column(String(50), default="cut")
    # cut - 硬切
    # fade - 淡入淡出
    # slide - 滑动
    # zoom - 缩放
    # dissolve - 溶解

    subtitle_style = Column(String(50), default="standard")
    # standard - 标准
    # highlight - 高亮关键词
    # emphasis - 强调
    # question - 问句样式

    effect_style = Column(String(50), default="none")
    # none - 无特效
    # zoom_in - 放大
    # zoom_out - 缩小
    # shake - 震动
    # blur - 模糊

    # AI推荐原因
    reason = Column(Text, nullable=True)
    # "该主播前三秒停留率最高"
    # "该片段与文案内容匹配度96%"

    # 匹配状态
    match_status = Column(String(50), default="pending")
    # matched - 已匹配
    # missing - 素材缺失
    # alternative - 使用替代方案

    # 匹配置信度
    match_score = Column(Float, default=0.0)  # 0-100

    # 字幕内容
    subtitle_text = Column(Text, nullable=True)
    subtitle_highlights = Column(JSON, nullable=True)  # 高亮词列表

    def __repr__(self):
        return f"<VideoEditSegment(seq={self.sequence}, role={self.role}, status={self.match_status})>"
