# -*- coding: utf-8 -*-
"""
口型同步后处理：嘴部细节复原 + 口型动力学微调。

来源：移植自「罗根视频生成」项目（D:/luogen_demo/pipeline/postprocess.py），
该项目经 4 轮参数调优 + 定量验证后锁定本文件中的常量，请勿凭直觉改动。

为什么需要它（病根不是模型能力，而是分辨率损失）：
  LatentSync 把人脸裁剪强制缩放到 512 做推理，再放大贴回原画面。
  实测嘴部在模型内只有约 129px，高频细节损失约 38%，
  生成嘴部的高频能量仅为真实嘴部的 49% —— 这就是"嘴部发黑发糊"的来源。
  超分/调参都救不回来（信息量上限就在 512），但**原素材里有真实的唇纹和牙齿**，
  可以用光流对齐后把那层高频搬回来。

两个阶段（只动纹理与张合幅度，绝不改音频驱动的口型时序）：
  1. restore_mouth_detail  嘴部细节 49% -> 75%（流水线实测可达 92%）
  2. refine_lip_dynamics   张合幅度 0.747 -> 0.839（时序相关性保持 0.953）

Post-processing stage for the digital-human pipeline.

Two locked-in refinements, validated against the real source material:

  1. Mouth detail restoration  -- LatentSync resizes the face crop to 512 for
     inference, so mouth detail is lost. We transfer the high-frequency layer
     from the REAL source frame (optical-flow aligned) back into the generated
     mouth. Measured: mouth detail 49% -> 75% of real.

  2. Lip dynamics refinement   -- the generated mouth spreads only 0.747x as
     wide as the real speaker. We amplify the width curve's own deviation and
     apply it as a clipped, radially-decaying warp. Measured: 0.747 -> 0.839,
     while lip-sync timing correlation stays at 0.953.

Only high-frequency texture and lip *amplitude* are touched. The audio-driven
lip *timing* produced by the model is never altered.
"""
import os
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

# ---- locked-in parameters (user-approved: detail 0.75 + lip refine strong) ----
DETAIL_STRENGTH = 0.75
DETAIL_SIGMA_HF = 1.5
DETAIL_CLIP = 18.0
DETAIL_FEATHER = 21
DETAIL_PAD = 0.18

# ---- 嘴部亮度/色度校正（Phoenix 新增，解决"嘴部发黑发暗"）----
# 实测（LAB 的 L 通道，嘴部凸包内部）：真人 144.0 vs 生成 120.7，暗约 23 个单位。
# 这不是融合边缘的暗环（边缘-外侧差值三个版本接近），而是 UNet 重绘的
# 嘴内区域整体偏暗——扩散模型在低分辨率下倾向把口腔阴影画得过重。
# 做法：以「同帧未被模型触碰的脸颊皮肤」为锚，把生成嘴部的亮度统计
# 对齐到原素材同区域的相对关系。只做低频增益，不动已复原的高频细节。
TONE_CORRECT = True
TONE_STRENGTH = 0.85      # 校正强度，1.0 = 完全对齐原素材相对亮度
TONE_MAX_GAIN = 1.35      # 增益上限，防止过曝导致嘴部发白
TONE_MIN_GAIN = 0.95
TONE_FEATHER = 31         # 羽化半径，避免出现校正边界
TONE_CHROMA = 0.6         # a/b 色度校正比例（唇色偏灰时补回血色）

LIP_AMP_BOOST = 1.45     # applied on top of measured target/current ratio
LIP_AMP_CAP = 2.2
LIP_SCALE_MIN = 0.86
LIP_SCALE_MAX = 1.20
LIP_SHIFT_CAP = 10.0
LIP_CURVE_SMOOTH = 0.7
LIP_FEATHER = 27


def _frame_count(path):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


class _LazyFrames:
    """按索引随机读取视频帧，避免把整段素材读进内存。

    全分辨率(1088x2336)素材整段驻留约 3.9GB，配合生成帧的副本会耗尽物理内存
    （实测进程被系统直接杀掉，没有 traceback）。这里保留一个小 LRU，
    因为相邻生成帧往往映射到同一供体帧。
    """

    def __init__(self, path, n, cache=8):
        self._cap = cv2.VideoCapture(str(path))
        self._n = n
        self._cache = {}
        self._order = []
        self._limit = cache
        self._pos = None

    def __len__(self):
        return self._n

    def __getitem__(self, i):
        i = int(i)
        if i in self._cache:
            return self._cache[i]
        if self._pos != i:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = self._cap.read()
        self._pos = i + 1 if ok else None
        if not ok:
            raise IndexError(i)
        self._cache[i] = fr
        self._order.append(i)
        if len(self._order) > self._limit:
            self._cache.pop(self._order.pop(0), None)
        return fr


def read_video(path, limit=None):
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
        if limit and len(frames) >= limit:
            break
    cap.release()
    return frames


def extract_landmarks(video_path, cache_path=None, scale=0.5, log=print):
    """68-point landmarks per frame, cached to .npy."""
    if cache_path and os.path.exists(cache_path):
        lm = np.load(cache_path)
        log(f"    landmarks loaded from cache: {lm.shape}")
        return lm
    # torch 2.11 会尝试用 inductor 编译 face_alignment 的检测网络，
    # 而本 venv 没有 triton（Windows 无稳定 wheel）→ TritonMissing。
    # 关键点提取不是瓶颈，直接关掉编译走 eager 即可。
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
    os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")
    try:
        import torch._dynamo as _dynamo
        _dynamo.config.suppress_errors = True
        _dynamo.reset()
    except Exception:
        pass

    import face_alignment
    try:
        lt = face_alignment.LandmarksType.TWO_D
    except AttributeError:
        lt = face_alignment.LandmarksType._2D
    fa = face_alignment.FaceAlignment(lt, flip_input=False, device="cuda")
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out, last, i = [], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        preds = fa.get_landmarks(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        if preds:
            last = preds[0] / scale
        out.append((last if last is not None else np.zeros((68, 2), np.float32)).astype(np.float32))
        i += 1
        if i % 100 == 0:
            log(f"    landmarks {i}/{total}")
    cap.release()
    lm = np.stack(out)
    if cache_path:
        np.save(cache_path, lm)
    return lm


def _mouth_mask(lm_frame, shape, offset=(0, 0), dilate=9, iters=2, feather=21):
    h, w = shape
    m = np.zeros((h, w), np.uint8)
    pts = (lm_frame[48:68] - np.asarray(offset)).astype(np.int32)
    cv2.fillConvexPoly(m, cv2.convexHull(pts), 255)
    if dilate:
        m = cv2.dilate(m, np.ones((dilate, dilate), np.uint8), iterations=iters)
    k = feather | 1
    return (cv2.GaussianBlur(m, (k, k), 0).astype(np.float32) / 255.0)[..., None]


def restore_mouth_detail(gen_frames, src_video, lm_gen, lm_src,
                         fps_gen, fps_src, strength=DETAIL_STRENGTH, log=print,
                         frame_offset=0):
    """Transfer real high-frequency mouth texture onto generated frames.

    frame_offset lets the caller process the video in chunks: donor frames are
    picked by absolute timeline position, so a chunk starting at frame 96 still
    pulls the right source frame instead of restarting from zero.
    """
    n_total = _frame_count(src_video)
    if not n_total:
        raise RuntimeError(f"cannot read source video: {src_video}")
    src_frames = _LazyFrames(src_video, n_total)
    H, W = gen_frames[0].shape[:2]
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setUseSpatialPropagation(True)
    out = []
    # LatentSync loops the reference video (forward/reverse alternating) when the
    # audio is longer than the material. Mirror that mapping so the texture donor
    # is always the frame that actually appears underneath.
    n_src = len(src_frames)

    def donor_index(t):
        pos = t / fps_gen * fps_src
        if pos < n_src:
            return int(round(pos))
        cycle = int(pos // n_src)
        off = pos - cycle * n_src
        if cycle % 2 == 1:
            off = n_src - 1 - off
        return int(min(n_src - 1, max(0, round(off))))

    for t, g in enumerate(gen_frames):
        si = donor_index(t + frame_offset)
        if t >= len(lm_gen) or si >= len(lm_src):
            out.append(g)
            continue
        p = np.concatenate([lm_gen[t][48:68], lm_gen[t][5:12]], 0)
        x0, y0 = p.min(0)
        x1, y1 = p.max(0)
        mw, mh = x1 - x0, y1 - y0
        bx0 = max(0, int(x0 - mw * DETAIL_PAD)); bx1 = min(W, int(x1 + mw * DETAIL_PAD))
        by0 = max(0, int(y0 - mh * DETAIL_PAD)); by1 = min(H, int(y1 + mh * DETAIL_PAD))
        if bx1 - bx0 < 20 or by1 - by0 < 20:
            out.append(g)
            continue
        cx0, cy0 = max(0, bx0 - 60), max(0, by0 - 60)
        cx1, cy1 = min(W, bx1 + 60), min(H, by1 + 60)
        gg = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)
        sg = cv2.cvtColor(src_frames[si], cv2.COLOR_BGR2GRAY)
        fg = np.ascontiguousarray(gg[cy0:cy1, cx0:cx1])
        fs = np.ascontiguousarray(sg[cy0:cy1, cx0:cx1])
        flow = dis.calc(fg, fs, None)
        gx, gy = np.meshgrid(np.arange(fg.shape[1], dtype=np.float32),
                             np.arange(fg.shape[0], dtype=np.float32))
        warped = cv2.remap(src_frames[si][cy0:cy1, cx0:cx1],
                           gx + flow[..., 0], gy + flow[..., 1],
                           cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        wf = warped.astype(np.float32)
        hf = np.clip(wf - cv2.GaussianBlur(wf, (0, 0), DETAIL_SIGMA_HF),
                     -DETAIL_CLIP, DETAIL_CLIP)
        full = np.zeros((H, W, 3), np.float32)
        full[cy0:cy1, cx0:cx1] = hf
        mask = _mouth_mask(lm_gen[t], (H, W), feather=DETAIL_FEATHER)
        out.append(np.clip(g.astype(np.float32) + full * mask * strength, 0, 255).astype(np.uint8))
        if (t + 1) % 100 == 0:
            log(f"    detail {t + 1}/{len(gen_frames)}")
    return out


def _skin_anchor(L, lm_frame):
    """取同帧脸颊皮肤的亮度均值作为锚点。

    这块区域在眼下到鼻侧之间，LatentSync 的 mask 不覆盖它，
    因此它在生成帧与原素材帧中应当基本一致，可用来抵消
    整体曝光/色调差异，只测量出"嘴部被画暗了多少"。
    """
    ex, ey = lm_frame[36]
    nx, ny = lm_frame[31]
    x0, x1 = int(min(ex, nx)), int(max(ex, nx))
    y0 = int(ey + (ny - ey) * 0.25)
    y1 = int(ey + (ny - ey) * 0.90)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    patch = L[max(0, y0):y1, max(0, x0):x1]
    return float(patch.mean()) if patch.size else None


def correct_mouth_tone(gen_frames, src_video, lm_gen, lm_src,
                       fps_gen, fps_src, strength=TONE_STRENGTH, log=print,
                       frame_offset=0):
    """把生成嘴部的亮度/色度对齐回原素材的相对水平。

    以脸颊皮肤为锚，计算原素材"嘴部相对皮肤"的亮度比，再把生成帧
    按同一比例校正。增益是逐帧标量（低频），因此不会削弱 restore_mouth_detail
    补回来的高频纹理，也不会引入新的边界。
    """
    n_src = _frame_count(src_video)
    if not n_src:
        log("    tone correct skipped (source unreadable)")
        return gen_frames
    src_frames = _LazyFrames(src_video, n_src)

    def donor_index(t):
        pos = t / fps_gen * fps_src
        if pos < n_src:
            return int(round(pos))
        cycle = int(pos // n_src)
        off = pos - cycle * n_src
        if cycle % 2 == 1:
            off = n_src - 1 - off
        return int(min(n_src - 1, max(0, round(off))))

    H, W = gen_frames[0].shape[:2]
    out, gains = [], []
    for t, g in enumerate(gen_frames):
        si = donor_index(t + frame_offset)
        if t >= len(lm_gen) or si >= len(lm_src) or lm_gen[t].max() <= 0:
            out.append(g)
            continue

        glab = cv2.cvtColor(g, cv2.COLOR_BGR2LAB).astype(np.float32)
        slab = cv2.cvtColor(src_frames[si], cv2.COLOR_BGR2LAB).astype(np.float32)
        g_anchor = _skin_anchor(glab[..., 0], lm_gen[t])
        s_anchor = _skin_anchor(slab[..., 0], lm_src[si])
        if not g_anchor or not s_anchor:
            out.append(g)
            continue

        # 嘴部凸包内的均值（生成 vs 原素材），各自除以自身皮肤锚点后比较
        mask_g = _mouth_mask(lm_gen[t], (H, W), dilate=5, iters=1,
                             feather=TONE_FEATHER)[..., 0]
        sel_g = mask_g > 0.5
        sh, sw = slab.shape[:2]
        mask_s = _mouth_mask(lm_src[si], (sh, sw), dilate=5, iters=1,
                             feather=TONE_FEATHER)[..., 0]
        sel_s = mask_s > 0.5
        if sel_g.sum() < 40 or sel_s.sum() < 40:
            out.append(g)
            continue

        g_rel = glab[..., 0][sel_g].mean() / g_anchor
        s_rel = slab[..., 0][sel_s].mean() / s_anchor
        gain = 1.0 + (s_rel / max(g_rel, 1e-6) - 1.0) * strength
        gain = float(np.clip(gain, TONE_MIN_GAIN, TONE_MAX_GAIN))
        gains.append(gain)

        # 亮度按羽化 mask 加权增益；色度往原素材方向拉一部分，补回唇色
        m3 = mask_g[..., None]
        res = glab.copy()
        res[..., 0] = glab[..., 0] * (1 + (gain - 1) * mask_g)
        if TONE_CHROMA > 0:
            for ch in (1, 2):
                d = slab[..., ch][sel_s].mean() - glab[..., ch][sel_g].mean()
                res[..., ch] = glab[..., ch] + d * TONE_CHROMA * mask_g
        res[..., 0] = np.clip(res[..., 0], 0, 255)
        res[..., 1:] = np.clip(res[..., 1:], 0, 255)
        out.append(cv2.cvtColor(res.astype(np.uint8), cv2.COLOR_LAB2BGR))
        if (t + 1) % 100 == 0:
            log(f"    tone {t + 1}/{len(gen_frames)}")

    if gains:
        log(f"    tone gain mean={np.mean(gains):.3f} max={np.max(gains):.3f}")
    return out


def refine_lip_dynamics(frames, lm_gen, lm_src, log=print, width_ref=None):
    """Widen lip spread to match the real speaker without touching timing.

    width_ref should be the FULL generated-landmark array when processing in
    chunks -- the amplification factor is derived from the curve's standard
    deviation, so computing it per chunk would make each chunk use a different
    amount of widening and produce visible steps.
    """
    def width_curve(l):
        fh = l[:, 8, 1] - l[:, 27, 1]
        return np.linalg.norm(l[:, 54] - l[:, 48], axis=1) / np.maximum(fh, 1e-6)

    gw_stat = width_curve(width_ref if width_ref is not None else lm_gen)
    gw = width_curve(lm_gen)
    sw = width_curve(lm_src)
    # only the statistic (std) of the real speaker is used, so differing
    # lengths are fine -- but guard against degenerate input
    if len(sw) < 8 or not np.isfinite(sw.std()) or sw.std() <= 0:
        log("    lip refine skipped (no usable reference statistics)")
        return frames
    cur, target = gw_stat.std(), sw.std()
    amp = min(LIP_AMP_CAP, (target / max(cur, 1e-9)) * LIP_AMP_BOOST)
    log(f"    lip width std {cur:.5f} -> target {target:.5f}, amp={amp:.3f}")
    dev = gaussian_filter1d(gw - gw_stat.mean(), LIP_CURVE_SMOOTH)
    desired = gw_stat.mean() + dev * amp
    scale = np.clip(desired / np.maximum(gw, 1e-6), LIP_SCALE_MIN, LIP_SCALE_MAX)

    H, W = frames[0].shape[:2]
    gx_full, gy_full = np.meshgrid(np.arange(W, dtype=np.float32),
                                   np.arange(H, dtype=np.float32))
    out = []
    for t, f in enumerate(frames):
        if t >= len(lm_gen):
            out.append(f)
            continue
        mp = lm_gen[t][48:68]
        cx, cy = mp.mean(0)
        x0, y0 = mp.min(0)
        x1, y1 = mp.max(0)
        mw, mh = x1 - x0, y1 - y0
        s = float(scale[t])
        if mw < 20 or mh < 8 or abs(s - 1.0) < 0.004:
            out.append(f)
            continue
        rx0 = int(max(0, cx - mw * 1.3)); rx1 = int(min(W, cx + mw * 1.3))
        ry0 = int(max(0, cy - mh * 2.2)); ry1 = int(min(H, cy + mh * 2.2))
        if rx1 - rx0 < 20 or ry1 - ry0 < 20:
            out.append(f)
            continue
        gx = gx_full[ry0:ry1, rx0:rx1]
        gy = gy_full[ry0:ry1, rx0:rx1]
        dx = (gx - cx) / (mw * 0.8)
        dy = (gy - cy) / (mh * 1.5)
        fall = np.exp(-(dx * dx + dy * dy) * 1.5).astype(np.float32)
        shift_x = np.clip((gx - cx) * (1.0 / s - 1.0) * fall, -LIP_SHIFT_CAP, LIP_SHIFT_CAP)
        roi = np.ascontiguousarray(f[ry0:ry1, rx0:rx1])
        warped = cv2.remap(roi, (gx + shift_x - rx0).astype(np.float32),
                           (gy - ry0).astype(np.float32),
                           cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        mf = _mouth_mask(lm_gen[t], (ry1 - ry0, rx1 - rx0), offset=(rx0, ry0),
                         dilate=13, feather=LIP_FEATHER)
        merged = f.copy().astype(np.float32)
        merged[ry0:ry1, rx0:rx1] = roi.astype(np.float32) * (1 - mf) + warped.astype(np.float32) * mf
        out.append(np.clip(merged, 0, 255).astype(np.uint8))
        if (t + 1) % 100 == 0:
            log(f"    lip refine {t + 1}/{len(frames)}")
    return out
