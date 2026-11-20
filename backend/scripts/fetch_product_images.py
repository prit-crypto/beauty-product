"""Download product photos listed in a JSON map {id: {"image_url", "source_page"} | null} into frontend/public/products.

Every file is checked to be a real image, resized to max 900 px and saved as <id>.webp. Sources are recorded in
backend/data/product_image_sources.json (photos belong to their brands; for the private demo only).
Usage: python scripts/fetch_product_images.py map1.json [map2.json ...]
"""
import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "products"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def main(paths: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources_file = Path(__file__).resolve().parents[1] / "data" / "product_image_sources.json"
    sources = json.loads(sources_file.read_text()) if sources_file.exists() else {}
    ok, failed = 0, []
    for path in paths:
        for pid, info in json.loads(Path(path).read_text()).items():
            if not info or not info.get("image_url"):
                continue
            try:
                r = httpx.get(info["image_url"], headers=UA, timeout=30, follow_redirects=True)
                r.raise_for_status()
                im = Image.open(io.BytesIO(r.content))
                im.load()
                if min(im.size) < 200:
                    raise ValueError(f"too small {im.size}")
                im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
                im.thumbnail((900, 900))
                im.save(OUT / f"{pid}.webp", "WEBP", quality=86)
                sources[pid] = {"image_url": info["image_url"], "source_page": info.get("source_page"), "match": info.get("match")}
                ok += 1
            except Exception as e:  # noqa: BLE001
                failed.append(f"{pid}: {type(e).__name__} {str(e)[:80]}")
    sources_file.write_text(json.dumps(sources, indent=1))
    print(f"saved {ok} photos to {OUT}")
    for f in failed:
        print("FAILED", f)


if __name__ == "__main__":
    main(sys.argv[1:])
