# youtube-automation

完全自動YouTube動画制作システム（クラウド完結・PC非依存・無料枠のみ）。

設計: `DESIGN.md`（運用側ワークスペース）／セットアップ記録: `SETUP.md`

## 仕組み

1. Google Sheets のキュー（シート名 `queue`）から `status = queued` の行を1本取る。
2. Gemini API で台本・タイトル・概要欄を生成（失敗時は将来のフォールバック先へ）。
3. Kokoro ONNX でナレーション音声を生成（GitHub Actions の CPU 上）。
4. FFmpeg で方式A（写真・イラスト＋ズーム/パン）として組み立て、字幕（SRT）を生成。
5. YouTube Data API でアップロードし、結果をキューに書き戻す。

## 必要な Secrets（登録済み）

- `YT_WEB_CLIENT_ID` / `YT_WEB_CLIENT_SECRET` — 更新トークンの交換に使う Web クライアント
- `YT_REFRESH_TOKEN` — YouTube + Sheets 用（youtube.upload / youtube / yt-analytics.readonly / spreadsheets）
- `DRIVE_REFRESH_TOKEN` — Drive 用（drive.file のみ）
- `GEMINI_API_KEY` — 台本生成
- `QUEUE_SHEET_ID` — キュー用スプレッドシートの ID

## 段階

- 段階1: 方式Aのみ・手動キュー1行を通す（公開範囲はリポジトリ変数 `UPLOAD_PRIVACY`、既定は `unlisted` で検証してから切り替える）。
- 段階2以降: 日次スケジュール、安全装置、分析の還元、方式の拡張。
