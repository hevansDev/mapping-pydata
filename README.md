# Mapping PyData

I created this project out of a desire for a better map of the international PyData community than the [one available on Meetup](https://www.meetup.com/pro/pydata/).

This repo consists of three main parts:

- [PyDataMap.py](./PyDataMap.py) a script which scrapes Meetup.com for group and event data, populates the [geocode_cache.json](./geocode_cache.json) with each group and it's location based on the group name itself (due to issues with the city field in Meetup), updates [pydata_groups.csv](./pydata_groups.csv) which stores data about upcoming and past events in aggregate by group name, and then produces static versions of the maps. This script is scheduled to run daily.

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
