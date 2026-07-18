"""
视频效果与导演学习模型

TASK-016.3A.8：AI导演学习记忆层 V2

核心表：
1. video_master_content - 视频本体（内容层）
2. video_publish_records - 平台发布记录（平台层）
3. platform_performance_scores - 平台效果评分
4. director_learning_memory - AI导演经验库
5. platform_strategy_profiles - 平台策略画像
6. creator_strategy_profile - 主播策略画像
"""

from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Float, DateTime, Boolean
from app.core.database import Base
from app.core.base_model import BaseModel


class VideoMasterContent(Base, BaseModel):
    """
    视频本体表 - 内容层

    代表"这个视频内容本身"，不依赖平台
    一个视频内容可以发布到多个平台
    """
    __tablename__ = "video_master_content"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    video_project_id = Column(Integer, ForeignKey("video_projects.id"), index=True, nullable=True)
    edit_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), nullable=True)

    # 内容信息
    title = Column(String(200), nullable=False)
    content_summary = Column(Text, nullable=True)
    script_content = Column(Text, nullable=True)

    # 内容特征
    template_type = Column(String(50), nullable=True)  # pain_point/story/expert/product/knowledge/emotion
    product_category = Column(String(100), nullable=True)
    content_type = Column(String(50), nullable=True)
    duration = Column(Integer, default=0)

    # 导演信息
    director_score = Column(Integer, default=0)  # 导演评分
    predicted_completion_rate = Column(Float, default=0.0)
    predicted_conversion_rate = Column(Float, default=0.0)

    # 实际效果汇总（跨平台加权）
    actual_performance = Column(JSON, nullable=True)
    # {
    #   "total_views": 100000,
    #   "weighted_score": 85,
    #   "best_platform": {"traffic": "douyin", "conversion": "wechat_video"},
    # }

    # 状态
    status = Column(String(50), default="draft")  # draft/editing/published/archived

    def __repr__(self):
        return f"<VideoMasterContent(title={self.title}, status={self.status})>"


class VideoPublishRecord(Base, BaseModel):
    """
    平台发布记录表 - 平台层

    一个视频内容在不同平台的发布记录和效果数据
    """
    __tablename__ = "video_publish_records"

    video_id = Column(Integer, ForeignKey("video_master_content.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 平台信息
    platform = Column(String(50), nullable=False, index=True)
    # douyin / wechat_video / xiaohongshu / kuaishou / bilibili

    publish_url = Column(String(500), nullable=True)
    publish_status = Column(String(50), default="draft")
    # draft / published / failed / removed

    publish_time = Column(DateTime, nullable=True)

    # 流量数据
    views = Column(Integer, default=0)
    exposures = Column(Integer, default=0)  # 曝光量
    reach = Column(Integer, default=0)  # 触达人数

    # 互动数据
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    favorites = Column(Integer, default=0)
    follows = Column(Integer, default=0)  # 涨粉数

    # 用户行为
    completion_rate = Column(Float, default=0.0)  # 完播率
    avg_watch_time = Column(Float, default=0.0)  # 平均观看时长（秒）
    first_3_second_retention = Column(Float, default=0.0)  # 3秒留存率
    first_5_second_retention = Column(Float, default=0.0)  # 5秒留存率

    # 转化数据（商业）
    profile_visits = Column(Integer, default=0)  # 主页访问
    private_message_count = Column(Integer, default=0)  # 私信数
    consultation_count = Column(Integer, default=0)  # 有效咨询数
    order_count = Column(Integer, default=0)  # 订单数
    gmv = Column(Float, default=0.0)  # 成交金额
    conversion_rate = Column(Float, default=0.0)  # 转化率

    # 数据更新时间
    data_updated_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<VideoPublishRecord(video_id={self.video_id}, platform={self.platform}, views={self.views})>"


class PlatformPerformanceScore(Base, BaseModel):
    """
    平台效果评分表

    针对每个平台的效果评分，不同平台有不同的评价维度和权重
    """
    __tablename__ = "platform_performance_scores"

    publish_record_id = Column(Integer, ForeignKey("video_publish_records.id"), index=True, nullable=False)
    video_id = Column(Integer, ForeignKey("video_master_content.id"), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    platform = Column(String(50), nullable=False, index=True)

    # 综合评分
    overall_score = Column(Integer, default=0)  # 0-100

    # 分维度评分
    traffic_score = Column(Integer, default=0)  # 流量表现
    engagement_score = Column(Integer, default=0)  # 互动表现
    conversion_score = Column(Integer, default=0)  # 转化表现
    customer_value_score = Column(Integer, default=0)  # 客户价值

    # 评分详情
    score_breakdown = Column(JSON, nullable=True)
    # {
    #   "traffic": {"score": 85, "weight": 0.4, "metrics": {...}},
    #   "engagement": {"score": 70, "weight": 0.3, "metrics": {...}},
    #   "conversion": {"score": 95, "weight": 0.2, "metrics": {...}},
    #   "customer_value": {"score": 80, "weight": 0.1, "metrics": {...}},
    # }

    # 各平台特性评分
    platform_specific = Column(JSON, nullable=True)
    # 抖音: {douyin_fans_growth: 80, douyin_hot_potential: 75}
    # 视频号: {wechat_share_rate: 85, wechat_private_conversion: 90}
    # 小红书: {xiaohongshu_collection: 88, xiaohongshu_search_value: 92}

    def __repr__(self):
        return f"<PlatformPerformanceScore(platform={self.platform}, score={self.overall_score})>"


class DirectorLearningMemory(Base, BaseModel):
    """
    AI导演经验库

    系统从历史数据中学习到的规律和经验
    这是AI导演的"记忆"，会不断积累和进化
    """
    __tablename__ = "director_learning_memory"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)  # 全局经验为null

    # 经验类型
    memory_type = Column(String(50), nullable=False, index=True)
    # template_success - 模板成功经验
    # segment_success - 素材片段成功经验
    # creator_success - 主播成功经验
    # product_success - 产品成功经验
    # platform_success - 平台成功经验
    # hook_success - 开场成功经验
    # strategy_pattern - 策略模式

    # 条件（在什么情况下）
    condition = Column(JSON, nullable=False)
    # {
    #   "creator_age": "40-50",
    #   "creator_gender": "female",
    #   "product_category": "health",
    #   "platform": "douyin",
    #   ...
    # }

    # 结论（应该怎么做）
    recommendation = Column(JSON, nullable=False)
    # {
    #   "template_type": "pain_point",
    #   "hook_style": "question",
    #   "best_duration": "35-45秒",
    #   "expected_improvement": {"completion_rate": 0.15, "conversion_rate": 0.22}
    # }

    # 置信度
    confidence_score = Column(Float, default=0.0)  # 0-1

    # 使用次数（验证次数）
    usage_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)

    # 来源数据
    source_video_ids = Column(JSON, nullable=True)  # 来源视频ID列表
    source_data_points = Column(Integer, default=0)  # 数据样本数

    # 状态
    is_verified = Column(Boolean, default=False)  # 是否经过验证
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<DirectorLearningMemory(type={self.memory_type}, confidence={self.confidence_score})>"


class PlatformStrategyProfile(Base, BaseModel):
    """
    平台策略画像表

    记录每个平台的内容策略和表现特征
    """
    __tablename__ = "platform_strategy_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    platform = Column(String(50), nullable=False, index=True)

    # 平台定位
    platform_role = Column(String(50), default="balanced")
    # traffic - 流量增长主阵地
    # conversion - 转化成交主阵地
    # content - 内容资产沉淀
    # community - 粉丝社群运营
    # balanced - 均衡发展

    # 最佳内容类型
    best_content_types = Column(JSON, nullable=True)
    # ["pain_point", "story"]

    # 最佳时长
    best_duration_range = Column(String(50), nullable=True)  # "30-45秒"

    # 最佳发布时间
    best_publish_times = Column(JSON, nullable=True)
    # ["07:00", "12:00", "20:00"]

    # 平台表现统计
    avg_views = Column(Integer, default=0)
    avg_completion_rate = Column(Float, default=0.0)
    avg_conversion_rate = Column(Float, default=0.0)
    total_published = Column(Integer, default=0)

    # 平台评分权重（此平台看重什么）
    weight_config = Column(JSON, nullable=True)
    # {
    #   "traffic": 0.4,
    #   "engagement": 0.3,
    #   "conversion": 0.2,
    #   "customer_value": 0.1
    # }

    def __repr__(self):
        return f"<PlatformStrategyProfile(user_id={self.user_id}, platform={self.platform})>"


class CreatorStrategyProfile(Base, BaseModel):
    """
    主播策略画像表

    记录主播的打法特征和最适合的策略
    """
    __tablename__ = "creator_strategy_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False, unique=True)

    # 最佳内容打法
    best_content_type = Column(String(50), nullable=True)  # pain_point/story/expert/product/knowledge/emotion
    best_content_types = Column(JSON, nullable=True)  # 多种类型排名

    # 最佳开场方式
    best_hook_style = Column(String(50), nullable=True)
    # question - 问题型
    # data - 数据型
    # story - 故事型
    # contrast - 反差型
    # warning - 警告型

    # 最佳镜头形式
    best_camera_style = Column(String(50), nullable=True)
    # front_face - 正脸讲话
    # side_face - 侧脸
    # scene - 场景展示
    # product_show - 产品展示

    # 最佳时长
    best_duration_range = Column(String(50), nullable=True)  # "35-45秒"

    # 成交方式
    best_conversion_style = Column(String(50), nullable=True)
    # trust_case - 信任+案例
    # direct_product - 直接产品
    # emotion_story - 情感故事
    # expert_knowledge - 专业知识

    # 不适合的方式
    weak_styles = Column(JSON, nullable=True)
    # ["hard_sell", "overly_formal"]

    # 各平台表现
    platform_performance = Column(JSON, nullable=True)
    # {
    #   "douyin": {"avg_views": 50000, "best_template": "pain_point"},
    #   "wechat_video": {"avg_conversion": 0.05, "best_template": "story"},
    # }

    # 整体策略建议
    strategy_recommendation = Column(Text, nullable=True)

    # 数据样本
    analyzed_videos = Column(Integer, default=0)
    last_updated = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<CreatorStrategyProfile(user_id={self.user_id}, best_content={self.best_content_type})>"
