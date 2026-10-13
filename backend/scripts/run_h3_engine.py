# -*- coding: utf-8 -*-
"""
run_h3_engine.py — H3 画面生成引擎的独立命令行入口（project-Phoenix）

用途：不依赖 FastAPI/DB，用 .venv_lipsync 直接跑 H3 讲解视频生成，
     便于任务系统/脚本以子进程方式调用，也方便人工验证。

用法：
  .venv_lipsync/Scripts/python.exe scripts/run_h3_engine.py \
      --person D:/path/person.png \
      --script D:/path/copy.txt \
      --scene park_walk \
      --out D:/path/final.mp4 \
      [--anchor D:/path/scene.jpg] [--width 512] [--height 960]
      [--hair "..."] [--person-tts-ref D:/phx_tts/ref.wav]

--scene 可传场景预设名(park_walk/lecture/teahouse/street_walk)或直接英文描述。
"""
import argparse, importlib.util, sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _load(mod_name, file_name):
    p = BACKEND / "app" / "services" / file_name
    spec = importlib.util.spec_from_file_location(mod_name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", required=True)
    ap.add_argument("--script", required=True, help="文案文本文件(UTF-8)")
    ap.add_argument("--scene", required=True, help="场景预设名或英文描述")
    ap.add_argument("--out", default=None, help="输出 mp4；默认 storage/footage/h3/")
    ap.add_argument("--anchor", default=None, help="可选：人工选定的统一场景定场帧")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--hair", default="")
    ap.add_argument("--seed", type=int, default=400000)
    ap.add_argument("--tts-ref", dest="tts_ref", default=None, help="CosyVoice 参考音色 wav")
    a = ap.parse_args()

    engine_mod = _load("h3_video_engine", "h3_video_engine.py")
    if a.tts_ref:
        import os
        os.environ["H3_REF_WAV"] = a.tts_ref

    eng = engine_mod.H3VideoEngine(BACKEND / "storage")
    if not eng.available():
        print("ERROR: ComfyUI 不在线（8188），请先启动 ComfyUI", file=sys.stderr)
        sys.exit(2)

    scene = engine_mod.SCENE_PRESETS.get(a.scene, a.scene)
    text = Path(a.script).read_text(encoding="utf-8")
    out = a.out
    if out:
        from pathlib import Path as P
        P(out).parent.mkdir(parents=True, exist_ok=True)

    result = eng.generate(
        person_image=a.person, script_text=text, scene=scene,
        anchor_image=a.anchor, width=a.width, height=a.height,
        hair_hint=a.hair, seed=a.seed,
    )
    if out:
        import shutil
        shutil.copyfile(result, out)
        result = P(out)
    print("OK", result)


if __name__ == "__main__":
    main()
