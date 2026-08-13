# Sapporo Live House Google Calendar

札幌のライブハウスの最新ライブ情報を Google カレンダーで購読するためのリポジトリです。

**対応ライブハウス:**
- PRECIOUS HALL (プレシャスホール) — <http://www.precioushall.com/schedule/>
- SOUND CRUE — <https://soundcrue.com/schedule/>

各公式スケジュールページを毎日スクレイピングし、`sapporo-live.ics` を自動更新します。
Google カレンダーがこの ICS を URL 購読することで常に最新のライブ情報が反映されます。

## 仕組み

```
precioushall.com / soundcrue.com (スケジュール + 各イベント詳細ページ)
        │ 毎日 11:00 JST (02:00 UTC) に GitHub Actions が実行
        ▼
scrape.py ──► sapporo-live.ics (GitHub 上で更新)
        │
        ▼
Google カレンダーがこの URL を定期的に自動同期
```

## セットアップ手順

### 1. GitHub に公開リポジトリを作成して push

Google カレンダーは認証なしで ICS を取得するため、**リポジトリは public にする必要があります**。

```bash
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<ユーザー名>/<リポジトリ名>.git
git push -u origin main
```

push すると GitHub Actions が自動でカレンダーを生成します。
(手動実行したい場合は GitHub の Actions タブ → Update Sapporo Live Calendar → Run workflow)

### 2. Google カレンダーに URL を登録

1. [Google カレンダー](https://calendar.google.com/) を開く
2. 左サイドバーの「他のカレンダー」横の「＋」→ 「URL で追加」
3. 以下の URL を貼り付けて追加

```
https://raw.githubusercontent.com/<ユーザー名>/<リポジトリ名>/main/sapporo-live.ics
```

### 3. 更新の確認

- GitHub Actions が毎日 11:00 JST に公式ページをチェックし、変更があれば `sapporo-live.ics` を更新
- Google カレンダーは購読したカレンダーを数時間〜1日程度の間隔で自動再取得するため、
  ライブ情報が公開されれば自動的に反映されます
- 更新状況は `last_run.json` に記録されます

## 各イベントに含まれる情報

- タイトル + 会場名 (例: `IDEALIST @ PRECIOUS HALL` / `“safari” @ SOUND CRUE`)
- 開始時刻 (PRECIOUS HALL は `ADM`、SOUND CRUE は `start` から抽出。
  終了時刻は未発表のため PRECIOUS HALL 約6時間 / SOUND CRUE 約3時間で想定)
- 出演者・LINEUP
- 入場料・開場時刻
- 公式詳細ページへのリンク

## ローカルで実行する場合

```bash
python3 scrape.py              # 全サイトを処理して sapporo-live.ics を生成
python3 scrape.py --source precioushall   # 特定サイトのみ (--source は複数指定可)
```

Python 3 の標準ライブラリのみで動作します (外部依存なし)。

注意: PRECIOUS HALL の公式サイトは Shift_JIS と UTF-8 のページが混在しています。
スクリプトはエンコーディングを自動判別して処理します。

※ 本カレンダーは非公式の情報集約です。イベント情報の正確性は各公式サイトの
スケジュールを確認してください。
