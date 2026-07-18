"""
Agent工具调用引擎

TASK-016.3B.1: AI Agent Tool Gateway

核心组件：
1. AgentToolGateway - 统一工具调用入口
2. DirectorPromptEngine - 将商业目标转化为剪辑策略
3. CaptionStrategyEngine - 字幕策略生成
4. CoverStrategyEngine - 封面策略生成
5. ProductionTaskOrchestrator - 生产任务编排器
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import json
import time

from app.services.tool_registry import ToolRegistry, ToolCategory
from app.services.external_tools import register_all_tools
from app.models.video_production import VideoProductionJob, VideoTimeline


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCallRecord:
    """工具调用记录"""

    def __init__(self, tool_name: str, params: Dict[str, Any], result: Dict[str, Any], duration: float):
        self.tool_name = tool_name
        self.params = params
        self.result = result
        self.duration = duration

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "result": self.result,
            "duration": self.duration,
        }


class DirectorPromptEngine:
    """AI导演Prompt引擎"""

    PLATFORM_STRATEGIES = {
        "douyin": {
            "duration": 35,
            "style": "快节奏、强Hook、视觉冲击",
            "priority": "traffic",
            "caption_style": "短、精、准、带话题",
        },
        "wechat_video": {
            "duration": 60,
            "style": "温和、信任、案例驱动",
            "priority": "conversion",
            "caption_style": "详细、信任、引导私信",
        },
        "xiaohongshu": {
            "duration": 45,
            "style": "知识型、清单式、收藏导向",
            "priority": "content",
            "caption_style": "标题党、干货清单、话题标签",
        },
        "kuaishou": {
            "duration": 40,
            "style": "接地气、互动强、粉丝导向",
            "priority": "community",
            "caption_style": "口语化、互动提问",
        },
    }

    CONTENT_TYPE_STRATEGIES = {
        "health": {
            "emotion": "trust",
            "camera_type": "face",
            "bgm_style": "轻柔钢琴",
            "bgm_bpm": "<120",
        },
        "beauty": {
            "emotion": "excitement",
            "camera_type": "closeup",
            "bgm_style": "流行音乐",
            "bgm_bpm": "120-140",
        },
        "food": {
            "emotion": "appetite",
            "camera_type": "food_closeup",
            "bgm_style": "轻快愉悦",
            "bgm_bpm": "100-120",
        },
        "education": {
            "emotion": "curiosity",
            "camera_type": "screen",
            "bgm_style": "无或轻音乐",
            "bgm_bpm": "<100",
        },
        "entertainment": {
            "emotion": "excitement",
            "camera_type": "dynamic",
            "bgm_style": "动感音乐",
            "bgm_bpm": ">140",
        },
    }

    def __init__(self):
        self._registry = ToolRegistry()

    def generate_cutting_strategy(
        self,
        product_name: str,
        product_category: str,
        creator_profile: Dict[str, Any],
        target_platform: str,
        commercial_goal: str = "conversion",
    ) -> Dict[str, Any]:
        """
        将商业目标转化为剪辑策略

        输入：
        - product_name: 产品名称
        - product_category: 产品类别
        - creator_profile: 主播画像
        - target_platform: 目标平台
        - commercial_goal: 商业目标

        输出：
        - 完整的剪辑策略
        """

        platform_strategy = self.PLATFORM_STRATEGIES.get(target_platform, {})
        content_strategy = self.CONTENT_TYPE_STRATEGIES.get(product_category, {})

        strategy = {
            "product": product_name,
            "product_category": product_category,
            "platform": target_platform,
            "commercial_goal": commercial_goal,
            "target_duration": platform_strategy.get("duration", 35),
            "style": platform_strategy.get("style", "通用"),
            "emotion": content_strategy.get("emotion", "neutral"),
            "camera_type": content_strategy.get("camera_type", "face"),
            "bgm_style": content_strategy.get("bgm_style", "轻音乐"),
            "bgm_bpm": content_strategy.get("bgm_bpm", "<120"),
            "caption_style": platform_strategy.get("caption_style", "通用"),
            "creator_best_content_type": creator_profile.get("best_content_type"),
            "creator_best_hook_style": creator_profile.get("best_hook_style"),
            "creator_best_duration_range": creator_profile.get("best_duration_range"),
            "creator_weak_styles": creator_profile.get("weak_styles", []),
        }

        strategy["scene_plan"] = self._generate_scene_plan(strategy)
        strategy["shot_list"] = self._generate_shot_list(strategy)
        strategy["material_requirements"] = self._generate_material_requirements(strategy)

        return strategy

    def _generate_scene_plan(self, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成场景计划"""
        duration = strategy["target_duration"]

        return [
            {
                "scene": 1,
                "name": "Hook",
                "duration": min(3, duration * 0.08),
                "content": "痛点冲击",
                "camera_type": "closeup",
                "emotion": "surprise",
                "required": True,
            },
            {
                "scene": 2,
                "name": "Pain Point",
                "duration": min(8, duration * 0.15),
                "content": "痛点描述",
                "camera_type": "face",
                "emotion": "concern",
                "required": True,
            },
            {
                "scene": 3,
                "name": "Solution",
                "duration": min(15, duration * 0.25),
                "content": "知识/解决方案",
                "camera_type": "screen",
                "emotion": "curiosity",
                "required": True,
            },
            {
                "scene": 4,
                "name": "Product",
                "duration": min(12, duration * 0.20),
                "content": "产品展示",
                "camera_type": "product_closeup",
                "emotion": "trust",
                "required": True,
            },
            {
                "scene": 5,
                "name": "Social Proof",
                "duration": min(8, duration * 0.15),
                "content": "信任/案例",
                "camera_type": "face",
                "emotion": "trust",
                "required": strategy["commercial_goal"] == "conversion",
            },
            {
                "scene": 6,
                "name": "CTA",
                "duration": min(5, duration * 0.12),
                "content": "成交引导",
                "camera_type": "face",
                "emotion": "urgency",
                "required": True,
            },
        ]

    def _generate_shot_list(self, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成镜头列表"""
        shots = []
        for scene in strategy["scene_plan"]:
            shots.append({
                "scene": scene["scene"],
                "shot_type": scene["camera_type"],
                "duration": scene["duration"],
                "content": scene["content"],
                "emotion": scene["emotion"],
            })
        return shots

    def _generate_material_requirements(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """生成素材需求"""
        return {
            "video": {
                "hook": {"role": "hook", "emotion": "surprise", "camera_type": "closeup"},
                "pain_point": {"role": "pain_point", "emotion": "concern", "camera_type": "face"},
                "knowledge": {"role": "knowledge", "emotion": "curiosity", "camera_type": "screen"},
                "product": {"role": "product", "emotion": "trust", "camera_type": "product_closeup"},
                "social_proof": {"role": "social_proof", "emotion": "trust", "camera_type": "face"},
                "conversion": {"role": "conversion", "emotion": "urgency", "camera_type": "face"},
            },
            "audio": {
                "bgm_style": strategy["bgm_style"],
                "bgm_bpm": strategy["bgm_bpm"],
                "narration_required": True,
            },
            "subtitle": {
                "style": strategy["caption_style"],
                "highlight_keywords": True,
                "emoji_required": True,
            },
            "cover": {
                "style": "high_click",
                "text_position": "top",
                "character_position": "right",
                "emotion": "surprise",
            },
        }


class CaptionStrategyEngine:
    """字幕策略引擎"""

    def __init__(self):
        self._registry = ToolRegistry()

    def generate_caption_strategy(
        self,
        raw_text: str,
        video_duration: float,
        content_type: str,
        platform: str,
    ) -> Dict[str, Any]:
        """
        根据原始文本生成字幕策略

        输入：
        - raw_text: 原始转录文本
        - video_duration: 视频时长
        - content_type: 内容类型
        - platform: 平台

        输出：
        - 字幕策略
        """

        sentences = raw_text.split("。")
        sentences = [s.strip() for s in sentences if s.strip()]

        avg_duration_per_sentence = video_duration / max(len(sentences), 1)

        segments = []
        current_time = 0.0

        for i, sentence in enumerate(sentences):
            segment_duration = min(max(len(sentence) * 0.3, 1.5), avg_duration_per_sentence * 1.5)

            keywords = self._extract_keywords(sentence, content_type)
            should_highlight = len(keywords) > 0

            segments.append({
                "id": i + 1,
                "text": sentence,
                "start_time": current_time,
                "end_time": current_time + segment_duration,
                "duration": segment_duration,
                "keywords": keywords,
                "highlight": should_highlight,
                "emoji": self._suggest_emoji(sentence, content_type),
                "style": self._determine_style(platform, i, len(sentences)),
            })

            current_time += segment_duration

        return {
            "raw_text": raw_text,
            "platform": platform,
            "content_type": content_type,
            "total_segments": len(segments),
            "avg_segment_duration": avg_duration_per_sentence,
            "segments": segments,
            "strategy": {
                "font_size": 48 if platform == "douyin" else 36,
                "font_color": "#ffffff",
                "background_opacity": 0.6,
                "highlight_color": "#ff6b6b",
                "animation": "pop" if platform == "douyin" else "fade",
            },
        }

    def _extract_keywords(self, text: str, content_type: str) -> List[str]:
        """提取关键词"""
        keywords = []

        health_keywords = ["身体", "健康", "疲劳", "免疫力", "睡眠", "减肥", "养生"]
        beauty_keywords = ["皮肤", "美白", "抗老", "护肤", "年轻", "紧致"]
        food_keywords = ["好吃", "营养", "健康", "美味", "口感"]

        if content_type == "health":
            for kw in health_keywords:
                if kw in text:
                    keywords.append(kw)
        elif content_type == "beauty":
            for kw in beauty_keywords:
                if kw in text:
                    keywords.append(kw)
        elif content_type == "food":
            for kw in food_keywords:
                if kw in text:
                    keywords.append(kw)

        return keywords[:3]

    def _suggest_emoji(self, text: str, content_type: str) -> Optional[str]:
        """建议表情符号"""
        if "不" in text or "没有" in text:
            return "❌"
        if "好" in text or "有效" in text:
            return "✅"
        if "为什么" in text or "怎么" in text:
            return "❓"
        if content_type == "health":
            return "💊"
        if content_type == "beauty":
            return "✨"
        if content_type == "food":
            return "🍱"
        return None

    def _determine_style(self, platform: str, index: int, total: int) -> str:
        """确定字幕风格"""
        if index == 0:
            return "hook"
        if index == total - 1:
            return "cta"
        if platform == "douyin":
            return "dynamic"
        return "normal"


class CoverStrategyEngine:
    """封面策略引擎"""

    def __init__(self):
        self._registry = ToolRegistry()

    def generate_cover_prompt(
        self,
        product_name: str,
        product_category: str,
        creator_profile: Dict[str, Any],
        platform: str,
        title: str,
    ) -> Dict[str, Any]:
        """
        生成封面生成Prompt

        输入：
        - product_name: 产品名称
        - product_category: 产品类别
        - creator_profile: 主播画像
        - platform: 平台
        - title: 视频标题

        输出：
        - 封面生成策略和Prompt
        """

        platform_config = {
            "douyin": {
                "size": "1024x1536",
                "text_position": "top_center",
                "style": "high_contrast",
            },
            "wechat_video": {
                "size": "1024x1024",
                "text_position": "bottom_center",
                "style": "trustworthy",
            },
            "xiaohongshu": {
                "size": "1024x1024",
                "text_position": "top_left",
                "style": "aesthetic",
            },
            "kuaishou": {
                "size": "1024x1536",
                "text_position": "center",
                "style": "casual",
            },
        }

        config = platform_config.get(platform, platform_config["wechat_video"])

        age_range = creator_profile.get("age_range", "30-40")
        gender = creator_profile.get("gender", "female")

        prompt = f"""
生成{product_category}类短视频封面，适合{platform}平台：

要求：
- 高点击率设计
- {gender}性，年龄{age_range}
- 表情{self._suggest_emotion(product_category)}
- 人物位于{self._suggest_position(platform)}
- 标题区域在{config['text_position']}
- 标题内容：{title}
- 风格：{config['style']}
- 背景简洁，突出主体
- 颜色鲜艳但不刺眼
- 适合移动端展示

不要出现文字，只生成图片主体。
        """

        return {
            "platform": platform,
            "product": product_name,
            "category": product_category,
            "size": config["size"],
            "prompt": prompt.strip(),
            "strategy": {
                "text_position": config["text_position"],
                "style": config["style"],
                "emotion": self._suggest_emotion(product_category),
            },
        }

    def _suggest_emotion(self, category: str) -> str:
        """建议表情"""
        emotions = {
            "health": "惊讶/关心",
            "beauty": "自信/愉悦",
            "food": "满足/期待",
            "education": "专注/好奇",
            "entertainment": "开心/兴奋",
        }
        return emotions.get(category, "自然")

    def _suggest_position(self, platform: str) -> str:
        """建议人物位置"""
        positions = {
            "douyin": "右侧",
            "wechat_video": "中间",
            "xiaohongshu": "左侧",
            "kuaishou": "右侧",
        }
        return positions.get(platform, "中间")


class ProductionTaskOrchestrator:
    """生产任务编排器"""

    def __init__(self):
        self._registry = ToolRegistry()
        self._director_engine = DirectorPromptEngine()
        self._caption_engine = CaptionStrategyEngine()
        self._cover_engine = CoverStrategyEngine()

    def orchestrate_production(
        self,
        job_id: int,
        product_name: str,
        product_category: str,
        creator_profile: Dict[str, Any],
        target_platforms: List[str],
        commercial_goal: str = "conversion",
    ) -> Dict[str, Any]:
        """
        编排完整的视频生产流程

        输入：
        - job_id: 生产任务ID
        - product_name: 产品名称
        - product_category: 产品类别
        - creator_profile: 主播画像
        - target_platforms: 目标平台列表
        - commercial_goal: 商业目标

        输出：
        - 生产编排结果
        """

        results = {
            "job_id": job_id,
            "product": product_name,
            "platforms": [],
            "total_variants": len(target_platforms),
        }

        for platform in target_platforms:
            platform_result = self._orchestrate_platform_production(
                job_id=job_id,
                product_name=product_name,
                product_category=product_category,
                creator_profile=creator_profile,
                platform=platform,
                commercial_goal=commercial_goal,
            )
            results["platforms"].append(platform_result)

        return results

    def _orchestrate_platform_production(
        self,
        job_id: int,
        product_name: str,
        product_category: str,
        creator_profile: Dict[str, Any],
        platform: str,
        commercial_goal: str,
    ) -> Dict[str, Any]:
        """编排单个平台的生产"""

        cutting_strategy = self._director_engine.generate_cutting_strategy(
            product_name=product_name,
            product_category=product_category,
            creator_profile=creator_profile,
            target_platform=platform,
            commercial_goal=commercial_goal,
        )

        cover_strategy = self._cover_engine.generate_cover_prompt(
            product_name=product_name,
            product_category=product_category,
            creator_profile=creator_profile,
            platform=platform,
            title=product_name,
        )

        return {
            "platform": platform,
            "commercial_goal": commercial_goal,
            "cutting_strategy": cutting_strategy,
            "cover_strategy": cover_strategy,
            "caption_strategy": {
                "style": cutting_strategy["caption_style"],
                "platform": platform,
            },
            "timeline_structure": cutting_strategy["scene_plan"],
            "material_requirements": cutting_strategy["material_requirements"],
        }

    def process_video(self, video_path: str, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理视频

        流程：
        1. 视频分析
        2. 音频转录
        3. 字幕生成
        4. 封面生成
        5. 视频渲染
        """

        steps = [
            ("video_analysis", {"video_path": video_path, "features": "all"}),
            ("whisper_transcribe", {"audio_path": video_path, "language": "zh"}),
        ]

        results = {}
        tool_calls = []

        for tool_name, params in steps:
            start_time = time.time()
            result = self._registry.call_tool(tool_name, **params)
            duration = time.time() - start_time

            tool_calls.append({
                "tool_name": tool_name,
                "params": params,
                "duration": round(duration, 2),
                "success": result["success"],
            })

            if result["success"]:
                results[tool_name] = result["data"]

        if "whisper_transcribe" in results:
            raw_text = results["whisper_transcribe"].get("text", "")
            if raw_text:
                caption_strategy = self._caption_engine.generate_caption_strategy(
                    raw_text=raw_text,
                    video_duration=strategy.get("target_duration", 35),
                    content_type=strategy.get("product_category", "general"),
                    platform=strategy.get("platform", "wechat_video"),
                )
                results["caption_strategy"] = caption_strategy

        return {
            "video_path": video_path,
            "results": results,
            "tool_calls": tool_calls,
            "success": all(tc["success"] for tc in tool_calls),
        }


class AgentToolGateway:
    """Agent工具调用网关"""

    def __init__(self):
        self._registry = ToolRegistry()
        register_all_tools()

    def get_available_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        if category:
            try:
                cat_enum = ToolCategory(category)
                tools = self._registry.find_by_category(cat_enum)
            except ValueError:
                tools = self._registry.list_tools()
        else:
            tools = self._registry.list_tools()

        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
                "provider": t.provider,
                "cost": t.cost,
                "status": t.status.value,
                "version": t.version,
            }
            for t in tools
        ]

    def get_llm_tool_list(self) -> List[Dict[str, Any]]:
        """获取LLM可调用的工具列表"""
        return self._registry.get_llm_tool_list()

    def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """调用工具"""
        return self._registry.call_tool(tool_name, **kwargs)

    def batch_call_tools(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量调用工具"""
        results = []
        for call in tool_calls:
            tool_name = call["tool_name"]
            params = call.get("params", {})
            result = self.call_tool(tool_name, **params)
            results.append({
                "tool_name": tool_name,
                "params": params,
                "result": result,
            })
        return results

    def generate_director_strategy(self, **kwargs) -> Dict[str, Any]:
        """生成导演策略"""
        engine = DirectorPromptEngine()
        return engine.generate_cutting_strategy(**kwargs)

    def generate_caption_strategy(self, **kwargs) -> Dict[str, Any]:
        """生成字幕策略"""
        engine = CaptionStrategyEngine()
        return engine.generate_caption_strategy(**kwargs)

    def generate_cover_prompt(self, **kwargs) -> Dict[str, Any]:
        """生成封面Prompt"""
        engine = CoverStrategyEngine()
        return engine.generate_cover_prompt(**kwargs)

    def orchestrate_production(self, **kwargs) -> Dict[str, Any]:
        """编排生产任务"""
        orchestrator = ProductionTaskOrchestrator()
        return orchestrator.orchestrate_production(**kwargs)

    def process_video(self, video_path: str, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """处理视频"""
        orchestrator = ProductionTaskOrchestrator()
        return orchestrator.process_video(video_path, strategy)
