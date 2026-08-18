import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import math
    from collections import defaultdict
    from pathlib import Path

    import folium
    from folium.plugins import MarkerCluster
    import pandas as pd

    return MarkerCluster, Path, folium, math, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # PyData Meetup Mapper

    This notebook creates interactive maps of PyData meetup groups worldwide.

    **Data source:** Scraped from [meetup.com/pro/pydata](https://www.meetup.com/pro/pydata)

    **Maps generated:**
    1. **World Map** - Simple orange markers
    2. **Layers Map** - Green (upcoming events) / Blue (no upcoming) with opacity based on recency
    3. **Inactive Map** - Highlights inactive groups in red, active groups faint blue
    """)
    return


@app.cell
def _(Path, pd):
    # Load cached data from CSV
    _csv_file = Path('pydata_groups.csv')

    if not _csv_file.exists():
        raise FileNotFoundError(f"{_csv_file} not found. Run PyDataMap.py first to generate data.")

    df = pd.read_csv(_csv_file)
    groups = df.to_dict('records')

    print(f"✓ Loaded {len(groups)} groups from cache")
    print(f"  - With upcoming events: {sum(1 for g in groups if g.get('has_upcoming_events'))}")
    print(f"  - Without upcoming events: {sum(1 for g in groups if not g.get('has_upcoming_events'))}")

    df
    return df, groups


@app.cell
def _(MarkerCluster, folium, math, pd):
    # Shared helper functions

    # Round coords to group nearby markers (2 decimal places ≈ 1km)
    def coord_key(lat, lon, precision=2):
        return (round(lat, precision), round(lon, precision))

    # Parse the alt_urls field into a list of (label, url) tuples.
    # Format: entries separated by '|', each entry optionally labelled as
    # 'Label::https://example.com'. Lets a group carry its old Meetup link
    # (or LinkedIn, Discord, etc.) alongside its current one without a
    # second row / second marker.
    def parse_alt_urls(value):
        from urllib.parse import urlparse

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

        # Meetup-derived stats (members, past/upcoming events, Meetup
        # leaders link) are meaningless for groups with no Meetup presence —
        # skip them rather than showing misleading zeros or a fabricated
        # Leaders link.
        if g.get('non_meetup'):
            return f"""
            {header}{format_alt_links_html(g)}
        """

        days = g.get('days_since_last_event')
        days_str = f"{int(days)} days ago" if pd.notna(days) else "Never"
        upcoming_str = "Yes ✓" if g.get('has_upcoming_events') else "No"
        past_count = g.get('past_events_count', 0) or 0
        return f"""
            {header}<br>
            👥 {g.get('members', '?')} members<br>
            📅 {int(past_count) if pd.notna(past_count) else 0} past events<br>
            ⏱️ Last event: {days_str}<br>
            🔜 Upcoming: {upcoming_str}<br>
            <a href='{g.get('events_url', '')}' target='_blank'>Events</a> |
            <a href='{g.get('leaders_url', '')}' target='_blank'>Leaders</a>{format_alt_links_html(g)}
        """

    # Style: Simple orange
    def get_marker_style_orange(group):
        return '#ee9041', 0.7

    # Style: Green/blue activity-based
    def get_marker_style_layers(group):
        if group.get('non_meetup'):
            return '#ee9041', 0.7  # neutral marker — non-Meetup groups have no activity data
        if group.get('has_upcoming_events'):
            return '#22c55e', 0.8  # green
        else:
            days = group.get('days_since_last_event')
            if pd.isna(days):
                return '#0000FF', 0.1  # blue, faint
            else:
                opacity = max(0.4, 0.9 - (math.log1p(days) / math.log1p(365)))
                return '#0000FF', opacity

    # Style: Red inactive, faint blue active
    def get_marker_style_inactive(group):
        if group.get('non_meetup'):
            return '#ee9041', 0.7  # neutral marker — non-Meetup groups have no activity data
        days = group.get('days_since_last_event')
        is_active = group.get('has_upcoming_events') or (pd.notna(days) and days < 100)

        if is_active:
            return '#0000FF', 0.1  # faint blue
        else:
            if pd.isna(days):
                return '#FF0000', 0.9  # bright red - never had events
            else:
                opacity = min(0.9, 0.1 + (math.log1p(days) / math.log1p(365)) * 0.8)
                return '#FF0000', opacity

    # Create a circle marker for a group
    def create_marker(g, style='orange'):
        members = g.get('members') or 10

        if style == 'orange':
            fill_color, fill_opacity = get_marker_style_orange(g)
            radius = 8
            popup = f"<a href='{g['url']}' target='_blank'>{g['name']}</a>{format_alt_links_html(g)}"
            tooltip = g['name']
        elif style == 'layers':
            fill_color, fill_opacity = get_marker_style_layers(g)
            radius = max(5, math.log(members) * 2)
            popup = folium.Popup(build_popup_html(g), max_width=300)
            tooltip = f"{g['name']} ({int(members)} members)"
        elif style == 'inactive':
            fill_color, fill_opacity = get_marker_style_inactive(g)
            radius = max(5, math.log(members) * 2)
            popup = folium.Popup(build_popup_html(g), max_width=300)
            tooltip = f"{g['name']} ({int(members)} members)"
        else:
            raise ValueError(f"Unknown style: {style}")

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

    # Create a map with given style
    def create_map(groups, style='orange'):
        from collections import defaultdict

        world_map = folium.Map(location=[30, 0], zoom_start=2)

        coord_groups = defaultdict(list)
        for g in groups:
            if pd.isna(g.get('lat')) or pd.isna(g.get('lon')):
                continue
            key = coord_key(g['lat'], g['lon'])
            coord_groups[key].append(g)

        for key, group_list in coord_groups.items():
            if len(group_list) == 1:
                create_marker(group_list[0], style=style).add_to(world_map)
            else:
                cluster = MarkerCluster(
                    options={
                        'spiderfyOnMaxZoom': True,
                        'disableClusteringAtZoom': 12
                    }
                ).add_to(world_map)
                for g in group_list:
                    create_marker(g, style=style).add_to(cluster)

        return world_map

    print("✓ Helper functions loaded")
    return (create_map,)


@app.cell
def _(mo):
    mo.md("""
    ## World Map (Simple)

    Basic orange markers showing all PyData groups.
    """)
    return


@app.cell
def _(create_map, groups):
    # Create and display simple orange map
    world_map = create_map(groups, style='orange')
    world_map.save('pydata_world_map.html')
    print("✓ Saved pydata_world_map.html")
    world_map
    return


@app.cell
def _(mo):
    mo.md("""
    ## World Map (Activity Layers)

    - **Green** = Has upcoming events
    - **Blue** = No upcoming events (opacity fades with time since last event)
    """)
    return


@app.cell
def _(create_map, groups):
    # Create and display activity-styled map
    layers_map = create_map(groups, style='layers')
    layers_map.save('pydata_world_map_layers.html')
    print("✓ Saved pydata_world_map_layers.html")
    layers_map
    return


@app.cell
def _(mo):
    mo.md("""
    ## World Map (Inactive Highlighted)

    - **Faint Blue** = Active (has upcoming events OR last event < 50 days ago)
    - **Red** = Inactive (brightness increases with inactivity)
    """)
    return


@app.cell
def _(create_map, groups):
    # Create and display inactive-highlighted map
    inactive_map = create_map(groups, style='inactive')
    inactive_map.save('pydata_world_map_inactive.html')
    print("✓ Saved pydata_world_map_inactive.html")
    inactive_map
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary Statistics
    """)
    return


@app.cell
def _(df):
    # Summary statistics
    _total = len(df)
    _with_upcoming = df['has_upcoming_events'].fillna(False).astype(bool).sum()
    _never_had_events = (df['past_events_count'].isna() | (df['past_events_count'] == 0)).sum()
    _has_upcoming_bool = df['has_upcoming_events'].fillna(False).astype(bool)
    _inactive_50_days = ((df['days_since_last_event'] >= 50) | df['days_since_last_event'].isna()) & ~_has_upcoming_bool

    print(f"Total groups: {_total}")
    print(f"With upcoming events: {int(_with_upcoming)}")
    print(f"Without upcoming events: {_total - int(_with_upcoming)}")
    print(f"Inactive (>50 days, no upcoming): {_inactive_50_days.sum()}")
    print(f"Never had events: {_never_had_events}")

    # Top 10 most active
    print("\nTop 10 by past events:")
    df.nlargest(10, 'past_events_count')[['name', 'city', 'past_events_count', 'members']]
    return


@app.cell
def _(df):
    # Most recently active
    print("Most recently active (by days since last event):")
    df[df['days_since_last_event'].notna()].nsmallest(10, 'days_since_last_event')[['name', 'city', 'days_since_last_event', 'has_upcoming_events']]
    return


@app.cell
def _(df):
    # Most inactive
    print("Most inactive (by days since last event):")
    df[df['days_since_last_event'].notna()].nlargest(10, 'days_since_last_event')[['name', 'city', 'days_since_last_event', 'has_upcoming_events']]
    return


@app.cell
def _(mo):
    mo.md(r"""
    # `meetups by` Country
    print("Most inactive (by days since last event):")
    df[df['days_since_last_event'].notna()].nlargest(10, 'days_since_last_event')[['name', 'city', 'days_since_last_event', 'has_upcoming_events']]
    """)
    return


@app.cell
def _(df):
    print("Total Meetups per Country")
    df['country'].value_counts().rename_axis('country').reset_index(name='total')
    return


if __name__ == "__main__":
    app.run()
