# PRECIOUS HALL (Sapporo) Google Calendar

札幌のライブハウス「プレシャスホール (PRECIOUS HALL)」の最新ライブ情報を
Google カレンダーで購読するためのリポジトリです。

公式スケジュールページ (<http://www.precioushall.com/schedule/>) を毎日スクレイピングし、
`precioushall.ics` を自動更新します。Google カレンダーがこの ICS を URL 購読することで
常に最新のライブ情報が反映されます。

## 仕組み

```
precioushall.com (Pick Upページ + 各イベント詳細ページ)
        │ 毎日 11:00 JST (02:00 UTC) に GitHub Actions が実行
        ▼
scrape.py ──► precioushall.ics (GitHub 上で更新)
        │
        ▼
Google カレンダーがこの URL を定期的に自動同期
```

## セットアップ手順

### 1. GitHub に公開リポジトリを作成して push

Google カレンダーは認証なしで ICS を取得するため、**リポジトリは public にする必要があります**。

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<ユーザー名>/<リポジトリ名>.git
git push -u origin main
```

push すると GitHub Actions が自動でカレンダーを生成します。
(手動実行したい場合は GitHub の Actions タブ → Update Precious Hall Calendar → Run workflow)

### 2. Google カレンダーに URL を登録

1. [Google カレンダー](https://calendar.google.com/) を開く
2. 左サイドバーの「他のカレンダー」横の「＋」→ 「URL で追加」
3. 以下の URL を貼り付けて追加

```
https://raw.githubusercontent.com/<ユーザー名>/<リポジトリ名>/main/precioushall.ics
```

### 3. 更新の確認

- GitHub Actions が毎日 11:00 JST に公式ページをチェックし、変更があれば `precioushall.ics` を更新
- Google カレンダーは購読したカレンダーを数時間〜1日程度の間隔で自動再取得するため、
  ライブ情報が公開されれば自動的に反映されます
- 前日の更新状況は `last_run.json` に記録されます

## 各イベントに含まれる情報

- タイトル + 会場名 (例: `IDEALIST @ PRECIOUS HALL`)
- 開始時刻 (詳細ページの `ADM` から抽出、終了時刻は未発表のため約6時間で想定)
- LINEUP (MUSIC BY / GUEST / SELECTOR)
- 入場料 (ADM)
- 公式詳細ページへのリンク

## ローカルで実行する場合

```bash
python3 scrape.py
```

Python 3 の標準ライブラリのみで動作します (外部依存なし)。

注意: 公式サイトは Shift_JIS と UTF-8 のページが混在しています。スクリプトは
エンコーディングを自動判別して処理します。
