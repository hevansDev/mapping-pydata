import base64
import os
import sys
from collections import Counter
from pathlib import Path

import folium
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from PyDataMap import build_popup_html, add_hash_navigation


ICON_DIR = Path(__file__).parent.parent.parent / "icons"


def load_icon(path):
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    ext = Path(path).suffix.lstrip(".")
    return f"data:image/{ext};base64,{data}"


STATUS_ICONS = {
    "spoken":    load_icon(ICON_DIR / "spoken.png"),
    "upcoming":  load_icon(ICON_DIR / "upcoming.png"),
    "unvisited": load_icon(ICON_DIR / "unvisited.png"),
}

# Render order: unvisited first, spoken second, upcoming last (on top)
STATUS_ORDER = {"unvisited": 0, "spoken": 1, "upcoming": 2}

# Values are (status, date, event_url) tuples
# date is a string or None, event_url is a specific event link or None
MY_GROUPS = {
    "https://www.meetup.com/pydata-london-meetup":     ("spoken",    None,          None),
    "https://www.meetup.com/meetup-group-djhiglzd":    ("spoken",  "2026-05-21",  None),  # PyData Glasgow
    "https://www.meetup.com/pydataireland":            ("unvisited", None,          None),  # PyData Ireland
    "https://www.meetup.com/pydata-bradford":          ("upcoming",  "2026-05-29",  "https://www.meetup.com/pydata-bradford/events/314497365/"),
    "https://www.meetup.com/PyData-Manchester":        ("spoken",    "2026-03-26",  "https://www.meetup.com/pydata-manchester/events/313770253/"),
    "https://www.meetup.com/pydata-leeds":             ("unvisited", None,          None),
    "https://www.meetup.com/pydata-huddersfield":      ("unvisited", None,          None),
    "https://www.meetup.com/pydata-hull":              ("spoken",   "2026-03-27",  "https://www.meetup.com/pydata-hull/events/313808503/"),
    "https://www.meetup.com/pydata-wolverhampton":     ("spoken", "2026-05-22",   None),
    "https://www.meetup.com/pydata-birmingham-uk":     ("unvisited", None,          None),
    "https://www.meetup.com/pydata-cornwall":          ("spoken",  "2026-05-7",   "https://www.meetup.com/pydata-cornwall/events/314013646/"),
    "https://www.meetup.com/pydata-cardiff-meetup":    ("unvisited", None,          None),
    "https://www.meetup.com/test-austin":              ("unvisited", None,          None),  # PyData Leicester
    "https://www.meetup.com/pydata-bristol":           ("unvisited", None,          None),
    "https://www.meetup.com/pydata-exeter":            ("spoken", "2026-05-06",  "https://www.meetup.com/pydata-exeter/events/314216811/"),
    "https://www.meetup.com/pydata-milton-keynes":     ("spoken",    "2026-04-23",  "https://www.meetup.com/pydata-milton-keynes/events/314008314/"),
    "https://www.meetup.com/pydata-cambridge-meetup":  ("unvisited", None,          None),
    "https://www.meetup.com/pydata-norwich":           ("unvisited", None,          None),
    "https://www.meetup.com/pydata-southampton":       ("spoken",    None,          None),
    "https://www.meetup.com/pydata-surrey":            ("unvisited", None,          None),
    "https://www.meetup.com/pydata-kent":              ("unvisited", None,          None),
    "https://www.meetup.com/pydata-edinburgh":         ("unvisited", None,          None),
}

STADIA_API_KEY = os.environ.get("STADIA_API_KEY", "your-key-here")


def should_skip_unvisited(g):
    days = g.get("days_since_last_event")
    past_events = g.get("past_events_count") or 0
    upcoming = g.get("upcoming_events_count") or 0
    print(f"Checking if {g['name']} should be skipped as unvisited: {past_events} past events, {upcoming} upcoming, {days} days since last event")
    if upcoming >= 2:
        print(f"  → Not skipping because there are {upcoming} upcoming events")
        return False, None
    if pd.isna(days) or days > 100:
        print(f"  → Skipping because last event was {days} days ago")
        return True, "inactive"
    if past_events <= 1:
        print(f"  → Skipping because there are only {past_events} past events")
        return True, "only 1 event"
    print(f"  → Not skipping because there are {past_events} past events and last event was {days} days ago")
    return False, None


def create_personal_map(output_file=None):
    if output_file is None:
        output_file = Path(__file__).parent / "pydata_personal_map.html"

    CSV_PATH = Path(__file__).parent.parent.parent / "pydata_groups.csv"
    df = pd.read_csv(CSV_PATH)
    if "members" in df.columns:
        df["members"] = df["members"].fillna(0).astype(int)
    groups = df.to_dict(orient="records")

    watercolor_url = (
        "https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg"
        f"?api_key={STADIA_API_KEY}"
    )
    world_map = folium.Map(
        location=[54, -2],
        zoom_start=6,
        tiles=watercolor_url,
        attr=(
            '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> '
            '&copy; <a href="https://stamen.com/">Stamen Design</a>'
        ),
        max_zoom=16,
    )

    # Create separate Leaflet panes per status so z-index is controlled at the
    # pane level — the only reliable way to stack DivIcon markers in Leaflet.
    # DivIcon ignores z_index_offset on folium.Marker; child CSS z-index is
    # trapped inside the marker pane's stacking context and has no effect.
    # CustomPane uses folium's own macro system so panes exist before markers.
    for pane_name, z in [("pane-unvisited", 400), ("pane-spoken", 500), ("pane-upcoming", 600)]:
        folium.map.CustomPane(pane_name, z_index=z).add_to(world_map)

    matched = 0
    skipped = 0
    unmatched_keys = set(MY_GROUPS.keys())

    # Resolve entries and sort so upcoming markers are added last (rendered on top)
    groups_to_render = []
    for g in groups:
        url = str(g.get("url", "")).rstrip("/").lower()
        entry = next(
            (v for k, v in MY_GROUPS.items() if k.rstrip("/").lower() == url),
            None
        )
        if entry:
            groups_to_render.append((g, entry))

    # ascending sort: unvisited=0 drawn first, spoken=1 next, upcoming=2 drawn last (on top)
    groups_to_render.sort(key=lambda x: STATUS_ORDER.get(x[1][0], 0))

    for g, entry in groups_to_render:
        url = str(g.get("url", "")).rstrip("/").lower()
        status, date, event_url = entry

        if pd.isna(g.get("lat")) or pd.isna(g.get("lon")):
            print(f"⚠ No coordinates for {g['name']}, skipping")
            continue

        if status == "unvisited":
            skip, reason = should_skip_unvisited(g)
            if skip:
                print(f"↷ {g['name']} skipped ({reason})")
                skipped += 1
                unmatched_keys.discard(
                    next(k for k in MY_GROUPS if k.rstrip("/").lower() == url)
                )
                continue

        group_url = g.get("url", "")
        city = g.get("city", "")

        if status == "upcoming":
            city_html = (
                f'<a href="{group_url}" target="_blank" '
                f'style="color:inherit;text-decoration:none;font-weight:bold;">{city}</a>'
            )
            if date:
                if event_url:
                    date_html = (
                        f'<a href="{event_url}" target="_blank" '
                        f'style="color:inherit;text-decoration:none;">{date}</a>'
                    )
                else:
                    date_html = date
                label = f"{city_html}<br><span style='font-size:10px;'>{date_html}</span>"
            else:
                label = city_html
        elif status == "spoken":
            label = (
                f'<a href="{group_url}" target="_blank" '
                f'style="color:inherit;text-decoration:none;font-weight:bold;">{city}</a>'
            )
        else:
            label = ""

        icon_html = f"""
            <div style="display:flex; flex-direction:column; align-items:center;">
                <img src="{STATUS_ICONS[status]}" style="width:24px;height:24px;">
                {"" if not label else f'<div style="background:rgba(255,255,255,0.85); border-radius:3px; padding:1px 4px; font-size:11px; font-family:sans-serif; white-space:nowrap; margin-top:2px; text-align:center; box-shadow:1px 1px 3px rgba(0,0,0,0.2);">{label}</div>'}
            </div>
        """

        icon = folium.DivIcon(
            html=icon_html,
            icon_size=(80, 50),
            icon_anchor=(40, 12),
        )

        tooltip = f"{g['name']} ({status})"
        if date:
            tooltip += f" — {date}"

        folium.Marker(
            location=[g["lat"], g["lon"]],
            popup=folium.Popup(build_popup_html(g), max_width=300),
            tooltip=tooltip,
            icon=icon,
            pane=f"pane-{status}",
        ).add_to(world_map)

        print(f"✓ {g['name']} ({status}){f' — {date}' if date else ''}")
        matched += 1

        unmatched_keys.discard(
            next(k for k in MY_GROUPS if k.rstrip("/").lower() == url)
        )

    if unmatched_keys:
        print("\n⚠ These URLs had no match in the CSV:")
        for k in sorted(unmatched_keys):
            print(f"  {k}")

    counts = Counter()
    for url, entry in MY_GROUPS.items():
        status, date, event_url = entry
        matched_url = url.rstrip("/").lower()
        group = next((g for g in groups if str(g.get("url", "")).rstrip("/").lower() == matched_url), None)
        if group is None:
            continue
        if status == "unvisited":
            skip, _ = should_skip_unvisited(group)
            if skip:
                continue
        counts[status] += 1

    total = sum(counts.values())
    pct = {s: round((counts[s] / total) * 100) if total else 0 for s in ["spoken", "upcoming", "unvisited"]}

    title_html = """
    <div style="position:fixed; top:16px; left:50%; transform:translateX(-50%);
                z-index:1000; font-family:georgia, serif; font-size:24px;
                font-weight:bold; letter-spacing:2px;
                background:white; padding:8px 20px; border-radius:6px;
                box-shadow:2px 2px 6px rgba(0,0,0,0.3);
                border-top:4px solid #e63946;">
        Tour de PyData
    </div>
    """
    world_map.get_root().html.add_child(folium.Element(title_html))

    progress_html = f"""
    <div style="position:fixed; bottom:0; left:0; right:0;
                z-index:1000; background:white; padding:10px 16px;
                font-family:sans-serif; font-size:12px;
                box-shadow:0 -2px 6px rgba(0,0,0,0.2);">
        <div style="display:flex; align-items:center; gap:16px; margin-bottom:6px;">
            <span style="font-weight:bold;">UK PyData Groups</span>
            <span>{counts['spoken']} spoken · {counts['upcoming']} upcoming · {counts['unvisited']} to visit</span>
            <div style="display:flex; align-items:center; gap:8px; margin-left:auto;">
                <img src="{STATUS_ICONS['spoken']}"    style="width:14px;height:14px;vertical-align:middle;"> Spoken
                <img src="{STATUS_ICONS['upcoming']}"  style="width:14px;height:14px;vertical-align:middle;"> Upcoming
                <img src="{STATUS_ICONS['unvisited']}" style="width:14px;height:14px;vertical-align:middle;"> Not yet visited
            </div>
        </div>
        <div style="display:flex; height:20px; border-radius:4px; overflow:hidden; width:100%;">
            <div style="width:{pct['spoken']}%;   background:#2a9d43; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; white-space:nowrap; overflow:hidden;">
                Spoken {pct['spoken']}%
            </div>
            <div style="width:{pct['upcoming']}%; background:#e6a817; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; white-space:nowrap; overflow:hidden;">
                Upcoming {pct['upcoming']}%
            </div>
            <div style="width:{pct['unvisited']}%;background:#ec2828; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; white-space:nowrap; overflow:hidden;">
                Not yet visited {pct['unvisited']}%
            </div>
        </div>
    </div>
    """
    world_map.get_root().html.add_child(folium.Element(progress_html))
    add_hash_navigation(world_map)
    world_map.save(str(output_file))
    print(f"\nMatched {matched} of {len(MY_GROUPS)} groups ({skipped} inactive unvisited skipped)")
    print(f"Saved {output_file}")


if __name__ == "__main__":
    create_personal_map()
