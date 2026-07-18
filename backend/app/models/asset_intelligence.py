"""
素材智能分析模型

AI素材智能分析管理系统 - 让AI看懂每一个主播素材
"""

from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Float, DateTime, Boolean
from app.core.database import Base
from app.core.base_model import BaseModel


class AssetIntelligence(Base, BaseModel):
    """
    素材智能分析表
    
    记录AI对每个素材的详细分析结果
    """
    __tablename__ = "asset_intelligence"

    asset_id = Column(Integer, ForeignKey("creator_assets.id"), index=True, nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 分析状态
    analysis_status = Column(String(50), default="pending", index=True)
    # pending / analyzing / completed / failed

    # 基础信息
    duration = Column(Float, default=0.0)  # 时长（秒）
    resolution = Column(String(50), nullable=True)  # 分辨率
    fps = Column(Float, nullable=True)  # 帧率
    file_size = Column(Integer, nullable=True)  # 文件大小（MB）

    # 画面质量评分 (0-100)
    quality_score = Column(Integer, default=0)
    clarity_score = Column(Integer, default=0)  # 清晰度
    lighting_score = Column(Integer, default=0)  # 光线
    color_score = Column(Integer, default=0)  # 色彩
    composition_score = Column(Integer, default=0)  # 构图

    # 人物分析
    face_visibility = Column(String(50), nullable=True)  # good / moderate / poor / none
    face_score = Column(Integer, default=0)  # 面部质量评分
    eye_contact = Column(String(50), nullable=True)  # strong / moderate / weak / none
    person_count = Column(Integer, default=1)  # 人数
    person_age_range = Column(String(50), nullable=True)  # 年龄段估计
    person_gender = Column(String(20), nullable=True)  # 性别估计

    # 情绪分析
    emotion_primary = Column(String(50), nullable=True)  # 主要情绪
    emotion_secondary = Column(String(50), nullable=True)  # 次要情绪
    emotion_score = Column(Integer, default=0)  # 情绪表现力评分

    # 场景分析
    scene_type = Column(String(50), nullable=True)  # 固定背景/客厅/厨房/户外等
    scene_score = Column(Integer, default=0)  # 场景质量评分
    background_cleanliness = Column(String(50), nullable=True)  # high / medium / low

    # 语音分析
    speech_detected = Column(Boolean, default=False)  # 是否检测到语音
    speech_score = Column(Integer, default=0)  # 语音清晰度评分
    voice_tone = Column(String(50), nullable=True)  # 语调类型 warm / professional / casual
    speech_pace = Column(String(50), nullable=True)  # 语速 slow / normal / fast

    # 整体评分
    overall_score = Column(Integer, default=0)  # 综合评分
    
    # 标签
    style = Column(String(100), nullable=True)  # 整体风格
    topics = Column(JSON, nullable=True)  # 适合主题列表
    tags = Column(JSON, nullable=True)  # AI标签
    
    # 完整分析结果
    analysis_result = Column(JSON, nullable=True)
    
    # 片段信息（自动切片）
    segments = Column(JSON, nullable=True)
    # [
    #   {
    #     "start": 12.5,
    #     "end": 18.3,
    #     "duration": 5.8,
    #     "score": 95,
    #     "emotion": "微笑",
    #     "tags": ["开场", "亲和力"],
    #     "description": "自然微笑讲话"
    #   }
    # ]
    
    # 使用统计
    usage_count = Column(Integer, default=0)  # 被使用次数
    last_used_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<AssetIntelligence(asset_id={self.asset_id}, score={self.overall_score})>"


class AssetAnalysisTask(Base, BaseModel):
    """
    素材分析任务表
    
    记录待分析/正在分析的素材任务队列
    """
    __tablename__ = "asset_analysis_tasks"

    asset_id = Column(Integer, ForeignKey("creator_assets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    status = Column(String(50), default="pending", index=True)
    # pending / processing / completed / failed
    
    priority = Column(Integer, default=0)  # 优先级，数字越大越优先
    
    # 分析类型
    analysis_types = Column(JSON, default=list)  # ["face", "emotion", "scene", "speech"]
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<AssetAnalysisTask(asset_id={self.asset_id}, status={self.status})>"


class AssetSearchIndex(Base, BaseModel):
    """
    素材搜索索引表
    
    为快速搜索建立索引
    """
    __tablename__ = "asset_search_index"

    asset_id = Column(Integer, ForeignKey("creator_assets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 搜索字段
    searchable_text = Column(Text, nullable=True)  # 可搜索文本（拼接所有标签、场景、情绪等）
    
    # 索引字段（用于快速过滤）
    scene_type = Column(String(50), nullable=True, index=True)
    emotion_primary = Column(String(50), nullable=True, index=True)
    emotion_secondary = Column(String(50), nullable=True, index=True)
    style = Column(String(100), nullable=True, index=True)
    topics = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    
    # 分数范围（用于范围查询）
    score_range = Column(String(20), nullable=True, index=True)  # high(80-100) / medium(60-79) / low(<60)
    
    # 更新标记
    is_indexed = Column(Boolean, default=False)
    indexed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<AssetSearchIndex(asset_id={self.asset_id})>"
