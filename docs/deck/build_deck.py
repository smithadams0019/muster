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


def data_uri(name: str, quality: int = 78) -> str:
    im = Image.open(HERE / name).convert("RGB")
    if im.width > 1800:
        im = im.resize((1800, round(im.height * 1800 / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


SHOTS = {
    "schedule": data_uri("ui-schedule.png"),
    "decisions": data_uri("ui-decisions.png"),
    "autonomy": data_uri("ui-autonomy.png"),
}

NOTES = [
    "Muster. An autonomous shift coordinator that knows the law. Before I show "
    "you what it does, the problem, because it is a stranger one than it looks.",

    "Somewhere right now a manager is writing next week's rota in a spreadsheet. "
    "That sounds like nothing. But eleven US jurisdictions now regulate how that "
    "spreadsheet is allowed to be filled in.",

    "And the enforcement is not theoretical. New York City settled with Starbucks "
    "for thirty-eight point nine million dollars, after finding more than five "
    "hundred thousand violations across three hundred locations. Chipotle, twenty "
    "million. Dunkin', Taco Bell, Theory and Walgreens have all settled over the "
    "same law. Those are companies with legal departments. The person I built this "
    "for runs three coffee shops and faces the identical rulebook.",

    "Here is what surprised me. The rules are not vague. They are arithmetic. "
    "Oregon owes one hour at the regular rate for adding a shift. Chicago owes a "
    "quarter over base for working inside the rest period. New York owes ten, "
    "twenty, forty-five or seventy-five dollars depending on the notice given. You "
    "can compute every one of them.",

    "Nobody does. Because the moment it matters is a sick call at six in the "
    "morning, and at six in the morning the manager has a hole in the rota and no "
    "time to work out which of four legal fixes is cheapest.",

    "So Muster does the computing. It drafts next week under the law, and then it "
    "holds that week together. A shift loses its worker, and it finds every lawful "
    "cover, prices each against that city's own ordinance, takes the cheapest, and "
    "writes a receipt naming the clause.",

    "This is the same sick call, at the same hour, at the same wage, in three "
    "cities. Eighteen dollars in Portland. Nothing in Chicago. Seventy-five in New "
    "York. Three different formulas from three different ordinances, and the "
    "rulebook is data, not code, so each figure carries the government source it "
    "was read from.",

    "You decide how much rope it gets. But two rules ignore that dial completely. "
    "Muster will never waive a worker's rest period on their behalf, and never asks "
    "a worker who has already said no. That is not my opinion about agents. Oregon "
    "requires the worker's own consent, New York requires it in writing, and "
    "Chicago's guidance says the Right to Rest has no exceptions.",

    "Strands Agents runs two loops on Bedrock. Claude does the reasoning and never "
    "the arithmetic. It ships an MCP server over the compliance engine, read-only, "
    "so nothing over that protocol can change anyone's week. Two hundred and "
    "twenty-six tests offline, and it is live on AWS right now. Let's use it.",
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
  <h2>The same sick call. Three cities.</h2>
  <div class="cities">
    <div class="city"><span class="place">Portland</span><b>$18.00</b><span class="why">one hour at the regular rate</span></div>
    <div class="city"><span class="place">Chicago</span><b>$0.00</b><span class="why">no tier for this change</span></div>
    <div class="city hot"><span class="place">New York</span><b>$75.00</b><span class="why">under 24 hours' notice</span></div>
  </div>
  <p class="closer">The rulebook is data, not code. Every figure carries the .gov source it was
    read from, so you can check the work without reading any Python.</p>
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

<section class="s">
  <div class="rule"></div>
  <h2>What powers it</h2>
  <ul class="stack">
    <li><h3>Strands Agents</h3><p>Two loops — DRAFT writes the week, HOLD keeps it together.</p></li>
    <li><h3>Amazon Bedrock</h3><p>Claude Sonnet 4.6 reasons. It never does the arithmetic.</p></li>
    <li><h3>Interventions and interrupts</h3><p>The autonomy boundary is executable code, and a paused run resumes days later.</p></li>
    <li><h3>An MCP server</h3><p>The compliance engine, read-only. It can price a change; it cannot change a week.</p></li>
  </ul>
  <p class="punch final">226 tests offline. &nbsp;Live on AWS right now. &nbsp;Let's use it.</p>
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

.cities { display:grid; grid-template-columns:repeat(3,1fr); gap:22px; margin-top:44px; }
.city { background:var(--wash); border:1px solid var(--line); border-radius:14px; padding:26px 24px; }
.city.hot { background:var(--accent-soft); border-color:#c9bcf5; }
.city .place { display:block; font-size:15px; font-weight:700; color:var(--ink-2);
  text-transform:uppercase; letter-spacing:.06em; }
.city b { display:block; margin-top:10px; font-family:var(--display); font-weight:800;
  font-size:56px; letter-spacing:-.04em; font-variant-numeric:tabular-nums; }
.city.hot b { color:var(--accent); }
.city .why { display:block; margin-top:8px; font-size:15px; color:var(--ink-2); }

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
