# Halifax Next

[Find your next Halifax bus or ferry](https://coolcode.ca/halifaxnext/)

Search any passenger stop by its number or street, filter by route, inspect a service date, and see next departures plus the last scheduled trip. Ferry-terminal shortcuts include Alderney and Woodside. Optional device favourites survive refresh; the stop URL can also be bookmarked. A street map shows fresh vehicle positions when the agency provides them.

<!-- coolcode:guide -->
Search 8330 for Spring Garden Road before Dresden Row, or open a ferry-terminal shortcut. Live labels require a fresh source prediction; scheduled times are timetable entries, and a missing position does not mean a trip is cancelled. Last service uses the selected service date, including trips after midnight.
<!-- /coolcode:guide -->

The ferry board excludes a trip’s final stop even when the source permits pickup there. This keeps inbound terminal arrivals out of the departures list.

Direct examples

- [Halifax Ferry Terminal Departures](https://coolcode.ca/halifaxnext/halifax-ferry-terminal.html)
- [Woodside Ferry Departures to Halifax](https://coolcode.ca/halifaxnext/woodside-ferry.html)

## Sources, dates and limits

[Halifax Transit static GTFS](https://gtfs.halifax.ca/static/google_transit.zip) supplies every passenger stop, route, service calendar, exception date and stop time. The initial edition has 81 routes, 2,347 passenger stops, 9,239 trips and 324,165 stop times, including Alderney and Woodside ferries. Eleven parent-station records are omitted from boarding-stop search. Counts come from each edition, not a fixed list. The current edition ends November 29, 2026; **retrieving it again does not extend that validity**. Dates outside the edition never receive a fabricated timetable.

Official public real-time feeds:

- `https://gtfs.halifax.ca/realtime/Vehicle/VehiclePositions.pb`
- `https://gtfs.halifax.ca/realtime/TripUpdate/TripUpdates.pb`
- `https://gtfs.halifax.ca/realtime/Alert/Alerts.pb`

The shared CoolCode Worker at `https://coolcode-visitor-api.jeffdyer.workers.dev` exposes `GET /api/halifaxnext/realtime?feed=trips&stop=8330` and `feed=vehicles` / `feed=alerts`. It relays bounded GTFS-realtime messages from fixed official URLs and caches source captures for 30 seconds in Cloudflare Cache API. The `X-CoolCode-Fetched-At` response header records the gateway capture time. A dedicated browser worker decodes the protobuf, extracts the source timestamp and filters stop predictions; heavy parsing does not consume edge CPU. Older JSON gateway responses remain compatible. Valid empty, stale, missing and failed feeds stay distinct. The page polls once per minute while visible, with an explicit pause control to save mobile data. Predictions older than three minutes fall back to explicitly labelled timetable times. Cancelled trips, skipped stops, service dates, negative delays and sequence-only updates are handled. Timetable times use GTFS service-day semantics, including hours after 24:00 and calendar exceptions. The tool does not infer that a missing prediction is on time.

Data: [Halifax Open Data Licence](https://data-hrm.hub.arcgis.com/pages/open-data-licence). Independent information, with no affiliation or endorsement. Positions and predictions can be incomplete, especially ferry service. Check [Halifax Transit](https://www.halifax.ca/transportation/halifax-transit) for travel decisions. Street-map tiles are © OpenStreetMap contributors.

## Expand or customize

Edit `web/config.json`: `default_stop` is any passenger `stop_id` in the feed; `poll_seconds` (minimum30) and `stale_seconds` control polling and source age. Set `api` to the deployed gateway. Change `bucket_count` only with a refresh; all real stops remain searchable regardless of the number of buckets. Starter IDs never constrain visitor input. To use a new default, edit the file, run the offline checks below, then push to main. To refresh source coverage, run `python3 scripts/refresh.py`, inspect `web/status.json`, run the checks and commit `web/data/` plus status. Previously captured editions with different route/stop counts remain readable.

The schedule workflow runs daily at **08:17 UTC**, and via `workflow_dispatch`. It validates the complete source before replacing the saved edition and publishes only after application, build and browser checks pass. An expired source fails collection, preserving the prior publication. The separately allowlisted weekly schedule guard restores workflows disabled for inactivity; the independent Linux watchdog must also dispatch `.github/workflows/pages.yml`, monitor `status.json.retrieved` (36-hour maximum), and verify `status.json.through` has not expired. The coverage probe matters even when a fresh download succeeds. No API key is required.

## Development

```sh
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 tests/browser_smoke.py
```

The build is offline and content-versions local assets. Sixty-four compact stop-time buckets keep the browser from fetching the entire region's timetable for one stop. Source and build code use no runtime package dependency; Playwright is test-only. Pages uses GitHub Actions at the repository subpath, without a CNAME. Gateway tests live with the shared hub service; parser and instance-handling tests live in this repository.

## Privacy

Search, timetable selection and nearest-stop calculations run locally. Selecting a stop sends its public ID to CoolCode’s gateway. Optional geolocation stays in the browser. Only an explicit “Save stop” action stores IDs in `coolcode:halifaxnext:stops`; “Clear saved stops” removes them. No cookies or account are needed. Opening the map requests public tiles from OpenStreetMap. Aggregate tool visits exclude stop queries and coordinates.

## Ready-to-use example

[Alderney Ferry Departures to Halifax](https://coolcode.ca/halifaxnext/alderney-ferry.html) opens this scenario in the same tool. See departures from Alderney Landing in Dartmouth, stop 1074, toward downtown Halifax. The board uses Halifax local time. Each departure identifies the available schedule or live update.
