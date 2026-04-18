# English Listening Quiz Generator

ElevenLabs の Text-to-Speech API を使って、英語リスニング問題の MP3 ファイルを自動生成するツールです。

## 概要

`script.txt` に原稿を書くだけで、複数の話者による自然な会話音声を MP3 として出力します。

- 話者ごとに異なる声を割り当て
- 各パーツの音量を自動で正規化（loudnorm）
- `ANSWER` 行はテキストに残しつつ音声には含めない

## ファイル構成

```
.
├── make_listening_elevenlabs.py  # メインスクリプト
├── script.txt                    # 原稿ファイル
├── script_prompt.md              # script.txt を AI で生成するためのプロンプト
├── .env                          # APIキー（Git管理外）
└── .gitignore
```

## セットアップ

### 1. 依存ライブラリのインストール

```bash
pip install elevenlabs python-dotenv
```

ffmpeg が未インストールの場合（macOS）:

```bash
brew install ffmpeg
```

### 2. `.env` ファイルの作成

```
ELEVENLABS_API_KEY=your_api_key_here
```

APIキーは [ElevenLabs](https://elevenlabs.io) → Developers → API Keys から発行してください。  
権限は **Text to Speech** と **Voices（read）** を有効にしてください。

## 使い方

### 1. 原稿を用意する

`script.txt` を編集します。`script_prompt.md` のプロンプトを AI に渡すと自動生成できます。

```
NARRATOR: Listening Quiz. You will hear a short conversation. Then answer the question.
A: Hey, you look a bit worn out. Rough day?
B: Yeah, I've been dealing with my landlord all week.
...
QUESTION: Question. What is the woman's main problem?
CHOICE: A. She cannot afford her current rent.
CHOICE: B. Her landlord keeps postponing their scheduled meeting.
CHOICE: C. She has already moved into a new apartment.
CHOICE: D. She cannot find any affordable listings online.
ANSWER: The correct answer is B. Her landlord keeps postponing their scheduled meeting.
```

#### ラベル一覧

| ラベル | 説明 |
|---|---|
| `NARRATOR` | イントロ・説明文 |
| `A` | 話者A（男性） |
| `B` | 話者B（女性） |
| `QUESTION` | 質問文 |
| `CHOICE` | 選択肢（複数行） |
| `ANSWER` | 正解（音声には含まれない） |

### 2. MP3 を生成する

```bash
python make_listening_elevenlabs.py
```

`listening_quiz.mp3` が生成されます。

## 使用している声

| 役割 | 声 | 特徴 |
|---|---|---|
| 話者A | Roger | 男性・アメリカ英語・casual |
| 話者B | Sarah | 女性・アメリカ英語・confident |
| ナレーター | Daniel | 男性・イギリス英語・broadcaster |

## 注意事項

- ElevenLabs の無料プランでは API 経由で利用できる声に制限があります
- `.env` ファイルは絶対に Git にコミットしないでください
