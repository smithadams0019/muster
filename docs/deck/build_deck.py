"""Build the Muster pitch deck as one self-contained HTML file.

Nine slides, about ninety seconds of talking, then straight into the live demo.
The order is deliberate: nobody hears what the product does until they already
know why it should exist, and the enforcement figures land before the mechanism.

No stock photography. The subject is a rota and an ordinance, and the honest
illustrations are the product's own screens and the numbers themselves — a
photograph of a smiling barista would be decoration standing in for evidence.

Screenshots are re-encoded and inlined as data URIs, so the output is one file
that works from file:// with no network and no asset folder.

    python build_deck.py        ->  muster-deck.html
"""

import base64
import io
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
OUT = HERE / "muster-deck.html"


def data_uri(name: str, quality: int = 78, crop: tuple[float, float, float, float] | None = None) -> str:
    """Inline an image, optionally cropping first.

    `crop` is (left, top, right, bottom) as fractions of the image, because a
    government site screenshotted whole is four-fifths navigation and the part
    worth showing is the paragraph carrying the figure.
    """
    im = Image.open(HERE / name).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((round(crop[0] * w), round(crop[1] * h),
                      round(crop[2] * w), round(crop[3] * h)))
    if im.width > 1800:
        im = im.resize((1800, round(im.height * 1800 / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


SHOTS = {
    "schedule": data_uri("ui-schedule.png"),
    "autonomy": data_uri("ui-autonomy.png"),
    # The primary sources themselves. Not an agency logo: a logo next to a
    # product implies the regulator endorses it, which is the last thing a
    # compliance tool should imply, and it is decoration rather than proof.
    # These pages carry the actual figures the rulebook encodes.
    # Cropped to roughly the aspect of the box they sit in, so `cover` has
    # nothing left to trim and no sentence loses its first or last word.
    "src_oregon": data_uri("src-oregon.png", crop=(0.09, 0.40, 0.72, 0.93)),
    "src_nyc": data_uri("src-nyc.png", crop=(0.18, 0.12, 0.87, 0.66)),
}

#: Speaker notes, one per slide, taken verbatim from video-narration.txt so the
#: two cannot drift. They used to be a second draft of the same talk, and the
#: two drafts disagreed - the deck still said "nothing in Chicago, seventy-five
#: in New York" after the world had been reseeded to price eighteen and forty
#: five.
NOTES = [
    "Muster. An autonomous shift coordinator that knows the law.",

    "First the problem, because it is stranger than it looks. Somewhere right now "
    "a manager is writing next week's rota in a spreadsheet. That sounds like "
    "nothing. But eleven US jurisdictions regulate how it may be filled in. "
    "Fourteen days notice. Premiums when it changes. Extra pay for too little "
    "rest. A worker's right to say no.",

    "New York City settled with Starbucks for thirty eight point nine million "
    "dollars, after more than five hundred thousand violations. Chipotle settled "
    "for twenty million. Dunkin, Taco Bell and Walgreens have settled over the "
    "same law. Those are companies with legal departments. The person I built "
    "this for runs three coffee shops and faces the same rulebook.",

    "Here is what surprised me when I read them. The rules are not vague. They "
    "are arithmetic. Every one computable. Almost nobody computes them.",

    "Because the moment it matters is six in the morning. A hole in the rota, "
    "four legal ways to fill it, two needing someone's permission. Nobody works "
    "that out at six.",

    "So Muster does the deciding. It drafts next week under the law, then holds "
    "it together. A shift loses its worker; Muster finds every lawful cover, "
    "prices each against that city's ordinance, and takes the cheapest. Every "
    "change writes a receipt naming the clause, the money, and who decided.",

    "The same sick call, same wage, in three cities. Eighteen dollars in "
    "Portland, eighteen in Chicago - an hour at the worker's own rate. Forty five "
    "in New York, a flat tier. And nothing at all in Portland if the cover comes "
    "off the standby list, a carve-out only Oregon offers.",

    "The rulebook is data, not code, and every figure carries the government "
    "source it was read from.",

    "You decide how much rope it gets. Two rules ignore that dial completely. "
    "Muster will never waive a worker's rest period on their behalf, and never "
    "asks someone who has already said no. At every level, including the most "
    "permissive. That is not my opinion about agents. Oregon requires the "
    "worker's own consent, New York requires it in writing, Chicago says the "
    "Right to Rest has no exceptions. An agent that could dial past those would "
    "not be more capable. It would be unlawful.",

    "Strands Agents runs two loops on Bedrock. Claude reasons and never does the "
    "arithmetic: the premiums, the rest remedies and the totals are pure "
    "functions, which is why they are testable. It ships an MCP server over that "
    "engine too - read only, so another agent can ask what a change costs but "
    "cannot change anyone's week.",
]

SLIDES = f"""
<section class="s cover">
  <div class="mark">M</div>
  <h1>Muster</h1>
  <p class="lede">An autonomous shift coordinator that knows the law.</p>
  <p class="kicker">Strands Agents &middot; Amazon Bedrock &middot; Professional Agents</p>
</section>

<section class="s">
  <div class="rule"></div>
  <h2>Someone is writing next week's rota<br>in a spreadsheet right now.</h2>
  <p class="big-sub">Eleven US jurisdictions regulate how they are allowed to fill it in.</p>
  <p class="closer">Fourteen days' notice. Premiums when it changes. Extra pay for too little
    rest. And a worker's right to say no.</p>
</section>

<section class="s">
  <div class="rule"></div>
  <h2>The enforcement is not theoretical</h2>
  <div class="stats">
    <div class="stat hot"><b>$38.9M</b><p>New York City's settlement with Starbucks</p><cite>NYC DCWP</cite></div>
    <div class="stat"><b>500,000+</b><p>violations found across 300+ NYC locations</p><cite>DCWP investigation</cite></div>
    <div class="stat hot"><b>$20M</b><p>Chipotle — the largest such settlement in city history at the time</p><cite>NYC Mayor's Office</cite></div>
  </div>
  <p class="closer">Those are companies with legal departments. My operator has three coffee
    shops and the same rulebook.</p>
</section>

<section class="s">
  <div class="rule"></div>
  <h2>The rules are not vague. They are arithmetic.</h2>
  <ul class="stack">
    <li><h3>Oregon</h3><p>+1 hour at the regular rate to add a shift &middot; +&frac12; rate per hour taken away</p></li>
    <li><h3>Chicago</h3><p>1.25&times; base inside the rest period &middot; &ge;50% of hours cancelled late</p></li>
    <li><h3>New York City</h3><p>$10 / $20 / $45 / $75 by notice band &middot; $100 for a clopening</p></li>
  </ul>
  <p class="punch">Every one of them computable. None of them computed.</p>
</section>

<section class="s quote">
  <h2>Because the moment it matters<br>is 6am.</h2>
  <p class="big-sub">A hole in the rota, four legal ways to fill it, and no time to work out
    which one is cheapest — or which one needs someone's permission.</p>
</section>

<section class="s shot">
  <div class="shot-text">
    <div class="rule"></div>
    <h2>So Muster does the deciding.</h2>
    <p class="body">It drafts next week under the law, then holds it together: every lawful
      cover found, priced against that city's ordinance, cheapest one taken.</p>
    <p class="body">Every change writes a receipt naming the clause, the money, the carve-out
      claimed and who decided.</p>
  </div>
  <img src="{SHOTS["schedule"]}" alt="The Muster schedule console">
</section>

<section class="s">
  <div class="rule"></div>
  <h2>The same sick call. Same wage. Four answers.</h2>
  <div class="cities">
    <div class="city"><span class="place">Portland</span><b>$18.00</b><span class="why">one hour at the worker's own rate</span></div>
    <div class="city"><span class="place">Chicago</span><b>$18.00</b><span class="why">the same rule, a different statute</span></div>
    <div class="city hot"><span class="place">New York</span><b>$45.00</b><span class="why">a flat tier &mdash; under 7 days' notice</span></div>
    <div class="city free"><span class="place">Portland &middot; standby</span><b>$0.00</b><span class="why">a carve-out only Oregon offers</span></div>
  </div>
  <p class="closer">The rulebook is data, not code. Every figure carries the .gov source it was
    read from &mdash; and the carve-out is only free when the worker is on the list <i>and</i>
    accepted. A claim on its own buys nothing.</p>
</section>

<section class="s">
  <div class="rule"></div>
  <h2>I did not summarise the law. I read it.</h2>
  <div class="sources">
    <figure><img src="{SHOTS["src_oregon"]}" alt="Oregon BOLI, predictive scheduling">
      <figcaption>oregon.gov/boli &mdash; <b>one hour at the regular rate</b>, and
        <b>one-half</b> per scheduled hour not worked</figcaption></figure>
    <figure><img src="{SHOTS["src_nyc"]}" alt="NYC 311, Fair Workweek Law">
      <figcaption>portal.311.nyc.gov &mdash; the Fair Workweek Law, and the agency
        that enforces it</figcaption></figure>
  </div>
  <p class="closer">Four jurisdictions, read from primary sources and encoded as data. Every
    figure in the rulebook carries the URL it came from, so the work can be checked without
    reading any Python.</p>
</section>

<section class="s shot">
  <div class="shot-text">
    <div class="rule"></div>
    <h2>Two rules ignore the dial.</h2>
    <p class="body">Muster will never waive a worker's rest period on their behalf, and never
      asks a worker who has already declined.</p>
    <p class="body"><b>At every level, including the most permissive one.</b></p>
    <p class="cites">Oregon requires the worker's own consent &middot; NYC requires it in writing
      &middot; Chicago: the Right to Rest <b>has no exceptions</b></p>
  </div>
  <img src="{SHOTS["autonomy"]}" alt="The autonomy dial and the two fixed rules">
</section>

<section class="s centred">
  <div class="rule"></div>
  <h2>What powers it</h2>
  <ul class="stack">
    <li><h3>Strands Agents</h3><p>Two loops — DRAFT writes the week, HOLD keeps it together.</p></li>
    <li><h3>Amazon Bedrock</h3><p>Claude Sonnet reasons. It never does the arithmetic.</p></li>
    <li><h3>Interventions and interrupts</h3><p>The autonomy boundary is executable code, and a paused run resumes days later.</p></li>
    <li><h3>An MCP server</h3><p>The compliance engine, read-only. It can price a change; it cannot change a week.</p></li>
  </ul>
</section>
"""

CSS = """
:root {
  --ground:#ffffff; --wash:#f7f8fa; --line:#e3e6ec;
  --ink:#161a25; --ink-2:#5a6273; --ink-3:#8c94a6;
  --accent:#4429c4; --accent-2:#2f1b7a; --accent-soft:#efeaff;
  --hot:#b42318;
  --display:'Figtree', system-ui, sans-serif;
  --sans:'Inter', system-ui, sans-serif;
  --mono:'JetBrains Mono', ui-monospace, monospace;
}

html, body { height:100%; }
body { margin:0; background:#0d0a1f; color:var(--ink);
  font-family:var(--sans); overflow:hidden; }

/* Fixed 1280x720 stage, scaled to the window, so the layout recorded at 1080p
   is pixel-identical to the one authored here. */
#fit { position:absolute; top:50%; left:50%; transform-origin:50% 50%; }
#stage { position:relative; width:1280px; height:720px; overflow:hidden;
  background:var(--ground); box-shadow:0 24px 80px rgba(0,0,0,.5); }

.s { position:absolute; inset:0; padding:60px 76px;
  display:flex; flex-direction:column;
  opacity:0; visibility:hidden; transition:opacity .28s ease; background:var(--ground); }
.s.on { opacity:1; visibility:visible; }

h1,h2,h3 { font-family:var(--display); margin:0; letter-spacing:-.028em;
  text-wrap:balance; color:var(--ink); }
h2 { font-size:44px; font-weight:800; line-height:1.08; }
p { margin:0; }

.rule { width:52px; height:6px; border-radius:3px; background:var(--accent); margin-bottom:20px; flex:none; }

.cover { justify-content:center; background:linear-gradient(120deg, var(--accent-2), var(--accent)); }
.cover .mark { width:56px; height:56px; border-radius:14px; background:#fff; color:var(--accent);
  display:flex; align-items:center; justify-content:center;
  font-family:var(--display); font-weight:800; font-size:30px; margin-bottom:26px; }
.cover h1 { font-size:104px; font-weight:800; letter-spacing:-.045em; line-height:1; color:#fff; }
.cover .lede { font-family:var(--display); font-size:29px; font-weight:600; color:#d9d0ff; margin-top:16px; }
.cover .kicker { font-family:var(--mono); font-size:14px; color:#b3a6f0; margin-top:38px; }

.big-sub { margin-top:22px; font-size:25px; line-height:1.45; color:var(--ink-2); max-width:940px; }
.closer { margin-top:auto; padding-top:22px; border-top:1px solid var(--line);
  font-size:20px; line-height:1.45; color:var(--ink-2); }
.punch { margin-top:auto; font-family:var(--display); font-weight:800; font-size:28px; color:var(--accent); }
.punch.final { font-size:26px; }
.body { margin-top:18px; font-size:20px; line-height:1.5; color:var(--ink-2); }
.cites { margin-top:22px; font-size:16px; line-height:1.5; color:var(--ink-3); }

/* The closing slide ends on the list itself, so it is centred rather than
   top-aligned against half a slide of white. */
.centred { justify-content:center; }

.quote { justify-content:center; background:var(--wash); }
.quote h2 { font-size:62px; letter-spacing:-.04em; }

.stats { display:grid; grid-template-columns:repeat(3,1fr); gap:34px; margin-top:52px; }
.stat b { display:block; font-family:var(--display); font-weight:800; font-size:70px;
  line-height:.95; letter-spacing:-.045em; font-variant-numeric:tabular-nums; }
.stat.hot b { color:var(--accent); }
.stat p { margin-top:14px; font-size:17px; line-height:1.4; color:var(--ink-2); }
.stat cite { display:block; margin-top:9px; font-family:var(--mono); font-style:normal;
  font-size:12px; color:var(--ink-3); }

.stack { list-style:none; margin:32px 0 0; padding:0; display:flex; flex-direction:column; gap:20px; }
.stack li { border-left:4px solid var(--accent); padding-left:18px; }
.stack h3 { font-size:22px; font-weight:700; }
.stack p { margin-top:4px; font-size:18px; color:var(--ink-2); }

.cities { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-top:44px; }
.city { background:var(--wash); border:1px solid var(--line); border-radius:14px; padding:24px 20px; }
.city.hot { background:var(--accent-soft); border-color:#c9bcf5; }
.city .place { display:block; font-size:13px; font-weight:700; color:var(--ink-2);
  text-transform:uppercase; letter-spacing:.05em; }
.city b { display:block; margin-top:10px; font-family:var(--display); font-weight:800;
  font-size:44px; letter-spacing:-.04em; font-variant-numeric:tabular-nums; }
.city.hot b { color:var(--accent); }
/* The carve-out is the one that costs nothing, so it is the one that looks
   different from the three that cost something. */
.city.free { background:#f0fdf6; border-color:#bfe6cf; }
.city.free b { color:#12734a; }
.city .why { display:block; margin-top:8px; font-size:14px; line-height:1.4; color:var(--ink-2); }

.sources { display:grid; grid-template-columns:1fr 1fr; gap:26px; margin-top:36px; }
.sources figure { margin:0; }
.sources img { width:100%; height:330px; object-fit:cover; object-position:left top;
  border:1px solid var(--line); border-radius:12px; box-shadow:0 6px 22px rgba(22,26,37,.10); }
.sources figcaption { margin-top:12px; font-family:var(--mono); font-size:12.5px;
  line-height:1.5; color:var(--ink-3); }
.sources figcaption b { font-family:var(--sans); font-weight:600; color:var(--ink-2); }

.shot { flex-direction:row; gap:38px; align-items:center; padding:52px 0 52px 76px; }
.shot-text { width:520px; flex:none; }
.shot img { flex:1 1 auto; width:100%; height:600px; object-fit:cover; object-position:left top;
  border:1px solid var(--line); border-radius:14px 0 0 14px; box-shadow:-8px 0 30px rgba(22,26,37,.10); }

#bar { position:fixed; top:0; left:0; height:3px; background:var(--accent); transition:width .28s ease; z-index:5; }
#chrome { position:fixed; inset:auto 0 0 0; padding:12px 18px; display:flex; gap:14px;
  justify-content:flex-end; font-family:var(--mono); font-size:12px;
  color:rgba(255,255,255,.5); opacity:0; transition:opacity .3s; pointer-events:none; }
#chrome.show { opacity:1; }
#notes { position:fixed; inset:auto 0 0 0; background:rgba(10,8,24,.95); color:#e6e2f5;
  font-size:14px; line-height:1.6; padding:18px 24px; display:none; }
#notes.show { display:block; }

@media (prefers-reduced-motion:reduce) { .s, #bar { transition:none; } }
"""

JS = """
const slides = [...document.querySelectorAll('.s')];
const notes = %NOTES%;
const bar = document.getElementById('bar');
const notesEl = document.getElementById('notes');
const counter = document.getElementById('count');
let i = 0;

function show(n) {
  i = Math.max(0, Math.min(slides.length - 1, n));
  slides.forEach((s, k) => s.classList.toggle('on', k === i));
  bar.style.width = ((i + 1) / slides.length * 100) + '%';
  counter.textContent = (i + 1) + ' / ' + slides.length;
  notesEl.textContent = notes[i] || '';
  location.hash = i + 1;
}

function fit() {
  const k = Math.min(innerWidth / 1280, innerHeight / 720);
  document.getElementById('fit').style.transform = 'translate(-50%, -50%) scale(' + k + ')';
}

addEventListener('resize', fit);
addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { show(i + 1); e.preventDefault(); }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') show(i - 1);
  else if (e.key === 'Home') show(0);
  else if (e.key === 'End') show(slides.length - 1);
  else if (e.key === 'n' || e.key === 'N') notesEl.classList.toggle('show');
  else if (e.key === 'f' || e.key === 'F') document.documentElement.requestFullscreen?.();
});

let idle;
addEventListener('mousemove', () => {
  const c = document.getElementById('chrome');
  c.classList.add('show');
  clearTimeout(idle);
  idle = setTimeout(() => c.classList.remove('show'), 2000);
});

fit();
show(parseInt(location.hash.slice(1)) - 1 || 0);
"""

import json

HTML = f"""<meta charset="utf-8">
<title>Muster Pitch Deck</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style>

<div id="bar"></div>
<div id="fit"><div id="stage">{SLIDES}</div></div>
<div id="chrome"><span id="count"></span><span>&larr; &rarr; to move &middot; N for notes &middot; F for full screen</span></div>
<div id="notes"></div>

<script>{JS.replace("%NOTES%", json.dumps(NOTES))}</script>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB, {HTML.count('<section')} slides)")
