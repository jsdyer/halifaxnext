"""Render native city examples from the same public snapshots as the interactive tool."""
from html import escape
import json
import re

from search_metadata import add_search_metadata


from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def load_sources(stage):
    folder = stage / "data"
    path = folder / "index.json"
    index = json.loads(path.read_text())
    ferry_routes = {route["id"] for route in index["routes"] if route["type"] == 4}
    ferry_trips = {n for n, trip in enumerate(index["trips"]) if trip[1] in ferry_routes}
    # Some published terminal arrival rows allow pickup even though the trip ends there.
    # Use the final sequence in the whole trip, independent of route headsign or stop numbering.
    final = {}
    for shard in folder.glob("stops-*.json"):
        for rows in json.loads(shard.read_text())["stops"].values():
            for trip, _, seq, _ in rows:
                if trip in ferry_trips:
                    trip_id = index["trips"][trip][0]
                    final[trip_id] = max(seq, final.get(trip_id, -1))
    index["ferry_final_sequences"] = final
    path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return folder, index


def runs_on(service, day):
    iso = day.isoformat()
    if iso in service["exceptions"]:
        return service["exceptions"][iso] == 1
    weekday = (day.weekday() + 1) % 7  # Halifax GTFS index stores Sunday first.
    return service["start"] <= iso <= service["end"] and service["days"][weekday] == 1


def case_content(sources, stop_id):
    folder, index = sources
    state = {"preset-stop": stop_id}
    stop = next((row for row in index["stops"] if row["id"] == stop_id), None)
    if not stop:
        return state, "<p>This stop is absent from the published timetable. Search for its current name on the board.</p>"
    bucket = json.loads((folder / f"stops-{stop['bucket']}.json").read_text())
    names = {r["id"]: r["name"] for r in index["routes"]}
    start, through = (date.fromisoformat(index[key]) for key in ("start", "through"))
    reference = max(start, min(through, date.fromisoformat(index["retrieved"][:10])))
    detail = "<p>No scheduled departures were found within the example week.</p>"
    for offset in range(7):
        day = reference + timedelta(days=offset)
        if day > through:
            break
        departures = []
        for trip_number, seconds, sequence, pickup in bucket["stops"].get(stop_id, []):
            trip, route, service, _, _ = index["trips"][trip_number]
            if pickup != 1 and sequence != index["ferry_final_sequences"].get(trip) and runs_on(index["services"][service], day):
                departures.append((seconds, route))
        if departures:
            rows = []
            for route in sorted({r for _, r in departures}):
                times = sorted(t for t, r in departures if r == route)
                zone = ZoneInfo(index["zone"])
                anchor = datetime.combine(day, time(12), tzinfo=zone).timestamp() - 12 * 3600
                first = datetime.fromtimestamp(anchor + times[0], tz=zone)
                first_time = first.strftime("%H:%M") + (" next day" if first.date() > day else "")
                rows.append(f"<li>{escape(names[route])} · {len(times)} scheduled departures · first at {first_time}</li>")
            detail = f"<p>Scheduled departures on {day.isoformat()} in Halifax local time</p><ul>" + "".join(rows) + "</ul>"
            break
    details = f'<p><strong>{escape(stop["name"])}</strong> · stop {escape(stop_id)} · schedule {start} to {through}</p>'
    source = '<p><a href="#stop-title">Open the departures board</a> · <a href="https://www.halifax.ca/transportation/halifax-transit/ferry-service">Halifax Transit ferry service</a> · <a href="' + escape(index["source"], quote=True) + '">Official GTFS timetable (ZIP)</a></p>'
    return state, details + detail + source


CASES = [
    ('halifax-ferry-terminal', 'Halifax Ferry Terminal Departures', 'Compare the Alderney and Woodside ferries leaving downtown Halifax. Open the departures board for stop 1073 or check the local-time schedule example below.', '1073'),
    ('woodside-ferry', 'Woodside Ferry Departures to Halifax', 'Find the mainland-bound ferry from Woodside in Dartmouth. The board opens at ferry stop 1075, separate from the numbered bus bays.', '1075'),
]


def publish_pages(stage, template, tool):
    sources = load_sources(stage)
    entries = []
    cases = list(CASES)
    alderney = json.loads((stage / "use-case.json").read_text())
    cases.insert(0, (alderney["slug"], alderney["title"], alderney["description"], "1074"))
    for slug, title, description, *fields in cases:
        filename = slug + ".html"
        attributes, evidence = case_content(sources, *fields)
        attributes["use-case"] = slug
        state = " ".join(f'data-{key}="{escape(str(value), quote=True)}"' for key, value in attributes.items())
        page = template.replace("<body ", "<body " + state + " ", 1)
        page = re.sub(r"<title>.*?</title>", lambda _: "<title>" + escape(title) + " · CoolCode</title>", page, count=1)
        page = re.sub(r"(<h1[^>]*>).*?</h1>", lambda m: m[1] + escape(title) + "</h1>", page, count=1, flags=re.S)
        page = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m[1] + escape(description, quote=True), page, count=1)
        example = '<section class="place-evidence" aria-label="Published example"><p>' + escape(description) + '</p>' + evidence + '</section>'
        page = page.replace("<!-- place-example -->", example).replace("<!-- place-links -->", '<a href="./">Open ' + escape(tool["title"]) + '</a>')
        info = {**tool, "title": title, "description": description, "url": tool["url"] + filename}
        (stage / filename).write_text(add_search_metadata(page, info), encoding="utf-8")
        entries.append('<a href="./' + filename + '">' + escape(title) + '</a>')
    home = template.replace("<!-- place-example -->", "").replace("<!-- place-links -->", " ".join(entries))
    (stage / "index.html").write_text(add_search_metadata(home, tool), encoding="utf-8")
