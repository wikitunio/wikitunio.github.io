#!/usr/bin/env python3
"""Fetch the latest YouTube Shorts for @DailyWhoaTV and write data/videos.json.

Source priority:
  1. YouTube Data API v3 (if YT_API_KEY env var is set) - full metadata.
  2. YouTube channel RSS feed - title, description, publish date.
  3. Channel /shorts page scrape (+ per-video pages for dates) - fallback.

Also applies category overrides from data/categories.json, auto-categorises
by keyword, and ensures empty editable transcript/source files exist for
every video under data/transcripts/ and data/sources/.

Stdlib only - runs on GitHub Actions ubuntu runners with plain python3.
"""

import html
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

CHANNEL_ID = "UC2wkh9HNC7qlUC-qD0MePHA"
CHANNEL_HANDLE = "@DailyWhoaTV"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
VIDEOS_JSON = os.path.join(DATA_DIR, "videos.json")
OVERRIDES_JSON = os.path.join(DATA_DIR, "categories.json")
TRANSCRIPTS_DIR = os.path.join(DATA_DIR, "transcripts")
SOURCES_DIR = os.path.join(DATA_DIR, "sources")

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

CATEGORIES = ["Space", "Mind & Body", "History",
              "Nature & Ocean", "Science & Tech", "Mysteries"]

KEYWORDS = {
    "Space": ["space", "planet", "black hole", "nasa", "galaxy", "moon",
              "star", "astronaut", "universe", "mars", "venus", "jupiter",
              "saturn", "neptune", "uranus", "pluto", "mercury",
              "comet", "asteroid", "nebula", "cosmos", "orbit",
              "rocket", "solar", "eclipse", "telescope", "exoplanet",
              "neutron star", "quasar", "big bang", "light-year",
              "light year", "supernova", "earth", "spinning", "rotation"],
    "Mind & Body": ["brain", "psychology", "mind", "body", "sleep", "dream",
                    "memory", "neuron", "heart", "blood", "dna", "muscle",
                    "pain", "eye", "vision", "hearing", "adrenaline",
                    "hormone", "sneeze", "hiccup", "stomach", "bone",
                    "giraffe", "neck", "taller", "height", "baader",
                    "bias", "organ"],
    "History": ["ancient", "history", "egypt", "roman", "rome", "greek",
                "civilization", "pyramid", "medieval", "viking", "empire",
                "pharaoh", "maya", "aztec", "colosseum", "titanic",
                "world war", "century", "eiffel"],
    "Nature & Ocean": ["ocean", "sea", "deep sea", "animal", "shark", "whale",
                       "octopus", "volcano", "earthquake", "weather", "storm",
                       "lightning", "tornado", "hurricane", "forest",
                       "desert", "river", "jellyfish", "squid", "tsunami",
                       "wolf", "dire", "extinction", "species", "dinosaur",
                       "fossil", "mammal", "cave", "crystal", "mineral",
                       "glacier", "iceberg", "soil", "microbe", "bacteria",
                       "fruit", "apple", "fish", "honey", "food", "fire",
                       "burning", "tree", "bird", "insect", "spider"],
    "Science & Tech": ["physics", "quantum", "chemistry", "experiment", "ai ",
                       "artificial intelligence", "robot", "computer",
                       "energy", "nuclear", "fusion", "laser", "math",
                       "engineering", "technology", "science", "electric",
                       "magnet", "water", "boil", "freeze", "ice",
                       "triple point", "hard drive", "radioactive",
                       "radiation", "banana", "tower", "thermal", "expand",
                       "puzzle", "probability", "monty"],
    "Mysteries": ["mystery", "mysteries", "unsolved", "illusion", "optical",
                  "disappear", "ghost", "alien", "ufo", "paradox",
                  "strange", "weird", "bizarre", "unexplained", "creepy"],
}


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def slugify(title, video_id):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-")
    if not slug:
        slug = "video"
    return f"{slug}-{video_id[:8].lower()}"


def auto_category(title, description):
    text = f"{title} {description}".lower()
    best, best_score = "Uncategorized", 0
    for cat in CATEGORIES:
        score = sum(1 for kw in KEYWORDS[cat] if kw in text)
        if score > best_score:
            best, best_score = cat, score
    return best


# ---- Source 1: YouTube Data API -------------------------------------------

def fetch_via_api(api_key):
    print("Trying YouTube Data API...")
    # Uploads playlist of the channel
    url = ("https://www.googleapis.com/youtube/v3/channels"
           f"?part=contentDetails&id={CHANNEL_ID}&key={api_key}")
    data = json.loads(http_get(url))
    items = data.get("items", [])
    if not items:
        raise RuntimeError("API returned no channel data")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    videos = []
    page_token = ""
    while len(videos) < 50:
        url = ("https://www.googleapis.com/youtube/v3/playlistItems"
               f"?part=snippet&playlistId={uploads}&maxResults=50"
               f"&pageToken={page_token}&key={api_key}")
        data = json.loads(http_get(url))
        for it in data.get("items", []):
            sn = it["snippet"]
            vid = sn["resourceId"]["videoId"]
            videos.append({
                "id": vid,
                "title": sn["title"],
                "description": sn.get("description", ""),
                "published": sn["publishedAt"][:10],
            })
        page_token = data.get("nextPageToken", "")
        if not page_token:
            break
    print(f"API returned {len(videos)} uploads")
    return videos


# ---- Source 2: RSS feed ----------------------------------------------------

def fetch_via_rss():
    print("Trying RSS feed...")
    url = (f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}")
    xml_text = http_get(url)
    if "<feed" not in xml_text[:2000]:
        raise RuntimeError("RSS endpoint did not return a feed")
    ns = {"a": "http://www.w3.org/2005/Atom",
          "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(xml_text)
    videos = []
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns).attrib.get("href", "")
        if "/shorts/" not in link:
            continue  # keep Shorts only
        vid = e.find("yt:videoId", ns).text
        title = e.find("a:title", ns).text or ""
        published = (e.find("a:published", ns).text or "")[:10]
        desc_el = e.find("m:group/m:description", ns)
        desc = desc_el.text if desc_el is not None and desc_el.text else ""
        videos.append({"id": vid, "title": title,
                       "description": desc, "published": published})
    print(f"RSS returned {len(videos)} shorts")
    if not videos:
        raise RuntimeError("RSS feed had no shorts entries")
    return videos


# ---- Source 3: /shorts page scrape -----------------------------------------

def fetch_via_scrape():
    print("Trying /shorts page scrape (fallback)...")
    page = http_get(f"https://www.youtube.com/{CHANNEL_HANDLE}/shorts")
    blocks = re.findall(r'"shortsLockupViewModel":\{(.*?)"reelWatchEndpoint"',
                        page)
    ids, titles = [], {}
    for m in re.finditer(r'"shortsLockupViewModel":\{"entityId":"[^"]*?",'
                         r'"accessibilityText":"(.*?)","onTap":\{"innertubeCommand"'
                         r':\{"clickTrackingParams":"[^"]*?","commandMetadata":'
                         r'\{"webCommandMetadata":\{"url":"/shorts/([A-Za-z0-9_-]{11})"',
                         page):
        acc, vid = m.group(1), m.group(2)
        if vid not in titles:
            ids.append(vid)
            # accessibilityText looks like "Title, 1.2 thousand views - play Short"
            # or "Title, No views - play Short"
            title = re.sub(r", (?:No views|[\d.,]+ (?:thousand |million )?views?)"
                           r" - play Short$", "", acc)
            titles[vid] = html.unescape(title).replace('\\"', '"')
    videos = []
    for vid in ids:
        videos.append({"id": vid, "title": titles.get(vid, vid),
                       "description": "", "published": ""})
    # Enrich with per-video pages (upload date + description),
    # with retries on rate limiting. Set SKIP_ENRICH=1 to skip.
    skip_enrich = os.environ.get("SKIP_ENRICH") == "1"
    for v in videos:
        if skip_enrich:
            break
        for attempt in range(3):
            try:
                wp = http_get(f"https://www.youtube.com/watch?v={v['id']}")
                m = re.search(r'"uploadDate":"(\d{4}-\d{2}-\d{2})"', wp)
                if m:
                    v["published"] = m.group(1)
                m = re.search(r'<meta name="description" content="([^"]*)"',
                              wp)
                if m:
                    v["description"] = html.unescape(m.group(1))
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"  warn: could not enrich {v['id']}: {e}")
                time.sleep(2 * (attempt + 1))
        time.sleep(0.6)
    print(f"Scrape returned {len(videos)} shorts")
    if not videos:
        raise RuntimeError("Scrape found no shorts")
    return videos


# ---- Main -------------------------------------------------------------------

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    os.makedirs(SOURCES_DIR, exist_ok=True)

    api_key = os.environ.get("YT_API_KEY", "").strip()
    videos = None
    errors = []
    if api_key:
        try:
            videos = fetch_via_api(api_key)
        except Exception as e:  # noqa: BLE001
            errors.append(f"API: {e}")
    if videos is None:
        try:
            videos = fetch_via_rss()
        except Exception as e:  # noqa: BLE001
            errors.append(f"RSS: {e}")
    if videos is None:
        try:
            videos = fetch_via_scrape()
        except Exception as e:  # noqa: BLE001
            errors.append(f"scrape: {e}")
    if videos is None:
        print("All sources failed:", "; ".join(errors), file=sys.stderr)
        sys.exit(1)

    overrides = {}
    if os.path.exists(OVERRIDES_JSON):
        with open(OVERRIDES_JSON, encoding="utf-8") as f:
            overrides = json.load(f)

    seen = set()
    out = []
    uncategorized = []
    for v in videos:
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        cat = overrides.get(v["id"]) or auto_category(v["title"],
                                                      v["description"])
        if cat == "Uncategorized":
            uncategorized.append(v)
        out.append({
            "id": v["id"],
            "title": v["title"],
            "description": v["description"],
            "published": v["published"],
            "category": cat,
            "slug": slugify(v["title"], v["id"]),
            "url": f"https://www.youtube.com/shorts/{v['id']}",
            "embed_url": f"https://www.youtube.com/embed/{v['id']}",
            "thumbnail": f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
        })
        # Empty editable files for transcript + sources
        for folder, label in ((TRANSCRIPTS_DIR, "transcript"),
                              (SOURCES_DIR, "sources")):
            path = os.path.join(folder, f"{v['id']}.md")
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"<!-- {label} for \"{v['title']}\" "
                            f"(https://www.youtube.com/shorts/{v['id']}) -->\n"
                            f"<!-- Fill this in; the site rebuilds daily. -->\n")

    payload = {
        "channel_id": CHANNEL_ID,
        "channel_handle": CHANNEL_HANDLE,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "video_count": len(out),
        "videos": out,
    }
    with open(VIDEOS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Uncategorized listing for the owner to categorise
    unc_path = os.path.join(DATA_DIR, "uncategorized.md")
    with open(unc_path, "w", encoding="utf-8") as f:
        f.write("# Uncategorized videos\n\n")
        f.write("Add entries to `data/categories.json` like "
                '`{"<videoId>": "Space"}` to categorise these.\n\n')
        for v in uncategorized:
            f.write(f"- [{v['title']}](https://www.youtube.com/shorts/{v['id']})"
                    f" — `{v['id']}`\n")
    print(f"Wrote {len(out)} videos to data/videos.json")
    print(f"Uncategorized: {len(uncategorized)}")
    for v in uncategorized:
        print(f"  UNCATEGORIZED: {v['id']} | {v['title'][:70]}")


if __name__ == "__main__":
    main()
