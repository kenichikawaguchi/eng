#!/usr/bin/env python3
"""
ElevenLabs を使った英語リスニング問題 MP3 生成スクリプト
実行前: pip install elevenlabs python-dotenv
実行方法: python3 make_listening_elevenlabs.py
原稿:    script.txt を編集してください（ANSWER行は音声に含まれません）
"""

import os
import time
import subprocess
from pathlib import Path
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    raise ValueError("ELEVENLABS_API_KEY が設定されていません。.env ファイルを確認してください。")

SCRIPT_FILE = "script.txt"
OUTPUT_FILE = "listening_quiz.mp3"
WORK_DIR = Path("audio_parts")
WORK_DIR.mkdir(exist_ok=True)

# ── 声の設定 ─────────────────────────────────────────────────────────────────
VOICE_MAP = {
    "A":        "CwhRBWXzGAHq8TQ4Fs17",   # Roger  (男性・アメリカ英語・casual)
    "B":        "EXAVITQu4vr4xnSDxMaL",   # Sarah  (女性・アメリカ英語・confident)
    "NARRATOR": "onwK4e9ZLuTAKqWW03F9",   # Daniel (男性・イギリス英語・broadcaster)
    "QUESTION": "onwK4e9ZLuTAKqWW03F9",
    "CHOICE":   "onwK4e9ZLuTAKqWW03F9",
}

# 各ラベルの後に挿入する無音の長さ（秒）
PAUSE_MAP = {
    "NARRATOR": 1.5,
    "A":        0.4,
    "B":        0.4,
    "QUESTION": 0.8,
    "CHOICE":   0.5,
}

MODEL = "eleven_multilingual_v2"

# ── script.txt を読み込む ─────────────────────────────────────────────────────
def load_script(path: str) -> list[tuple[str, str]]:
    """
    script.txt を読み込み [(ラベル, テキスト), ...] を返す。
    ANSWER行はスキップ（テキストファイルには残るが音声には含まれない）。
    """
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            if ":" not in raw:
                continue
            label, text = raw.split(":", 1)
            label = label.strip().upper()
            text  = text.strip()
            if label == "ANSWER":
                print(f"[SKIP] {text}")   # 確認用に表示はする
                continue
            lines.append((label, text))
    return lines

# ── 音声生成 ─────────────────────────────────────────────────────────────────
client = ElevenLabs(api_key=API_KEY)
script = load_script(SCRIPT_FILE)

wav_parts = []
for i, (label, text) in enumerate(script):
    voice_id = VOICE_MAP.get(label)
    if not voice_id:
        print(f"[WARN] ラベル '{label}' に対応するボイスがありません。スキップします。")
        continue

    out_path = WORK_DIR / f"part_{i:03d}.mp3"
    print(f"[{i+1}/{len(script)}] {label}: {text[:60]}...")

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=MODEL,
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.8,
            style=0.2,
        ),
        output_format="mp3_44100_128",
    )
    with open(out_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    # 音量を正規化（全声を同じラウドネスに揃える）
    normalized_path = WORK_DIR / f"norm_{i:03d}.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(out_path),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(normalized_path)
    ], check=True, capture_output=True)
    out_path = normalized_path

    pause = PAUSE_MAP.get(label, 0.4)
    wav_parts.append((out_path, pause))
    time.sleep(0.3)  # API レート制限対策

# ── ffmpeg で結合 ─────────────────────────────────────────────────────────────
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

print(f"\n✅ 完成: {OUTPUT_FILE}  ({Path(OUTPUT_FILE).stat().st_size / 1024:.0f} KB)")
