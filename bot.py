import discord
import os
import re
import json
import asyncio
import tempfile
from datetime import datetime
import anthropic
import gspread
from google.oauth2.service_account import Credentials

# ── 設定 ──────────────────────────────────────────────
DISCORD_TOKEN      = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GOOGLE_SHEET_ID    = os.environ["GOOGLE_SHEET_ID"]
TASK_SHEET_NAME    = os.environ.get("TASK_SHEET_NAME", "タスク管理")
# Railway では GOOGLE_CREDS_JSON に credentials.json の中身をそのまま貼る
# ローカルでは GOOGLE_CREDS_FILE にファイルパスを指定
GOOGLE_CREDS_JSON  = os.environ.get("GOOGLE_CREDS_JSON")
GOOGLE_CREDS_FILE  = os.environ.get("GOOGLE_CREDS_FILE", "credentials.json")
# ──────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)
ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    # Railway: 環境変数にJSONを丸ごと入れている場合
    if GOOGLE_CREDS_JSON:
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(creds_dict, f)
            creds_path = f.name
    else:
        creds_path = GOOGLE_CREDS_FILE

    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(GOOGLE_SHEET_ID).worksheet(TASK_SHEET_NAME)


def parse_tasks_with_ai(message_text: str) -> list[dict]:
    today = datetime.now().strftime("%Y/%m/%d")
    prompt = f"""
以下のDiscordメッセージから今日のタスクを抽出してください。
今日の日付: {today}

メッセージ:
{message_text}

タスクをJSON配列で返してください。各タスクは以下のフィールドを持ちます:
- task_name: タスク名（必須）
- category: カテゴリ（推測。例: 開発/企画/品質/管理）
- assignee: 担当者名（メッセージにあれば。なければ空文字）
- priority: 優先度（高/中/低。推測）
- due_date: 期限（YYYY/MM/DD形式。記載があれば。なければ今日の日付）
- estimated_hours: 工数見積もり（数値。記載があれば。なければ0）
- comment: 備考・メモ

JSONのみ返してください。説明文・コードブロック記号は不要です。
"""
    response = ai_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def get_next_number(sheet) -> int:
    col_a = sheet.col_values(1)
    nums = []
    for v in col_a[7:]:  # 8行目以降がデータ行
        try:
            nums.append(int(v))
        except (ValueError, TypeError):
            pass
    return max(nums, default=0) + 1


def append_tasks(tasks: list[dict]) -> int:
    sheet = get_sheet()
    next_num = get_next_number(sheet)
    today = datetime.now().strftime("%Y/%m/%d")
    rows = []
    for i, t in enumerate(tasks):
        rows.append([
            next_num + i,
            t.get("task_name", ""),
            t.get("category", ""),
            t.get("assignee", ""),
            t.get("priority", "中"),
            today,
            t.get("due_date", today),
            "未着手",
            0,
            "",
            t.get("comment", ""),
            t.get("estimated_hours", 0),
            0,
        ])

    all_values = sheet.get_all_values()
    start_row = max(len(all_values) + 1, 8)
    sheet.update(f"A{start_row}", rows, value_input_option="USER_ENTERED")
    return len(rows)


@discord_client.event
async def on_ready():
    print(f"✅ Bot起動: {discord_client.user}")
    ch = discord_client.get_channel(DISCORD_CHANNEL_ID)
    if ch:
        await ch.send("🤖 タスクBotが起動しました！今日のタスクを投稿してください。")


@discord_client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id != DISCORD_CHANNEL_ID:
        return
    if len(message.content.strip()) < 5:
        return

    thinking = await message.channel.send("🔍 タスクを解析中...")

    try:
        tasks = parse_tasks_with_ai(message.content)
        if not tasks:
            await thinking.edit(content="⚠️ タスクが検出できませんでした。もう少し詳しく書いてみてください。")
            return

        count = append_tasks(tasks)

        lines = [f"✅ **{count}件のタスクをスプレッドシートに追加しました！**\n"]
        for t in tasks:
            emoji = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(t.get("priority", "中"), "🟡")
            line = f"{emoji} **{t['task_name']}**"
            if t.get("due_date"): line += f"　期限: {t['due_date']}"
            if t.get("assignee"): line += f"　担当: {t['assignee']}"
            lines.append(line)

        await thinking.edit(content="\n".join(lines))

    except json.JSONDecodeError:
        await thinking.edit(content="❌ AI解析に失敗しました。もう一度お試しください。")
    except Exception as e:
        await thinking.edit(content=f"❌ エラーが発生しました: {str(e)}")


if __name__ == "__main__":
    discord_client.run(DISCORD_TOKEN)
