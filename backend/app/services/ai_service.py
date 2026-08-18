from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import os
import re
import time
import logging
import httpx

try:
    from app.core.config import settings
except Exception:      # GPU worker 用独立 venv 加载本模块，无 pydantic_settings
    settings = None

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    @abstractmethod
    def generate_content(self, prompt: str, model: str = None) -> str:
        pass

    @abstractmethod
    def get_model_list(self) -> list:
        pass


class MockAIProvider(AIProvider):
    def generate_content(self, prompt: str, model: str = None) -> str:
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

    def get_model_list(self) -> list:
        return ["mock-gpt-4", "mock-claude-3"]


class OllamaProvider(AIProvider):
    """本机 Ollama 大模型。

    为什么需要：火山方舟的两把 key 都不可用（一把是 Agent Plan 编程套餐
    且配额耗尽，另一把账号未开通任何文本模型），而文案是产品的核心环节，
    不能长期依赖一个随时会断的外部服务。本机有 RTX 5090 与常驻 Ollama，
    跑 26B~30B 模型生成中文口播完全够用，还顺带满足「数据不出本机」。

    实测（script_expert 完整 prompt，要求输出结构化 JSON）：
      gemma4:26b       12s，JSON 可解析，口语化最自然  -> 默认
      qwen3-coder:30b   1s，速度最快但文风偏硬        -> 备选
      deepseek-r1:32b  60s 且强制输出思维链           -> 不适合

    ⚠️ 必须传 format=json：不传时模型会在 JSON 前后掺入解释文字与
    ```json 围栏，导致上层 json.loads 直接失败（实测必现）。
    """

    def __init__(self):
        # ⚠️ 不要在这里依赖 settings：本类会被 GPU worker 用 .venv_lipsync
        # 单独加载，那个环境没有 pydantic_settings，导入即失败。
        # 配置一律走环境变量，缺省值写死。
        self.base_url = (os.environ.get("OLLAMA_URL")
                         or "http://127.0.0.1:11434").rstrip("/")
        self.default_model = os.environ.get("OLLAMA_MODEL", "gemma4:26b")
        self.timeout = float(os.environ.get("OLLAMA_TIMEOUT", "600"))

    def _post(self, path: str, payload: dict):
        # 绕开系统代理：本机回环地址走代理会直接连不上
        transport = httpx.HTTPTransport(retries=0)
        with httpx.Client(timeout=self.timeout, trust_env=False,
                          transport=transport) as client:
            return client.post(self.base_url + path, json=payload)

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=5, trust_env=False) as client:
                r = client.get(self.base_url + "/api/tags")
            if r.status_code != 200:
                return False
            names = [m.get("name", "") for m in r.json().get("models", [])]
            base = self.default_model.split(":")[0]
            return any(base in n for n in names)
        except Exception:
            return False

    def generate_content(self, prompt: str, model: str = None) -> str:
        payload = {
            "model": model or self.default_model,
            "prompt": prompt,
            "stream": False,
            # 关掉思维链：推理模型会把草稿也输出，污染 JSON
            "think": False,
            # 强制 JSON，见类注释
            "format": "json",
            "options": {"temperature": 0.85, "num_predict": 2048},
        }
        try:
            resp = self._post("/api/generate", payload)
            resp.raise_for_status()
            text = (resp.json() or {}).get("response", "").strip()
        except Exception as e:
            logger.error("OllamaProvider 调用失败: %s", e)
            return json.dumps(
                {"error": f"ollama_failed: {type(e).__name__}: {e}"},
                ensure_ascii=False)

        if not text:
            return json.dumps({"error": "ollama_empty_response"},
                              ensure_ascii=False)
        # 已要求 format=json，但仍做一次容错清理（模型偶发加围栏）
        return _strip_json_fence(text)

    def get_model_list(self) -> list:
        try:
            with httpx.Client(timeout=10, trust_env=False) as client:
                r = client.get(self.base_url + "/api/tags")
            return [m.get("name") for m in r.json().get("models", [])]
        except Exception:
            return [self.default_model]


class RemoteOllamaProvider(AIProvider):
    """线上后端 -> 反向隧道 -> 本机 GPU worker 的 /llm 端点。

    Ollama 只跑在本机（生产服务器没有 GPU），而 worker 已经有一条保活隧道，
    所以复用它，不再单独暴露 11434 端口。
    与 local_tts 的远程派发同一个思路与同一条通道。
    """

    def __init__(self):
        self.base_url = (os.environ.get("LLM_REMOTE_HTTP")
                         or getattr(settings, "LLM_REMOTE_HTTP", None)
                         or getattr(settings, "TTS_REMOTE_HTTP", None)
                         or "").rstrip("/")
        self.model = (os.environ.get("OLLAMA_MODEL")
                      or getattr(settings, "OLLAMA_MODEL", None) or "")
        self.timeout = float(os.environ.get("LLM_HTTP_TIMEOUT", "900"))
        if not self.base_url:
            raise ValueError("LLM_REMOTE_HTTP / TTS_REMOTE_HTTP 未配置")

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=8, trust_env=False) as c:
                r = c.get(self.base_url + "/health")
            return r.status_code == 200 and bool(r.json().get("llm_available"))
        except Exception as e:
            logger.warning("远程 LLM 探活失败: %s", e)
            return False

    def generate_content(self, prompt: str, model: str = None) -> str:
        data = {"prompt": prompt}
        if model or self.model:
            data["model"] = model or self.model
        try:
            with httpx.Client(timeout=self.timeout, trust_env=False) as c:
                r = c.post(self.base_url + "/llm", data=data)
            if r.status_code != 200:
                logger.error("远程 LLM HTTP %s: %s", r.status_code, r.text[:200])
                return json.dumps(
                    {"error": f"remote_llm_http_{r.status_code}"},
                    ensure_ascii=False)
            text = (r.json() or {}).get("response", "").strip()
        except Exception as e:
            logger.error("远程 LLM 调用失败: %s", e)
            return json.dumps({"error": f"remote_llm_failed: {type(e).__name__}"},
                              ensure_ascii=False)
        if not text:
            return json.dumps({"error": "remote_llm_empty"}, ensure_ascii=False)
        return _strip_json_fence(text)

    def get_model_list(self) -> list:
        return [self.model] if self.model else []


def _strip_json_fence(text: str) -> str:
    """剥掉 ```json 围栏与 JSON 前后的解说文字，尽量交出可解析的 JSON。"""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    # 只截取最外层花括号，丢掉模型自作主张的前后说明
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        return t[start:end + 1]
    return t


class _RetryableHTTPError(Exception):
    """可重试的 HTTP 状态（限流与服务端错误）。"""

    def __init__(self, status_code: int, retry_after=None):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after


class AIQuotaExceededError(Exception):
    """配额耗尽。与限流不同：重试没有意义，必须换 key 或等配额重置。"""


def _quota_exceeded(resp) -> Optional[str]:
    """识别配额耗尽。火山方舟用 429 同时表达「限流」与「配额用尽」，
    但后者重试毫无意义（实测 4 次退避白等 15s），必须区分开。"""
    try:
        err = (resp.json() or {}).get("error") or {}
    except Exception:
        return None
    code = str(err.get("code") or "")
    msg = str(err.get("message") or "")
    if "QuotaExceeded" in code or "quota" in msg.lower():
        return msg or code
    return None


class ArkProvider(AIProvider):
    """火山方舟 Agent Plan (OpenAI 兼容 Responses API)."""

    def __init__(self):
        self.base_url = (settings.ARK_BASE_URL or "").rstrip("/")
        self.api_key = settings.ARK_API_KEY
        self.default_model = settings.ARK_MODEL or "ark-code-latest"
        self.timeout = settings.ARK_TIMEOUT
        # 限流场景下 2 次、间隔 1s 远远不够，实测直连成功但经本 provider 却 429
        self.max_attempts = int(os.environ.get("ARK_MAX_ATTEMPTS", "4"))
        self.retry_base_delay = float(os.environ.get("ARK_RETRY_BASE_DELAY", "2"))
        if not self.base_url or not self.api_key:
            raise ValueError("ARK_BASE_URL / ARK_API_KEY 未配置")

    def generate_content(self, prompt: str, model: str = None) -> str:
        url = f"{self.base_url}/responses"
        payload = {
            "model": model or self.default_model,
            "input": prompt,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # 重试策略：原实现只重试 1 次且固定 sleep(1)，对 429 限流几乎无效 ——
        # 两次请求间隔太短会继续撞在限流窗口里，结果整条链路降级到 mock，
        # 用户拿到的是写死的模板文案（表现为"文案不是实时创作的"）。
        # 现在区分限流与其他错误：429/5xx 做指数退避并尊重 Retry-After。
        last_err: Optional[Exception] = None
        for attempt in range(self.max_attempts):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    quota_msg = _quota_exceeded(resp)
                    if quota_msg:
                        raise AIQuotaExceededError(quota_msg)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise _RetryableHTTPError(resp.status_code,
                                              resp.headers.get("Retry-After"))
                resp.raise_for_status()
                data = resp.json()
                # Responses API: output[].content[].text (type=output_text)
                for item in data.get("output", []):
                    if item.get("type") == "message":
                        for c in item.get("content", []):
                            if c.get("type") == "output_text":
                                return c.get("text", "")
                # 兜底: 返回原始 JSON 字符串, 让上层 json.loads 尝试解析
                return json.dumps(data, ensure_ascii=False)
            except AIQuotaExceededError as e:
                # 配额耗尽，重试只会白等。直接返回，让上层给出准确提示。
                logger.error("Ark 配额耗尽，无法生成内容: %s", e)
                return json.dumps(
                    {"error": f"ai_quota_exceeded: {e}"}, ensure_ascii=False)
            except Exception as e:
                last_err = e
                if attempt < self.max_attempts - 1:
                    delay = self._retry_delay(e, attempt)
                    logger.warning(
                        "ArkProvider 第 %s/%s 次失败(%s)，%.1fs 后重试",
                        attempt + 1, self.max_attempts, type(e).__name__, delay)
                    time.sleep(delay)
                    continue
                logger.error(
                    "ArkProvider 调用失败 (%s 次)，将降级为模板文案: %s",
                    self.max_attempts, e)
                return json.dumps(
                    {"error": f"ark_provider_failed: {type(e).__name__}: {e}"},
                    ensure_ascii=False)
        return json.dumps({"error": f"ark_provider_unreachable: {last_err}"},
                          ensure_ascii=False)

    def _retry_delay(self, err: Exception, attempt: int) -> float:
        """退避时长。限流优先按服务端 Retry-After，否则指数退避加抖动。"""
        import random
        if isinstance(err, _RetryableHTTPError) and err.retry_after:
            try:
                return min(float(err.retry_after), 30.0)
            except (TypeError, ValueError):
                pass
        base = self.retry_base_delay * (2 ** attempt)
        return min(base + random.uniform(0, 0.5), 30.0)

    def get_model_list(self) -> list:
        return [self.default_model]


class AIService:
    PROVIDERS = {
        "mock": MockAIProvider,
        "ark": ArkProvider,
        "ollama": OllamaProvider,
        "remote_ollama": RemoteOllamaProvider,
    }

    def __init__(self, provider: str = None, model: str = None):
        # 默认从 settings.AI_PROVIDER 读, 允许显式覆盖
        provider = provider or settings.AI_PROVIDER or "mock"
        self.provider_cls = self.PROVIDERS.get(provider)
        if not self.provider_cls:
            raise ValueError(f"Unknown AI provider: {provider}")
        try:
            self.provider = self.provider_cls()
        except Exception as e:
            # provider 初始化失败 (如缺 key) 回退到 mock, 避免整个应用起不来
            logger.warning("AI provider %s init failed (%s), fallback to mock", provider, e)
            self.provider = MockAIProvider()
            provider = "mock"
        self.provider_name = provider
        self.model = model
        self._call_history = []

    def generate(self, prompt: str) -> Dict[str, Any]:
        start_time = time.time()
        result = self.provider.generate_content(prompt, self.model)
        duration = time.time() - start_time

        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            parsed = {"raw": result}

        self._call_history.append({
            "prompt": prompt[:200],
            "duration": round(duration, 2),
            "has_error": "error" in parsed,
        })

        return parsed

    def get_call_stats(self) -> Dict[str, Any]:
        if not self._call_history:
            return {"total_calls": 0, "avg_duration": 0, "error_count": 0}
        total = len(self._call_history)
        avg_duration = sum(c["duration"] for c in self._call_history) / total
        error_count = sum(1 for c in self._call_history if c["has_error"])
        return {
            "total_calls": total,
            "avg_duration": round(avg_duration, 2),
            "error_count": error_count,
        }

    @classmethod
    def list_providers(cls) -> list:
        return list(cls.PROVIDERS.keys())
