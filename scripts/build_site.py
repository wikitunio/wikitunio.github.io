#!/usr/bin/env python3
"""Build the static tunio.me site from data/videos.json.

Generates:
  index.html                 homepage (with "Latest videos" section)
  archive/index.html         all videos + category filter buttons
  videos/<slug>/index.html   one page per video (embed, description,
                             transcript, sources, VideoObject JSON-LD)

Stdlib only - runs on GitHub Actions ubuntu runners with plain python3.
Design, colours, fonts and copy match the existing site; shared styles
live in assets/style.css.
"""

import html
import json
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = BASE_DIR  # built files land at repo root

CATEGORIES = ["Space", "Mind & Body", "History",
              "Nature & Ocean", "Science & Tech", "Mysteries"]

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700'
         '&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">')


def esc(s):
    return html.escape(s or "", quote=True)


def fmt_date(iso):
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%b %-d, %Y")
    except ValueError:
        return iso


def md_to_html(md_text):
    """Tiny markdown subset -> HTML. Strips HTML comments first."""
    text = re.sub(r"<!--.*?-->", "", md_text or "", flags=re.S)
    if not text.strip():
        return ""
    out, in_list, para = [], False, []

    def flush_para():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def inline(s):
        s = esc(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?[^)]+)\)",
                   r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
        return s

    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if line.lstrip().startswith("## "):
            flush_para()
            out.append("<h3>" + inline(line.lstrip()[3:].strip()) + "</h3>")
        elif line.lstrip().startswith(("- ", "* ")):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append("<li>" + inline(line.lstrip()[2:].strip()) + "</li>")
        else:
            para.append(line.strip())
    flush_para()
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def nav(home=False):
    def href(anchor):
        return anchor if home else "/" + anchor
    return f"""<nav>
  <div class="wrap">
    <a class="logo" href="/">The Daily <span>Whoa</span></a>
    <ul>
      <li><a href="{href('#videos')}">Videos</a></li>
      <li><a href="{href('#what')}">What we do</a></li>
      <li><a href="{href('#factory')}">The Factory</a></li>
      <li><a href="{href('#platforms')}">Platforms</a></li>
      <li><a href="{href('#about')}">About</a></li>
    </ul>
    <a class="btn small" href="https://www.youtube.com/@DailyWhoaTV" target="_blank" rel="noopener">Watch now</a>
  </div>
</nav>"""


FOOTER = """<footer>
  <div class="wrap">
    <span>&copy; 2026 The Daily Whoa. All rights reserved.</span>
    <span><a href="/archive/">Videos</a> &middot; <a href="mailto:hello@tunio.me">hello@tunio.me</a> &middot; tunio.me</span>
  </div>
</footer>"""

GLOWS = '<div class="glow g1"></div><div class="glow g2"></div><div class="glow g3"></div>'


def page(title, description, body, home=False, extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{FONTS}
<link rel="stylesheet" href="/assets/style.css">
{extra_head}</head>
<body>
{GLOWS}
{nav(home)}
{body}
{FOOTER}
</body>
</html>
"""


def latest_videos_section(videos):
    cards = []
    for v in videos[:6]:
        date = fmt_date(v['published'])
        meta = f"{date} &middot; {esc(v['category'])}" if date else esc(v['category'])
        cards.append(f"""<div class="vcard">
  <div class="vembed"><iframe src="{esc(v['embed_url'])}" title="{esc(v['title'])}"
    loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen></iframe></div>
  <h3><a href="/videos/{esc(v['slug'])}/">{esc(v['title'])}</a></h3>
  <p class="vmeta">{meta}</p>
</div>""")
    grid = "\n".join(cards) if cards else \
        "<p class='sub'>Fresh videos are on their way — check back soon.</p>"
    return f"""<section id="videos">
  <div class="wrap">
    <div class="kicker">LATEST VIDEOS</div>
    <h2>Fresh from the factory.</h2>
    <p class="sub">Our newest Shorts, updated daily. Tap any video to watch it with its transcript and sources.</p>
    <div class="vgrid">
{grid}
    </div>
    <p style="margin-top:28px"><a class="btn ghost" href="/archive/">Browse the full archive</a></p>
  </div>
</section>"""


HOME_BODY_TAIL = """<section id="what">
  <div class="wrap">
    <div class="kicker">WHAT WE DO</div>
    <h2>Sixty seconds that rewire your brain.</h2>
    <p class="sub">Every video starts with a question you can't un-ask — then answers it with real science, real footage, and cinematic sound design. Family-friendly, fact-checked, impossible to scroll past.</p>
    <div class="grid">
      <div class="card"><div class="icon">🪐</div><h3>Space &amp; Extreme Physics</h3><p>Black holes, neutron stars, time dilation — the universe at its most absurd, made intuitive.</p></div>
      <div class="card"><div class="icon">🧠</div><h3>Mind &amp; Human Body</h3><p>Psychology quirks, body mysteries, and the strange wiring you run on every day.</p></div>
      <div class="card"><div class="icon">🏛️</div><h3>History &amp; Civilizations</h3><p>Ancient engineering, lost worlds, and the plot twists they never taught you.</p></div>
      <div class="card"><div class="icon">🌊</div><h3>Nature &amp; Ocean</h3><p>Deep-sea aliens, animal superpowers, and weather that breaks the scale.</p></div>
      <div class="card"><div class="icon">⚗️</div><h3>Science &amp; Technology</h3><p>How things work, what-if physics, and the experiments hiding in plain sight.</p></div>
      <div class="card"><div class="icon">🌀</div><h3>Mysteries &amp; Illusions</h3><p>Optical illusions, unsolved puzzles, and realities that aren't what they seem.</p></div>
    </div>
  </div>
</section>

<section id="factory">
  <div class="wrap">
    <div class="kicker">THE FACTORY</div>
    <h2>A content pipeline no human team could match.</h2>
    <p class="sub">We run The Daily Whoa like a factory, not a channel. An automated loop ideates, produces, and publishes around the clock — with human taste guarding every frame.</p>
    <div class="steps">
      <div class="step"><h3>Idea Engine</h3><p>Every morning the pipeline generates and scores twenty video concepts — ranked by curiosity gap, visual potential, and verified accuracy before anything gets made.</p></div>
      <div class="step"><h3>Production</h3><p>Scripts, real motion footage, sound design, and karaoke-style captions are assembled per platform spec — then pass an automated quality gate that checks every frame.</p></div>
      <div class="step"><h3>Publishing</h3><p>Finished videos ship to YouTube Shorts first, then cascade to TikTok, Instagram Reels, and Facebook Reels — daily, without missing a beat.</p></div>
    </div>
  </div>
</section>

<section id="platforms">
  <div class="wrap">
    <div class="kicker">PLATFORMS</div>
    <h2>Find us wherever you scroll.</h2>
    <p class="sub">One factory, four storefronts. New videos land everywhere, every day.</p>
    <div class="plats">
      <div class="plat"><div class="icon"><svg viewBox="0 0 24 24" fill="#FF0000" aria-label="YouTube"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg></div><h3>YouTube Shorts</h3><p>@DailyWhoaTV</p><a href="https://www.youtube.com/@DailyWhoaTV" target="_blank" rel="noopener">Watch &rarr;</a></div>
      <div class="plat"><div class="icon"><svg viewBox="0 0 24 24" fill="#f2f2fa" aria-label="TikTok"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg></div><h3>TikTok</h3><p>@dailywhoa13</p><a href="https://www.tiktok.com/@dailywhoa13" target="_blank" rel="noopener">Watch &rarr;</a></div>
      <div class="plat"><div class="icon"><svg viewBox="0 0 24 24" fill="#E1306C" aria-label="Instagram"><path d="M12 0C8.74 0 8.333.015 7.053.072 5.775.132 4.905.333 4.14.63c-.789.306-1.459.717-2.126 1.384S.935 3.35.63 4.14C.333 4.905.131 5.775.072 7.053.012 8.333 0 8.74 0 12s.015 3.667.072 4.947c.06 1.277.261 2.148.558 2.913.306.788.717 1.459 1.384 2.126.667.666 1.336 1.079 2.126 1.384.766.296 1.636.499 2.913.558C8.333 23.988 8.74 24 12 24s3.667-.015 4.947-.072c1.277-.06 2.148-.262 2.913-.558.788-.306 1.459-.718 2.126-1.384.666-.667 1.079-1.335 1.384-2.126.296-.765.499-1.636.558-2.913.06-1.28.072-1.687.072-4.947s-.015-3.667-.072-4.947c-.06-1.277-.262-2.149-.558-2.913-.306-.789-.718-1.459-1.384-2.126C21.319 1.347 20.651.935 19.86.63c-.765-.297-1.636-.499-2.913-.558C15.667.012 15.26 0 12 0zm0 2.16c3.203 0 3.585.016 4.85.071 1.17.055 1.805.249 2.227.415.562.217.96.477 1.382.896.419.42.679.819.896 1.381.164.422.36 1.057.413 2.227.057 1.266.07 1.646.07 4.85s-.015 3.585-.074 4.85c-.061 1.17-.256 1.805-.421 2.227-.224.562-.479.96-.899 1.382-.419.419-.824.679-1.38.896-.42.164-1.065.36-2.235.413-1.274.057-1.649.07-4.859.07-3.211 0-3.586-.015-4.859-.074-1.171-.061-1.816-.256-2.236-.421-.569-.224-.96-.479-1.379-.899-.421-.419-.69-.824-.9-1.38-.165-.42-.359-1.065-.42-2.235-.045-1.26-.061-1.649-.061-4.844 0-3.196.016-3.586.061-4.861.061-1.17.255-1.814.42-2.234.21-.57.479-.96.9-1.381.419-.419.81-.689 1.379-.898.42-.166 1.051-.361 2.221-.421 1.275-.045 1.65-.06 4.859-.06l.045.03zm0 3.678c-3.405 0-6.162 2.76-6.162 6.162 0 3.405 2.76 6.162 6.162 6.162 3.405 0 6.162-2.76 6.162-6.162 0-3.405-2.76-6.162-6.162-6.162zM12 16c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm7.846-10.405c0 .795-.646 1.44-1.44 1.44-.795 0-1.44-.646-1.44-1.44 0-.794.646-1.439 1.44-1.439.793-.001 1.44.645 1.44 1.439z"/></svg></div><h3>Instagram</h3><p>@dailywhoatv</p><a href="https://www.instagram.com/dailywhoatv" target="_blank" rel="noopener">Watch &rarr;</a></div>
      <div class="plat"><div class="icon"><svg viewBox="0 0 24 24" fill="#1877F2" aria-label="Facebook"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg></div><h3>Facebook</h3><p>The Daily Whoa</p><a href="https://www.facebook.com/Dailywhoatv/" target="_blank" rel="noopener">Watch &rarr;</a></div>
    </div>
  </div>
</section>

<section id="about">
  <div class="wrap">
    <div class="about">
      <div>
        <div class="kicker">ABOUT</div>
        <h2>A studio, not just a channel.</h2>
        <p>The Daily Whoa started in October 2026 with a simple bet: that <b>AI plus human taste</b> can out-produce any traditional content team — without sacrificing accuracy or craft.</p>
        <p>We're bootstrapped and independent, building toward a multi-channel faceless media network. Every claim is verified, every video is family-friendly, and every day the factory ships.</p>
      </div>
      <ul class="facts">
        <li><span>Founded</span><b>October 2026</b></li>
        <li><span>Stage</span><b>Bootstrapped &middot; Pre-seed</b></li>
        <li><span>Based in</span><b>Pakistan &middot; Remote-first</b></li>
        <li><span>Contact</span><b><a href="mailto:hello@tunio.me" style="color:var(--cyan)">hello@tunio.me</a></b></li>
      </ul>
    </div>
  </div>
</section>"""

HOME_HEADER = """<header id="top">
  <div class="wrap">
    <span class="eyebrow">AI-NATIVE MEDIA STARTUP &middot; EST. 2026</span>
    <h1>Curiosity,<br><span class="grad">manufactured daily.</span></h1>
    <p class="lede">The Daily Whoa is an AI-native video studio. We make short films about the world's most mind-bending facts &mdash; space, science, psychology, history &mdash; and publish them every single day, on every short-form platform.</p>
    <div class="cta-row">
      <a class="btn" href="https://www.youtube.com/@DailyWhoaTV" target="_blank" rel="noopener">Watch on YouTube</a>
      <a class="btn ghost" href="#factory">How it works</a>
    </div>
    <div class="strip">
      <div><b>4</b><span>Platforms publishing daily</span></div>
      <div><b>10<span style="font-size:1rem;color:var(--muted)">/day</span></b><span>Target production cadence</span></div>
      <div><b>100%</b><span>Original scripts &amp; ideas</span></div>
      <div><b>AI-native</b><span>End-to-end pipeline</span></div>
    </div>
  </div>
</header>"""


def build_home(videos):
    body = HOME_HEADER + latest_videos_section(videos) + HOME_BODY_TAIL
    return page("The Daily Whoa \u2014 An AI-Native Media Startup",
                "The Daily Whoa is an AI-native video studio. We manufacture "
                "curiosity \u2014 short films about the world's most "
                "mind-bending facts, published daily across every short-form "
                "platform.", body, home=True)


def build_archive(videos):
    has_uncat = any(v["category"] == "Uncategorized" for v in videos)
    buttons = ['<button class="fbtn active" data-filter="all">All</button>']
    for c in CATEGORIES:
        buttons.append(f'<button class="fbtn" data-filter="{esc(c)}">'
                       f'{esc(c)}</button>')
    if has_uncat:
        buttons.append('<button class="fbtn" data-filter="Uncategorized">'
                       'Uncategorized</button>')
    cards = []
    for v in videos:
        date = fmt_date(v['published'])
        meta = f"{date} &middot; {esc(v['category'])}" if date else esc(v['category'])
        cards.append(f"""<div class="acard" data-category="{esc(v['category'])}">
  <a href="/videos/{esc(v['slug'])}/"><img src="{esc(v['thumbnail'])}" alt="{esc(v['title'])}" loading="lazy"></a>
  <div class="acard-body">
    <span class="cat">{esc(v['category'])}</span>
    <h3><a href="/videos/{esc(v['slug'])}/">{esc(v['title'])}</a></h3>
    <p class="vmeta">{meta}</p>
  </div>
</div>""")
    js = """<script>
document.querySelectorAll('.fbtn').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.fbtn').forEach(function(b){b.classList.remove('active')});
    btn.classList.add('active');
    var f = btn.getAttribute('data-filter');
    document.querySelectorAll('.acard').forEach(function(card){
      card.style.display = (f === 'all' || card.getAttribute('data-category') === f) ? '' : 'none';
    });
  });
});
</script>"""
    body = f"""<section>
  <div class="wrap">
    <div class="kicker">VIDEO ARCHIVE</div>
    <h2>Every Whoa, ever.</h2>
    <p class="sub">The full catalogue of Daily Whoa Shorts. Filter by topic, or open any video for its transcript and sources.</p>
    <div class="filters">
{' '.join(buttons)}
    </div>
    <div class="agrid">
{chr(10).join(cards)}
    </div>
  </div>
</section>
{js}"""
    return page("Video Archive \u2014 The Daily Whoa",
                "Browse every Daily Whoa short film by topic: space, mind & "
                "body, history, nature & ocean, science & tech, mysteries.",
                body)


def read_md(folder, video_id):
    path = os.path.join(DATA_DIR, folder, f"{video_id}.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_video(v):
    transcript = md_to_html(read_md("transcripts", v["id"]))
    sources = md_to_html(read_md("sources", v["id"]))
    desc_html = "".join(
        f"<p>{esc(p.strip())}</p>" for p in (v["description"] or "").split("\n")
        if p.strip())
    sections = ""
    if transcript:
        sections += (f'<div class="vsection"><h2>Transcript</h2>'
                     f'{transcript}</div>')
    if sources:
        sections += (f'<div class="vsection"><h2>Sources</h2>'
                     f'{sources}</div>')
    ld = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": v["title"],
        "description": (v["description"] or v["title"])[:500],
        "thumbnailUrl": v["thumbnail"],
        "uploadDate": v["published"],
        "embedUrl": v["embed_url"],
        "contentUrl": v["url"],
    }
    extra = ('<script type="application/ld+json">\n'
             + json.dumps(ld, ensure_ascii=False, indent=2)
             + '\n</script>')
    date = fmt_date(v['published'])
    date_html = f'\n    <p class="vmeta">{esc(date)}</p>' if date else ""
    body = f"""<section class="vpage">
  <div class="wrap narrow">
    <p><a class="back" href="/archive/">&larr; All videos</a></p>
    <span class="cat">{esc(v['category'])}</span>
    <h1 class="vtitle">{esc(v['title'])}</h1>{date_html}
    <div class="vplayer"><iframe src="{esc(v['embed_url'])}" title="{esc(v['title'])}"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowfullscreen></iframe></div>
    <div class="vdesc">{desc_html}</div>
    {sections}
    <p style="margin-top:32px"><a class="btn" href="{esc(v['url'])}" target="_blank" rel="noopener">Watch on YouTube</a></p>
  </div>
</section>"""
    return page(f"{v['title']} \u2014 The Daily Whoa",
                (v["description"] or v["title"])[:160], body,
                extra_head=extra)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    with open(os.path.join(DATA_DIR, "videos.json"), encoding="utf-8") as f:
        data = json.load(f)
    videos = data.get("videos", [])
    # Newest first; entries without dates keep feed order at the end.
    videos.sort(key=lambda v: (v.get("published") or "", ),
                reverse=True)

    write(os.path.join(OUT_DIR, "index.html"), build_home(videos))
    write(os.path.join(OUT_DIR, "archive", "index.html"),
          build_archive(videos))
    for v in videos:
        write(os.path.join(OUT_DIR, "videos", v["slug"], "index.html"),
              build_video(v))
    print(f"Built index.html, archive/index.html, "
          f"{len(videos)} video pages")


if __name__ == "__main__":
    main()
