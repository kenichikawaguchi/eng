#!/usr/bin/env python3
"""
Kokoro TTS を使った英語リスニング問題 MP3 生成スクリプト

実行前: pip install kokoro soundfile
       brew install ffmpeg  (未インストールの場合)

実行方法: python3 make_listening_kokoro.py

原稿: script.txt を編集してください（ANSWER行は音声に含まれません）
"""

import subprocess
import numpy as np
import soundfile as sf
from pathlib import Path
from kokoro import KPipeline

SCRIPT_FILE = "script.txt"
import os
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "listening_quiz.mp3")

WORK_DIR = Path("audio_parts")
WORK_DIR.mkdir(exist_ok=True)

SAMPLE_RATE = 24000

# ── 声の設定（ElevenLabsと同じ役割分担） ──────────────────────────────────────
# am_ = American male, af_ = American female
# bm_ = British male, bf_ = British female
VOICE_MAP = {
    "A":        "am_adam",    # 話者A: 男性・アメリカ英語 (Roger相当)
    "B":        "af_heart",   # 話者B: 女性・アメリカ英語 (Sarah相当)
    "NARRATOR": "bm_george",  # ナレーター: 男性・イギリス英語 (Daniel相当)
    "QUESTION": "bm_george",
    "CHOICE":   "bm_george",
}

# 各ラベルの後に挿入する無音の長さ（秒）- 元スクリプトと同じ値
PAUSE_MAP = {
    "NARRATOR": 1.5,
    "A":        0.4,
    "B":        0.4,
    "QUESTION": 0.8,
    "CHOICE":   0.5,
}

# ── script.txt を読み込む ─────────────────────────────────────────────────────
def load_script(path: str) -> list[tuple[str, str]]:
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw or ":" not in raw:
                continue
            label, text = raw.split(":", 1)
            label = label.strip().upper()
            text = text.strip()
            if label == "ANSWER":
                print(f"[SKIP] {text}")
                continue
            lines.append((label, text))
    return lines

# ── Kokoro パイプラインを初期化（英語） ──────────────────────────────────────
pipeline = KPipeline(lang_code='en-us')

script = load_script(SCRIPT_FILE)
wav_parts = []

for i, (label, text) in enumerate(script):
    voice = VOICE_MAP.get(label)
    if not voice:
        print(f"[WARN] ラベル '{label}' に対応するボイスがありません。スキップします。")
        continue

    out_wav = WORK_DIR / f"part_{i:03d}.wav"
    print(f"[{i+1}/{len(script)}] {label} ({voice}): {text[:60]}...")

    # Kokoro で音声生成（複数チャンクを結合）
    chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=0.95):
        chunks.append(audio)

    audio_data = np.concatenate(chunks) if chunks else np.zeros(100)
    sf.write(str(out_wav), audio_data, SAMPLE_RATE)

    # 音量を正規化（元スクリプトと同じ loudnorm 設定）
    normalized_path = WORK_DIR / f"norm_{i:03d}.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(out_wav),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(normalized_path)
    ], check=True, capture_output=True)

    pause = PAUSE_MAP.get(label, 0.4)
    wav_parts.append((normalized_path, pause))

# ── ffmpeg で結合（元スクリプトと同じロジック） ───────────────────────────────
filelist = WORK_DIR / "filelist.txt"
concat_parts = []

for idx, (part_path, pause_sec) in enumerate(wav_parts):
    is_last = (idx == len(wav_parts) - 1)
    concat_parts.append(f"file '{part_path.resolve()}'")
    if pause_sec > 0 and not is_last:
        silence_path = WORK_DIR / f"silence_{part_path.stem}.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(pause_sec),
            "-c:a", "libmp3lame", "-q:a", "3",
            str(silence_path)
        ], check=True, capture_output=True)
        concat_parts.append(f"file '{silence_path.resolve()}'")

filelist.write_text("\n".join(concat_parts))

subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", str(filelist),
    "-c:a", "libmp3lame", "-q:a", "2",
    OUTPUT_FILE
], check=True)

print(f"\n✅ 完成: {OUTPUT_FILE} ({Path(OUTPUT_FILE).stat().st_size / 1024:.0f} KB)")
