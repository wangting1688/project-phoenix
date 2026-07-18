"""
视频生产执行编排层数据模型

TASK-016.3B.0：AI视频生产执行编排层

核心表：
- video_production_jobs: 视频生产任务
- video_timeline: 视频时间线
- video_variants: 视频版本管理
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
    JSON,
    DateTime,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class VideoProductionJob(Base, BaseModel):
    """视频生产任务"""

    __tablename__ = "video_production_jobs"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    video_project_id = Column(Integer, ForeignKey("video_projects.id"), index=True, nullable=True)
    source_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), nullable=True)

    title = Column(String(200), nullable=False)
    job_type = Column(String(50), default="short_video")
    status = Column(String(50), default="pending")

    total_duration = Column(Integer, default=0)
    estimated_duration = Column(Integer, default=0)

    creator_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    target_platforms = Column(JSON, nullable=True)
    variant_count = Column(Integer, default=0)

    business_stage = Column(String(50), default="growth", index=True)
    evaluation_goal = Column(String(50), default="followers")
    # followers - 涨粉
    # engagement - 互动
    # conversion - 成交
    # private_traffic - 私域引流

    timeline_generated = Column(Boolean, default=False)
    material_matched = Column(Boolean, default=False)
    subtitle_ready = Column(Boolean, default=False)
    bgm_ready = Column(Boolean, default=False)
    cover_ready = Column(Boolean, default=False)
    rendering_done = Column(Boolean, default=False)

    blocked_reasons = Column(JSON, nullable=True)
    progress = Column(Integer, default=0)

    timeline = relationship("VideoTimeline", back_populates="job", cascade="all, delete-orphan")
    variants = relationship("VideoVariant", back_populates="job", cascade="all, delete-orphan")


class VideoTimeline(Base, BaseModel):
    """视频时间线 - 最核心的表"""

    __tablename__ = "video_timeline"

    production_job_id = Column(
        Integer,
        ForeignKey("video_production_jobs.id"),
        index=True,
        nullable=False,
    )
    job = relationship("VideoProductionJob", back_populates="timeline")

    sequence = Column(Integer, nullable=False, default=0)

    start_time = Column(Float, nullable=False, default=0.0)
    end_time = Column(Float, nullable=False, default=0.0)

    layer = Column(String(50), default="main")

    content_type = Column(String(50), nullable=False)
    source_type = Column(String(50), nullable=True)
    source_id = Column(Integer, nullable=True)

    role = Column(String(50), nullable=True)
    segment_type = Column(String(50), nullable=True)

    effect_config = Column(JSON, nullable=True)
    transition_config = Column(JSON, nullable=True)

    audio_config = Column(JSON, nullable=True)
    subtitle_config = Column(JSON, nullable=True)

    status = Column(String(50), default="pending")
    material_found = Column(Boolean, default=False)
    material_duration = Column(Float, default=0.0)
    material_gap = Column(Float, default=0.0)

    original_segment_id = Column(Integer, ForeignKey("video_edit_segments.id"), nullable=True)


class VideoVariant(Base, BaseModel):
    """视频版本管理"""

    __tablename__ = "video_variants"

    production_job_id = Column(
        Integer,
        ForeignKey("video_production_jobs.id"),
        index=True,
        nullable=False,
    )
    job = relationship("VideoProductionJob", back_populates="variants")

    platform = Column(String(50), nullable=False)
    strategy = Column(String(50), nullable=True)

    target_duration = Column(Integer, default=0)
    actual_duration = Column(Integer, default=0)

    variant_config = Column(JSON, nullable=True)

    status = Column(String(50), default="pending")

    output_video_path = Column(String(500), nullable=True)
    output_video_url = Column(String(500), nullable=True)

    director_score = Column(Integer, default=0)
    predicted_play = Column(Integer, default=0)
    predicted_conversion = Column(Float, default=0.0)

    subtitle_file_path = Column(String(500), nullable=True)
    cover_file_path = Column(String(500), nullable=True)
    bgm_file_path = Column(String(500), nullable=True)


class VideoProductionStep(Base, BaseModel):
    """视频生产步骤 - 支持失败重试"""

    __tablename__ = "video_production_steps"

    job_id = Column(
        Integer,
        ForeignKey("video_production_jobs.id"),
        index=True,
        nullable=False,
    )
    job = relationship("VideoProductionJob", backref="steps")

    sequence = Column(Integer, nullable=False, default=0)

    step_type = Column(String(50), nullable=False)

    status = Column(String(50), default="pending")

    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    tool_name = Column(String(100), nullable=True)
    tool_params = Column(JSON, nullable=True)

    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float, default=0.0)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class GrowthReviewReport(Base, BaseModel):
    """增长复盘报告 - Growth Quality Agent对导演方案的反馈"""

    __tablename__ = "growth_review_reports"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    video_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), index=True, nullable=False)
    production_job_id = Column(Integer, ForeignKey("video_production_jobs.id"), nullable=True)

    stage = Column(String(50), default="growth")

    overall_score = Column(Integer, default=0)
    passed = Column(Boolean, default=False)

    hook_score = Column(Integer, default=0)
    retention_score = Column(Integer, default=0)
    emotion_score = Column(Integer, default=0)
    follow_reason_score = Column(Integer, default=0)
    platform_fit_score = Column(Integer, default=0)
    creator_fit_score = Column(Integer, default=0)
    commercial_pressure_index = Column(Integer, default=0)

    organic_growth_score = Column(Integer, default=0)

    problems = Column(JSON, nullable=True)
    director_actions = Column(JSON, nullable=True)
    suggestions = Column(JSON, nullable=True)

    review_count = Column(Integer, default=1)
    previous_report_id = Column(Integer, ForeignKey("growth_review_reports.id"), nullable=True)

    version_type = Column(String(50), default="standard")

    evaluation_goal = Column(String(50), default="followers")


class VideoVersion(Base, BaseModel):
    """视频版本 - 支持涨粉版/私域版/成交版"""

    __tablename__ = "video_versions"

    production_job_id = Column(Integer, ForeignKey("video_production_jobs.id"), index=True, nullable=False)
    job = relationship("VideoProductionJob", backref="versions")

    version_type = Column(String(50), nullable=False)
    version_name = Column(String(200), nullable=True)

    commercial_pressure_index = Column(Integer, default=0)
    commercial_strategy = Column(String(200), nullable=True)

    timeline_override = Column(JSON, nullable=True)
    config_override = Column(JSON, nullable=True)

    output_path = Column(String(500), nullable=True)
    output_url = Column(String(500), nullable=True)

    status = Column(String(50), default="pending")

    growth_score = Column(Integer, default=0)
    predicted_play = Column(Integer, default=0)
    predicted_conversion = Column(Float, default=0.0)


class OrganicGrowthInsight(Base, BaseModel):
    """自然增长洞察 - 记录"为什么这个视频涨了/没涨"的结构化记忆"""

    __tablename__ = "organic_growth_insights"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    video_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), index=True, nullable=True)
    publish_record_id = Column(Integer, ForeignKey("video_publish_records.id"), nullable=True)

    insight_type = Column(String(50), nullable=False)

    platform = Column(String(50), nullable=False, index=True)
    product_category = Column(String(100), nullable=True, index=True)
    creator_id = Column(Integer, nullable=True, index=True)

    conditions = Column(JSON, nullable=True)

    observation = Column(JSON, nullable=True)
    conclusion = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.5)

    actual_play = Column(Integer, default=0)
    actual_growth_rate = Column(Float, default=0.0)
    actual_follow_rate = Column(Float, default=0.0)

    related_creators = Column(JSON, nullable=True)
    related_platforms = Column(JSON, nullable=True)
    related_products = Column(JSON, nullable=True)

    usage_count = Column(Integer, default=0)


class ProductionBlockTask(Base, BaseModel):
    """生产阻塞任务 - 素材不足时自动创建"""

    __tablename__ = "production_block_tasks"

    production_job_id = Column(
        Integer,
        ForeignKey("video_production_jobs.id"),
        index=True,
        nullable=False,
    )
    timeline_id = Column(
        Integer,
        ForeignKey("video_timeline.id"),
        nullable=True,
    )

    block_type = Column(String(50), nullable=False)
    priority = Column(String(20), default="medium")
    status = Column(String(50), default="pending")

    required_content_type = Column(String(50), nullable=True)
    required_duration = Column(Float, default=0.0)
    available_duration = Column(Float, default=0.0)
    gap_duration = Column(Float, default=0.0)

    target_role = Column(String(50), nullable=True)
    target_emotion = Column(String(50), nullable=True)
    target_creator_id = Column(Integer, nullable=True)

    reason = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)

    collection_task_id = Column(Integer, nullable=True)


class GrowthDecisionMemory(Base, BaseModel):
    """增长决策知识图谱 - 记录什么条件下什么决策有效"""

    __tablename__ = "growth_decision_memory"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    content_type = Column(String(50), nullable=True, index=True)
    opening_pattern = Column(String(100), nullable=True, index=True)
    structure_type = Column(String(50), nullable=True, index=True)

    creator_profile = Column(JSON, nullable=True)
    creator_id = Column(Integer, nullable=True, index=True)

    platform = Column(String(50), nullable=True, index=True)
    product_category = Column(String(100), nullable=True, index=True)
    topic = Column(String(200), nullable=True, index=True)

    commercial_stage = Column(String(50), nullable=True, index=True)
    business_stage = Column(String(50), nullable=True, index=True)

    conditions = Column(JSON, nullable=True)
    decisions = Column(JSON, nullable=True)

    result = Column(JSON, nullable=True)
    actual_views = Column(Integer, default=0)
    actual_followers = Column(Integer, default=0)
    actual_engagement_rate = Column(Float, default=0.0)
    actual_conversion_rate = Column(Float, default=0.0)

    confidence_score = Column(Float, default=0.5)
    success_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)

    source_video_id = Column(Integer, nullable=True)
    source_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), nullable=True)


class GrowthFailureMemory(Base, BaseModel):
    """失败经验库 - 记录什么条件下什么决策失败"""

    __tablename__ = "growth_failure_memory"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    failure_type = Column(String(50), nullable=False, index=True)
    failure_pattern = Column(String(500), nullable=True, index=True)

    platform = Column(String(50), nullable=True, index=True)
    product_category = Column(String(100), nullable=True, index=True)
    creator_type = Column(String(100), nullable=True, index=True)
    creator_id = Column(Integer, nullable=True, index=True)

    business_stage = Column(String(50), nullable=True, index=True)
    evaluation_goal = Column(String(50), nullable=True, index=True)

    conditions = Column(JSON, nullable=True)

    result = Column(JSON, nullable=True)
    avg_retention = Column(Float, default=0.0)
    avg_views = Column(Integer, default=0)

    lesson = Column(Text, nullable=True)
    avoid_actions = Column(JSON, nullable=True)
    recommended_actions = Column(JSON, nullable=True)

    confidence_score = Column(Float, default=0.5)
    occurrence_count = Column(Integer, default=0)

    source_video_id = Column(Integer, nullable=True)
    source_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), nullable=True)


class GrowthAttributionRecord(Base, BaseModel):
    """增长归因记录 - 记录成功/失败的因素及贡献度"""

    __tablename__ = "growth_attribution_records"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    video_id = Column(Integer, nullable=True, index=True)
    video_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), nullable=True)
    publish_record_id = Column(Integer, ForeignKey("video_publish_records.id"), nullable=True)

    platform = Column(String(50), nullable=True, index=True)

    success_factors = Column(JSON, nullable=True)

    failure_factors = Column(JSON, nullable=True)

    overall_outcome = Column(String(50), nullable=True)

    total_contribution = Column(Float, default=0.0)

    confidence_score = Column(Float, default=0.5)


class GrowthExperimentMemory(Base, BaseModel):
    """实验记忆 - 记录A/B测试结果"""

    __tablename__ = "growth_experiment_memories"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    experiment_type = Column(String(100), nullable=False, index=True)

    variable = Column(String(200), nullable=False)

    variant_a = Column(JSON, nullable=True)
    variant_b = Column(JSON, nullable=True)

    winner = Column(String(10), nullable=True)
    winner_confidence = Column(Float, default=0.0)

    metrics = Column(JSON, nullable=True)

    sample_size = Column(Integer, default=0)
    significance_level = Column(Float, default=0.05)

    related_creator_id = Column(Integer, nullable=True)
    related_platform = Column(String(50), nullable=True, index=True)
    related_product_category = Column(String(100), nullable=True, index=True)

    status = Column(String(50), default="draft")
    # draft / running / collecting / completed / learned

    hypothesis = Column(Text, nullable=True)

    usage_count = Column(Integer, default=0)


class AudienceGrowthMemory(Base, BaseModel):
    """用户认知记忆 - 记录用户群体的偏好和特征"""

    __tablename__ = "audience_growth_memories"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    audience_segment = Column(String(100), nullable=False, index=True)

    demographic = Column(JSON, nullable=True)

    pain_points = Column(JSON, nullable=True)

    content_preferences = Column(JSON, nullable=True)

    high_frequency_comments = Column(JSON, nullable=True)

    engagement_patterns = Column(JSON, nullable=True)

    conversion_patterns = Column(JSON, nullable=True)

    confidence_score = Column(Float, default=0.5)

    sample_size = Column(Integer, default=0)

    related_platforms = Column(JSON, nullable=True)


class GrowthKnowledgeEdge(Base, BaseModel):
    """增长知识边 - 连接所有增长节点的因果关系"""

    __tablename__ = "growth_knowledge_edges"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(Integer, nullable=True)
    source_value = Column(String(200), nullable=True, index=True)

    relation_type = Column(String(50), nullable=False, index=True)

    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(Integer, nullable=True)
    target_value = Column(String(200), nullable=True, index=True)

    impact_score = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.5)

    calibrated_confidence = Column(Float, default=0.5)

    previous_confidence = Column(Float, default=0.5)
    confidence_delta = Column(Float, default=0.0)

    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    prediction_count = Column(Integer, default=0)
    prediction_success_count = Column(Integer, default=0)

    source_memory_type = Column(String(50), nullable=True)

    conditions = Column(JSON, nullable=True)

    context_condition = Column(JSON, nullable=True)

    usage_count = Column(Integer, default=0)
    verified_count = Column(Integer, default=0)

    last_verified_at = Column(DateTime, nullable=True)

    status = Column(String(20), default="candidate", index=True)
    # candidate / observing / validated / trusted / core_rule / deprecated / archived
    decay_rate = Column(Float, default=0.01)

    evidence_level = Column(String(5), default="D", index=True)
    # A: 大量数据+实验 / B: 大量案例 / C: 初步发现 / D: 猜测


class AudienceBeliefMemory(Base, BaseModel):
    """用户信念记忆 - 记录用户认知变化"""

    __tablename__ = "audience_belief_memories"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    audience_segment = Column(String(100), nullable=False, index=True)

    old_belief = Column(Text, nullable=False)
    new_belief = Column(Text, nullable=False)

    trigger_content = Column(String(500), nullable=True)
    trigger_type = Column(String(50), nullable=True)

    evidence = Column(JSON, nullable=True)

    confidence = Column(Float, default=0.5)

    sample_size = Column(Integer, default=0)

    related_platform = Column(String(50), nullable=True)
    related_product_category = Column(String(100), nullable=True)


class GrowthHypothesis(Base, BaseModel):
    """增长假设 - AI主动提出的实验假设"""

    __tablename__ = "growth_hypotheses"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    hypothesis = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    condition_type = Column(String(50), nullable=True, index=True)
    condition_value = Column(String(200), nullable=True, index=True)

    predicted_effect = Column(String(200), nullable=True)
    predicted_impact = Column(Float, default=0.0)

    evidence_count = Column(Integer, default=0)
    source_data = Column(JSON, nullable=True)

    status = Column(String(20), default="proposed", index=True)
    # proposed / accepted / experiment_created / validated / rejected

    experiment_id = Column(Integer, nullable=True)

    priority_score = Column(Float, default=0.0)

    created_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)


class AudienceBeliefNode(Base, BaseModel):
    """用户信念节点 - 信念图中的节点"""

    __tablename__ = "audience_belief_nodes"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    audience_segment = Column(String(100), nullable=False, index=True)
    belief_content = Column(Text, nullable=False)

    belief_category = Column(String(50), nullable=True, index=True)
    # awareness / interest / consideration / purchase / loyalty

    confidence = Column(Float, default=0.5)
    sample_size = Column(Integer, default=0)

    related_platform = Column(String(50), nullable=True)
    related_product_category = Column(String(100), nullable=True)


class AudienceBeliefEdge(Base, BaseModel):
    """用户信念边 - 信念节点之间的转换关系"""

    __tablename__ = "audience_belief_edges"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    from_node_id = Column(Integer, ForeignKey("audience_belief_nodes.id"), nullable=False, index=True)
    to_node_id = Column(Integer, ForeignKey("audience_belief_nodes.id"), nullable=False, index=True)

    trigger_type = Column(String(50), nullable=True)
    trigger_pattern = Column(String(200), nullable=True)

    conversion_rate = Column(Float, default=0.0)
    confidence = Column(Float, default=0.5)

    sample_size = Column(Integer, default=0)

    related_platform = Column(String(50), nullable=True)
    related_product_category = Column(String(100), nullable=True)


class GrowthPredictionError(Base, BaseModel):
    """预测误差记忆 - 记录AI预测与实际结果的差异"""

    __tablename__ = "growth_prediction_errors"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    prediction_type = Column(String(50), nullable=False, index=True)
    # completion_rate / engagement_rate / follower_gain / conversion

    predicted_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=False)

    error_rate = Column(Float, default=0.0)
    error_direction = Column(String(20), nullable=True)
    # over_estimate / under_estimate

    strategy_used = Column(String(100), nullable=True)

    causal_edges_used = Column(JSON, nullable=True)

    context_conditions = Column(JSON, nullable=True)

    root_cause_analysis = Column(Text, nullable=True)

    correction_suggestion = Column(Text, nullable=True)

    related_video_id = Column(Integer, nullable=True)
    related_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), nullable=True)

    reflection_status = Column(String(20), default="pending", index=True)
    # pending / analyzed / corrected

    analyzed_at = Column(DateTime, nullable=True)


class StrategyCalibrationRecord(Base, BaseModel):
    """策略置信度校准记录 - 记录AI预测准确率"""

    __tablename__ = "strategy_calibration_records"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    strategy_type = Column(String(100), nullable=False, index=True)

    original_confidence = Column(Float, nullable=False)
    calibrated_confidence = Column(Float, default=0.5)

    prediction_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)

    calibration_date = Column(DateTime, nullable=True)

    platform = Column(String(50), nullable=True, index=True)
    product_category = Column(String(100), nullable=True, index=True)

    context_conditions = Column(JSON, nullable=True)


class DirectorMistakeMemory(Base, BaseModel):
    """导演错误记忆 - 记录AI导演判断失误案例"""

    __tablename__ = "director_mistake_memories"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    mistake_type = Column(String(100), nullable=False, index=True)

    recommendation = Column(Text, nullable=False)

    expected_outcome = Column(Text, nullable=True)
    actual_outcome = Column(Text, nullable=True)

    mistake_reason = Column(Text, nullable=True)

    missing_context = Column(JSON, nullable=True)

    correct_strategy = Column(Text, nullable=True)

    learning = Column(Text, nullable=True)

    related_video_id = Column(Integer, nullable=True)
    related_plan_id = Column(Integer, ForeignKey("video_edit_plans.id"), nullable=True)

    occurrence_count = Column(Integer, default=1)

    verified = Column(Boolean, default=False)


class GrowthEvidenceScore(Base, BaseModel):
    """因果证据评分 - 拆解置信度来源"""

    __tablename__ = "growth_evidence_scores"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    edge_id = Column(Integer, ForeignKey("growth_knowledge_edges.id"), nullable=False, index=True)

    sample_size = Column(Integer, default=0)
    experiment_count = Column(Integer, default=0)
    platform_count = Column(Integer, default=0)
    creator_count = Column(Integer, default=0)

    time_span_days = Column(Integer, default=0)

    prediction_accuracy = Column(Float, default=0.5)
    sample_diversity = Column(Float, default=0.0)
    experiment_validation = Column(Float, default=0.0)
    context_stability = Column(Float, default=0.0)

    final_confidence = Column(Float, default=0.0)

    evidence_level = Column(String(5), default="D", index=True)
    # A: 大量数据+实验 / B: 大量案例 / C: 初步发现 / D: 猜测


class GrowthKnowledgeConflict(Base, BaseModel):
    """知识冲突记录"""

    __tablename__ = "growth_knowledge_conflicts"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    edge_a_id = Column(Integer, ForeignKey("growth_knowledge_edges.id"), nullable=False)
    edge_b_id = Column(Integer, ForeignKey("growth_knowledge_edges.id"), nullable=False)

    conflict_type = Column(String(50), nullable=True, index=True)
    # opposite_effect / contradictory / context_dependent

    resolution_status = Column(String(20), default="detected", index=True)
    # detected / analyzing / resolved / needs_review

    resolution = Column(Text, nullable=True)
    # depends_on_creator / depends_on_platform / merged / one_deprecated

    resolved_by = Column(String(20), nullable=True)
    # system / human

    resolved_at = Column(DateTime, nullable=True)

    context_a = Column(JSON, nullable=True)
    context_b = Column(JSON, nullable=True)
