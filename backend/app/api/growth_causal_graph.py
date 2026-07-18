"""
Growth Causal Graph API - 增长因果图接口

TASK-016.3B.5.4：增长因果图层
TASK-016.3B.5.5：增长大脑自动学习层
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.growth_causal_graph_service import GrowthCausalGraphService
from app.services.growth_hypothesis_engine import GrowthHypothesisEngine

router = APIRouter(prefix="/growth-causal", tags=["增长因果图"])


# ==================== 知识边管理 ====================

@router.post("/edges")
async def add_knowledge_edge(
    source_type: str,
    source_value: str,
    relation_type: str,
    target_type: str,
    target_value: str,
    impact_score: float = 0.0,
    confidence: float = 0.5,
    conditions: Optional[Dict[str, Any]] = None,
    source_memory_type: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """添加知识边"""
    service = GrowthCausalGraphService()
    try:
        result = service.add_knowledge_edge(
            source_type, source_value, relation_type,
            target_type, target_value, impact_score,
            confidence, conditions, source_memory_type,
        )
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.get("/edges")
async def query_causal_path(
    source_type: str,
    source_value: str,
    target_type: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """查询因果路径"""
    service = GrowthCausalGraphService()
    try:
        edges = service.query_causal_path(source_type, source_value, target_type)
        return {"success": True, "data": edges}
    finally:
        service.close()


# ==================== 从记忆学习 ====================

@router.post("/learn/experiment/{experiment_id}")
async def learn_from_experiment(experiment_id: int, current_user = Depends(get_current_user)):
    """从实验中学习因果关系"""
    service = GrowthCausalGraphService()
    try:
        result = service.learn_from_experiment(experiment_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.post("/learn/attribution/{attribution_id}")
async def learn_from_attribution(attribution_id: int, current_user = Depends(get_current_user)):
    """从归因中学习因果关系"""
    service = GrowthCausalGraphService()
    try:
        result = service.learn_from_attribution(attribution_id)
        return result
    finally:
        service.close()


@router.post("/learn/decision/{decision_id}")
async def learn_from_decision(decision_id: int, current_user = Depends(get_current_user)):
    """从决策记忆中学习"""
    service = GrowthCausalGraphService()
    try:
        result = service.learn_from_decision_memory(decision_id)
        return result
    finally:
        service.close()


@router.post("/learn/failure/{failure_id}")
async def learn_from_failure(failure_id: int, current_user = Depends(get_current_user)):
    """从失败记忆中学习"""
    service = GrowthCausalGraphService()
    try:
        result = service.learn_from_failure_memory(failure_id)
        return result
    finally:
        service.close()


# ==================== 策略推荐 ====================

@router.post("/recommend")
async def recommend_strategy(
    platform: str = "wechat_video",
    product_category: str = "health",
    business_stage: str = "growth",
    creator_profile: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """基于因果图推荐策略"""
    service = GrowthCausalGraphService()
    try:
        conditions = {
            "platform": platform,
            "product_category": product_category,
            "business_stage": business_stage,
            "creator_profile": creator_profile,
        }
        recommendations = service.recommend_strategy(conditions)
        conflicts = service.find_conflicts(conditions)

        return {
            "success": True,
            "recommendations": recommendations,
            "conflicts": conflicts,
            "conditions": conditions,
        }
    finally:
        service.close()


# ==================== 冲突检测 ====================

@router.post("/conflicts")
async def find_conflicts(
    platform: Optional[str] = None,
    business_stage: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """查找冲突关系"""
    service = GrowthCausalGraphService()
    try:
        conditions = {
            "platform": platform,
            "business_stage": business_stage,
        }
        conflicts = service.find_conflicts(conditions)
        return {"success": True, "conflicts": conflicts}
    finally:
        service.close()


# ==================== 用户信念记忆 ====================

@router.post("/belief")
async def create_belief_memory(
    audience_segment: str,
    old_belief: str,
    new_belief: str,
    trigger_content: Optional[str] = None,
    trigger_type: Optional[str] = None,
    confidence: float = 0.5,
    platform: Optional[str] = None,
    product_category: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """创建用户信念记忆"""
    from app.core.database import SessionLocal
    from app.models.video_production import AudienceBeliefMemory

    db = SessionLocal()
    try:
        belief = AudienceBeliefMemory(
            user_id=current_user.id,
            audience_segment=audience_segment,
            old_belief=old_belief,
            new_belief=new_belief,
            trigger_content=trigger_content,
            trigger_type=trigger_type,
            confidence=confidence,
            related_platform=platform,
            related_product_category=product_category,
        )
        db.add(belief)
        db.commit()
        db.refresh(belief)

        service = GrowthCausalGraphService()
        try:
            service.add_knowledge_edge(
                source_type="trigger_type",
                source_value=trigger_type or trigger_content[:50],
                relation_type="improves",
                target_type="audience_belief",
                target_value=audience_segment,
                impact_score=confidence,
                confidence=confidence,
                conditions={"platform": platform},
                source_memory_type="belief",
            )
        finally:
            service.close()

        return {"success": True, "belief_id": belief.id}
    finally:
        db.close()


@router.get("/belief/{audience_segment}")
async def get_belief_memories(audience_segment: str, current_user = Depends(get_current_user)):
    """获取用户信念记忆"""
    from app.core.database import SessionLocal
    from app.models.video_production import AudienceBeliefMemory

    db = SessionLocal()
    try:
        beliefs = db.query(AudienceBeliefMemory).filter(
            AudienceBeliefMemory.audience_segment == audience_segment,
            AudienceBeliefMemory.user_id == current_user.id
        ).order_by(AudienceBeliefMemory.confidence.desc()).all()

        return {
            "success": True,
            "data": [
                {
                    "id": b.id,
                    "audience_segment": b.audience_segment,
                    "old_belief": b.old_belief,
                    "new_belief": b.new_belief,
                    "trigger_content": b.trigger_content,
                    "trigger_type": b.trigger_type,
                    "confidence": b.confidence,
                    "platform": b.related_platform,
                    "product_category": b.related_product_category,
                    "created_at": str(b.created_at),
                }
                for b in beliefs
            ],
        }
    finally:
        db.close()


# ==================== 自动学习 ====================

@router.post("/auto-learn")
async def auto_learn(current_user = Depends(get_current_user)):
    """自动学习入口"""
    service = GrowthCausalGraphService()
    try:
        result = service.auto_learn()
        return result
    finally:
        service.close()


@router.post("/edge/{edge_id}/update-confidence")
async def update_edge_confidence(edge_id: int, success: bool, current_user = Depends(get_current_user)):
    """更新知识边置信度"""
    service = GrowthCausalGraphService()
    try:
        result = service.update_edge_confidence(edge_id, success)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.post("/apply-decay")
async def apply_decay(current_user = Depends(get_current_user)):
    """应用衰减机制"""
    service = GrowthCausalGraphService()
    try:
        result = service.apply_decay()
        return result
    finally:
        service.close()


@router.get("/edge/{edge_id}")
async def get_edge_detail(edge_id: int, current_user = Depends(get_current_user)):
    """获取知识边详情"""
    service = GrowthCausalGraphService()
    try:
        result = service.get_edge_detail(edge_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


# ==================== 增长假设引擎 ====================

@router.post("/hypothesis/propose")
async def propose_hypothesis(
    hypothesis: str,
    description: Optional[str] = None,
    condition_type: Optional[str] = None,
    condition_value: Optional[str] = None,
    predicted_effect: Optional[str] = None,
    predicted_impact: float = 0.0,
    evidence_count: int = 0,
    source_data: Optional[Dict[str, Any]] = None,
    priority_score: float = 0.0,
    current_user = Depends(get_current_user),
):
    """提出新假设"""
    engine = GrowthHypothesisEngine()
    try:
        result = engine.propose_hypothesis({
            "user_id": current_user.id,
            "hypothesis": hypothesis,
            "description": description,
            "condition_type": condition_type,
            "condition_value": condition_value,
            "predicted_effect": predicted_effect,
            "predicted_impact": predicted_impact,
            "evidence_count": evidence_count,
            "source_data": source_data,
            "priority_score": priority_score,
        })
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        engine.close()


@router.post("/hypothesis/discover")
async def discover_hypotheses(limit: int = 10, current_user = Depends(get_current_user)):
    """发现潜在假设"""
    engine = GrowthHypothesisEngine()
    try:
        hypotheses = engine.discover_patterns(current_user.id, limit)
        return {"success": True, "hypotheses": hypotheses}
    finally:
        engine.close()


@router.post("/hypothesis/auto-generate")
async def auto_generate_hypotheses(current_user = Depends(get_current_user)):
    """自动生成假设"""
    engine = GrowthHypothesisEngine()
    try:
        result = engine.auto_generate_hypotheses(current_user.id)
        return result
    finally:
        engine.close()


@router.get("/hypothesis/{hypothesis_id}")
async def evaluate_hypothesis(hypothesis_id: int, current_user = Depends(get_current_user)):
    """评估假设"""
    engine = GrowthHypothesisEngine()
    try:
        result = engine.evaluate_hypothesis(hypothesis_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        engine.close()


@router.post("/hypothesis/{hypothesis_id}/create-experiment")
async def create_experiment_from_hypothesis(hypothesis_id: int, current_user = Depends(get_current_user)):
    """从假设创建实验"""
    engine = GrowthHypothesisEngine()
    try:
        result = engine.create_experiment_from_hypothesis(hypothesis_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        engine.close()


@router.get("/hypotheses/pending")
async def get_pending_hypotheses(limit: int = 20, current_user = Depends(get_current_user)):
    """获取待处理假设"""
    engine = GrowthHypothesisEngine()
    try:
        hypotheses = engine.get_pending_hypotheses(current_user.id, limit)
        return {"success": True, "data": hypotheses}
    finally:
        engine.close()


# ==================== 用户信念图 ====================

@router.post("/belief-node")
async def create_belief_node(
    audience_segment: str,
    belief_content: str,
    belief_category: Optional[str] = None,
    confidence: float = 0.5,
    sample_size: int = 0,
    platform: Optional[str] = None,
    product_category: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """创建信念节点"""
    from app.core.database import SessionLocal
    from app.models.video_production import AudienceBeliefNode

    db = SessionLocal()
    try:
        node = AudienceBeliefNode(
            user_id=current_user.id,
            audience_segment=audience_segment,
            belief_content=belief_content,
            belief_category=belief_category,
            confidence=confidence,
            sample_size=sample_size,
            related_platform=platform,
            related_product_category=product_category,
        )
        db.add(node)
        db.commit()
        db.refresh(node)

        return {"success": True, "node_id": node.id}
    finally:
        db.close()


@router.post("/belief-edge")
async def create_belief_edge(
    from_node_id: int,
    to_node_id: int,
    trigger_type: Optional[str] = None,
    trigger_pattern: Optional[str] = None,
    conversion_rate: float = 0.0,
    confidence: float = 0.5,
    sample_size: int = 0,
    platform: Optional[str] = None,
    product_category: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """创建信念边（转换关系）"""
    from app.core.database import SessionLocal
    from app.models.video_production import AudienceBeliefEdge

    db = SessionLocal()
    try:
        edge = AudienceBeliefEdge(
            user_id=current_user.id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            trigger_type=trigger_type,
            trigger_pattern=trigger_pattern,
            conversion_rate=conversion_rate,
            confidence=confidence,
            sample_size=sample_size,
            related_platform=platform,
            related_product_category=product_category,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)

        return {"success": True, "edge_id": edge.id}
    finally:
        db.close()


@router.get("/belief-graph/{audience_segment}")
async def get_belief_graph(audience_segment: str, current_user = Depends(get_current_user)):
    """获取用户信念图"""
    from app.core.database import SessionLocal
    from app.models.video_production import AudienceBeliefNode, AudienceBeliefEdge

    db = SessionLocal()
    try:
        nodes = db.query(AudienceBeliefNode).filter(
            AudienceBeliefNode.audience_segment == audience_segment,
            AudienceBeliefNode.user_id == current_user.id,
        ).all()

        edges = db.query(AudienceBeliefEdge).filter(
            AudienceBeliefEdge.user_id == current_user.id,
        ).all()

        node_map = {n.id: n for n in nodes}

        return {
            "success": True,
            "audience_segment": audience_segment,
            "nodes": [
                {
                    "id": n.id,
                    "belief_content": n.belief_content,
                    "belief_category": n.belief_category,
                    "confidence": n.confidence,
                    "sample_size": n.sample_size,
                    "platform": n.related_platform,
                    "product_category": n.related_product_category,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "from_belief": node_map[e.from_node_id].belief_content if e.from_node_id in node_map else None,
                    "to_belief": node_map[e.to_node_id].belief_content if e.to_node_id in node_map else None,
                    "trigger_type": e.trigger_type,
                    "trigger_pattern": e.trigger_pattern,
                    "conversion_rate": e.conversion_rate,
                    "confidence": e.confidence,
                    "sample_size": e.sample_size,
                }
                for e in edges
                if e.from_node_id in node_map and e.to_node_id in node_map
            ],
        }
    finally:
        db.close()


# ==================== 自我反思层 ====================

@router.post("/reflection/prediction-error")
async def record_prediction_error(
    prediction_type: str,
    predicted_value: float,
    actual_value: float,
    strategy_used: Optional[str] = None,
    causal_edges_used: Optional[List[int]] = None,
    context_conditions: Optional[Dict[str, Any]] = None,
    related_video_id: Optional[int] = None,
    related_plan_id: Optional[int] = None,
    current_user = Depends(get_current_user),
):
    """记录预测误差"""
    from app.services.growth_reflection_service import GrowthReflectionService

    service = GrowthReflectionService()
    try:
        result = service.record_prediction_error({
            "user_id": current_user.id,
            "prediction_type": prediction_type,
            "predicted_value": predicted_value,
            "actual_value": actual_value,
            "strategy_used": strategy_used,
            "causal_edges_used": causal_edges_used,
            "context_conditions": context_conditions,
            "related_video_id": related_video_id,
            "related_plan_id": related_plan_id,
        })
        return result
    finally:
        service.close()


@router.post("/reflection/analyze/{error_id}")
async def analyze_prediction_error(error_id: int, current_user = Depends(get_current_user)):
    """分析预测误差根因"""
    from app.services.growth_reflection_service import GrowthReflectionService

    service = GrowthReflectionService()
    try:
        result = service.analyze_prediction_error(error_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


@router.post("/reflection/calibrate/{strategy_type}")
async def calibrate_strategy_confidence(strategy_type: str, current_user = Depends(get_current_user)):
    """校准策略置信度"""
    from app.services.growth_reflection_service import GrowthReflectionService

    service = GrowthReflectionService()
    try:
        result = service.calibrate_strategy_confidence(strategy_type, current_user.id)
        return result
    finally:
        service.close()


@router.get("/reflection/weekly")
async def get_weekly_reflection(current_user = Depends(get_current_user)):
    """获取每周反思总结"""
    from app.services.growth_reflection_service import GrowthReflectionService

    service = GrowthReflectionService()
    try:
        result = service.get_weekly_reflection(current_user.id)
        return result
    finally:
        service.close()


@router.post("/reflection/auto-correct")
async def auto_correct_from_errors(current_user = Depends(get_current_user)):
    """从预测误差自动纠错"""
    service = GrowthCausalGraphService()
    try:
        result = service.auto_correct_from_errors(current_user.id)
        return result
    finally:
        service.close()


@router.get("/reflection/low-accuracy-edges")
async def get_low_accuracy_edges(threshold: float = 0.6, current_user = Depends(get_current_user)):
    """获取低准确率知识边"""
    service = GrowthCausalGraphService()
    try:
        edges = service.get_low_accuracy_edges(current_user.id, threshold)
        return {"success": True, "data": edges}
    finally:
        service.close()


@router.post("/edge/{edge_id}/calibrate")
async def calibrate_edge_confidence(edge_id: int, current_user = Depends(get_current_user)):
    """校准知识边置信度"""
    service = GrowthCausalGraphService()
    try:
        result = service.calibrate_edge_confidence(edge_id, current_user.id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


@router.post("/edge/{edge_id}/context")
async def add_context_condition(edge_id: int, context: Dict[str, Any], current_user = Depends(get_current_user)):
    """添加上下文条件"""
    service = GrowthCausalGraphService()
    try:
        result = service.add_context_condition(edge_id, context)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


@router.post("/edges/query-with-context")
async def query_edges_with_context(
    source_type: str,
    source_value: str,
    context: Optional[Dict[str, Any]] = None,
    current_user = Depends(get_current_user),
):
    """查询带上下文条件的知识边"""
    service = GrowthCausalGraphService()
    try:
        edges = service.query_edges_with_context(source_type, source_value, context)
        return {"success": True, "data": edges}
    finally:
        service.close()


@router.post("/director/mistake")
async def record_director_mistake(
    mistake_type: str,
    recommendation: str,
    expected_outcome: Optional[str] = None,
    actual_outcome: Optional[str] = None,
    mistake_reason: Optional[str] = None,
    correct_strategy: Optional[str] = None,
    learning: Optional[str] = None,
    related_video_id: Optional[int] = None,
    related_plan_id: Optional[int] = None,
    current_user = Depends(get_current_user),
):
    """记录导演错误"""
    from app.services.growth_reflection_service import GrowthReflectionService

    service = GrowthReflectionService()
    try:
        result = service.record_director_mistake({
            "user_id": current_user.id,
            "mistake_type": mistake_type,
            "recommendation": recommendation,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "mistake_reason": mistake_reason,
            "correct_strategy": correct_strategy,
            "learning": learning,
            "related_video_id": related_video_id,
            "related_plan_id": related_plan_id,
        })
        return result
    finally:
        service.close()


@router.post("/director/analyze")
async def analyze_director_decision(plan_id: int, actual_results: Dict[str, Any], current_user = Depends(get_current_user)):
    """分析导演决策"""
    from app.services.director_reflection_agent import DirectorReflectionAgent

    agent = DirectorReflectionAgent()
    try:
        result = agent.analyze_director_decision(plan_id, actual_results)
        return result
    finally:
        agent.close()


@router.get("/director/weekly-critique")
async def weekly_self_critique(current_user = Depends(get_current_user)):
    """每周自我批判"""
    from app.services.director_reflection_agent import DirectorReflectionAgent

    agent = DirectorReflectionAgent()
    try:
        result = agent.weekly_self_critique(current_user.id)
        return result
    finally:
        agent.close()


@router.post("/director/update-rules")
async def update_director_rules(current_user = Depends(get_current_user)):
    """更新导演规则"""
    from app.services.director_reflection_agent import DirectorReflectionAgent

    agent = DirectorReflectionAgent()
    try:
        result = agent.update_director_rules(current_user.id)
        return result
    finally:
        agent.close()


# ==================== 治理层 ====================

@router.post("/governance/evidence-score/{edge_id}")
async def calculate_evidence_score(edge_id: int, current_user = Depends(get_current_user)):
    """计算知识边证据评分"""
    from app.services.growth_governance_service import GrowthGovernanceService

    service = GrowthGovernanceService()
    try:
        result = service.calculate_evidence_score(edge_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


@router.get("/governance/detect-conflicts")
async def detect_conflicts(current_user = Depends(get_current_user)):
    """检测知识冲突"""
    from app.services.growth_governance_service import GrowthGovernanceService

    service = GrowthGovernanceService()
    try:
        conflicts = service.detect_conflicts(current_user.id)
        return {"success": True, "conflicts": conflicts}
    finally:
        service.close()


@router.post("/governance/resolve-conflict/{conflict_id}")
async def resolve_conflict(
    conflict_id: int,
    resolution: str,
    resolved_by: str = "system",
    current_user = Depends(get_current_user),
):
    """解决知识冲突"""
    from app.services.growth_governance_service import GrowthGovernanceService

    service = GrowthGovernanceService()
    try:
        result = service.resolve_conflict(conflict_id, resolution, resolved_by)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


@router.post("/governance/promote-edge/{edge_id}")
async def promote_edge_status(edge_id: int, current_user = Depends(get_current_user)):
    """提升知识边生命周期状态"""
    from app.services.growth_governance_service import GrowthGovernanceService

    service = GrowthGovernanceService()
    try:
        result = service.promote_edge_status(edge_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


@router.get("/governance/review-summary")
async def review_pending_knowledge(current_user = Depends(get_current_user)):
    """获取待审核知识概览"""
    from app.services.growth_governance_service import GrowthGovernanceService

    service = GrowthGovernanceService()
    try:
        result = service.review_pending_knowledge(current_user.id)
        return result
    finally:
        service.close()


@router.get("/governance/edge-lifecycle/{edge_id}")
async def get_edge_lifecycle(edge_id: int, current_user = Depends(get_current_user)):
    """获取知识边生命周期信息"""
    from app.services.growth_governance_service import GrowthGovernanceService

    service = GrowthGovernanceService()
    try:
        result = service.get_edge_lifecycle(edge_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        service.close()


@router.post("/guard/review")
async def review_new_knowledge(
    source_type: str,
    source_value: str,
    target_type: str,
    target_value: str,
    relation_type: str,
    confidence: float = 0.5,
    sample_size: int = 0,
    experiment_count: int = 0,
    current_user = Depends(get_current_user),
):
    """审核新知识"""
    from app.services.growth_learning_guard_agent import GrowthLearningGuardAgent

    agent = GrowthLearningGuardAgent()
    try:
        result = agent.review_new_knowledge({
            "source_type": source_type,
            "source_value": source_value,
            "target_type": target_type,
            "target_value": target_value,
            "relation_type": relation_type,
            "confidence": confidence,
            "sample_size": sample_size,
            "experiment_count": experiment_count,
        })
        return result
    finally:
        agent.close()


@router.post("/guard/approve/{edge_id}")
async def approve_learning(edge_id: int, current_user = Depends(get_current_user)):
    """批准学习"""
    from app.services.growth_learning_guard_agent import GrowthLearningGuardAgent

    agent = GrowthLearningGuardAgent()
    try:
        result = agent.approve_learning(edge_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        agent.close()


@router.post("/guard/reject/{edge_id}")
async def reject_learning(edge_id: int, reason: str = "", current_user = Depends(get_current_user)):
    """拒绝学习"""
    from app.services.growth_learning_guard_agent import GrowthLearningGuardAgent

    agent = GrowthLearningGuardAgent()
    try:
        result = agent.reject_learning(edge_id, reason)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        agent.close()


@router.post("/guard/batch-review")
async def batch_review_candidates(limit: int = 20, current_user = Depends(get_current_user)):
    """批量审核候选知识"""
    from app.services.growth_learning_guard_agent import GrowthLearningGuardAgent

    agent = GrowthLearningGuardAgent()
    try:
        result = agent.batch_review_candidates(current_user.id, limit)
        return result
    finally:
        agent.close()


@router.get("/guard/observation-pool")
async def get_observation_pool(limit: int = 20, current_user = Depends(get_current_user)):
    """获取观察池"""
    from app.services.growth_learning_guard_agent import GrowthLearningGuardAgent

    agent = GrowthLearningGuardAgent()
    try:
        edges = agent.get_observation_pool(current_user.id, limit)
        return {"success": True, "data": edges}
    finally:
        agent.close()
