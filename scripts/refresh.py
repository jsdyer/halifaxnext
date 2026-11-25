#!/usr/bin/env python3
"""Validate official Halifax GTFS, then atomically replace a compact browser edition."""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://gtfs.halifax.ca/static/google_transit.zip'

def seconds(value):
    pieces = value.strip().split(':')
    if len(pieces) != 3:
        raise ValueError('Invalid GTFS time')
    h, m, s = map(int, pieces)
    if not 0 <= h <= 47 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError('GTFS time outside supported 48-hour service day')
    return h * 3600 + m * 60 + s

def iso(value):
    return datetime.strptime(value, '%Y%m%d').strftime('%Y-%m-%d')

def collect(raw, config, retrieved=None):
    if len(raw) > 25000000:
        raise ValueError('GTFS archive exceeds limit')
    z = zipfile.ZipFile(io.BytesIO(raw))
    def rows(name):
        info = z.getinfo(name)
        if info.file_size > 90000000:
            raise ValueError('GTFS table exceeds limit')
        return list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig')))
    info = rows('feed_info.txt')[0]
    start, through = iso(info['feed_start_date']), iso(info['feed_end_date'])
    if start > through:
        raise ValueError('Inverted feed coverage')
    routes = {r['route_id']: {'id':r['route_id'], 'short':r['route_short_name'], 'name':r['route_long_name'], 'type':int(r['route_type'])} for r in rows('routes.txt')}
    stops = {s['stop_id']: {'id':s['stop_id'],'code':s['stop_code'],'name':s['stop_name'],'lat':float(s['stop_lat']),'lon':float(s['stop_lon']),'routes':set()} for s in rows('stops.txt') if s.get('location_type','') in ('','0')}
    if not routes or not stops or len(stops)>20000 or len(routes)>1000:
        raise ValueError('Missing or excessive GTFS coverage')
    for s in stops.values():
        if not 42 <= s['lat'] <= 47 or not -67 <= s['lon'] <= -58:
            raise ValueError('Stop outside Halifax regional bounds')
    services = {r['service_id']: {'start':iso(r['start_date']),'end':iso(r['end_date']),'days':[int(r[d]) for d in ['sunday','monday','tuesday','wednesday','thursday','friday','saturday']],'exceptions':{}} for r in rows('calendar.txt')}
    for row in rows('calendar_dates.txt'):
        service=services.setdefault(row['service_id'],{'start':start,'end':through,'days':[0]*7,'exceptions':{}})
        service['exceptions'][iso(row['date'])]=int(row['exception_type'])
    trips=[]; indices={}
    for t in rows('trips.txt'):
        if t['route_id'] not in routes or t['service_id'] not in services:
            raise ValueError('Trip refers to missing route/service')
        indices[t['trip_id']]=len(trips)
        trips.append([t['trip_id'],t['route_id'],t['service_id'],t['trip_headsign'],t.get('direction_id','')])
    bucket_count=config.get('bucket_count',64)
    if not isinstance(bucket_count,int) or not 1<=bucket_count<=128:
        raise ValueError('bucket_count must be 1–128')
    buckets=[{} for _ in range(bucket_count)]; count=0
    # Stable lexical partition also handles valid nonnumeric future stop IDs.
    for i,s in enumerate(sorted(stops)):
        stops[s]['bucket']=i%bucket_count;buckets[i%bucket_count][s]=[]
    for t in rows('stop_times.txt'):
        stop=t['stop_id']; trip=indices.get(t['trip_id'])
        if stop not in stops or trip is None:
            raise ValueError('Stop time refers to missing trip or stop')
        seq=int(t['stop_sequence']); depart=seconds(t['departure_time'])
        if seq<0:raise ValueError('Negative stop sequence')
        stops[stop]['routes'].add(trips[trip][1])
        buckets[stops[stop]['bucket']][stop].append([trip,depart,seq,int(t.get('pickup_type') or 0)])
        count+=1
    if not trips or not count:
        raise ValueError('No scheduled trips')
    for s in stops.values():s['routes']=sorted(s['routes'])
    stamp=retrieved or datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    digest=hashlib.sha256(raw).hexdigest()
    index={'schema':1,'source':SOURCE,'retrieved':stamp,'start':start,'through':through,'edition':info.get('feed_version',''),'sha256':digest,'zone':'America/Halifax','routes':list(routes.values()),'stops':list(stops.values()),'services':services,'trips':trips,'stop_times':count}
    return index,buckets

def refresh(root=ROOT):
    config=json.loads((root/'web/config.json').read_text())
    request=urllib.request.Request(SOURCE,headers={'User-Agent':'CoolCode HalifaxNext/1.0 (+https://coolcode.ca/halifaxnext/)'})
    with urllib.request.urlopen(request,timeout=45) as response:
        raw=response.read(25000001)
    index,buckets=collect(raw,config)
    # A stale provider edition must not overwrite the last usable publication.
    today=datetime.now(timezone.utc).date().isoformat()
    if index['through']<today:raise ValueError('Provider schedule has expired; keeping the prior publication')
    with tempfile.TemporaryDirectory(dir=root,prefix='gtfs-') as tmp:
        target=Path(tmp)/'data';target.mkdir()
        (target/'index.json').write_text(json.dumps(index,separators=(',',':'))+'\n')
        for i,b in enumerate(buckets):
            (target/f'stops-{i}.json').write_text(json.dumps({'schema':1,'edition':index['sha256'],'stops':b},separators=(',',':'))+'\n')
        status={k:index[k] for k in ['retrieved','start','through','edition','sha256','stop_times']}
        status.update(routes=len(index['routes']),stops=len(index['stops']),trips=len(index['trips']))
        destination=root/'web/data'
        if destination.exists():shutil.rmtree(destination)
        shutil.move(str(target),destination)
        (root/'web/status.json').write_text(json.dumps(status,indent=2)+'\n')
    print(f"Validated {status['routes']} routes, {status['stops']} stops, {status['stop_times']} stop times; {index['start']} to {index['through']}")

if __name__=='__main__':refresh()
