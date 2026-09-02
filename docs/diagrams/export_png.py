"""Export each page of the .drawio file to a trimmed PNG.

The .drawio file is the editable source and belongs in the repo. Devpost's
gallery takes images, so each page also ships as a PNG, rendered through
draw.io's own viewer so the export cannot drift from what opens in the editor,
then trimmed of the whitespace the fixed-size render leaves around it.

    python export_png.py    ->  muster-how-it-works.png, muster-under-the-hood.png
"""

import asyncio
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.async_api import async_playwright

HERE = Path(__file__).parent
SRC = HERE / "muster-architecture.drawio"
NAMES = ["muster-how-it-works.png", "muster-under-the-hood.png"]
VIEWER = "https://viewer.diagrams.net/js/viewer-static.min.js"


def trim(path: Path, pad: int = 28) -> None:
    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).getbbox()
    if not box:
        return
    l, t, r, b = box
    im.crop((max(0, l - pad), max(0, t - pad),
             min(im.width, r + pad), min(im.height, b + pad))).save(path)


async def main() -> None:
    pages = re.findall(r"(<diagram\b.*?</diagram>)", SRC.read_text(), re.S)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
        for page_xml, name in zip(pages, NAMES):
            xml = f'<mxfile host="app.diagrams.net" type="device">{page_xml}</mxfile>'
            cfg = json.dumps({"nav": False, "toolbar": "", "resize": True, "xml": xml})
            # The browser unescapes entities in an attribute before the viewer
            # reads them, so the escaped line breaks in the labels need escaping
            # again here - "&" first, or the rest is undone.
            cfg = (cfg.replace("&", "&amp;").replace("<", "&lt;")
                      .replace(">", "&gt;").replace("'", "&#39;"))
            html = ('<!doctype html><html><body style="margin:0;background:#fff">'
                    f'<div class="mxgraph" data-mxgraph=\'{cfg}\'></div>'
                    f'<script src="{VIEWER}"></script></body></html>')
            tab = await browser.new_page(viewport={"width": 1700, "height": 1000},
                                         device_scale_factor=2)
            await tab.set_content(html, wait_until="networkidle")
            await tab.wait_for_timeout(4000)
            out = HERE / name
            await tab.screenshot(path=str(out), full_page=True)
            trim(out)
            print("wrote", out, Image.open(out).size)
            await tab.close()
        await browser.close()


asyncio.run(main())
