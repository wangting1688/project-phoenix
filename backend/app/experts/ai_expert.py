import os
import json
from typing import Dict, Any, Optional


class PromptLoader:
    @staticmethod
    def load_prompt(prompt_name: str) -> str:
        prompt_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "prompts",
            f"{prompt_name}.txt"
        )
        prompt_path = os.path.abspath(prompt_path)
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def format_prompt(prompt_template: str, **kwargs) -> str:
        for key, value in kwargs.items():
            prompt_template = prompt_template.replace(f"{{{key}}}", str(value))
        return prompt_template


class MockAIProvider:
    @staticmethod
    def generate_content(prompt: str) -> str:
        import random
        try:
            if "Content Expert" in prompt or "内容策略" in prompt:
                topic = "unknown"
                for line in prompt.split("\n"):
                    if "topic" in line.lower():
                        topic = line.split(":")[-1].strip()
                        break
                
                return json.dumps({
                    "title": f"{topic}的健康管理秘诀",
                    "category": "健康知识",
                    "audience": "40-55岁女性",
                    "pain_point": "中年女性常见健康困扰",
                    "content_angle": "从生活方式入手，科学改善健康",
                    "consultation_score": random.randint(85, 95),
                    "reason": "该主题咨询潜力高，适合目标受众"
                }, ensure_ascii=False)

            elif "Planning Expert" in prompt or "短视频导演" in prompt:
                return json.dumps({
                    "style": "生活故事",
                    "emotion": "共鸣",
                    "scene": "厨房",
                    "structure": "3秒吸引-20秒故事-30秒价值-7秒互动",
                    "duration": 60,
                    "opening_hook": "很多40岁后的女人，身体开始出现各种小问题"
                }, ensure_ascii=False)

            elif "Script Expert" in prompt or "短视频编剧" in prompt:
                topic = "睡眠"
                for line in prompt.split("\n"):
                    if "topic" in line.lower():
                        topic = line.split(":")[-1].strip()
                        break

                story_version = f"""大家好，我是XX。前几年我和很多姐妹一样，{topic}问题特别严重。那时候我每天晚上躺在床上，脑子里像放电影一样，翻来覆去睡不着。后来我尝试了很多方法，终于找到了适合中年女性的{topic}秘诀。今天就把这些经验分享给大家..."""

                knowledge_version = f"""为什么很多女性到了40岁以后{topic}会变差？主要有几个原因：第一是荷尔蒙变化，第二是生活压力，第三是不良习惯。针对这些问题，我总结了三个方法：首先...其次...最后..."""

                chat_version = f"""姐妹们，你们有没有{topic}不好的困扰？我最近发现了一个特别有效的方法，想和大家聊聊。其实啊，{topic}问题说复杂也复杂，说简单也简单，关键在于找对方法..."""

                return json.dumps({
                    "story_version": story_version,
                    "knowledge_version": knowledge_version,
                    "chat_version": chat_version,
                    "score": {
                        "opening_attraction": random.randint(80, 95),
                        "resonance": random.randint(85, 98),
                        "professional_value": random.randint(75, 90),
                        "consultation_potential": random.randint(80, 95),
                        "advertising_control": random.randint(90, 100),
                        "total": random.randint(82, 96)
                    }
                }, ensure_ascii=False)

            elif "Compliance Expert" in prompt or "合规审核" in prompt:
                return json.dumps({
                    "pass": True,
                    "risk_score": random.randint(5, 25),
                    "medical_risk": random.randint(0, 15),
                    "advertising_risk": random.randint(0, 10),
                    "platform_risk": random.randint(0, 10),
                    "problems": [],
                    "suggestions": ["建议增加更多生活案例", "整体合规性良好"],
                    "modified_text": ""
                }, ensure_ascii=False)

            elif "Video Expert" in prompt or "视频导演" in prompt:
                return json.dumps({
                    "voice_style": "温暖亲切",
                    "scene_plan": [
                        {"time": "0-3s", "action": "主播面向镜头微笑", "suggested_footage": "客厅场景"},
                        {"time": "3-23s", "action": "主播讲述生活故事", "suggested_footage": "厨房/卧室"},
                        {"time": "23-53s", "action": "主播分享健康知识", "suggested_footage": "客厅"},
                        {"time": "53-60s", "action": "主播引导互动", "suggested_footage": "近景"}
                    ],
                    "subtitle_style": "简洁清晰，白色字体",
                    "music": "轻柔背景音乐",
                    "editing_plan": "节奏适中，每段内容切换自然",
                    "cover_text": "45岁后必看的健康秘诀"
                }, ensure_ascii=False)

            elif "Operation Expert" in prompt or "运营专家" in prompt:
                topic = "健康"
                for line in prompt.split("\n"):
                    if "topic" in line.lower():
                        topic = line.split(":")[-1].strip()
                        break
                
                return json.dumps({
                    "titles": [
                        f"{topic}不好？这几个方法一定要试试",
                        f"45岁后，{topic}问题怎么解决？",
                        f"别再为{topic}发愁了，这样做效果最好"
                    ],
                    "hashtags": [f"{topic}", "健康生活", "女性健康", "养生", "中年女性", "健康知识", "生活方式", "健康管理", "自我提升", "正能量"],
                    "comment_strategy": [
                        "你们有没有类似的困扰？",
                        "欢迎在评论区分享你的经验",
                        "觉得有用的话记得点赞收藏"
                    ],
                    "private_message_guide": "如果你也有类似困扰，可以私信我交流一下"
                }, ensure_ascii=False)

            else:
                return json.dumps({"result": "AI处理完成"}, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


class AIExpertService:
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider or MockAIProvider()

    def content_expert(self, topic: str, user_profile: str = "") -> Dict[str, Any]:
        prompt = PromptLoader.load_prompt("content_expert")
        formatted_prompt = PromptLoader.format_prompt(
            prompt,
            topic=topic,
            user_profile=user_profile
        )
        result = self.ai_provider.generate_content(formatted_prompt)
        return json.loads(result)

    def planning_expert(self, content_result: Dict[str, Any]) -> Dict[str, Any]:
        prompt = PromptLoader.load_prompt("planning_expert")
        formatted_prompt = PromptLoader.format_prompt(
            prompt,
            content_result=json.dumps(content_result, ensure_ascii=False)
        )
        result = self.ai_provider.generate_content(formatted_prompt)
        return json.loads(result)

    def script_expert(self, topic: str, planning: Dict[str, Any]) -> Dict[str, Any]:
        prompt = PromptLoader.load_prompt("script_expert")
        formatted_prompt = PromptLoader.format_prompt(
            prompt,
            topic=topic,
            planning=json.dumps(planning, ensure_ascii=False)
        )
        result = self.ai_provider.generate_content(formatted_prompt)
        return json.loads(result)

    def compliance_expert(self, script: str) -> Dict[str, Any]:
        prompt = PromptLoader.load_prompt("compliance_expert")
        formatted_prompt = PromptLoader.format_prompt(
            prompt,
            script=script
        )
        result = self.ai_provider.generate_content(formatted_prompt)
        return json.loads(result)

    def video_expert(self, script: str) -> Dict[str, Any]:
        prompt = PromptLoader.load_prompt("video_expert")
        formatted_prompt = PromptLoader.format_prompt(
            prompt,
            script=script
        )
        result = self.ai_provider.generate_content(formatted_prompt)
        return json.loads(result)

    def operation_expert(self, topic: str, script: str) -> Dict[str, Any]:
        prompt = PromptLoader.load_prompt("operation_expert")
        formatted_prompt = PromptLoader.format_prompt(
            prompt,
            topic=topic,
            script=script[:500]
        )
        result = self.ai_provider.generate_content(formatted_prompt)
        return json.loads(result)
