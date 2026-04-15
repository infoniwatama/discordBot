# Discord タスクBot セットアップガイド

## 全体の流れ
```
毎朝Discordに投稿
    ↓
Bot がメッセージを受信
    ↓
Claude API でタスクを自動解析
    ↓
Google スプレッドシートに追記
```

---

## ステップ1: Discord Bot を作成

1. https://discord.com/developers/applications を開く
2. **「New Application」** をクリック → 名前を入力
3. 左メニュー **「Bot」** → **「Add Bot」**
4. **「Reset Token」** をクリックしてトークンをコピー（`.env` の `DISCORD_TOKEN` に貼る）
5. 「Privileged Gateway Intents」で **Message Content Intent** を ON にする
6. 左メニュー **「OAuth2」→「URL Generator」**
   - Scopes: `bot` にチェック
   - Bot Permissions: `Send Messages`, `Read Message History`, `View Channels` にチェック
7. 生成されたURLをブラウザで開いてサーバーに招待

**チャンネルIDの取得方法:**
- Discordの設定 → 「詳細設定」→「開発者モード」をON
- 対象チャンネルを右クリック → 「IDをコピー」

---

## ステップ2: Google Sheets API を設定

1. https://console.cloud.google.com/ を開く
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「APIを有効化」→ **Google Sheets API** と **Google Drive API** を有効化
4. 「認証情報」→「認証情報を作成」→ **サービスアカウント**
5. サービスアカウントを作成後、「キー」→「鍵を追加」→ **JSON** でダウンロード
6. ダウンロードしたJSONを `credentials.json` としてこのフォルダに置く
7. JSONの中の `client_email` をコピー
8. Google スプレッドシートを開いて「共有」→ コピーしたメールアドレスを **編集者** として追加
9. スプレッドシートのURLからIDをコピー
   - 例: `https://docs.google.com/spreadsheets/d/【ここがID】/edit`

---

## ステップ3: 環境変数を設定

`.env.example` をコピーして `.env` を作成し、各値を入力:

```
DISCORD_TOKEN=（ステップ1でコピーしたトークン）
DISCORD_CHANNEL_ID=（対象チャンネルのID）
ANTHROPIC_API_KEY=（Claude APIキー: https://console.anthropic.com/）
GOOGLE_SHEET_ID=（スプレッドシートのID）
GOOGLE_CREDS_FILE=credentials.json
TASK_SHEET_NAME=タスク管理
```

---

## ステップ4: 実行方法

### ローカルPC で動かす場合
```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# .env を読み込んで起動
pip install python-dotenv

# bot.py の先頭に以下を追加（ローカル実行時のみ）:
# from dotenv import load_dotenv; load_dotenv()

python bot.py
```

### Railway でクラウド実行する場合
1. https://railway.app にサインアップ
2. 「New Project」→「Deploy from GitHub repo」でこのフォルダをpush したリポジトリを選択
3. 「Variables」タブで `.env` の内容をすべて追加
4. `credentials.json` の内容は `GOOGLE_CREDS_JSON` という変数に丸ごと貼り付け
   - `bot.py` の `get_sheet()` 内を以下に変更:
     ```python
     import json, tempfile
     creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
     with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
         json.dump(creds_json, f)
         creds_path = f.name
     creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
     ```
5. デプロイ完了後、Botが自動起動します（無料プランで月500時間）

---

## 使い方

タスク用チャンネルに自由形式でメッセージを投稿するだけです。

**投稿例:**
```
今日やること
- APIの設計レビュー（高優先度、午前中）
- 田中さんと週次MTG 13時〜
- バグ修正 #234、2時間くらいかかりそう
- ドキュメント更新（低優先度）
```

Botが自動解析してスプレッドシートに追記し、結果をDiscordに返信します。

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| Botが応答しない | Message Content IntentがOFF | Discord Developer PortalでONに |
| スプレッドシートに書き込めない | 共有設定が不足 | サービスアカウントのメールを編集者に追加 |
| タスク解析が不正確 | メッセージが曖昧 | もう少し具体的に書くと精度が上がります |
