# Mapping PyData

I created this project out of a desire for a better map of the international PyData community than the [one available on Meetup](https://www.meetup.com/pro/pydata/).

This repo consists of three main parts:

- [PyDataMap.py](./PyDataMap.py) a script which scrapes Meetup.com for group and event data, populates the [geocode_cache.json](./geocode_cache.json) with each group and it's location based on the group name itself (due to issues with the city field in Meetup), updates [pydata_groups.csv](./pydata_groups.csv) which stores data about upcoming and past events in aggregate by group name, and then produces static versions of the maps. This script is scheduled to run daily. Groups that exist outside of Meetup (university clubs, conference series, Discord-only communities, groups that have moved to LinkedIn or their own website) can be added manually to [pydata_groups_manual.csv](./pydata_groups_manual.csv) and are merged into the maps at render time, or flagged directly on their existing row in [pydata_groups.csv](./pydata_groups.csv) via the `non_meetup` column — see "Non-Meetup groups" below.

- [MapsExplained.py](./) a [marimo](https://marimo.io/) notebook which can be used to create and explore the maps based on cached data in [geocode_cache.json](./geocode_cache.json) and [pydata_groups.csv](./pydata_groups.csv). This is intended to make it easy to create your own maps with this data. It also includes some example queries that can be made against the collected data i.e. top 10 most recent events.

- The maps (which are hosted via GitHub Pages): 
    - [World Map](https://hevansdev.github.io/mapping-pydata/pydata_world_map.html) a 1:1 recreation of the [map from Meetup](https://www.meetup.com/pro/pydata/) but with the location of Meetups corrected.
    - [World Map Active](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html) a map intended to make it easy to spot active PyData groups with a view towards attending / speaking at them.
    - [World Map Inactive](https://hevansdev.github.io/mapping-pydata/pydata_world_map_inactive.html) a map intended to draw attention to groups that haven't hosted an event in a while. You should consider volunteering for, speaking at, or sponsoring these groups to help them out.
    - [World Map Non-Pro](https://hevansdev.github.io/mapping-pydata/pydata_world_map_non_pro.html) a map of (independent?) PyData groups not included in the PyData Meetup Pro Network.

## FAQ

### Why is my group shown in the wrong location?

I am using [geopy](https://github.com/geopy/geopy) to geoencode group names to produce coordinates for each group. This is not a perfect process particularly as many groups deviate from the `PyData {location}` naming convention. To get around this I've added a series of aliases (or hints) to the geocode cache as shown below.

```json
"hints": {
    "PyMC Online Meetup": null,
    "PyData En Espa\u00f1ol Global.": null,
    "NEO AI - a PyData Group": "Cleveland, Ohio, USA",
    "PyData Ireland": "Dublin, Ireland",
    "PyData T&T": "Port of Spain, Trinidad and Tobago",
    "PyData Katsina": "Katsina, Nigeria",
    "Copenhagen Julia Meetup Group": "Copenhagen, Denmark",
    "PyData Boston - Cambridge": "Boston, Massachusetts, USA",
    "PyData Athens": "Athens, Greece",
    "Pydata Belgium": "Brussels, Belgium",
    ...
```

If your group is shown in the wrong location you can raise an issue or a PR with an alias for your group (or manually edit the latitude and longitude in the coords section of the cache file).

### How can I make versions of this map focused on a specific country or area?

The maps support URL hash navigation in the format `#zoom/lat/lng`. Simply append a hash to any map URL to set the initial view.

**Examples:**
- [The UK](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#6/54.5/-2): `https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#6/54.5/-2`
- [Europe](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/50/10): `https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/50/10`
- [Continental US](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/39/-98): `https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/39/-98`
- [India](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#5/20/78): `https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#5/20/78`
- [Australia](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/-25/135): `https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/-25/135`
- [Brazil](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/-15/-50): `https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html#4/-15/-50`

**To find coordinates for your own view:**
1. Open any of the maps
2. Pan and zoom to your desired view
3. The URL hash will automatically update as you move
4. Copy the URL to share

## Contributing

If you have an idea for how to improve this project please fork and raise PRs. [Contact Hugh](mailto:hughevans.dev) for all other inquiries.

### Adding a group that isn't on Meetup

If you know of a PyData community that doesn't have a Meetup page (a university club, a conference series, a Discord-only group, etc.), you can add it to [pydata_groups_manual.csv](./pydata_groups_manual.csv). The required columns are `name`, `url`, `city`, `country`, `lat`, and `lon`. Use the `source` column to describe where the group comes from — current values are `discord`, `conference`, and `university`. All other columns are optional and can be left blank.

### Non-Meetup groups

Meetup's "has upcoming events" / "days since last event" fields drive the **Active** and **Inactive** maps, but that data doesn't exist for groups that never had a Meetup page, or that have since moved off Meetup (e.g. to LinkedIn or their own website). Rather than showing those groups as misleadingly active or inactive, set the `non_meetup` column to `True` on their row and they'll render with the same neutral marker used on the simple [World Map](https://hevansdev.github.io/mapping-pydata/pydata_world_map.html) instead.

- Groups added via [pydata_groups_manual.csv](./pydata_groups_manual.csv) default to `non_meetup = True` automatically, since they have no Meetup activity data by definition.
- Groups that already have a row in [pydata_groups.csv](./pydata_groups.csv) (because they used to be tracked on Meetup) but have since moved elsewhere — update their `url` to the new LinkedIn/website page and set `non_meetup` to `True` on that same row. There's no need to move them to the manual CSV or duplicate the entry.

Any row that leaves `non_meetup` blank is treated as `False` (normal Meetup-tracked group).

### Cataloguing multiple links for the same group

A group only ever gets one row and one marker, but it can have more than one link worth keeping — a LinkedIn page it's also active on, a Discord, an old Meetup page it's moved off of, etc. Use the `alt_urls` column on its existing row in [pydata_groups.csv](./pydata_groups.csv) (or [pydata_groups_manual.csv](./pydata_groups_manual.csv)) for this rather than adding a second row, which would just create a duplicate marker at (roughly) the same spot.

**To add an alt link:** find the group's row and set `alt_urls` to the link, optionally labelled as `Label::https://example.com` — an unlabelled bare URL falls back to a label derived from its domain. To add more than one, separate them with `|`.

```
alt_urls: LinkedIn::https://www.linkedin.com/company/pydata-cyprus
```

```
alt_urls: LinkedIn::https://www.linkedin.com/company/pydata-cyprus|Discord::https://discord.gg/example
```

This is independent of `non_meetup` — a group can still be an active, Meetup-tracked group (`non_meetup` left blank/`False`) and simply have an extra link noted alongside it. Adding an `alt_urls` value doesn't change how it's styled on the Active/Inactive maps.

If a group has moved off Meetup entirely rather than just gaining a second presence, combine this with the [non-Meetup workflow](#non-meetup-groups) above — swap `url` to the new primary link, set `non_meetup` to `True`, and put the old Meetup link in `alt_urls` so it isn't lost:

```
url: https://www.linkedin.com/company/pydata-cyprus
non_meetup: True
alt_urls: Meetup (until 2026)::https://www.meetup.com/PyData-Cyprus
```

Either way, `alt_urls` renders as extra links in the marker popup on every map, underneath the group's primary link.
