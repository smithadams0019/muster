"""Build the Muster video thumbnail, 1280x720.

A thumbnail is judged at about a fifth of its size, in a grid, beside competing
thumbnails, so it gets one idea and no sentences. The idea here is the gap that
made the project: an enormous enforcement number set against the person who has
none of the resources to avoid it.

    python build_thumb.py       ->  thumbnail.html  (render at 1280x720)
"""

from pathlib import Path

HERE = Path(__file__).parent

HTML = """<meta charset="utf-8">
<title>Muster thumbnail</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@700;800;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap">
<style>
  :root {
    --ink:#161a25; --ink-2:#5a6273;
    --accent:#4429c4; --accent-2:#2f1b7a; --wash:#f4f2fd;
  }
  html, body { margin:0; background:#000; }

  /* Authored at exactly the upload size, so nothing is resampled on the way
     to YouTube. */
  .t { position:relative; width:1280px; height:720px; overflow:hidden;
       background:var(--wash); font-family:'Inter', system-ui, sans-serif; }

  /* The figure is the whole thumbnail. At grid size a numeral survives being
     shrunk further than any sentence will. */
  .fig { position:absolute; left:64px; top:96px; margin:0;
    font-family:'Figtree',sans-serif; font-weight:900; font-size:210px;
    line-height:.84; letter-spacing:-.055em; color:var(--accent);
    font-variant-numeric:tabular-nums; }
  .for { position:absolute; left:70px; top:322px; margin:0; width:1150px;
    font-family:'Figtree',sans-serif; font-weight:800; font-size:52px;
    line-height:1.06; letter-spacing:-.03em; color:var(--ink); }
  .for span { color:var(--ink-2); font-weight:700; }

  .rule { position:absolute; left:70px; top:470px; width:104px; height:7px;
    border-radius:4px; background:var(--ink); }
  .kick { position:absolute; left:70px; top:508px; margin:0; width:940px;
    font-size:27px; line-height:1.35; color:var(--ink-2); }

  .lock { position:absolute; left:70px; bottom:50px;
    display:flex; align-items:center; gap:14px; }
  .mark { width:38px; height:38px; border-radius:10px; background:var(--accent);
    color:#fff; display:flex; align-items:center; justify-content:center;
    font-family:'Figtree',sans-serif; font-weight:800; font-size:21px; }
  .name { font-family:'Figtree',sans-serif; font-weight:800; font-size:34px;
    letter-spacing:-.035em; color:var(--ink); }
  .desc { font-family:'JetBrains Mono',monospace; font-size:15px; color:var(--ink-2);
    padding-left:14px; border-left:2px solid var(--ink-2); opacity:.8; }

  /* A quiet corner wash so the flat ground does not read as unfinished. */
  .glow { position:absolute; right:-160px; top:-160px; width:620px; height:620px;
    border-radius:50%; background:radial-gradient(closest-side,
      rgba(68,41,196,.16), rgba(68,41,196,0)); }
</style>

<div class="t">
  <div class="glow"></div>
  <p class="fig">$38.9M</p>
  <p class="for">was the settlement for getting <span>shift schedules</span> wrong.</p>
  <div class="rule"></div>
  <p class="kick">Starbucks had lawyers. Your local coffee shop has the same rulebook.</p>
  <div class="lock">
    <div class="mark">M</div>
    <div class="name">Muster</div>
    <div class="desc">agentic scheduling &middot; AWS</div>
  </div>
</div>
"""

(HERE / "thumbnail.html").write_text(HTML, encoding="utf-8")
print("wrote", HERE / "thumbnail.html")
