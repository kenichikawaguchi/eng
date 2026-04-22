#!/usr/bin/env python3
"""
毎日自動実行スクリプト
  1. パラメータをランダム選択（難易度・ジャンル・話者の関係・トピック）
  2. Gemini API でリスニングスクリプト生成
  3. Kokoro で MP3 生成
  4. OCI Object Storage にアップロード
     - listening/listening_quiz_YYYYMMDD.mp3
     - listening/listening_quiz_YYYYMMDD.json  ← 追加
     - index.json                               ← 追加（全問題一覧）

cron例 (毎朝7時 JST = UTC 22時):
  0 22 * * * /home/ken/repo/eng/.venv/bin/python3 /home/ken/repo/eng/generate_daily.py >> /home/ken/repo/eng/logs/cron.log 2>&1
"""

import json
import os
import random
import subprocess
import sys
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from google import genai
import oci
from dotenv import load_dotenv

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
today_str = datetime.now(JST).strftime("%Y%m%d")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"{today_str}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

OCI_BUCKET_NAME    = os.environ["OCI_BUCKET_NAME"]
OCI_NAMESPACE      = os.environ["OCI_NAMESPACE"]
OCI_CONFIG_PROFILE = os.environ.get("OCI_CONFIG_PROFILE", "DEFAULT")
OCI_PREFIX         = os.environ.get("OCI_OBJECT_PREFIX", "listening/")

SCRIPT_FILE = BASE_DIR / "script.txt"
OUTPUT_DIR  = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

OCI_BASE_URL = (
    f"https://objectstorage.ap-osaka-1.oraclecloud.com"
    f"/n/{OCI_NAMESPACE}/b/{OCI_BUCKET_NAME}/o"
)

DIFFICULTIES  = ["初級", "中級", "上級"]
GENRES        = ["日常会話", "ビジネス", "旅行", "ニュース"]
RELATIONSHIPS = ["同僚","友人","見知らぬ人","家族","上司と部下","店員と客","先生と学生","ルームメイト"]
TOPICS = [
    "引越し","出張の準備","週末の予定","新しいカフェ","健康診断","映画の感想",
    "旅行の計画","就職活動","オンラインショッピング","料理レシピ","公共交通機関",
    "テレワーク","語学学習","誕生日プレゼント","スポーツ観戦","読書","ペット",
    "環境問題","新しいスマートフォン","レストランの予約","友人の結婚式","自転車通勤",
    "図書館","ボランティア活動","荷物の紛失","天気と服装","転職活動","在宅勤務の悩み",
    "ジムの入会","サブスクリプションの解約","公園でのピクニック","美術館の展覧会",
    "コンサートのチケット","スーパーでの買い物","ホテルのチェックイン","道に迷う",
]

def pick_params() -> dict:
    week_num = datetime.now(JST).isocalendar()[1]
    return {
        "difficulty": DIFFICULTIES[week_num % len(DIFFICULTIES)],
        "genre": random.choice(GENRES),
        "relationship": random.choice(RELATIONSHIPS),
        "topic": random.choice(TOPICS),
    }

PROMPT_TEMPLATE = """\
以下のフォーマットに従って、英語リスニング問題のスクリプトを1問分だけ作成してください。

## 出力フォーマット

NARRATOR: （イントロ。問題の概要を説明する1文）
A: （話者Aのセリフ）
B: （話者Bのセリフ）
A: ...
B: ...
（会話は6〜10ターン程度）
QUESTION: Question. （質問文）
CHOICE: A. （選択肢A）
CHOICE: B. （選択肢B）
CHOICE: C. （選択肢C）
CHOICE: D. （選択肢D）
ANSWER: The correct answer is （A/B/C/D）. （正解の選択肢テキスト）

## ルール

* 各行は必ず `ラベル: テキスト` の形式にする
* 使えるラベルは NARRATOR / A / B / QUESTION / CHOICE / ANSWER のみ
* ANSWER行は1行だけ、最後に置く
* 正解は4択のうち1つだけ
* 不正解の選択肢は「もっともらしいが明確に違う」内容にする
* 会話中に答えが明確に含まれていること（推測不要）
* コロン（:）はラベルの区切りにのみ使う。テキスト中にコロンを入れない

## 本日のパラメータ

* 難易度: {difficulty}
* ジャンル: {genre}
* 話者の関係: {relationship}
* トピック: {topic}

## 注意事項

* フォーマット以外の説明文・コメントは出力しない
* コードブロック（```）で囲まない
* 1問分のみ出力する
"""

def generate_script(params: dict) -> str:
    log.info(f"Gemini でスクリプト生成開始: {params}")
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = PROMPT_TEMPLATE.format(**params)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(temperature=1.0, max_output_tokens=1024),
    )
    script_text = response.text.strip()
    if script_text.startswith("```"):
        lines = script_text.splitlines()
        script_text = "\n".join(l for l in lines if not l.startswith("```")).strip()
    log.info(f"スクリプト生成完了 ({len(script_text)} 文字)")
    return script_text

def validate_script(script_text: str) -> bool:
    required = {"NARRATOR", "A", "B", "QUESTION", "CHOICE", "ANSWER"}
    found = set()
    for line in script_text.splitlines():
        if ":" in line:
            found.add(line.split(":", 1)[0].strip().upper())
    missing = required - found
    if missing:
        log.warning(f"スクリプトに不足ラベル: {missing}")
        return False
    return True

def parse_script(script_text: str) -> dict:
    lines, answer, question, choices = [], "", "", []
    for raw in script_text.splitlines():
        raw = raw.strip()
        if not raw or ":" not in raw:
            continue
        # ``` を含む行はスキップ
        if raw.startswith("```"):
            continue
        label, text = raw.split(":", 1)
        label, text = label.strip().upper(), text.strip()
        text = text.replace("```", "").strip()
        if not text:
            continue
        if label == "ANSWER":
            answer = text
        elif label == "QUESTION":
            question = text
            lines.append({"label": label, "text": text})
        elif label == "CHOICE":
            choices.append(text)
            lines.append({"label": label, "text": text})
        else:
            lines.append({"label": label, "text": text})
    return {"lines": lines, "answer": answer, "question": question, "choices": choices}

STUDY_PROMPT_TEMPLATE = """\
以下の英語リスニング問題のスクリプトを使って、日本人英語学習者向けの学習コンテンツを作成してください。

## スクリプト

{script}

## 出力形式

以下のJSON形式で出力してください。JSONのみ出力し、説明文やコードブロックは不要です。

{{
  "explanation": {{
    "summary": "この会話の概要（日本語・2〜3文）",
    "correct_answer": "正解がなぜ正しいかの解説（日本語・2〜3文）",
    "wrong_answers": [
      {{"choice": "A", "reason": "なぜ不正解かの解説（日本語）"}},
      {{"choice": "B", "reason": "なぜ不正解かの解説（日本語）"}},
      {{"choice": "C", "reason": "なぜ不正解かの解説（日本語）"}},
      {{"choice": "D", "reason": "なぜ不正解かの解説（日本語）"}}
    ],
    "listening_tips": "この問題で聞き取るべきポイント（日本語・1〜2文）"
  }},
  "vocabulary": [
    {{
      "word": "単語またはフレーズ",
      "reading": "発音ヒント（カタカナまたはローマ字）",
      "meaning": "日本語の意味",
      "example": "スクリプト中の使用例または類似例文"
    }}
  ],
  "dictation": [
    {{
      "original": "元のセリフ（話者名なし）",
      "blanked": "重要な単語を___に置き換えたセリフ（1文に1〜3箇所）",
      "answers": ["穴の答え1", "穴の答え2"]
    }}
  ]
}}

## ルール

* vocabularyは会話中の重要な単語・フレーズを5〜8個選ぶ
* dictationはNARRATOR・A・Bのセリフから6〜8行選ぶ（QUESTIONとCHOICEは除く）
* dictationの穴は内容語（名詞・動詞・形容詞）を中心に選ぶ
* wrong_answersは正解の選択肢を除いた3つについて記載する
* JSONのキーはすべて英語、値の日本語テキストはそのまま
"""

def generate_study_content(script_text: str) -> dict:
    log.info("学習コンテンツ生成開始")
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = STUDY_PROMPT_TEMPLATE.format(script=script_text)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            temperature=0.5,
            max_output_tokens=2048,
        ),
    )
    text = response.text.strip()
    # コードブロック除去
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.startswith("```")).strip()
    study = json.loads(text)
    log.info("学習コンテンツ生成完了")
    return study

def generate_mp3(output_path: Path) -> None:
    log.info("Kokoro で MP3 生成開始")
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "make_listening_kokoro.py")],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        env={**os.environ, "OUTPUT_FILE": str(output_path)},
    )
    if result.returncode != 0:
        log.error(f"MP3 生成失敗:\n{result.stderr}")
        raise RuntimeError("MP3 生成に失敗しました")
    log.info(result.stdout.strip())
    log.info(f"MP3 生成完了: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")

def _get_oci_client():
    config = oci.config.from_file(profile_name=OCI_CONFIG_PROFILE)
    return oci.object_storage.ObjectStorageClient(config)

def upload_file(local_path: Path, object_name: str, content_type: str) -> str:
    client = _get_oci_client()
    with open(local_path, "rb") as f:
        client.put_object(
            namespace_name=OCI_NAMESPACE, bucket_name=OCI_BUCKET_NAME,
            object_name=object_name, put_object_body=f, content_type=content_type,
        )
    url = f"{OCI_BASE_URL}/{object_name.replace('/', '%2F')}"
    log.info(f"アップロード完了: {object_name}")
    return url

def upload_bytes(data: bytes, object_name: str, content_type: str) -> str:
    import io
    client = _get_oci_client()
    client.put_object(
        namespace_name=OCI_NAMESPACE, bucket_name=OCI_BUCKET_NAME,
        object_name=object_name, put_object_body=io.BytesIO(data),
        content_type=content_type,
    )
    url = f"{OCI_BASE_URL}/{object_name.replace('/', '%2F')}"
    log.info(f"アップロード完了: {object_name}")
    return url

INDEX_OBJECT = "index.json"

def load_index() -> list:
    client = _get_oci_client()
    try:
        resp = client.get_object(
            namespace_name=OCI_NAMESPACE, bucket_name=OCI_BUCKET_NAME,
            object_name=INDEX_OBJECT,
        )
        return json.loads(resp.data.content.decode("utf-8"))
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            return []
        raise

def update_index(entry: dict) -> None:
    index = [e for e in load_index() if e.get("date") != entry["date"]]
    index.insert(0, entry)
    index.sort(key=lambda e: e["date"], reverse=True)
    data = json.dumps(index, ensure_ascii=False, indent=2).encode("utf-8")
    upload_bytes(data, INDEX_OBJECT, "application/json")
    log.info(f"index.json 更新完了 ({len(index)} 件)")

def main():
    log.info(f"===== 本日の英語リスニング生成 ({today_str}) =====")

    params = pick_params()
    log.info(f"本日のパラメータ: {params}")

    script_text = None
    for attempt in range(1, 4):
        try:
            script_text = generate_script(params)
            if validate_script(script_text):
                break
            log.warning(f"バリデーション失敗 (試行 {attempt}/3)、再生成します")
        except Exception as e:
            log.warning(f"スクリプト生成エラー (試行 {attempt}/3): {e}")
    else:
        log.error("スクリプト生成を3回試みましたが失敗しました")
        sys.exit(1)

    SCRIPT_FILE.write_text(script_text, encoding="utf-8")
    (LOG_DIR / f"{today_str}_script.txt").write_text(script_text, encoding="utf-8")
    log.info("script.txt 更新完了")

    mp3_name   = f"listening_quiz_{today_str}.mp3"
    mp3_path   = OUTPUT_DIR / mp3_name
    mp3_object = f"{OCI_PREFIX}{mp3_name}"
    try:
        generate_mp3(mp3_path)
    except Exception as e:
        log.error(f"MP3 生成失敗: {e}")
        sys.exit(1)

    log.info("MP3 を OCI にアップロード中")
    mp3_url = upload_file(mp3_path, mp3_object, "audio/mpeg")

    parsed = parse_script(script_text)
    date_display = datetime.now(JST).strftime("%Y年%-m月%-d日")

    # 学習コンテンツ生成（失敗してもメインは止めない）
    study = {}
    try:
        study = generate_study_content(script_text)
    except Exception as e:
        log.warning(f"学習コンテンツ生成失敗（スキップ）: {e}")

    sidecar = {
        "date": today_str,
        "date_display": date_display,
        "params": params,
        "lines": parsed["lines"],
        "question": parsed["question"],
        "choices": parsed["choices"],
        "answer": parsed["answer"],
        "study": study,
        "mp3_url": mp3_url,
        "generated_at": datetime.now(JST).isoformat(),
    }
    json_name   = f"listening_quiz_{today_str}.json"
    json_object = f"{OCI_PREFIX}{json_name}"
    json_data   = json.dumps(sidecar, ensure_ascii=False, indent=2).encode("utf-8")
    json_url    = upload_bytes(json_data, json_object, "application/json")

    index_entry = {
        "date": today_str,
        "date_display": date_display,
        "params": params,
        "mp3_url": mp3_url,
        "json_url": json_url,
    }
    update_index(index_entry)

    meta = {**index_entry, "generated_at": datetime.now(JST).isoformat()}
    (LOG_DIR / f"{today_str}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    log.info("===== 完了 =====")
    log.info(f"MP3 URL : {mp3_url}")
    log.info(f"JSON URL: {json_url}")

if __name__ == "__main__":
    main()
