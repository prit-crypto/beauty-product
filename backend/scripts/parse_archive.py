"""Parse archived WooCommerce product pages (web.archive.org snapshots of drbeautycare.org)."""
import html
import json
import os
import re
import sys


def clean(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def grab(pat: str, t: str) -> str:
    m = re.search(pat, t, re.S)
    return m.group(1) if m else ""


def parse_page(t: str) -> dict:
    title = clean(grab(r'<h1[^>]*product_title[^>]*>(.*?)</h1>', t)) or clean(grab(r"<title>(.*?)</title>", t))
    prices = re.findall(r"([\d,]+\.\d\d)", clean(grab(r'<p class="price">(.*?)</p>', t)))
    short = clean(grab(r'woocommerce-product-details__short-description">(.*?)</div>', t))
    desc = clean(grab(r'id="tab-description"[^>]*>(.*?)</div>\s*(?:<div class="woocommerce-Tabs-panel|</div>)', t))
    cats = re.findall(r'rel="tag">([^<]+)</a>', grab(r'class="posted_in">(.*?)</span>', t))
    image = grab(r'property="og:image" content="([^"]+)"', t)
    return {
        "name": title,
        "prices_aed": [float(p.replace(",", "")) for p in prices],
        "categories": [html.unescape(c) for c in cats],
        "short": short,
        "description": desc,
        "original_image_url": image,
    }


def parse_dir(d: str) -> list[dict]:
    out = []
    for f in sorted(os.listdir(d)):
        if not f.endswith(".html"):
            continue
        with open(os.path.join(d, f), encoding="utf-8", errors="ignore") as fh:
            rec = parse_page(fh.read())
        rec["slug"] = f[:-5]
        out.append(rec)
    return out


if __name__ == "__main__":
    json.dump(parse_dir(sys.argv[1]), sys.stdout, ensure_ascii=False, indent=1)
