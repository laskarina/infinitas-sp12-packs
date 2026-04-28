# IIDX INFINITAS × ☆12難易度表

beatmania IIDX INFINITAS の収録曲のうち、
[SP☆12非公式難易度表](https://iidx-sp12.github.io/) に掲載されている譜面の難易度を、
カテゴリ別に一覧できる対応表です。

**GitHub Actions による週次自動更新** に対応。新パック追加・難易度改定が反映されると、月曜の昼に `data.json` が自動更新されます。

## 対象カテゴリ

| カテゴリ | 種別 |
| --- | --- |
| 新規追加曲 | 直近に追加された曲 |
| 初期収録曲 | INFINITASベーシックコースで遊べる曲（IIDXバージョン別にサブグループ化） |
| DJP解禁曲 | DJP解禁曲 |
| BIT解禁曲 | BIT解禁曲（IIDXバージョン別にサブグループ化） |
| 楽曲パック | 各パック（vol.1〜最新版）を個別に表示 |

LEGGENDARIA譜面はそれぞれ Lディスク入手元のカテゴリ／パックに紐づけて表示。

## 機能

- 難易度フィルタ（S+〜F）
- ノマゲ／ハードの切替表示
- カテゴリ／パック単位のジャンプリンク
- レスポンシブ対応

## ファイル構成

```
.
├── index.html              # サイト本体（data.json を fetch）
├── data.json               # 集計データ（自動更新）
├── scripts/
│   └── build.py            # 上流2ソース → data.json 生成
├── .github/workflows/
│   └── update.yml          # 週次 cron + 手動実行
└── README.md
```

## 動作の流れ

```
[週次 cron / 手動トリガー]
        ↓
GitHub Actions が build.py を実行
        ↓
  iidx-sp12.github.io/songs.json   ←── fetch
  e-amusement の楽曲一覧 HTML       ←── fetch
        ↓
  パース → マージ → data.json 生成
        ↓
  差分があれば自動コミット & push
        ↓
[GitHub Pages]
  index.html が data.json を fetch して描画
```

## セットアップ（初回のみ）

### 1. リポジトリ作成

```bash
git init
git add .
git commit -m "Initial commit"

# GitHub に新規リポジトリを作成
git branch -M main
git remote add origin https://github.com/<your-user>/<repo-name>.git
git push -u origin main
```

### 2. GitHub Pages を有効化

リポジトリページで:

1. **Settings** → **Pages**
2. **Source**: `Deploy from a branch`
3. **Branch**: `main` / `/ (root)` → **Save**

数分後に `https://<your-user>.github.io/<repo-name>/` で公開されます。

### 3. Actions の権限を確認

1. **Settings** → **Actions** → **General**
2. **Workflow permissions**: **Read and write permissions** → **Save**

これで Actions が自動コミットできるようになります。

### 4. 初回データ生成

ローカルで一度走らせて `data.json` をコミット:

```bash
python3 scripts/build.py
git add data.json
git commit -m "Generate initial data.json"
git push
```

または、Actions タブから `Update data.json` ワークフローを **Run workflow** で手動実行しても同じです（こちらの方が楽）。

## ローカル動作確認

```bash
python3 scripts/build.py
python3 -m http.server 8000
# → http://localhost:8000/ にアクセス
```

`fetch()` を使うので `file://` ではなく HTTP 経由が必要です。

## カスタマイズ

### 更新頻度を変えたい

`.github/workflows/update.yml` の cron を編集:

```yaml
schedule:
  - cron: '0 3 * * 1'   # 毎週月曜 03:00 UTC (= 月曜 12:00 JST)
```

### data.json を手動更新したい

Actions タブから `Update data.json` を **Run workflow** で実行できます。

## データ仕様

`data.json` のスキーマ（v2）:

```jsonc
{
  "schema_version": 2,
  "generated_at": "ISO8601 UTC",
  "sources": {
    "songs": { "url": "...", "sha256": "...", "size": ... },
    "packs": { "url": "...", "sha256": "...", "size": ... }
  },
  "stats": {
    "section_count": 46, "category_count": 4, "pack_count": 42, "chart_count": 495
  },
  "sections": [
    // category section (flat)
    { "type": "category", "id": "newsong", "name": "新規追加曲",
      "subtitle": "...", "rows": [...], "total": 2 },
    // category section (grouped by IIDX version)
    { "type": "category", "id": "default", "name": "初期収録曲",
      "groups": [ { "label": "beatmania IIDX 12 HAPPY SKY", "rows": [...] }, ... ],
      "total": 207 },
    // pack section
    { "type": "pack", "name": "...vol.29...",
      "rows": [...], "total": 50 }
  ]
}
```

各 `row`:

```jsonc
{
  "t": "曲名",  "k": "A"|"L"|"H",  "y": 0|1,  // y: スペシャルセレクション
  "n": "地力S+", "h": "地力S+",                // 表示用ラベル
  "nt": "S+",  "ht": "S+",                    // ティアのみ抽出（フィルタ用）
  "nk": 0|1,   "hk": 0|1,                     // 個人差フラグ
  "v": 32                                     // IIDX版数
}
```

## データソース

- 難易度表: [iidx-sp12.github.io/songs.json](https://iidx-sp12.github.io/songs.json)
- 楽曲一覧: [KONAMI e-amusement](https://p.eagate.573.jp/game/infinitas/2/music/index.html)

## 注意事項

- 本ページは KONAMI および ☆12難易度表運営とは無関係の非公式な集計ページです。
- 譜面の難易度評価は ☆12難易度表 の更新により変動します。
- LEGGENDARIA譜面は、Lディスクの入手元が当該カテゴリ／パックに紐づくもののみ含まれます。
- 上流ページの構造変更により Actions が失敗する可能性があります。失敗時は Actions タブのログを確認のうえ、`scripts/build.py` のパース部分を更新してください。
