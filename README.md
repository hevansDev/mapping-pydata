# Mapping PyData

I created this project out of a desire for a better map of the international PyData community than the [one available on Meetup](https://www.meetup.com/pro/pydata/). It's since grown to cover Python user groups more broadly through the [PSF's Meetup Pro Network](https://www.python.org/psf/meetup-pro/) and the [PyTexas Meetup Pro Network](https://www.meetup.com/pro/pytexas/) too (see "Networks" below).

This repo consists of three main parts:

- [PyDataMap.py](./PyDataMap.py) a script which scrapes Meetup.com for group and event data for each network in `NETWORKS` (currently PyData, the PSF Python Network, and PyTexas), populates the [geocode_cache.json](./geocode_cache.json) with each group's location (preferring the city Meetup reports for the group, falling back to parsing the group's name when the city is missing or a placeholder), updates each network's own CSV ([pydata_groups.csv](./pydata_groups.csv), [psf_groups.csv](./psf_groups.csv), [pytexas_groups.csv](./pytexas_groups.csv)) which stores data about upcoming and past events in aggregate by group name, and then produces static versions of the maps for each network plus a combined map across all of them. This script is scheduled to run daily. Groups that exist outside of Meetup (university clubs, conference series, Discord-only communities, groups that have moved to LinkedIn or their own website) can be added manually to the shared manual CSV ([groups_manual.csv](./groups_manual.csv)) and are merged into the maps at render time, or flagged directly on their existing row via the `non_meetup` column (see "Non-Meetup groups" below).

- [MapsExplained.py](./) a [marimo](https://marimo.io/) notebook which can be used to create and explore the PyData maps based on cached data in [geocode_cache.json](./geocode_cache.json) and [pydata_groups.csv](./pydata_groups.csv). This is intended to make it easy to create your own maps with this data. It also includes some example queries that can be made against the collected data i.e. top 10 most recent events.

- The maps (which are hosted via GitHub Pages), see the full index below.

## Map index

All maps are static HTML, regenerated daily by [PyDataMap.py](./PyDataMap.py), and hosted via GitHub Pages.

| Network | World map | Active | Inactive | Non-Pro |
| --- | --- | --- | --- | --- |
| PyData | [pydata_world_map.html](https://hevansdev.github.io/mapping-pydata/pydata_world_map.html) | [pydata_world_map_active.html](https://hevansdev.github.io/mapping-pydata/pydata_world_map_active.html) | [pydata_world_map_inactive.html](https://hevansdev.github.io/mapping-pydata/pydata_world_map_inactive.html) | [pydata_world_map_non_pro.html](https://hevansdev.github.io/mapping-pydata/pydata_world_map_non_pro.html) |
| PSF Python Network | [psf_world_map.html](https://hevansdev.github.io/mapping-pydata/psf_world_map.html) | [psf_world_map_active.html](https://hevansdev.github.io/mapping-pydata/psf_world_map_active.html) | [psf_world_map_inactive.html](https://hevansdev.github.io/mapping-pydata/psf_world_map_inactive.html) | [psf_world_map_non_pro.html](https://hevansdev.github.io/mapping-pydata/psf_world_map_non_pro.html) |
| PyTexas | [pytexas_world_map.html](https://hevansdev.github.io/mapping-pydata/pytexas_world_map.html) | [pytexas_world_map_active.html](https://hevansdev.github.io/mapping-pydata/pytexas_world_map_active.html) | [pytexas_world_map_inactive.html](https://hevansdev.github.io/mapping-pydata/pytexas_world_map_inactive.html) | [pytexas_world_map_non_pro.html](https://hevansdev.github.io/mapping-pydata/pytexas_world_map_non_pro.html) |
| Combined (all networks) | [all_python_world_map.html](https://hevansdev.github.io/mapping-pydata/all_python_world_map.html) | [all_python_world_map_active.html](https://hevansdev.github.io/mapping-pydata/all_python_world_map_active.html) | [all_python_world_map_inactive.html](https://hevansdev.github.io/mapping-pydata/all_python_world_map_inactive.html) | n/a |

- **World map** is a 1:1 recreation of the relevant Meetup Pro network page ([PyData](https://www.meetup.com/pro/pydata/), [PSF](https://www.meetup.com/pro/python-software-foundation-meetups/), [PyTexas](https://www.meetup.com/pro/pytexas/)) but with locations corrected.
- **Active** is intended to make it easy to spot active groups with a view towards attending / speaking at them.
- **Inactive** draws attention to groups that haven't hosted an event in a while. Consider volunteering for, speaking at, or sponsoring these groups to help them out.
- **Non-Pro** shows only groups outside that network's Meetup Pro network (manually-added groups, see "Non-Meetup groups" below). There's no combined Non-Pro map: "in the Pro network" is a per-network fact, so it doesn't have one unambiguous meaning across networks.
- **Combined** merges every group from every network onto one map. A group listed in more than one network still only gets a single marker (see "Networks" below).

Also in this repo but not part of the regularly-regenerated set above: [experiments/TourDePyData](./experiments/TourDePyData) contains a personal, one-off map tracking which UK/Ireland PyData groups Hugh has spoken at as part of his [Tour de PyData](https://hughevans.dev/the-tour-de-pydata-challenging-myself-to-speak-at-every-pydata-meetup-in-the-uk-and-ireland/) challenge.

## Networks

Meetup Pro networks (PyData, the PSF Python Network, PyTexas, and any future ones) are declared in the `NETWORKS` dict at the top of [PyDataMap.py](./PyDataMap.py): each entry just needs a Meetup Pro URL, a CSV filename, an optional manual CSV, a sanity-check minimum group count, and a filename prefix for its maps. Adding a new network means adding an entry there; the scraping, geocoding, enrichment, and map-generation code is shared and network-agnostic. The manual CSV is shared across all networks (see "Adding a group that isn't on Meetup" below) rather than being one-per-network, so most new networks only need the four other fields.

Each network gets its own CSV and its own set of maps, so nothing about the existing PyData maps/URLs changes. A `network` column on each row records which network's CSV a group came from (defaults to that network if the column is missing, for backwards compatibility with CSVs written before multi-network support).

For the combined maps, groups are merged by Meetup URL: a group present in more than one network's CSV becomes a single row with a `networks` field listing all of them (e.g. `pydata,psf`) rather than being duplicated into two markers at the same spot or silently dropped from one. Where a group is genuinely cross-listed, its popup on the combined map shows a small badge listing which networks it belongs to; single-network groups don't show this, since the map's own title already makes that obvious.

## FAQ

### Why is my group shown in the wrong location?

I am using [geopy](https://github.com/geopy/geopy) to geocode each group's location, preferring the city Meetup reports for the group and falling back to parsing a location out of the group name when the city is missing or a placeholder like "New group". This is not a perfect process, particularly for groups whose city doesn't resolve cleanly on its own (ambiguous names shared with other places, unusual formatting, etc.) or whose name-based fallback doesn't follow the `PyData {location}` convention. To get around this I've added a series of aliases (or hints) to the geocode cache as shown below.

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

If you know of a Python community that doesn't have a Meetup page (a university club, a conference series, a Discord-only group, etc.), you can add it to the shared manual CSV — [groups_manual.csv](./groups_manual.csv), used by every network (set via `manual_csv_file` in `NETWORKS`). The required columns are `name`, `url`, `city`, `country`, `lat`, `lon`, and `network` (which network the group belongs to, e.g. `pydata` — use a comma-separated list like `pydata,psf` for a group that should appear on more than one network's maps). Use the `source` column to describe where the group comes from (current values are `discord`, `conference`, `university`, `github`, and `pyladies.com` — the last covers PyLadies chapters listed on [pyladies.com/locations](https://pyladies.com/locations/) that aren't part of the PSF Meetup Pro network). All other columns are optional and can be left blank. Adding a manual group for a future network just means using that network's key in the `network` column; no new file is needed.

### Non-Meetup groups

Meetup's "has upcoming events" / "days since last event" fields drive the **Active** and **Inactive** maps, but that data doesn't exist for groups that never had a Meetup page, or that have since moved off Meetup (e.g. to LinkedIn or their own website). Rather than showing those groups as misleadingly active or inactive, set the `non_meetup` column to `True` on their row and they'll render with the same neutral marker used on the simple [World Map](https://hevansdev.github.io/mapping-pydata/pydata_world_map.html) instead.

- Groups added via the shared manual CSV ([groups_manual.csv](./groups_manual.csv)) default to `non_meetup = True` automatically, since they have no Meetup activity data by definition.
- Groups that already have a row in [pydata_groups.csv](./pydata_groups.csv) (because they used to be tracked on Meetup) but have since moved elsewhere: update their `url` to the new LinkedIn/website page and set `non_meetup` to `True` on that same row. There's no need to move them to the manual CSV or duplicate the entry.

Any row that leaves `non_meetup` blank is treated as `False` (normal Meetup-tracked group).

### Cataloguing multiple links for the same group

A group only ever gets one row and one marker, but it can have more than one link worth keeping: a LinkedIn page it's also active on, a Discord, an old Meetup page it's moved off of, etc. Use the `alt_urls` column on its existing row in its network's CSV (e.g. [pydata_groups.csv](./pydata_groups.csv)) or in [groups_manual.csv](./groups_manual.csv) for this rather than adding a second row, which would just create a duplicate marker at (roughly) the same spot.

**To add an alt link:** find the group's row and set `alt_urls` to the link, optionally labelled as `Label::https://example.com`. An unlabelled bare URL falls back to a label derived from its domain. To add more than one, separate them with `|`.

```
alt_urls: LinkedIn::https://www.linkedin.com/company/pydata-cyprus
```

```
alt_urls: LinkedIn::https://www.linkedin.com/company/pydata-cyprus|Discord::https://discord.gg/example
```

This is independent of `non_meetup`: a group can still be an active, Meetup-tracked group (`non_meetup` left blank/`False`) and simply have an extra link noted alongside it. Adding an `alt_urls` value doesn't change how it's styled on the Active/Inactive maps.

If a group has moved off Meetup entirely rather than just gaining a second presence, combine this with the [non-Meetup workflow](#non-meetup-groups) above: swap `url` to the new primary link, set `non_meetup` to `True`, and put the old Meetup link in `alt_urls` so it isn't lost:

```
url: https://www.linkedin.com/company/pydata-cyprus
non_meetup: True
alt_urls: Meetup (until 2026)::https://www.meetup.com/PyData-Cyprus
```

Either way, `alt_urls` renders as extra links in the marker popup on every map, underneath the group's primary link.
