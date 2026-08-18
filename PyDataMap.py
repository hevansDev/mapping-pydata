# PyDataMap.py
import asyncio
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import folium
from folium.plugins import MarkerCluster
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from playwright.async_api import async_playwright

CACHE_FILE = Path("geocode_cache.json")
MANUAL_GROUPS_FILE = Path("pydata_groups_manual.csv")

ESRI_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'
ESRI_ATTR = 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012'

# Columns that should always be whole numbers (never floats or sets)
INT_COLUMNS = ['members', 'past_events_count', 'organizer_count', 'days_since_last_event', 'pro_network_misses', 'upcoming_events_count']


def sanitise_int(value, default=None):
    """Coerce a value to int, handling NaN, sets, floats, and strings."""
    if isinstance(value, set):
        value = next(iter(value), None)
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def sanitise_dataframe(df):
    """Ensure integer columns are stored as nullable integers in the DataFrame."""
    for col in INT_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: sanitise_int(x))
            df[col] = pd.array(df[col], dtype=pd.Int64Dtype())
    return df


def get_cached_pydata_groups():
    if Path("pydata_groups.csv").exists():
        df = pd.read_csv("pydata_groups.csv")
        if 'in_pro_network' not in df.columns:
            df['in_pro_network'] = False
        if 'pro_network_misses' not in df.columns:
            df['pro_network_misses'] = 0
        if 'non_meetup' not in df.columns:
            df['non_meetup'] = False
        else:
            df['non_meetup'] = df['non_meetup'].fillna(False).astype(bool)
        # Rows with a non-blank 'source' were added via the manual CSV at some
        # point (discord/conference/university/github/etc.) and are always
        # non-Meetup, regardless of what non_meetup was saved as previously —
        # this self-heals rows that were merged in before the non_meetup
        # column existed and got defaulted to False.
        if 'source' in df.columns:
            has_source = df['source'].notna() & (df['source'].astype(str).str.strip() != '')
            df.loc[has_source, 'non_meetup'] = True
        # Backwards compat: derive count from old boolean column if present
        if 'upcoming_events_count' not in df.columns:
            if 'has_upcoming_events' in df.columns:
                df['upcoming_events_count'] = df['has_upcoming_events'].apply(lambda x: 1 if x else 0)
            else:
                df['upcoming_events_count'] = 0
        df = sanitise_dataframe(df)
        return df.to_dict(orient='records')
    return None


def load_manual_groups():
    if not MANUAL_GROUPS_FILE.exists():
        return []
    df = pd.read_csv(MANUAL_GROUPS_FILE)
    df = sanitise_dataframe(df)
    if 'source' not in df.columns:
        df['source'] = 'manual'
    # Manual groups have no Meetup presence and therefore no reliable
    # activity data (upcoming/past events). Default them to non_meetup so
    # they render with a neutral marker instead of active/inactive styling,
    # unless the CSV explicitly overrides this per-row.
    if 'non_meetup' not in df.columns:
        df['non_meetup'] = True
    else:
        df['non_meetup'] = df['non_meetup'].fillna(True).astype(bool)
    records = df.to_dict(orient='records')
    print(f"Loaded {len(records)} manual groups from {MANUAL_GROUPS_FILE}")
    return records


# Scrape all PyData groups from meetup.com/pro/pydata
async def get_pydata_groups():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto('https://www.meetup.com/pro/pydata/')
        await page.wait_for_selector('[data-testid="group"]')

        groups = await page.evaluate('''
            async () => {
                const allGroups = new Map();
                let lastCount = 0;
                let stableCount = 0;

                while (stableCount < 10) {
                    document.querySelectorAll('[data-testid="group"]').forEach(el => {
                        const link = el.querySelector('a');
                        const url = link?.href || '';
                        if (url && !allGroups.has(url)) {
                            const text = el.innerText;
                            const memberMatch = text.match(/([\\d,]+)\\s*members?/i);
                            const ratingMatch = text.match(/^([\\d.]+)$/m);
                            const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
                            const firstLine = lines[0] || '';
                            const locationMatch = firstLine.match(/^([^,]+),\\s*(\\d+)$/);
                            const cleanUrl = url.split('?')[0];

                            allGroups.set(cleanUrl, {
                                name: el.querySelector('h3')?.textContent?.trim() || '',
                                url: cleanUrl,
                                urlname: cleanUrl.match(/meetup\\.com\\/([^\\/]+)/)?.[1] || '',
                                members: memberMatch ? parseInt(memberMatch[1].replace(/,/g, '')) : null,
                                city: locationMatch ? locationMatch[1] : firstLine.split(',')[0],
                                rating: ratingMatch ? parseFloat(ratingMatch[1]) : null,
                            });
                        }
                    });

                    window.scrollTo(0, document.body.scrollHeight);
                    await new Promise(r => setTimeout(r, 2000));

                    if (allGroups.size === lastCount) stableCount++;
                    else stableCount = 0;
                    lastCount = allGroups.size;
                }
                return Array.from(allGroups.values());
            }
        ''')
        await browser.close()

    for g in groups:
        g['in_pro_network'] = True

    return groups


# Get public data from main group page - no login required
async def get_group_details_public(page, group_url):
    # Use domcontentloaded instead of networkidle — Meetup keeps background
    # connections alive indefinitely, causing networkidle to never fire.
    await page.goto(group_url, wait_until='domcontentloaded', timeout=15000)

    # Wait for the key content to be present rather than relying on network state
    try:
        await page.wait_for_selector('h1', timeout=10000)
    except Exception:
        pass  # proceed anyway and let the evaluate scrape what it can

    details = await page.evaluate('''
        () => {
            const text = document.body.innerText;

            const pastMatch = text.match(/Past events\\s*(\\d+)/);
            const pastEventsCount = pastMatch ? parseInt(pastMatch[1]) : 0;

            const organizerMatch = text.match(/and (\\d+) others/);
            let organizerCount = organizerMatch ? parseInt(organizerMatch[1]) + 1 : null;

            const organizerLink = document.querySelector('a[href*="/members/?op=leaders"]');
            const primaryOrganizer = organizerLink?.previousElementSibling?.innerText?.trim() || 
                                     organizerLink?.parentElement?.querySelector('img')?.alt?.replace('Photo of the user ', '') ||
                                     null;

            let lastEventDate = null;
            if (pastEventsCount > 0) {
                const allTimeElements = document.querySelectorAll('time[datetime]');
                for (const timeEl of allTimeElements) {
                    const parent = timeEl.closest('a[href*="/events/"]');
                    if (parent && parent.href.includes('eventOrigin=group_past_events')) {
                        lastEventDate = timeEl.getAttribute('datetime');
                        break;
                    }
                }

                if (!lastEventDate) {
                    const pastSection = document.evaluate(
                        "//h2[contains(text(), 'Past events')]/following::time[@datetime][1]",
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;
                    if (pastSection) {
                        lastEventDate = pastSection.getAttribute('datetime');
                    }
                }

                if (!lastEventDate) {
                    const now = new Date();
                    allTimeElements.forEach(timeEl => {
                        if (!lastEventDate) {
                            const dt = timeEl.getAttribute('datetime');
                            if (dt) {
                                const eventDate = new Date(dt.split('[')[0]);
                                if (eventDate < now) {
                                    lastEventDate = dt;
                                }
                            }
                        }
                    });
                }
            }

            const upcomingEventCards = document.querySelectorAll('a[href*="eventOrigin=group_upcoming_events"]');
            const upcomingEventsCount = upcomingEventCards.length;

            // Scrape member count from the individual group page as a reliable source
            const memberMatch = text.match(/([\\d,]+)\\s*members/i);
            const members = memberMatch ? parseInt(memberMatch[1].replace(/,/g, '')) : null;

            return {
                members: members,
                past_events_count: pastEventsCount,
                organizer_count: organizerCount,
                primary_organizer: primaryOrganizer,
                last_event_date: lastEventDate,
                upcoming_events_count: upcomingEventsCount
            };
        }
    ''')

    base = group_url.rstrip('/')
    details['events_url'] = f"{base}/events/"
    details['leaders_url'] = f"{base}/members/?op=leaders"

    if details.get('past_events_count', 0) > 0 and details.get('last_event_date'):
        try:
            date_str = details['last_event_date'].split('[')[0]
            last_event = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            details['days_since_last_event'] = (now - last_event).days
        except Exception:
            details['days_since_last_event'] = None
    else:
        details['days_since_last_event'] = None

    return details


# Load existing cache or return default structure
def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {
        "hints": {},
        "coords": {}
    }


# Save cache to file
def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


# Get the geocoding query for a group name
def get_query_for_group(name, cache):
    if name in cache['hints']:
        return cache['hints'][name]
    return name.replace('PyData ', '').replace(' Meetup', '').replace(' Group', '').replace('PyData', '')


# Geocode groups with caching
def geocode_groups(groups):
    cache = load_cache()

    geolocator = Nominatim(user_agent="pydata_mapper", timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5)

    results = []
    cache_hits = 0
    api_calls = 0

    for group in groups:
        name = group['name']
        query = get_query_for_group(name, cache)

        if query is None:
            print(f"⊘ {name} (skipped)")
            continue

        if query in cache['coords']:
            cached = cache['coords'][query]
            results.append({
                **group,
                'query': query,
                'lat': cached['lat'],
                'lon': cached['lon']
            })
            print(f"✓ {name} -> {query} ({cached['lat']:.2f}, {cached['lon']:.2f}) [cached]")
            cache_hits += 1
            continue

        try:
            location = geocode(query)
            if location:
                cache['coords'][query] = {
                    'lat': location.latitude,
                    'lon': location.longitude,
                    'display_name': location.address
                }
                results.append({
                    **group,
                    'query': query,
                    'lat': location.latitude,
                    'lon': location.longitude
                })
                print(f"✓ {name} -> {query} ({location.latitude:.2f}, {location.longitude:.2f})")
                api_calls += 1
            else:
                print(f"✗ {name} -> {query} (not found)")
        except Exception as e:
            print(f"✗ {name} -> {query} (error: {type(e).__name__})")

    save_cache(cache)

    print(f"\nGeocoded {len(results)} of {len(groups)} groups")
    print(f"Cache hits: {cache_hits}, API calls: {api_calls}")

    return results


# Extract country from cached display_name
def get_country_from_cache(query):
    cache = load_cache()
    if query in cache['coords']:
        display_name = cache['coords'][query].get('display_name', '')
        parts = display_name.split(', ')
        if parts:
            return parts[-1].strip()
    return None


# Calculate fill color and opacity for layers map (green/blue active styling)
def get_marker_style_layers(group):
    if group.get('non_meetup'):
        return '#ee9041', 0.7  # neutral marker — non-Meetup groups have no activity data
    if group.get('upcoming_events_count', 0) > 0:
        fill_color = '#22c55e'  # green
        fill_opacity = 0.9
    else:
        fill_color = '#0000FF'  # blue
        days = group.get('days_since_last_event')
        if days is None:
            fill_opacity = 0.1
        else:
            fill_opacity = max(0.4, 0.9 - (math.log1p(days) / math.log1p(365)))
    return fill_color, fill_opacity


# Calculate fill color and opacity for inactive map (red inactive, faint blue active)
def get_marker_style_inactive(group):
    if group.get('non_meetup'):
        return '#ee9041', 0.7  # neutral marker — non-Meetup groups have no activity data
    days = group.get('days_since_last_event')
    if group.get('upcoming_events_count', 0) > 0 or (days is not None and days < 100):
        fill_color = '#0000FF'  # blue
        fill_opacity = 0.1
    else:
        fill_color = '#FF0000'  # red
        if days is None:
            fill_opacity = 0.9  # Never had events - bright red
        else:
            fill_opacity = min(0.9, 0.1 + (math.log1p(days) / math.log1p(365)) * 0.8)
    return fill_color, fill_opacity


# Parse the alt_urls field into a list of (label, url) tuples.
# Format: entries separated by '|', each entry optionally labelled as
# 'Label::https://example.com'. A bare URL with no '::' label gets an
# auto-generated label from its domain. Lets a group carry its old Meetup
# link (or LinkedIn, Discord, etc.) alongside its current one without
# needing a second row / second marker.
def parse_alt_urls(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if not isinstance(value, str) or not value.strip():
        return []

    links = []
    for entry in value.split('|'):
        entry = entry.strip()
        if not entry:
            continue
        if '::' in entry:
            label, url = entry.split('::', 1)
            label, url = label.strip(), url.strip()
        else:
            url = entry
            label = urlparse(url).netloc or url
        if url:
            links.append((label, url))
    return links


# Render alt_urls as a small HTML fragment of extra links, or '' if none
def format_alt_links_html(g):
    links = parse_alt_urls(g.get('alt_urls'))
    if not links:
        return ''
    rendered = ' · '.join(f"<a href='{url}' target='_blank'>{label}</a>" for label, url in links)
    return f"<br>🔗 Also: {rendered}"


# Build popup HTML for a group
def build_popup_html(g):
    header = f"""<b><a href='{g['url']}' target='_blank'>{g['name']}</a></b><br>
        📍 {g.get('city', 'Unknown')}"""

    # Meetup-derived stats (members, past/upcoming events, Meetup leaders
    # link) are meaningless for groups with no Meetup presence — skip them
    # rather than showing misleading zeros or a fabricated Leaders link.
    if g.get('non_meetup'):
        return f"""
        {header}{format_alt_links_html(g)}
    """

    days = g.get('days_since_last_event')
    days_str = f"{days} days ago" if days is not None else "Never"
    upcoming_count = g.get('upcoming_events_count') or 0
    upcoming_str = f"{upcoming_count} ✓" if upcoming_count > 0 else "No"
    past_count = g.get('past_events_count') or 0
    members = g.get('members') or 0

    return f"""
        {header}<br>
        👥 {members} members<br>
        📅 {past_count} past events<br>
        ⏱️ Last event: {days_str}<br>
        🔜 Upcoming: {upcoming_str}<br>
        <a href='{g.get('events_url', '')}' target='_blank'>Events</a> |
        <a href='{g.get('leaders_url', '')}' target='_blank'>Leaders</a>{format_alt_links_html(g)}
    """


# Round coords to group nearby markers (2 decimal places ≈ 1km)
def coord_key(lat, lon, precision=2):
    return (round(lat, precision), round(lon, precision))


# Create a circle marker for a group
def create_marker(g, style='orange'):
    members = max(1, g.get('members') or 1)

    if style == 'layers':
        fill_color, fill_opacity = get_marker_style_layers(g)
        radius = max(5, math.log(members) * 2)
        popup = folium.Popup(build_popup_html(g), max_width=300)
        tooltip = f"{g['name']} ({members} members)"
    elif style == 'inactive':
        fill_color, fill_opacity = get_marker_style_inactive(g)
        radius = max(5, math.log(members) * 2)
        popup = folium.Popup(build_popup_html(g), max_width=300)
        tooltip = f"{g['name']} ({members} members)"
    else:
        fill_color = '#ee9041'
        fill_opacity = 0.7
        radius = 8
        popup = f"<a href='{g['url']}' target='_blank'>{g['name']}</a>{format_alt_links_html(g)}"
        tooltip = g['name']

    return folium.CircleMarker(
        location=[g['lat'], g['lon']],
        radius=radius,
        popup=popup,
        tooltip=tooltip,
        color=fill_color,
        fill=True,
        fill_color=fill_color,
        fill_opacity=fill_opacity,
        weight=0
    )


def add_hash_navigation(world_map):
    hash_script = """
    <script>
    (function() {
        function parseHash() {
            var hash = window.location.hash;
            if (hash) {
                var parts = hash.replace('#', '').split('/');
                if (parts.length === 3) {
                    var zoom = parseInt(parts[0]);
                    var lat = parseFloat(parts[1]);
                    var lng = parseFloat(parts[2]);
                    if (!isNaN(zoom) && !isNaN(lat) && !isNaN(lng)) {
                        return {zoom: zoom, lat: lat, lng: lng};
                    }
                }
            }
            return null;
        }
        
        var checkMap = setInterval(function() {
            for (var key in window) {
                if (window[key] instanceof L.Map) {
                    var map = window[key];
                    clearInterval(checkMap);
                    var view = parseHash();
                    if (view) {
                        map.setView([view.lat, view.lng], view.zoom);
                    }
                    
                    map.on('moveend', function() {
                        var center = map.getCenter();
                        var zoom = map.getZoom();
                        history.replaceState(null, null, '#' + zoom + '/' + center.lat.toFixed(4) + '/' + center.lng.toFixed(4));
                    });
                    break;
                }
            }
        }, 100);
    })();
    </script>
    """
    world_map.get_root().html.add_child(folium.Element(hash_script))


def make_base_map(location=[30, 0], zoom_start=2):
    world_map = folium.Map(location=location, zoom_start=zoom_start, tiles=None)
    folium.TileLayer(
        tiles=ESRI_TILE_URL,
        attr=ESRI_ATTR,
        name='Esri World Street Map',
    ).add_to(world_map)
    return world_map


def _add_markers_to_map(world_map, groups_enriched, style):
    coord_groups = defaultdict(list)
    for g in groups_enriched:
        if 'lat' not in g or 'lon' not in g:
            continue
        key = coord_key(g['lat'], g['lon'])
        coord_groups[key].append(g)

    for key, groups in coord_groups.items():
        if len(groups) == 1:
            create_marker(groups[0], style=style).add_to(world_map)
        else:
            cluster = MarkerCluster(
                options={
                    'spiderfyOnMaxZoom': True,
                    'disableClusteringAtZoom': 12
                }
            ).add_to(world_map)
            for g in groups:
                create_marker(g, style=style).add_to(cluster)


# Create simple world map with orange circle markers (only cluster overlapping)
def create_world_map(groups_enriched, output_file='pydata_world_map.html'):
    world_map = make_base_map()
    _add_markers_to_map(world_map, groups_enriched, style='orange')
    add_hash_navigation(world_map)
    world_map.save(output_file)
    print(f"Saved {output_file}")


# Create world map with activity-based styling
def create_world_map_layers(groups_enriched, output_file='pydata_world_map_active.html'):
    world_map = make_base_map()
    _add_markers_to_map(world_map, groups_enriched, style='layers')
    add_hash_navigation(world_map)
    world_map.save(output_file)
    print(f"Saved {output_file}")


# Create world map highlighting inactive groups
def create_world_map_inactive(groups_enriched, output_file='pydata_world_map_inactive.html'):
    world_map = make_base_map()
    _add_markers_to_map(world_map, groups_enriched, style='inactive')
    add_hash_navigation(world_map)
    world_map.save(output_file)
    print(f"Saved {output_file}")


# Create world map showing only groups outside the Pro network
def create_world_map_non_pro(groups_enriched, output_file='pydata_world_map_non_pro.html'):
    non_pro = [g for g in groups_enriched if not g.get('in_pro_network', True)]
    world_map = make_base_map()
    _add_markers_to_map(world_map, non_pro, style='orange')
    add_hash_navigation(world_map)
    world_map.save(output_file)
    print(f"Saved {output_file} ({len(non_pro)} non-Pro groups)")


# Load cached enrichment data from CSV
def load_enrichment_cache(csv_file='pydata_groups.csv'):
    cache = {}
    if Path(csv_file).exists():
        df = pd.read_csv(csv_file)
        df = sanitise_dataframe(df)
        for _, row in df.iterrows():
            cache[row['url']] = row.to_dict()
    return cache


async def main():
    print("=" * 60)
    print("Fetching PyData groups from cache...")
    groups = get_cached_pydata_groups()
    print("=" * 60)

    print("Looking for new PyData groups on Meetup...")
    new_groups = await get_pydata_groups()
    pro_urls = {g['url'] for g in new_groups}
    print(f"Found {len(new_groups)} groups in Pro network")

    if new_groups:
        print(f"Found {len(new_groups)} new groups\n", flush=True)

        print("=" * 60, flush=True)
        print("Geocoding new groups...")
        groups_with_coords = geocode_groups(new_groups)
        for g in groups_with_coords:
            g['country'] = get_country_from_cache(g.get('query', ''))

        print("=" * 60, flush=True)
        print("Append new groups to cache...")
        if groups is not None:
            existing_urls = set(g['url'] for g in groups)
            combined_groups = groups + [g for g in groups_with_coords if g['url'] not in existing_urls]
        else:
            combined_groups = groups_with_coords

        # Only update pro network status if scrape looks complete.
        # If the scrape returned fewer than 80% of cached groups, it was likely
        # a partial load — skip the update to avoid false removals.
        cached_pro_count = sum(1 for g in combined_groups if g.get('in_pro_network', False))
        if len(new_groups) < cached_pro_count * 0.8:
            print(
                f"\n⚠️  Scrape returned only {len(new_groups)} groups vs "
                f"{cached_pro_count} cached Pro groups "
                f"— skipping Pro network status update to avoid false removals."
            )
        else:
            # Use a miss counter — only mark as removed after 3 consecutive misses.
            for g in combined_groups:
                was_pro = g.get('in_pro_network', False)
                now_pro = g['url'] in pro_urls

                if now_pro:
                    # Confirmed present — reset miss counter
                    g['in_pro_network'] = True
                    g['pro_network_misses'] = 0
                elif was_pro:
                    # Not seen this run — increment miss counter
                    misses = int(g.get('pro_network_misses') or 0) + 1
                    g['pro_network_misses'] = misses
                    if misses >= 3:
                        print(f"  ⚠️  No longer in Pro network (confirmed {misses}x): {g['name']}")
                        g['in_pro_network'] = False
                    else:
                        print(f"  ⚠️  Not seen in Pro network (miss {misses}/3): {g['name']} — keeping for now")
                        g['in_pro_network'] = True  # keep until confirmed absent
                else:
                    g['in_pro_network'] = False
                    g['pro_network_misses'] = 0

        df = pd.DataFrame(combined_groups)
        df = sanitise_dataframe(df)
        df.to_csv('pydata_groups.csv', index=False)

        print("Reloading cache...")
        groups = get_cached_pydata_groups()

    print("\n" + "=" * 60)
    if len(groups) < 135:
        raise Exception(f"Expected at least 135 groups in cache, found {len(groups)}. Scrape may have been incomplete.")

    print("\n" + "=" * 60)
    print(f"Enriching {len(groups)} groups with event details...")
    print("=" * 60, flush=True)

    enrichment_cache = load_enrichment_cache()
    print(f"Loaded {len(enrichment_cache)} groups from enrichment cache\n", flush=True)

    all_groups_enriched = []
    fresh_count = 0
    cached_count = 0
    failed_count = 0

    SCRAPE_RETRIES = 2  # number of retry attempts before falling back to cache

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 800})

        for i, group in enumerate(groups):
            print(f"[{i + 1}/{len(groups)}] {group['name']}...", end=' ', flush=True)

            details = None
            last_error = None

            for attempt in range(1 + SCRAPE_RETRIES):
                try:
                    details = await get_group_details_public(page, group['url'] + '/')
                    break  # success — exit retry loop
                except Exception as e:
                    last_error = e
                    if attempt < SCRAPE_RETRIES:
                        print(f"retrying ({attempt + 1}/{SCRAPE_RETRIES})...", end=' ', flush=True)
                        await asyncio.sleep(2)

            if details is not None:
                enriched = {**group, **details}
                # Prefer member count from individual page if the Pro listing
                # scrape missed it (details['members'] is the more reliable source)
                if not details.get('members') and group.get('members'):
                    enriched['members'] = group['members']
                all_groups_enriched.append(enriched)
                days = details.get('days_since_last_event')
                days_str = f"{days} days ago" if days is not None else "never"
                upcoming = details.get('upcoming_events_count', 0)
                upcoming_str = f"✓ {upcoming}" if upcoming > 0 else "✗"
                members_str = f", members: {enriched.get('members', '?')}"
                print(f"✓ {details.get('past_events_count', 0) or 0} events, last: {days_str}, upcoming: {upcoming_str}{members_str}", flush=True)
                fresh_count += 1
            else:
                # All attempts failed — fall back to cache
                cached = enrichment_cache.get(group['url'])
                if cached and 'past_events_count' in cached:
                    enriched = {**group}
                    for key in ['past_events_count', 'organizer_count', 'primary_organizer',
                                'last_event_date', 'upcoming_events_count', 'days_since_last_event',
                                'events_url', 'leaders_url']:
                        if key in cached and cached.get(key) is not None:
                            enriched[key] = cached[key]
                    all_groups_enriched.append(enriched)
                    days = enriched.get('days_since_last_event')
                    days_str = f"{days} days ago" if days is not None else "never"
                    upcoming = enriched.get('upcoming_events_count', 0) or 0
                    upcoming_str = f"✓ {upcoming}" if upcoming > 0 else "✗"
                    print(f"⟳ {enriched.get('past_events_count', 0) or 0} events, last: {days_str}, upcoming: {upcoming_str} [cached]", flush=True)
                    cached_count += 1
                else:
                    print(f"✗ {type(last_error).__name__} (no cache)", flush=True)
                    all_groups_enriched.append(group)
                    failed_count += 1

        await browser.close()

    print("\n" + "=" * 60)
    print(f"Enrichment complete: {fresh_count} fresh, {cached_count} cached, {failed_count} failed")

    manual_groups = load_manual_groups()
    if manual_groups:
        meetup_urls = {g['url'] for g in all_groups_enriched}
        new_manual = [g for g in manual_groups if g['url'] not in meetup_urls]
        all_groups_enriched = all_groups_enriched + new_manual
        print(f"Added {len(new_manual)} manual groups (total: {len(all_groups_enriched)})")

    print("Generating maps...")
    print("=" * 60, flush=True)

    create_world_map(all_groups_enriched, 'pydata_world_map.html')
    create_world_map_layers(all_groups_enriched, 'pydata_world_map_active.html')
    create_world_map_inactive(all_groups_enriched, 'pydata_world_map_inactive.html')
    create_world_map_non_pro(all_groups_enriched, 'pydata_world_map_non_pro.html')

    df = pd.DataFrame(all_groups_enriched)
    df = sanitise_dataframe(df)
    df.to_csv('pydata_groups.csv', index=False)
    print("Saved pydata_groups.csv", flush=True)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())