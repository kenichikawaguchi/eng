以下のフォーマットに従って、英語リスニング問題のスクリプトを作成してください。

## 出力フォーマット

```
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
```

## ルール

- 各行は必ず `ラベル: テキスト` の形式にする
- 使えるラベルは NARRATOR / A / B / QUESTION / CHOICE / ANSWER のみ
- ANSWER行は1行だけ、最後に置く
- 正解は4択のうち1つだけ
- 不正解の選択肢は「もっともらしいが明確に違う」内容にする
- 会話中に答えが明確に含まれていること（推測不要）
- コロン（:）はラベルの区切りにのみ使う。テキスト中にコロンを入れない

## パラメータ（必要に応じて指定）

- 難易度: 初級 / 中級 / 上級
- ジャンル: 日常会話 / ビジネス / 旅行 / ニュース
- 話者の関係: 同僚 / 友人 / 見知らぬ人 / 家族 など
- トピック: （自由記述。例: 引越し、出張の準備、週末の予定 など）

## 出力例

```
NARRATOR: Listening Quiz. You will hear a short conversation between two colleagues. Then answer the question.
A: Hey, you look a bit worn out. Rough day?
B: Yeah, I've been dealing with my landlord all week. He keeps cancelling our meeting about the lease renewal.
A: That's incredibly frustrating. How many times has he cancelled?
B: Three times now. At this point, I'm seriously thinking about just looking for a new place.
A: Honestly, that might be worth it. A colleague of mine just found a really nice two-bedroom for well under the going rate.
B: Really? I thought the rental market was still ridiculously overpriced.
A: Prices have actually come down in a few neighbourhoods. It's worth checking some listings this weekend.
B: Maybe you're right. I'll have a look. I can't keep waiting around for my landlord to get his act together.
QUESTION: Question. What is the woman's main problem?
CHOICE: A. She cannot afford her current rent.
CHOICE: B. Her landlord keeps postponing their scheduled meeting.
CHOICE: C. She has already moved into a new apartment.
CHOICE: D. She cannot find any affordable listings online.
ANSWER: The correct answer is B. Her landlord keeps postponing their scheduled meeting.
```

## 注意事項

- フォーマット以外の説明文・コメントは出力しない
- コードブロック（```）で囲まない
- 1問分のみ出力する
