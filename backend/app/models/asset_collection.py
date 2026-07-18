"""
素材采集相关模型

用于主播素材采集中心：
- 告诉主播应该拍什么素材
- 追踪素材采集进度
- 管理素材库
"""

from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Float, Date
from app.core.database import Base
from app.core.base_model import BaseModel


class AssetCollectionTask(Base, BaseModel):
    """
    素材采集任务表 - 系统推荐的素材采集计划
    
    每天/每周生成采集建议，告诉主播应该拍什么
    """
    __tablename__ = "asset_collection_tasks"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 任务信息
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # 优先级
    priority = Column(String(20), default="high")  # high / medium / low

    # 素材类型
    asset_type = Column(String(50), nullable=False)  # video / image / audio
    asset_role = Column(String(50), default="creator")  # creator / b_roll / background

    # 拍摄指导
    shooting_guide = Column(JSON, nullable=True)
    # {
    #   "scene": "客厅",
    #   "action": "正面讲话",
    #   "emotion": "自然微笑",
    #   "duration_min": 20,
    #   "duration_max": 60,
    #   "tips": ["坐姿端正", "光线充足", "背景干净"]
    # }

    # 标签（用于后续匹配）
    tags = Column(JSON, nullable=True)
    scene = Column(String(100), nullable=True)
    emotion = Column(String(50), nullable=True)

    # 进度
    status = Column(String(50), default="pending", index=True)
    # pending / in_progress / completed / skipped
    progress = Column(Integer, default=0)  # 0-100
    uploaded_asset_id = Column(Integer, ForeignKey("creator_assets.id"), nullable=True)

    # 时间
    due_date = Column(Date, nullable=True)  # 截止日期
    estimated_time = Column(Integer, default=5)  # 预计用时（分钟）

    # 统计
    usage_count = Column(Integer, default=0)  # 已被使用次数

    def __repr__(self):
        return f"<AssetCollectionTask(title={self.title}, priority={self.priority})>"


class AssetCollectionPlan(Base, BaseModel):
    """
    素材采集计划表 - 每日/每周采集计划
    
    聚合多个采集任务，形成整体计划
    """
    __tablename__ = "asset_collection_plans"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 计划信息
    title = Column(String(200), nullable=False)
    plan_type = Column(String(50), default="daily")  # daily / weekly / custom
    plan_date = Column(Date, index=True)

    # 统计
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    total_estimated_time = Column(Integer, default=0)  # 总预计时间（分钟）

    # 状态
    status = Column(String(50), default="active")  # active / completed / archived

    def __repr__(self):
        return f"<AssetCollectionPlan(title={self.title}, date={self.plan_date})>"


class AssetCategory(Base, BaseModel):
    """
    素材分类表 - 素材类型体系
    
    建立素材分类标准，用于智能推荐
    """
    __tablename__ = "asset_categories"

    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, nullable=True)
    category_type = Column(String(50), default="creator")  # creator / b_roll / background

    # 分类说明
    description = Column(Text, nullable=True)

    # 拍摄建议
    shooting_tips = Column(JSON, nullable=True)
    recommended_duration = Column(Integer, default=30)  # 建议时长（秒）

    # 优先级
    sort_order = Column(Integer, default=0)
    is_required = Column(Integer, default=0)  # 是否必须素材

    def __repr__(self):
        return f"<AssetCategory(name={self.name})>"


class DailyAssetRecommendation(Base, BaseModel):
    """
    每日素材推荐表 - 系统每日推荐的素材采集清单
    
    基于主播当前缺什么、需要什么，生成每日推荐
    """
    __tablename__ = "daily_asset_recommendations"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    recommend_date = Column(Date, index=True)

    # 推荐内容
    recommendations = Column(JSON, nullable=True)
    # [
    #   {
    #     "rank": 1,
    #     "title": "正面讲话 30秒",
    #     "priority": "high",
    #     "reason": "最基础的口播素材，使用率最高",
    #     "estimated_time": "5分钟",
    #     "tags": ["正面", "讲话", "自然"]
    #   },
    #   ...
    # ]

    # 统计
    total_recommended = Column(Integer, default=0)
    high_priority_count = Column(Integer, default=0)
    total_estimated_time = Column(Integer, default=0)

    def __repr__(self):
        return f"<DailyAssetRecommendation(user_id={self.user_id}, date={self.recommend_date})>"