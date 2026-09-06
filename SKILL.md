---
name: pleasanter-manual
description: Pleasanter (プリザンター) のインストール、パラメータ設定、API、スクリプト、サーバスクリプト、拡張機能、Extensions/Development Tools/Operations Tools/Code Assist など、開発・運用に関する質問が来たら必ずこのスキルを使うこと。ユーザが「プリザンターで〜する方法」「Pleasanterのマニュアルでは」「エラーが出た」など製品固有の質問をした場合、まずこのスキルのreferences/index.mdでキャッシュ済み記事を検索し、該当があれば読み込んで回答する。ローカルにキャッシュされた公式マニュアルの開発リファレンス。
---

# Pleasanter マニュアル ローカルリファレンス

`references/` 配下に、Pleasanter公式マニュアル (https://www.pleasanter.org/ja/manual) の記事本文を
Markdownでキャッシュしてあります。個人の開発リファレンス用途のローカルコピーです。

## 使い方

1. `references/index.md` を読み、質問に関連しそうな記事のタイトルを探す。
   - 見出しやタイトルで見つからない場合は `grep -ril` などでキーワード検索してよい。
2. 該当する `references/<slug>.md` を読み込み、その内容をもとに回答する。
3. 回答の最後に、参照した記事の `source_url` (frontmatterに記載) を出典として明記する。
   - 本文を丸ごと引用せず、要点を自分の言葉でまとめること。長い引用はしない。
4. キャッシュに載っていない/古い可能性がある場合は、`source_url` を直接fetchして最新内容を確認してから回答する。

## 索引の構造

`references/index.md` は「タイトル — URL」の一覧です。カテゴリ単位の見出しは持たないフラットな索引なので、
まずキーワードで探し、見つからなければ関連しそうな複数記事を横断的にあたること。

## 更新方法

このキャッシュは `scripts/scrape_manual.py` で生成されています。マニュアルが更新された場合は、
以下を実行して再取得してください（サーバへの負荷軽減のため1秒間隔でアクセスします）。

```bash
pip install requests beautifulsoup4 trafilatura --break-system-packages
cd scripts
python scrape_manual.py            # 初回: 全記事URLを検出して全文取得
python scrape_manual.py --resume   # 2回目以降: 検出済みURL一覧を使い、未取得分のみ取得
```

キャッシュ済みの `.md` ファイルは上書きされないので、特定記事だけ更新したい場合は
該当ファイルを削除してから `--resume` で再実行してください。

## 注意事項

- このキャッシュは個人の開発作業を助けるための参照用です。再配布や商用利用を検討する場合は
  [マニュアル二次利用ガイドライン](https://www.pleasanter.org/manual-reuse-guidelines/) を確認してください。
- 本文を長文のまま出力・転載しない。要約・言い換えを基本とし、必要な場合のみ15語未満の短い引用に留める。
