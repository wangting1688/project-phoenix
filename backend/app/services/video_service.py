import os
import json
import random
from typing import Dict, List, Any


class VideoCompositionService:
    """视频合成服务 - 将文案+素材合成为最终视频"""

    def __init__(self):
        self.storage_path = os.path.join(os.path.dirname(__file__), "..", "..", "storage")
        self.output_path = os.path.join(self.storage_path, "output")
        os.makedirs(self.output_path, exist_ok=True)

    def analyze_script(self, script: str) -> Dict[str, Any]:
        """分析脚本，提取关键词用于素材匹配"""
        keywords = []
        scene_map = {
            "睡眠": ["卧室", "夜晚", "床", "枕头"],
            "厨房": ["厨房", "做饭", "灶台"],
            "家庭": ["客厅", "沙发", "家人"],
            "运动": ["公园", "户外", "操场"],
            "喝茶": ["茶室", "茶杯", "桌子"],
            "散步": ["户外", "公园", "小路"],
            "焦虑": ["窗边", "天空", "思考"],
            "健康": ["厨房", "客厅", "水杯"],
            "养生": ["茶室", "厨房", "客厅"],
            "气血": ["厨房", "餐桌"],
            "肠胃": ["厨房", "餐桌", "餐厅"],
            "更年期": ["客厅", "卧室", "沙发"],
        }

        scenes = set()
        for keyword, scene_list in scene_map.items():
            if keyword in script:
                scenes.update(scene_list)

        if not scenes:
            scenes = {"客厅", "厨房", "卧室"}

        return {
            "keywords": list(scenes),
            "duration_estimate": len(script) // 4,  # 约每4字1秒
            "scene_count": max(4, len(script) // 60),
        }

    def match_footages(
        self, script_analysis: Dict, footages: List[Dict]
    ) -> List[Dict]:
        """根据脚本分析匹配素材"""
        keywords = set(script_analysis["keywords"])
        matched = []

        for footage in footages:
            score = 0
            if footage.get("scene") and footage["scene"] in keywords:
                score += 3
            if footage.get("topics"):
                for t in footage["topics"]:
                    if any(k in t for k in keywords):
                        score += 2
            if footage.get("emotion"):
                score += 1
            if score > 0:
                matched.append({**footage, "match_score": score})

        matched.sort(key=lambda x: x["match_score"], reverse=True)

        needed = script_analysis["scene_count"]
        if len(matched) < needed:
            for f in footages:
                if f not in matched:
                    matched.append({**f, "match_score": 0})
                    if len(matched) >= needed:
                        break

        return matched[:needed]

    def generate_subtitle(self, script: str) -> List[Dict[str, str]]:
        """生成字幕时间轴"""
        sentences = []
        current = ""
        for char in script:
            current += char
            if char in "。！？!?\n" and len(current) > 5:
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())

        subtitles = []
        time_offset = 0
        for s in sentences:
            duration = max(2, len(s) // 4)
            subtitles.append({
                "text": s,
                "start": f"{int(time_offset // 60):02d}:{int(time_offset % 60):02d}",
                "end": f"{int((time_offset + duration) // 60):02d}:{int((time_offset + duration) % 60):02d}",
                "start_sec": time_offset,
                "end_sec": time_offset + duration,
            })
            time_offset += duration

        return subtitles

    def generate_tts_config(self, script: str, voice_style: str = "warm") -> Dict:
        """生成TTS语音配置"""
        voice_map = {
            "warm": {"voice": "female_warm", "speed": 0.9, "pitch": 0},
            "professional": {"voice": "female_calm", "speed": 1.0, "pitch": 0},
            "casual": {"voice": "female_friendly", "speed": 1.0, "pitch": 1},
        }
        config = voice_map.get(voice_style, voice_map["warm"])
        return {
            "text": script,
            "voice": config["voice"],
            "speed": config["speed"],
            "pitch": config["pitch"],
            "format": "mp3",
            "sample_rate": 16000,
        }

    def generate_bgm_config(self, emotion: str = "calm") -> Dict:
        """生成背景音乐配置"""
        bgm_map = {
            "calm": {"style": "轻柔钢琴", "volume": 0.15},
            "warm": {"style": "温暖吉他", "volume": 0.20},
            "energetic": {"style": "轻快电子", "volume": 0.15},
            "sad": {"style": "悲伤弦乐", "volume": 0.10},
        }
        return bgm_map.get(emotion, bgm_map["calm"])

    def generate_cover_config(self, title: str, topic: str) -> Dict:
        """生成封面配置"""
        return {
            "title": title[:20] if len(title) > 20 else title,
            "subtitle": topic[:15] if len(topic) > 15 else topic,
            "bg_color": "#667eea",
            "text_color": "#ffffff",
            "font_size": 48,
            "format": "png",
            "size": "1080x1920",
        }

    def build_composition_plan(
        self,
        script: str,
        footages: List[Dict],
        voice_style: str = "warm",
        emotion: str = "calm",
    ) -> Dict[str, Any]:
        """构建完整的视频合成方案"""
        analysis = self.analyze_script(script)
        matched = self.match_footages(analysis, footages)
        subtitles = self.generate_subtitle(script)
        tts_config = self.generate_tts_config(script, voice_style)
        bgm_config = self.generate_bgm_config(emotion)

        title = script[:30].replace("\n", " ") + "..." if len(script) > 30 else script
        cover_config = self.generate_cover_config(title, analysis["keywords"][0] if analysis["keywords"] else "")

        scene_plan = []
        current_time = 0
        for i, footage in enumerate(matched):
            duration = subtitles[-1]["end_sec"] // len(matched) if matched else 10
            scene_plan.append({
                "index": i + 1,
                "footage_id": footage.get("id"),
                "footage_path": footage.get("file_path"),
                "start": current_time,
                "duration": duration,
                "subtitles": [s for s in subtitles if current_time <= s["start_sec"] < current_time + duration],
            })
            current_time += duration

        total_duration = subtitles[-1]["end_sec"] if subtitles else 60

        return {
            "script_analysis": analysis,
            "scene_plan": scene_plan,
            "subtitles": subtitles,
            "tts_config": tts_config,
            "bgm_config": bgm_config,
            "cover_config": cover_config,
            "total_duration": total_duration,
            "output_format": {
                "resolution": "1080x1920",
                "aspect_ratio": "9:16",
                "video_codec": "h264",
                "audio_codec": "aac",
                "container": "mp4",
                "fps": 30,
            },
            "ffmpeg_commands": self._build_ffmpeg_commands(scene_plan, tts_config, bgm_config, subtitles),
        }

    def _build_ffmpeg_commands(
        self, scene_plan, tts_config, bgm_config, subtitles
    ) -> List[str]:
        """构建FFmpeg命令链"""
        commands = []

        # Step 1: 合并素材视频片段
        concat_files = " ".join([f"-i {s['footage_path']}" for s in scene_plan if s.get("footage_path")])
        if concat_files:
            commands.append(
                f"ffmpeg {concat_files} -filter_complex concat=n={len(scene_plan)}:v=1:a=0 -y temp_video.mp4"
            )

        # Step 2: 生成TTS音频 (占位，实际需要对接TTS服务)
        commands.append(
            f"# TTS: voice={tts_config['voice']} speed={tts_config['speed']}"
        )

        # Step 3: 生成字幕文件
        commands.append("# Generate SRT subtitle file")

        # Step 4: 合并视频+音频+字幕+背景音乐
        commands.append(
            f"ffmpeg -i temp_video.mp4 -i audio.mp3 -i bgm.mp3 "
            f"-filter_complex '[0:v]scale=1080:1920[v];"
            f"[1:a]volume=1.0[a1];[2:a]volume={bgm_config['volume']}[a2];"
            f"[a1][a2]amix=inputs=2[a]' "
            f"-map '[v]' -map '[a]' -c:v libx264 -c:a aac -y output.mp4"
        )

        # Step 5: 添加字幕
        commands.append(
            f"ffmpeg -i output.mp4 -vf subtitles=subtitles.srt -c:a copy -y final_output.mp4"
        )

        return commands

    def get_quality_score(self, plan: Dict) -> Dict[str, Any]:
        """评估视频质量评分"""
        scene_count = len(plan.get("scene_plan", []))
        subtitle_count = len(plan.get("subtitles", []))
        duration = plan.get("total_duration", 0)

        realism = min(100, 60 + scene_count * 10)
        info_value = min(100, 50 + subtitle_count * 5)
        # 节奏评分：30-90秒为最佳范围，过短或过长适度扣分
        if 30 <= duration <= 90:
            rhythm = 95
        elif 15 <= duration < 30:
            rhythm = 80
        elif duration > 90:
            rhythm = max(60, 95 - (duration - 90) * 2)
        else:
            rhythm = 60
        subtitle_quality = 85
        risk = 90

        total = (
            realism * 0.30
            + info_value * 0.25
            + rhythm * 0.20
            + subtitle_quality * 0.15
            + risk * 0.10
        )

        return {
            "realism": realism,
            "info_value": info_value,
            "rhythm": rhythm,
            "subtitle_quality": subtitle_quality,
            "risk_safety": risk,
            "total": round(total, 1),
            "pass": total >= 80,
        }


video_service = VideoCompositionService()
