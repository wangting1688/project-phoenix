"""
Agent工具调用网关 API

TASK-016.3B.1: AI Agent Tool Gateway

提供工具列表查询、工具调用、策略生成、生产编排等接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.agent_tool_gateway import AgentToolGateway

router = APIRouter(prefix="/agent-gateway", tags=["AI Agent网关"])


# ==================== 工具管理 ====================

@router.get("/tools")
async def get_available_tools(
    category: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """获取可用工具列表"""
    gateway = AgentToolGateway()
    tools = gateway.get_available_tools(category)
    return {
        "success": True,
        "data": tools,
    }


@router.get("/tools/llm")
async def get_llm_tool_list(current_user = Depends(get_current_user)):
    """获取LLM可调用的工具列表"""
    gateway = AgentToolGateway()
    tools = gateway.get_llm_tool_list()
    return {
        "success": True,
        "data": tools,
    }


@router.post("/tools/call")
async def call_tool(
    tool_name: str,
    params: Dict[str, Any],
    current_user = Depends(get_current_user),
):
    """调用工具"""
    gateway = AgentToolGateway()
    result = gateway.call_tool(tool_name, **params)
    return {
        "success": result.get("success", False),
        "data": result.get("data"),
        "error": result.get("error"),
    }


@router.post("/tools/batch-call")
async def batch_call_tools(
    tool_calls: List[Dict[str, Any]],
    current_user = Depends(get_current_user),
):
    """批量调用工具"""
    gateway = AgentToolGateway()
    results = gateway.batch_call_tools(tool_calls)
    return {
        "success": True,
        "data": results,
    }


# ==================== 导演策略生成 ====================

@router.post("/strategy/director")
async def generate_director_strategy(
    product_name: str,
    product_category: str,
    target_platform: str,
    creator_profile: Dict[str, Any],
    commercial_goal: str = "conversion",
    current_user = Depends(get_current_user),
):
    """
    生成导演策略

    将商业目标转化为剪辑策略、镜头计划、素材需求
    """
    gateway = AgentToolGateway()
    strategy = gateway.generate_director_strategy(
        product_name=product_name,
        product_category=product_category,
        creator_profile=creator_profile,
        target_platform=target_platform,
        commercial_goal=commercial_goal,
    )
    return {
        "success": True,
        "data": strategy,
    }


# ==================== 字幕策略生成 ====================

@router.post("/strategy/caption")
async def generate_caption_strategy(
    raw_text: str,
    video_duration: float,
    content_type: str,
    platform: str = "wechat_video",
    current_user = Depends(get_current_user),
):
    """
    生成字幕策略

    根据原始文本生成结构化的字幕分段、关键词高亮、表情符号建议
    """
    gateway = AgentToolGateway()
    strategy = gateway.generate_caption_strategy(
        raw_text=raw_text,
        video_duration=video_duration,
        content_type=content_type,
        platform=platform,
    )
    return {
        "success": True,
        "data": strategy,
    }


# ==================== 封面策略生成 ====================

@router.post("/strategy/cover")
async def generate_cover_prompt(
    product_name: str,
    product_category: str,
    title: str,
    platform: str = "wechat_video",
    creator_profile: Optional[Dict[str, Any]] = None,
    current_user = Depends(get_current_user),
):
    """
    生成封面生成策略

    根据产品、平台、主播画像生成高质量的封面Prompt
    """
    gateway = AgentToolGateway()
    strategy = gateway.generate_cover_prompt(
        product_name=product_name,
        product_category=product_category,
        creator_profile=creator_profile or {},
        platform=platform,
        title=title,
    )
    return {
        "success": True,
        "data": strategy,
    }


# ==================== 生产编排 ====================

@router.post("/orchestrate")
async def orchestrate_production(
    job_id: int,
    product_name: str,
    product_category: str,
    target_platforms: List[str],
    creator_profile: Dict[str, Any],
    commercial_goal: str = "conversion",
    current_user = Depends(get_current_user),
):
    """
    编排完整的视频生产流程

    根据商业目标、产品、主播画像、目标平台生成完整的生产计划
    """
    gateway = AgentToolGateway()
    result = gateway.orchestrate_production(
        job_id=job_id,
        product_name=product_name,
        product_category=product_category,
        creator_profile=creator_profile,
        target_platforms=target_platforms,
        commercial_goal=commercial_goal,
    )
    return {
        "success": True,
        "data": result,
    }


# ==================== 视频处理 ====================

@router.post("/process-video")
async def process_video(
    video_path: str,
    strategy: Dict[str, Any],
    current_user = Depends(get_current_user),
):
    """
    处理视频

    流程：视频分析 → 音频转录 → 字幕生成 → 封面生成
    """
    gateway = AgentToolGateway()
    result = gateway.process_video(video_path, strategy)
    return {
        "success": result.get("success", False),
        "data": result,
    }


# ==================== 工具测试 ====================

@router.post("/tools/test/{tool_name}")
async def test_tool(
    tool_name: str,
    params: Optional[Dict[str, Any]] = None,
    current_user = Depends(get_current_user),
):
    """测试工具调用"""
    gateway = AgentToolGateway()
    result = gateway.call_tool(tool_name, **(params or {}))
    return {
        "tool_name": tool_name,
        "success": result.get("success", False),
        "result": result.get("data"),
        "error": result.get("error"),
    }


# ==================== 策略预览 ====================

@router.post("/strategy/preview")
async def preview_strategy(
    product_name: str,
    product_category: str,
    platform: str,
    current_user = Depends(get_current_user),
):
    """
    预览完整策略

    生成导演策略、字幕策略、封面策略的完整预览
    """
    gateway = AgentToolGateway()

    director_strategy = gateway.generate_director_strategy(
        product_name=product_name,
        product_category=product_category,
        creator_profile={},
        target_platform=platform,
        commercial_goal="conversion",
    )

    cover_strategy = gateway.generate_cover_prompt(
        product_name=product_name,
        product_category=product_category,
        creator_profile={},
        platform=platform,
        title=product_name,
    )

    return {
        "success": True,
        "data": {
            "director_strategy": director_strategy,
            "cover_strategy": cover_strategy,
            "caption_strategy": {
                "style": director_strategy["caption_style"],
                "platform": platform,
            },
        },
    }
