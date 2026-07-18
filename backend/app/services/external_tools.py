"""
外部AI能力封装层

TASK-016.3B.1: AI Agent Tool Gateway

封装各种外部AI服务，统一通过ToolRegistry注册和调用。

支持的工具：
1. Whisper - 语音转文字
2. LLM - 大语言模型
3. VideoAnalysis - 视频理解
4. ImageGenerator - 图片生成
5. FFmpeg - 视频处理
6. AudioProcessing - 音频处理
"""

import os
import subprocess
import tempfile
from typing import Dict, Any, Optional, List

from app.services.tool_registry import (
    BaseTool,
    ToolParameter,
    ToolCategory,
)


class WhisperTool(BaseTool):
    """Whisper语音转文字工具"""

    NAME = "whisper_transcribe"
    DESCRIPTION = "使用Whisper模型将音频文件转录为文字"
    CATEGORY = ToolCategory.AUDIO
    PARAMETERS = [
        ToolParameter(
            name="audio_path",
            type="string",
            description="音频文件路径",
            required=True,
        ),
        ToolParameter(
            name="language",
            type="string",
            description="语言代码（zh/en/ja等）",
            required=False,
            default="zh",
        ),
        ToolParameter(
            name="model",
            type="string",
            description="模型大小（tiny/base/small/medium/large）",
            required=False,
            default="base",
        ),
    ]
    PROVIDER = "OpenAI Whisper"
    COST = 0.0

    def execute(self, **kwargs) -> Dict[str, Any]:
        audio_path = kwargs.get("audio_path")
        language = kwargs.get("language", "zh")
        model = kwargs.get("model", "base")

        if not audio_path or not os.path.exists(audio_path):
            return {"error": "Audio file not found"}

        try:
            command = [
                "whisper",
                audio_path,
                "--language", language,
                "--model", model,
                "--output_format", "json",
                "--verbose", "False",
            ]

            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                return {"error": result.stderr}

            import json

            output_dir = os.path.dirname(audio_path)
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            json_path = os.path.join(output_dir, f"{base_name}.json")

            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    data = json.load(f)
                return data

            return {"error": "Output file not generated"}

        except Exception as e:
            return {"error": str(e)}


class LLMCompletionTool(BaseTool):
    """LLM文本生成工具"""

    NAME = "llm_completion"
    DESCRIPTION = "调用大语言模型生成文本"
    CATEGORY = ToolCategory.AI
    PARAMETERS = [
        ToolParameter(
            name="prompt",
            type="string",
            description="提示词",
            required=True,
        ),
        ToolParameter(
            name="model",
            type="string",
            description="模型名称",
            required=False,
            default="gpt-4o-mini",
        ),
        ToolParameter(
            name="max_tokens",
            type="integer",
            description="最大token数",
            required=False,
            default=512,
        ),
        ToolParameter(
            name="temperature",
            type="float",
            description="温度参数（0-2）",
            required=False,
            default=0.7,
        ),
    ]
    PROVIDER = "OpenAI"
    COST = 0.001

    def execute(self, **kwargs) -> Dict[str, Any]:
        prompt = kwargs.get("prompt")
        model = kwargs.get("model", "gpt-4o-mini")
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.7)

        if not prompt:
            return {"error": "Prompt is required"}

        try:
            import openai

            client = openai.OpenAI()

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            return {
                "text": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

        except ImportError:
            return {"error": "OpenAI not installed", "fallback": prompt}
        except Exception as e:
            return {"error": str(e), "fallback": prompt}


class VideoAnalysisTool(BaseTool):
    """视频理解工具"""

    NAME = "video_analysis"
    DESCRIPTION = "分析视频内容，提取关键信息"
    CATEGORY = ToolCategory.VIDEO
    PARAMETERS = [
        ToolParameter(
            name="video_path",
            type="string",
            description="视频文件路径",
            required=True,
        ),
        ToolParameter(
            name="features",
            type="string",
            description="分析特征（faces/scenes/objects/audio/all）",
            required=False,
            default="all",
        ),
    ]
    PROVIDER = "OpenCV/PySceneDetect"
    COST = 0.0

    def execute(self, **kwargs) -> Dict[str, Any]:
        video_path = kwargs.get("video_path")
        features = kwargs.get("features", "all")

        if not video_path or not os.path.exists(video_path):
            return {"error": "Video file not found"}

        try:
            result = {
                "video_path": video_path,
                "features": features,
                "analysis": {},
            }

            if features in ("all", "scenes"):
                try:
                    from scenedetect import SceneManager, open_video, ContentDetector

                    video = open_video(video_path)
                    scene_manager = SceneManager()
                    scene_manager.add_detector(ContentDetector())
                    scene_manager.detect_scenes(video)
                    scenes = scene_manager.get_scene_list()

                    result["analysis"]["scenes"] = [
                        {
                            "start_frame": scene[0].get_frames(),
                            "end_frame": scene[1].get_frames(),
                            "start_time": scene[0].get_seconds(),
                            "end_time": scene[1].get_seconds(),
                        }
                        for scene in scenes
                    ]
                except ImportError:
                    result["analysis"]["scenes"] = ["PySceneDetect not installed"]

            if features in ("all", "faces"):
                try:
                    import cv2

                    face_cascade = cv2.CascadeClassifier(
                        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                    )

                    cap = cv2.VideoCapture(video_path)
                    face_count = 0
                    fps = cap.get(cv2.CAP_PROP_FPS)

                    while cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            break
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                        if len(faces) > 0:
                            face_count += 1
                        cap.set(cv2.CAP_PROP_POS_FRAMES, cap.get(cv2.CAP_PROP_POS_FRAMES) + int(fps))

                    cap.release()
                    result["analysis"]["faces_detected"] = face_count > 0
                    result["analysis"]["face_frames"] = face_count

                except ImportError:
                    result["analysis"]["faces"] = ["OpenCV not installed"]

            result["success"] = True
            return result

        except Exception as e:
            return {"error": str(e)}


class ImageGeneratorTool(BaseTool):
    """图片生成工具"""

    NAME = "image_generate"
    DESCRIPTION = "使用AI生成图片"
    CATEGORY = ToolCategory.IMAGE
    PARAMETERS = [
        ToolParameter(
            name="prompt",
            type="string",
            description="图片描述",
            required=True,
        ),
        ToolParameter(
            name="size",
            type="string",
            description="图片尺寸（1024x1024/1024x1792等）",
            required=False,
            default="1024x1024",
        ),
        ToolParameter(
            name="model",
            type="string",
            description="生成模型（dall-e-3/stable-diffusion）",
            required=False,
            default="dall-e-3",
        ),
    ]
    PROVIDER = "OpenAI DALL-E"
    COST = 0.04

    def execute(self, **kwargs) -> Dict[str, Any]:
        prompt = kwargs.get("prompt")
        size = kwargs.get("size", "1024x1024")
        model = kwargs.get("model", "dall-e-3")

        if not prompt:
            return {"error": "Prompt is required"}

        try:
            import openai

            client = openai.OpenAI()

            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
            )

            return {
                "url": response.data[0].url,
                "revised_prompt": response.data[0].revised_prompt,
            }

        except ImportError:
            return {
                "error": "OpenAI not installed",
                "fallback_url": f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={prompt}&image_size=square_hd",
            }
        except Exception as e:
            return {
                "error": str(e),
                "fallback_url": f"https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt={prompt}&image_size=square_hd",
            }


class FFmpegTool(BaseTool):
    """FFmpeg视频处理工具"""

    NAME = "ffmpeg_process"
    DESCRIPTION = "使用FFmpeg处理视频（裁剪、合并、转码等）"
    CATEGORY = ToolCategory.MEDIA
    PARAMETERS = [
        ToolParameter(
            name="input_path",
            type="string",
            description="输入视频路径",
            required=True,
        ),
        ToolParameter(
            name="output_path",
            type="string",
            description="输出视频路径",
            required=True,
        ),
        ToolParameter(
            name="operation",
            type="string",
            description="操作类型（trim/merge/resize/extract_audio/add_audio/watermark）",
            required=True,
        ),
        ToolParameter(
            name="start_time",
            type="float",
            description="开始时间（秒）",
            required=False,
        ),
        ToolParameter(
            name="duration",
            type="float",
            description="持续时间（秒）",
            required=False,
        ),
        ToolParameter(
            name="width",
            type="integer",
            description="目标宽度",
            required=False,
        ),
        ToolParameter(
            name="height",
            type="integer",
            description="目标高度",
            required=False,
        ),
        ToolParameter(
            name="audio_path",
            type="string",
            description="音频文件路径",
            required=False,
        ),
        ToolParameter(
            name="watermark_text",
            type="string",
            description="水印文字",
            required=False,
        ),
    ]
    PROVIDER = "FFmpeg"
    COST = 0.0

    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_path")
        output_path = kwargs.get("output_path")
        operation = kwargs.get("operation")

        if not input_path or not os.path.exists(input_path):
            return {"error": "Input file not found"}

        if not output_path:
            return {"error": "Output path is required"}

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            command = ["ffmpeg", "-y", "-i", input_path]

            if operation == "trim":
                start_time = kwargs.get("start_time", 0)
                duration = kwargs.get("duration")
                if duration:
                    command.extend(["-ss", str(start_time), "-t", str(duration)])
                else:
                    command.extend(["-ss", str(start_time)])

            elif operation == "resize":
                width = kwargs.get("width")
                height = kwargs.get("height")
                if width and height:
                    command.extend(["-vf", f"scale={width}:{height}"])

            elif operation == "extract_audio":
                command.extend(["-vn", "-acodec", "copy"])

            elif operation == "add_audio":
                audio_path = kwargs.get("audio_path")
                if audio_path and os.path.exists(audio_path):
                    command.extend(["-i", audio_path])
                    command.extend(["-c:v", "copy", "-c:a", "aac"])

            elif operation == "watermark":
                watermark_text = kwargs.get("watermark_text", "")
                if watermark_text:
                    command.extend([
                        "-vf",
                        f"drawtext=text='{watermark_text}':fontsize=24:fontcolor=white:x=10:y=10",
                    ])

            command.append(output_path)

            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "output_path": output_path,
                    "operation": operation,
                }
            else:
                return {"error": result.stderr}

        except Exception as e:
            return {"error": str(e)}


class AudioProcessingTool(BaseTool):
    """音频处理工具"""

    NAME = "audio_processing"
    DESCRIPTION = "音频处理（降噪、变调、音量调整）"
    CATEGORY = ToolCategory.AUDIO
    PARAMETERS = [
        ToolParameter(
            name="input_path",
            type="string",
            description="输入音频路径",
            required=True,
        ),
        ToolParameter(
            name="output_path",
            type="string",
            description="输出音频路径",
            required=True,
        ),
        ToolParameter(
            name="operation",
            type="string",
            description="操作类型（noise_reduction/change_pitch/volume/adjust_speed）",
            required=True,
        ),
        ToolParameter(
            name="volume_gain",
            type="float",
            description="音量增益（dB）",
            required=False,
        ),
        ToolParameter(
            name="pitch_shift",
            type="integer",
            description="音调偏移（半音）",
            required=False,
        ),
        ToolParameter(
            name="speed_factor",
            type="float",
            description="速度因子",
            required=False,
            default=1.0,
        ),
    ]
    PROVIDER = "FFmpeg/AudioProcessing"
    COST = 0.0

    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_path")
        output_path = kwargs.get("output_path")
        operation = kwargs.get("operation")

        if not input_path or not os.path.exists(input_path):
            return {"error": "Input file not found"}

        if not output_path:
            return {"error": "Output path is required"}

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            command = ["ffmpeg", "-y", "-i", input_path]

            if operation == "volume":
                gain = kwargs.get("volume_gain", 0)
                command.extend(["-af", f"volume={gain}dB"])

            elif operation == "change_pitch":
                pitch = kwargs.get("pitch_shift", 0)
                command.extend(["-af", f"asetrate=44100*{2**(pitch/12)},aresample=44100"])

            elif operation == "adjust_speed":
                speed = kwargs.get("speed_factor", 1.0)
                command.extend(["-af", f"atempo={speed}"])

            elif operation == "noise_reduction":
                command.extend(["-af", "highpass=f=200,lowpass=f=3000"])

            command.append(output_path)

            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "output_path": output_path,
                    "operation": operation,
                }
            else:
                return {"error": result.stderr}

        except Exception as e:
            return {"error": str(e)}


def register_all_tools():
    """注册所有工具"""
    tools = [
        WhisperTool(),
        LLMCompletionTool(),
        VideoAnalysisTool(),
        ImageGeneratorTool(),
        FFmpegTool(),
        AudioProcessingTool(),
    ]

    for tool in tools:
        tool.register()

    return tools
