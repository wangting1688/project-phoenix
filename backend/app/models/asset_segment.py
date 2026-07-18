"""
素材片段模型

TASK-016.3A.5：AI素材片段化能力增强

核心表：asset_segments
将长视频拆分为可被剪辑调用的独立片段
"""

from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Float, DateTime, Boolean
from app.core.database import Base
from app.core.base_model import BaseModel


class AssetSegment(Base, BaseModel):
    """
    素材片段表 - 独立数据表
    
    将原始素材拆分为可被AI剪辑直接调用的片段
    """
    __tablename__ = "asset_segments"

    asset_id = Column(Integer, ForeignKey("creator_assets.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 片段信息
    segment_number = Column(Integer, nullable=False)  # 片段序号
    start_time = Column(Float, nullable=False)  # 开始时间（秒）
    end_time = Column(Float, nullable=False)  # 结束时间（秒）
    duration = Column(Float, nullable=False)  # 时长（秒）

    # 商业角色标签（短视频结构位置）
    segment_role = Column(String(50), index=True, nullable=False)
    # hook - 3秒抓人
    # problem - 提出问题
    # explain - 知识解释
    # trust - 建立信任
    # emotion - 情感共鸣
    # product - 产品关联
    # ending - 结尾互动
    # transition - 过渡转场

    # 情绪
    emotion = Column(String(50), index=True, nullable=False)
    # 亲切、认真、开心、自然、疑问、真诚、热情、思考、放松

    # 用途描述
    purpose = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)

    # 评分
    quality_score = Column(Integer, default=0)  # 片段质量评分
    conversion_score = Column(Integer, default=0)  # 转化潜力评分
    reuse_score = Column(Integer, default=0)  # 复用价值评分
    commercial_value_score = Column(Integer, default=0)  # 商业价值评分（综合复用+转化+停留+互动）

    # 标签
    tags = Column(JSON, nullable=True)  # 片段标签

    # 场景信息
    scene_type = Column(String(50), nullable=True)
    background_cleanliness = Column(String(50), nullable=True)

    # 人物表现
    face_visibility = Column(String(50), nullable=True)
    eye_contact = Column(String(50), nullable=True)
    speech_detected = Column(Boolean, default=False)

    # 语音信息
    voice_tone = Column(String(50), nullable=True)
    speech_pace = Column(String(50), nullable=True)

    # 使用统计
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # 分析状态
    analysis_status = Column(String(50), default="completed", index=True)

    def __repr__(self):
        return f"<AssetSegment(asset_id={self.asset_id}, role={self.segment_role}, score={self.quality_score})>"


class CreatorPerformanceProfile(Base, BaseModel):
    """
    主播表现画像表
    
    基于历史素材分析，发现主播最容易成功的表现方式
    """
    __tablename__ = "creator_performance_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False, unique=True)

    # 最佳情绪
    best_emotion = Column(String(50), nullable=True)
    emotion_scores = Column(JSON, nullable=True)
    # {
    #   "亲切": {"usage_count": 20, "avg_score": 92, "conversion_rate": 0.15},
    #   "认真": {"usage_count": 15, "avg_score": 88, "conversion_rate": 0.12},
    # }

    # 最佳场景
    best_scene = Column(String(50), nullable=True)
    scene_scores = Column(JSON, nullable=True)

    # 最佳时长
    best_duration_range = Column(String(50), nullable=True)  # "15-30秒"
    duration_preference = Column(JSON, nullable=True)

    # 最佳内容类型
    best_content_type = Column(String(50), nullable=True)  # "故事型" / "知识型" / "科普型"
    content_type_scores = Column(JSON, nullable=True)

    # 转化风格
    conversion_style = Column(String(50), nullable=True)  # "聊天式" / "专业式" / "情感式"

    # 角色表现
    best_segment_roles = Column(JSON, nullable=True)
    # ["hook", "explain", "trust"]

    # 整体表现评分
    overall_performance_score = Column(Integer, default=0)

    # 分析统计
    analyzed_segments = Column(Integer, default=0)
    total_usage_count = Column(Integer, default=0)

    # 更新时间
    last_updated_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<CreatorPerformanceProfile(user_id={self.user_id}, best_emotion={self.best_emotion})>"
