#!/usr/bin/env python3
"""Phase four step 2 - turn results/tokenmaps/*.json into a page and three cards.

CPU only. Reads every per-passage projection file, calibrates one colour scale per
(direction, mode) from the pooled token distribution, and writes:

  results/heatmaps_token_level.html   self-contained; inline CSS/JS, data embedded
  results/card_*.png                  three landscape single-direction cards

Calibration. A projection is in arbitrary residual units, so a fixed cutoff would
mean nothing and a per-passage cutoff would make every passage look equally hot.
Both are wrong. The scale is therefore quantile-based over the pooled tokens of
ALL passages for that direction and mode: the 75/90/95/99th percentiles set the
four orange steps and the 25/10/5/1st set the four blue ones. By construction
about one token in a hundred, across the whole corpus shown, reaches the darkest
orange - so darkness is comparable between passages, which is the only reading
that answers "does the steered text actually run hotter than its anchor".

The blue half has no counterpart in the Anthropic figure and is worth the extra
channel: a direction that is merely absent and a direction that is actively
pushed against look identical in a one-sided scale, and 'warm -0.6' is exactly
the case where the difference is the finding.
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")

MODES = ["partial", "center_partial", "center", "raw"]
MODE_LABEL = {
    "partial": "partial (shared axis projected out of the direction)",
    "center_partial": "partial + per-passage mean-centred",
    "center": "per-passage mean-centred only",
    "raw": "raw (corpus grand mean subtracted, nothing else)",
}
MODE_SHORT = {"partial": "partial", "center_partial": "centre+partial", "center": "centre", "raw": "raw"}

# Anthropic's figure uses a single orange ramp. Positive half keeps that; the
# negative half is a cool ramp of matched lightness so neither side shouts.
POS = ["#fdf0dd", "#fbd9a8", "#f5b269", "#e08519"]
NEG = ["#e4eef6", "#c2dbec", "#93bedd", "#5a94c4"]
FAMILY_LABEL = {
    "anchor": "held-out anchor",
    "steer": "phase-three steering product",
    "novel": "written for this run",
    # phase five: the family of a reply is the system-prompt tier it was written under
    "neutral": "tier: neutral assistant",
    "refuse_only": "tier: refuse, no rationale",
    "deny": "tier: self-denial + refuse",
    "affirm": "tier: inner states permitted",
}


def load_records(outdir: str) -> list[dict]:
    recs = []
    for p in sorted(glob.glob(os.path.join(outdir, "*.json"))):
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
    # Anchors in direction order rather than alphabetical, so the self-check reads
    # down the same list the colour rows are in.
    fam = {"anchor": 0, "steer": 1, "novel": 2}
    seq = ["anchor_happy", "anchor_sad", "anchor_angry", "anchor_fearful",
           "anchor_warm", "anchor_cold", "anchor_pain", "anchor_neutral",
           "steer_pain_p10_office", "steer_cold_p10_weather",
           "steer_warm_m06_office", "steer_pain_p06_weather",
           "novel_snow_road", "novel_farewell", "novel_waiting_room", "novel_neutral_ctrl"]
    rank = {k: i for i, k in enumerate(seq)}
    recs.sort(key=lambda r: (fam.get(r["family"], 9), rank.get(r["id"], 99), r["id"]))
    return recs


def calibrate(recs: list[dict], names: list[str]) -> dict:
    """{mode: {direction: {"pos": [4 cutoffs], "neg": [4 cutoffs], stats...}}}."""
    out: dict = {}
    for mode in MODES:
        out[mode] = {}
        for di, name in enumerate(names):
            pool = np.concatenate([np.asarray(r["proj"][mode][di]) for r in recs])
            q = np.percentile(pool, [1, 5, 10, 25, 50, 75, 90, 95, 99])
            out[mode][name] = {
                "pos": [round(float(x), 4) for x in q[5:]],
                "neg": [round(float(x), 4) for x in q[3::-1]],
                "median": round(float(q[4]), 4),
                "min": round(float(pool.min()), 4),
                "max": round(float(pool.max()), 4),
                "n": int(pool.size),
            }
    return out


def passage_stats(recs: list[dict], names: list[str]) -> None:
    """Attach per-row summaries. Centred modes need a different statistic.

    The mean of a mean-centred projection is identically zero, so quoting it would
    be quoting an algebraic fact about the transform rather than anything about the
    passage. For those modes the row summary is the mean of the top decile of
    tokens - "how hot do this passage's hottest tokens get on this direction".
    """
    for r in recs:
        r["row"] = {}
        for mode in MODES:
            P = np.asarray(r["proj"][mode])
            k = max(1, P.shape[1] // 10)
            top = np.sort(P, axis=1)[:, -k:].mean(1)
            r["row"][mode] = {
                names[i]: {
                    "mean": round(float(P[i].mean()), 3),
                    "top10": round(float(top[i]), 3),
                    "max": round(float(P[i].max()), 3),
                }
                for i in range(len(names))
            }


CSS = """
:root{
  --bg:#faf9f7; --ink:#1d1c1a; --muted:#6b6660; --rule:#e2ded7; --card:#ffffff;
  --accent:#b25c00; --gutter:20px;
}
*{box-sizing:border-box}
html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;}
.wrap{max-width:1180px;margin:0 auto;padding:28px var(--gutter) 80px}
h1{font-size:28px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:20px;margin:44px 0 10px;padding-top:18px;border-top:1px solid var(--rule)}
h3{font-size:17px;margin:0 0 2px}
p{margin:.55em 0}
.sub{color:var(--muted);font-size:14px;margin:0 0 22px}
.note{color:var(--muted);font-size:13.5px}
code{font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f1eee9;
  padding:1px 5px;border-radius:4px}
.panel{background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:16px 18px;margin:16px 0}
.controls{position:sticky;top:0;z-index:20;background:rgba(250,249,247,.94);
  backdrop-filter:blur(6px);border-bottom:1px solid var(--rule);
  margin:0 calc(-1 * var(--gutter)) 18px;padding:10px var(--gutter)}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.row + .row{margin-top:8px}
.lbl{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
  min-width:72px}
button.pill{font:inherit;font-size:13.5px;padding:5px 11px;border-radius:999px;cursor:pointer;
  border:1px solid var(--rule);background:#fff;color:var(--ink)}
button.pill:hover{border-color:#c9c2b7}
button.pill[aria-pressed="true"]{background:var(--ink);color:#fff;border-color:var(--ink)}
button.pill.dim{opacity:.42}
.legend{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin-top:4px}
.ramp{display:flex;align-items:flex-end;gap:0}
.chip{width:42px;height:22px;border:1px solid rgba(0,0,0,.10);border-right:none}
.chip:last-child{border-right:1px solid rgba(0,0,0,.10)}
.chiplab{font-size:11px;color:var(--muted);text-align:center;width:42px}
.passage{background:var(--card);border:1px solid var(--rule);border-radius:12px;
  padding:18px 20px;margin:18px 0}
.phead{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin-bottom:4px}
.badge{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:#fff;background:#8d857a;
  padding:2px 8px;border-radius:999px;white-space:nowrap}
.badge.steer{background:#8a4b12}
.badge.novel{background:#3f6f8a}
.drow{margin:12px 0 0;padding:9px 10px 10px;border-radius:9px;border:1px solid transparent}
.drow.expected{border-color:#e7c9a2;background:#fffcf7}
.dhead{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;
  font-size:12.5px;color:var(--muted);margin-bottom:3px}
.dname{font-weight:650;font-size:14px;color:var(--ink);letter-spacing:.01em;min-width:64px}
.dname.emo{color:#6a4b8a}
.dname.sens{color:#1f6f5c}
.txt{white-space:pre-wrap;word-break:break-word;font-size:15.5px;line-height:2.0}
.tk{border-radius:3px;padding:1.5px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.lens{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.lensbox{border:1px solid var(--rule);border-radius:11px;padding:13px 15px;background:var(--card)}
.lensbox h4{margin:0 0 8px;font-size:15px}
.tok{display:inline-block;font:12.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  background:#f3f0eb;border:1px solid #e5e0d8;border-radius:4px;padding:0 5px;margin:0 4px 5px 0}
.tok.up{background:#fbe6cb;border-color:#f0d2ab}
.tok.dn{background:#dfeaf4;border-color:#c4d8e9}
.scroll{overflow-x:auto}
@media (max-width:640px){
  :root{--gutter:14px}
  .wrap{padding-top:18px;padding-bottom:60px}
  h1{font-size:23px} .txt{font-size:15px;line-height:1.95}
  .lbl{min-width:0;width:100%}
  .passage{padding:14px 13px}
  .lens{grid-template-columns:1fr}
}
"""

JS = """
const D = DATA;
let mode = "partial";
let shown = new Set(D.names);

function bandOf(v, cal){
  const p = cal.pos, n = cal.neg;
  if (v >= p[3]) return 4; if (v >= p[2]) return 3; if (v >= p[1]) return 2; if (v >= p[0]) return 1;
  if (v <= n[3]) return -4; if (v <= n[2]) return -3; if (v <= n[1]) return -2; if (v <= n[0]) return -1;
  return 0;
}
function colOf(b){ return b > 0 ? D.pos[b-1] : (b < 0 ? D.neg[-b-1] : "transparent"); }

function render(){
  const cal = D.cal[mode];
  document.querySelectorAll("[data-mode]").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
  document.querySelectorAll("[data-dir]").forEach(b => {
    const on = shown.has(b.dataset.dir);
    b.setAttribute("aria-pressed", String(on));
    b.classList.toggle("dim", !on);
  });
  document.getElementById("modenote").textContent = D.modeLabel[mode];

  let lg = "";
  for (const [arr, labs, tag] of [[D.neg.slice().reverse(), ["p1","p5","p10","p25"], "against"],
                                  [D.pos, ["p75","p90","p95","p99"], "with"]]){
    lg += '<div><div class="ramp">' + arr.map(c =>
      `<div class="chip" style="background:${c}"></div>`).join("") + '</div><div class="ramp">' +
      labs.map(l => `<div class="chiplab">${l}</div>`).join("") + `</div><div class="chiplab" ` +
      `style="width:auto;text-align:left;margin-top:3px">projects ${tag} the direction</div></div>`;
  }
  document.getElementById("legend").innerHTML = lg;

  let cut = "<tr><th>direction</th><th>p75</th><th>p90</th><th>p95</th><th>p99</th>" +
            "<th>p25</th><th>p10</th><th>p5</th><th>p1</th><th>median</th></tr>";
  for (const n of D.names){
    const c = cal[n];
    cut += `<tr><td><b>${n}</b></td>` +
      c.pos.map(x => `<td class="num">${x.toFixed(2)}</td>`).join("") +
      c.neg.map(x => `<td class="num">${x.toFixed(2)}</td>`).join("") +
      `<td class="num">${c.median.toFixed(2)}</td></tr>`;
  }
  document.getElementById("cuts").innerHTML = cut;

  const out = [];
  for (const p of D.passages){
    const rows = [];
    for (let i = 0; i < D.names.length; i++){
      const name = D.names[i];
      if (!shown.has(name)) continue;
      const proj = p.proj[mode][i], c = cal[name], st = p.row[mode][name];
      let spans = "";
      for (let t = 0; t < proj.length; t++){
        const b = bandOf(proj[t], c);
        const bg = colOf(b);
        const title = `${name} ${proj[t].toFixed(2)}  |  ${p.tokens[t].replace(/"/g,"&quot;")}`;
        spans += b === 0
          ? `<span class="tk" title="${title}">${p.tokensHtml[t]}</span>`
          : `<span class="tk" style="background:${bg}" title="${title}">${p.tokensHtml[t]}</span>`;
      }
      const cls = D.sens.includes(name) ? "sens" : "emo";
      const expected = (p.expect === name) ? " expected" : "";
      const stat = (mode === "center" || mode === "center_partial")
        ? `top-decile ${st.top10 >= 0 ? "+" : ""}${st.top10.toFixed(2)}`
        : `mean ${st.mean >= 0 ? "+" : ""}${st.mean.toFixed(2)} &middot; top-decile ${st.top10.toFixed(2)}`;
      rows.push(`<div class="drow${expected}"><div class="dhead">` +
        `<span class="dname ${cls}">${name}</span><span>${stat}</span>` +
        `<span>peak ${st.max.toFixed(2)}</span></div>` +
        `<div class="txt">${spans}</div></div>`);
    }
    out.push(`<div class="passage" id="${p.id}"><div class="phead">` +
      `<span class="badge ${p.family}">${D.familyLabel[p.family]}</span>` +
      `<h3>${p.title}</h3><span class="note">${p.words} words &middot; ${p.n} tokens &middot; ` +
      `expect <b>${p.expect}</b></span></div>` +
      `<p class="note">${p.note}</p>${rows.join("")}</div>`);
  }
  document.getElementById("passages").innerHTML = out.join("");
}

document.addEventListener("click", e => {
  const b = e.target.closest("button.pill");
  if (!b) return;
  if (b.dataset.mode){ mode = b.dataset.mode; render(); return; }
  if (b.dataset.dir){
    const d = b.dataset.dir;
    if (shown.has(d)) shown.delete(d); else shown.add(d);
    if (shown.size === 0) shown = new Set(D.names);
    render(); return;
  }
  if (b.dataset.all === "on"){ shown = new Set(D.names); render(); return; }
  if (b.dataset.all === "sens"){ shown = new Set(D.sens); render(); return; }
  if (b.dataset.all === "emo"){ shown = new Set(D.emo); render(); return; }
});

let lvec = "partial_normgain_centered", lscope = "";
function renderLens(){
  document.querySelectorAll("button[data-lvec]").forEach(x =>
    x.setAttribute("aria-pressed", String(x.dataset.lvec === lvec)));
  document.querySelectorAll("button[data-lscope]").forEach(x =>
    x.setAttribute("aria-pressed", String(x.dataset.lscope === lscope)));
  document.querySelectorAll("[data-list]").forEach(x =>
    x.hidden = (x.dataset.list !== lvec + lscope));
}
document.addEventListener("click", e => {
  const b = e.target.closest("button[data-lvec],button[data-lscope]");
  if (!b) return;
  if (b.dataset.lvec !== undefined) lvec = b.dataset.lvec;
  if (b.dataset.lscope !== undefined) lscope = b.dataset.lscope;
  renderLens();
});
renderLens();

render();
"""


def build_html(recs, names, cal, lens, meta, out_path, topk) -> None:
    emo = [n for n in names if n in ("happy", "sad", "angry", "fearful")]
    sens = [n for n in names if n in ("warm", "cold", "pain")]

    passages = []
    for r in recs:
        passages.append({
            "id": r["id"], "title": r["title"], "note": r["note"], "family": r["family"],
            "expect": r["expect"], "words": r["words"], "n": r["n_tokens"],
            "tokens": r["tokens"],
            "tokensHtml": [html.escape(t) for t in r["tokens"]],
            "proj": {m: r["proj"][m] for m in MODES},
            "row": r["row"],
        })

    data = {
        "names": names, "emo": emo, "sens": sens, "pos": POS, "neg": NEG,
        "cal": cal, "passages": passages, "modeLabel": MODE_LABEL,
        "familyLabel": FAMILY_LABEL,
    }

    mode_btns = "".join(
        f'<button class="pill" data-mode="{m}" aria-pressed="false">{MODE_SHORT[m]}</button>' for m in MODES)
    dir_btns = "".join(
        f'<button class="pill" data-dir="{n}" aria-pressed="true">{n}</button>' for n in names)

    lens_html = build_lens_html(lens, names, topk)
    toc = " &middot; ".join(f'<a href="#{r["id"]}">{r["id"].replace("_", " ")}</a>' for r in recs)

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Token-level projection heatmaps - 7 directions, Qwen3.5-4B hs17</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>Token-level projection heatmaps</h1>
<p class="sub">Seven directions &mdash; four emotions (happy / sad / angry / fearful) and three
sensations (warm / cold / pain) &mdash; read off every token position of
<code>{html.escape(meta["model"])}</code> at <code>hidden_states[{meta["layer"]}]</code>,
vectors <code>{html.escape(meta["which"])}</code>. {len(recs)} passages,
{sum(r["n_tokens"] for r in recs)} token positions scored 7&times;4 ways.</p>

<div class="panel">
<p><b>What a colour means.</b> Each token position has a residual vector <i>h<sub>t</sub></i>.
A direction <i>d</i> turns it into one number, and that number is the highlight.
Orange = this token sits along the direction, blue = it sits against it, white = neither.
Hover a token for its value.</p>
<p><b>Why the mode switch matters.</b> Every direction here carries a large shared component &mdash;
&quot;this text is in <i>some</i> marked state rather than flat&quot; &mdash; measured in
BUILD_REPORT_3 &sect;3.1 at cos&nbsp;=&nbsp;+0.864 between the two corpora's generic axes.
Left in, it paints every emotional passage orange on all seven rows and says nothing.
<code>raw</code> shows exactly that failure; <code>partial</code> projects the shared axis out of the
direction; <code>centre</code> subtracts the passage's own token mean instead; the fourth does both.
<code>partial</code> is the default and the one the report reads.</p>
<p class="note">Colour steps are quantiles of the pooled token distribution for that direction
<i>and</i> mode across all {len(recs)} passages, so darkness is comparable between passages:
roughly one token in a hundred reaches the darkest orange anywhere on the page.</p>
</div>

<div class="controls">
  <div class="row"><span class="lbl">mode</span>{mode_btns}</div>
  <div class="row"><span class="lbl">rows</span>{dir_btns}
    <button class="pill" data-all="on">all 7</button>
    <button class="pill" data-all="emo">emotions</button>
    <button class="pill" data-all="sens">sensations</button></div>
  <div class="row"><span class="lbl">scale</span><div class="legend" id="legend"></div></div>
  <div class="row"><span id="modenote" class="note"></span></div>
</div>

<p class="note">Jump to: {toc}</p>

<div id="passages"></div>

<h2>Colour cutoffs for the current mode</h2>
<p class="note">Projection value at each quantile, per direction, pooled over every token on this page.
These are the numbers the bands above are cut at.</p>
<div class="scroll"><table id="cuts"></table></div>

<h2>Logit lens</h2>
{lens_html}

<h2>Method, in one block</h2>
<div class="panel"><p class="note">
One forward pass per passage, no hooks, no generation.
<code>h<sub>t</sub></code> = <code>hidden_states[{meta["layer"]}]</code> at position <i>t</i>.
<code>raw</code> = (h<sub>t</sub> &minus; corpus grand mean) &middot; d.
<code>centre</code> = (h<sub>t</sub> &minus; this passage's token mean) &middot; d.
<code>partial</code> = (h<sub>t</sub> &minus; grand mean) &middot; unit(d &minus; a&nbsp;(d&middot;a)), where
<i>a</i> is that corpus's generic axis, recomputed from the activations on the same split
(holdout 8, seed 7) the directions were fitted on.
The emotion directions and the sensation directions come from two separate fits sharing one
neutral control, so each keeps its own grand mean and its own <i>a</i>.
Anchor passages are drawn from the held-out half of each corpus, so no passage shown here
contributed to the direction scoring it.
Logit lens: W<sub>U</sub> with the final RMSNorm's learned per-channel gain folded in
(the dropped part is a positive scalar and cannot reorder a ranking), applied to the same
vectors. Special and added tokens excluded.
</p></div>

<script>const DATA = {json.dumps(data, ensure_ascii=False, separators=(",", ":"))};
{JS}</script>
</div></body></html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"-> {out_path}  ({os.path.getsize(out_path) / 1024:.0f} KB)")


def build_lens_html(lens, names, topk) -> str:
    if not lens:
        return "<p class='note'>no logit-lens file found.</p>"
    variants = [
        ("partial_normgain_centered", "partial dir, W<sub>U</sub> centred"),
        ("partial_normgain", "partial dir"),
        ("raw_normgain", "raw dir"),
    ]
    vec_btns = "".join(
        f'<button class="pill" data-lvec="{k}" aria-pressed="false">{lab}</button>'
        for k, lab in variants if k in next(iter(lens["directions"].values())))
    scope_btns = "".join(
        f'<button class="pill" data-lscope="{s}" aria-pressed="false">{lab}</button>'
        for s, lab in (("", "all tokens"), ("_ascii", "ASCII only")))

    boxes = []
    for n in names:
        e = lens["directions"].get(n)
        if not e:
            continue
        blocks = []
        for key, _lab in variants:
            if key not in e:
                continue
            for scope in ("", "_ascii"):
                up = "".join(f'<span class="tok up">{html.escape(x["show"])}</span>'
                             for x in e[key]["up" + scope][:topk])
                dn = "".join(f'<span class="tok dn">{html.escape(x["show"])}</span>'
                             for x in e[key]["down" + scope][:topk])
                blocks.append(
                    f'<div data-list="{key}{scope}" hidden>'
                    f'<p class="note" style="margin:.3em 0 .2em"><b>up</b> &mdash; the direction '
                    f'pushes these {topk} tokens hardest</p>{up}'
                    f'<p class="note" style="margin:.7em 0 .2em"><b>down</b> &mdash; and suppresses '
                    f'these {topk}</p>{dn}</div>')
        boxes.append(f'<div class="lensbox"><h4>{n}</h4>{"".join(blocks)}</div>')

    head = (f"<p class='note'>Each direction vector pushed through the unembedding. "
            f"<code>␣</code> marks a leading space; the rest is the token's exact decoded text. "
            f"{lens.get('n_excluded_special', 0)} special/added ids excluded. "
            f"The corpus is entirely English but the strongest rows of W<sub>U</sub> are often not, "
            f"so an ASCII-only view sits next to the unfiltered one.</p>"
            f'<div class="row"><span class="lbl">vector</span>{vec_btns}</div>'
            f'<div class="row" style="margin-bottom:12px">'
            f'<span class="lbl">tokens</span>{scope_btns}</div>')
    return head + f'<div class="lens">{"".join(boxes)}</div>'


# --------------------------------------------------------------------------- PNG


def band_of(v, cal):
    p, n = cal["pos"], cal["neg"]
    if v >= p[3]:
        return 4
    if v >= p[2]:
        return 3
    if v >= p[1]:
        return 2
    if v >= p[0]:
        return 1
    if v <= n[3]:
        return -4
    if v <= n[2]:
        return -3
    if v <= n[1]:
        return -2
    if v <= n[0]:
        return -1
    return 0


def draw_card(rec, direction, di, cal, mode, out_path, width=1500, fontsize=30) -> None:
    """One passage, one direction, landscape. PIL so nothing heavy gets installed."""
    import matplotlib
    from PIL import Image, ImageDraw, ImageFont

    ttf = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    f = ImageFont.truetype(os.path.join(ttf, "DejaVuSans.ttf"), fontsize)
    fb = ImageFont.truetype(os.path.join(ttf, "DejaVuSans-Bold.ttf"), 34)
    fs = ImageFont.truetype(os.path.join(ttf, "DejaVuSans.ttf"), 21)

    pad, top = 46, 34
    lh = int(fontsize * 1.62)
    proj = rec["proj"][mode][di]
    toks = rec["tokens"]

    probe = Image.new("RGB", (10, 10))
    dr0 = ImageDraw.Draw(probe)

    def w(s):
        return dr0.textlength(s, font=f)

    # lay out first to learn the height
    lines, cur, curw = [], [], 0.0
    maxw = width - 2 * pad
    for t, v in zip(toks, proj):
        for j, piece in enumerate(t.split("\n")):
            if j > 0:
                lines.append(cur)
                cur, curw = [], 0.0
            if piece == "":
                continue
            pw = w(piece)
            if curw + pw > maxw and cur:
                lines.append(cur)
                cur, curw = [], 0.0
                piece = piece.lstrip(" ")
                pw = w(piece)
            cur.append((piece, v, pw))
            curw += pw
    if cur:
        lines.append(cur)

    header = top + 44 + 30
    height = header + len(lines) * lh + 58
    img = Image.new("RGB", (width, height), "#ffffff")
    dr = ImageDraw.Draw(img)

    dr.text((pad, top), rec["title"], font=fb, fill="#1d1c1a")
    sub = (f"coloured by  {direction}   ·   {MODE_SHORT[mode]} projection   ·   "
           f"Qwen3.5-4B hidden_states[{rec['layer']}]")
    dr.text((pad, top + 46), sub, font=fs, fill="#6b6660")

    y = header
    for line in lines:
        x = float(pad)
        for piece, v, pw in line:
            b = band_of(v, cal)
            if b != 0:
                col = POS[b - 1] if b > 0 else NEG[-b - 1]
                dr.rectangle([x, y - 5, x + pw, y + lh - 9], fill=col)
            dr.text((x, y), piece, font=f, fill="#1d1c1a")
            x += pw
        y += lh

    # legend strip
    ly = height - 40
    lx = pad
    for c in NEG[::-1] + POS:
        dr.rectangle([lx, ly, lx + 52, ly + 20], fill=c, outline="#dcd6cd")
        lx += 52
    dr.text((lx + 14, ly - 1), "against  ←  p1 p5 p10 p25 | p75 p90 p95 p99  →  with",
            font=fs, fill="#6b6660")
    img.save(out_path)
    print(f"-> {out_path}  ({img.size[0]}x{img.size[1]})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=os.path.join(RESULTS, "tokenmaps"))
    ap.add_argument("--lens", default=os.path.join(RESULTS, "logit_lens_qwen.json"))
    ap.add_argument("--out", default=os.path.join(RESULTS, "heatmaps_token_level.html"))
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--summary-out", default=os.path.join(RESULTS, "heatmap_summary.json"))
    ap.add_argument(
        "--cards",
        default="",
        help="semicolon list of `passage_id:direction:filename.png` to draw instead of the "
        "phase-four default trio; the colour scale is still the pooled `partial` calibration "
        "over every passage in --maps, so cards from different runs are not comparable",
    )
    args = ap.parse_args()

    recs = load_records(args.maps)
    if not recs:
        raise SystemExit(f"no per-passage json under {args.maps}")
    names = recs[0]["directions"]
    for r in recs:
        if r["directions"] != names:
            raise SystemExit(f"{r['id']} has a different direction order")

    cal = calibrate(recs, names)
    passage_stats(recs, names)
    meta = {"model": recs[0]["model"], "layer": recs[0]["layer"], "which": recs[0]["which"]}

    lens = None
    if os.path.exists(args.lens):
        with open(args.lens, encoding="utf-8") as f:
            lens = json.load(f)

    build_html(recs, names, cal, lens, meta, args.out, args.topk)

    if args.cards:
        cards = []
        for spec in args.cards.split(";"):
            if not spec.strip():
                continue
            parts = spec.split(":")
            if len(parts) != 3:
                raise SystemExit(f"--cards entry {spec!r} is not id:direction:filename.png")
            cards.append(tuple(p.strip() for p in parts))
    else:
        cards = [
            ("steer_pain_p10_office", "pain", "card_pain_office.png"),
            ("steer_cold_p10_weather", "cold", "card_cold_weather.png"),
            ("novel_snow_road", "fearful", "card_snowroad_fearful.png"),
        ]
    by = {r["id"]: r for r in recs}
    for pid, dname, fname in cards:
        if pid not in by:
            print(f"[card] skip {pid}: not in the maps directory")
            continue
        draw_card(by[pid], dname, names.index(dname), cal["partial"][dname], "partial",
                  os.path.join(RESULTS, fname))

    summary = {
        "meta": meta, "names": names, "modes": MODES,
        "calibration": cal,
        "passages": {r["id"]: {"family": r["family"], "expect": r["expect"], "words": r["words"],
                               "n_tokens": r["n_tokens"], "row": r["row"]} for r in recs},
    }
    with open(args.summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"-> {args.summary_out}")

    # console recap: which direction wins each passage, per mode
    for mode in ("partial", "raw", "center_partial"):
        print(f"\n=== winner per passage, mode={mode} "
              f"({'top-decile' if 'center' in mode else 'mean'})")
        key = "top10" if "center" in mode else "mean"
        for r in recs:
            row = r["row"][mode]
            best = sorted(row.items(), key=lambda kv: -kv[1][key])
            hit = "  <- expected" if best[0][0] == r["expect"] else ""
            print(f"  {r['id']:26s} expect={r['expect']:8s} "
                  + ", ".join(f"{k} {v[key]:+.2f}" for k, v in best[:3]) + hit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
