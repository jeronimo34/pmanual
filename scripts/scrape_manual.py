#!/usr/bin/env python3
"""
Pleasanter 公式マニュアル (https://www.pleasanter.org/ja/manual) を
カテゴリツリーごと再帰的にクロールし、末端記事のURL一覧と本文キャッシュを作るスクリプト。

事前準備:
    pip install requests beautifulsoup4 trafilatura --break-system-packages

使い方:
    # まず2〜3件だけ試す（カテゴリツリーは深く辿らず、動作確認用）
    python scrape_manual.py --max-categories 1 --limit 3

    # 特定のURLだけピンポイントで試す（発見フェーズを完全にスキップ）
    python scrape_manual.py --urls https://www.pleasanter.org/ja/manual/site,https://www.pleasanter.org/ja/manual/basic-operations-folder

    # 本番: 全件検出して全文取得
    python scrape_manual.py

    # 途中から再開したい場合 (index.json があれば新規URLだけ追記取得)
    python scrape_manual.py --resume

出力:
    ../references/index.md      … 全記事のタイトル・URL・カテゴリ一覧 (索引)
    ../references/<slug>.md     … 記事ごとの本文キャッシュ (Markdown, frontmatter付き)
    ../references/index.json    … 索引の生データ (再開用)
"""

import argparse
import json
import re
import sys
import time
import urllib.parse as up
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None

BASE = "https://www.pleasanter.org"
START_URLS = [
    f"{BASE}/ja/manual",
    f"{BASE}/ja/manual?category=1_9100",
]
OUT_DIR = Path(__file__).resolve().parent.parent / "references"
INDEX_JSON = OUT_DIR / "index.json"
INDEX_MD = OUT_DIR / "index.md"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PleasanterManualArchiver/1.0; personal dev reference)"
}
REQUEST_INTERVAL_SEC = 1.0  # サーバに負荷をかけすぎないためのウェイト

LEAF_RE = re.compile(r"^/ja/manual/[A-Za-z0-9\-_]+/?$")
CATEGORY_RE = re.compile(r"^/ja/manual\?category=[0-9_]+$")


def normalize(href: str) -> str | None:
    if not href:
        return None
    url = up.urljoin(BASE, href)
    parsed = up.urlparse(url)
    if parsed.netloc not in ("www.pleasanter.org", "pleasanter.org"):
        return None
    path_q = parsed.path + (("?" + parsed.query) if parsed.query else "")
    if LEAF_RE.match(parsed.path):
        return BASE + parsed.path.rstrip("/")
    if CATEGORY_RE.match(path_q):
        return BASE + path_q
    return None


def fetch(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"  [warn] fetch failed: {url} ({e})", file=sys.stderr)
        return None


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def discover_all_leaf_urls(max_categories: int | None = None) -> dict[str, str]:
    """カテゴリツリーをBFSで辿り、末端記事URL -> リンクテキスト(仮タイトル) を集める

    max_categories を指定すると、その件数だけカテゴリページを訪問した時点で
    打ち切る（動作確認用の軽量モード）。None なら全件を辿る。
    """
    seen_categories: set[str] = set()
    leaves: dict[str, str] = {}
    frontier = list(START_URLS)
    start = time.time()

    while frontier:
        if max_categories is not None and len(seen_categories) >= max_categories:
            print(f"[discover] max-categories={max_categories} に達したため打ち切り")
            break
        url = frontier.pop(0)
        if url in seen_categories:
            continue
        seen_categories.add(url)
        elapsed = format_duration(time.time() - start)
        print(
            f"[discover] visited={len(seen_categories)} queued={len(frontier)} "
            f"leaves_found={len(leaves)} elapsed={elapsed} :: {url}"
        )
        html = fetch(url)
        time.sleep(REQUEST_INTERVAL_SEC)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            norm = normalize(a["href"])
            if not norm:
                continue
            if norm.startswith(f"{BASE}/ja/manual?category="):
                if norm not in seen_categories:
                    frontier.append(norm)
            else:
                text = a.get_text(strip=True)
                if norm not in leaves or (text and not leaves[norm]):
                    leaves[norm] = text
    return leaves


def slugify(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def scrape_article(url: str, fallback_title: str) -> dict | None:
    html = fetch(url)
    time.sleep(REQUEST_INTERVAL_SEC)
    if not html:
        return None

    title = fallback_title
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        title = soup.title.string.split("|")[0].strip()

    body_md = None
    if trafilatura is not None:
        body_md = trafilatura.extract(
            html, output_format="markdown", include_links=True, url=url
        )
    if not body_md:
        # trafilatura が無い/失敗した場合の簡易フォールバック
        for tag in soup(["nav", "header", "footer", "script", "style"]):
            tag.decompose()
        body_md = soup.get_text("\n", strip=True)

    return {"url": url, "title": title, "body_md": body_md}


def save_article(article: dict) -> Path:
    slug = slugify(article["url"])
    path = OUT_DIR / f"{slug}.md"
    front_matter = (
        "---\n"
        f"title: \"{article['title']}\"\n"
        f"source_url: {article['url']}\n"
        "---\n\n"
    )
    path.write_text(front_matter + (article["body_md"] or ""), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resume", action="store_true",
        help="index.json があれば流用し、未取得の本文だけ取りに行く"
    )
    parser.add_argument(
        "--max-categories", type=int, default=None,
        help="発見フェーズで訪問するカテゴリページ数の上限（動作確認用。例: 1）"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="実際に本文取得する記事数の上限（動作確認用。例: 3）"
    )
    parser.add_argument(
        "--urls", type=str, default=None,
        help="カンマ区切りでURLを直接指定。発見フェーズを完全にスキップして即座に本文取得する"
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.urls:
        leaves = {u.strip(): "" for u in args.urls.split(",") if u.strip()}
        print(f"[urls] 指定された {len(leaves)} 件のURLを直接処理します（発見フェーズをスキップ）")
    elif args.resume and INDEX_JSON.exists():
        leaves = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
        print(f"[resume] {len(leaves)} 件のURL一覧を読み込みました")
    else:
        leaves = discover_all_leaf_urls(max_categories=args.max_categories)
        INDEX_JSON.write_text(
            json.dumps(leaves, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[discover] 末端記事URLを {len(leaves)} 件検出しました")

    if args.limit is not None:
        leaves = dict(list(leaves.items())[: args.limit])
        print(f"[limit] 先頭 {len(leaves)} 件だけ本文取得します")

    index_lines = ["# Pleasanter マニュアル 索引\n"]
    total = len(leaves)
    start = time.time()
    done = 0
    for i, (url, hint_title) in enumerate(sorted(leaves.items()), 1):
        slug = slugify(url)
        target = OUT_DIR / f"{slug}.md"
        pct = (i / total * 100) if total else 100
        elapsed = time.time() - start
        avg = elapsed / done if done else None
        eta = format_duration(avg * (total - i + 1)) if avg else "計算中"
        prefix = f"[{i}/{total}] ({pct:5.1f}%) elapsed={format_duration(elapsed)} eta={eta}"
        if target.exists():
            print(f"{prefix} skip (cached): {slug}")
        else:
            print(f"{prefix} fetch: {slug}")
            article = scrape_article(url, hint_title or slug)
            done += 1
            if article:
                save_article(article)
            else:
                print(f"  [warn] 取得失敗のためスキップ: {slug}")
                continue
        # index.md 用にタイトルを取得（キャッシュ済みファイルの frontmatter から）
        text = target.read_text(encoding="utf-8") if target.exists() else ""
        m = re.search(r'title: "(.*?)"', text)
        title = m.group(1) if m else (hint_title or slug)
        index_lines.append(f"- [{title}]({slug}.md) — {url}")

    INDEX_MD.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    total_elapsed = format_duration(time.time() - start)
    print(f"\n完了: references/index.md と {len(leaves)} 件の記事キャッシュを出力しました。(所要時間 {total_elapsed})")


if __name__ == "__main__":
    main()
