import io, csv, zipfile, unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh import collect, seconds

def archive(extra=False):
    rows={
    'feed_info.txt':[['feed_start_date','feed_end_date','feed_version'],['20261124','20261129','test']],
    'routes.txt':[['route_id','route_short_name','route_long_name','route_type'],['1','1','One','3']],
    'stops.txt':[['stop_id','stop_code','stop_name','stop_lat','stop_lon','location_type'],['s','s','Main','44.65','-63.58','0']],
    'calendar.txt':[['service_id','start_date','end_date','sunday','monday','tuesday','wednesday','thursday','friday','saturday'],['d','20261124','20261129','0','1','1','1','1','1','0']],
    'calendar_dates.txt':[['service_id','date','exception_type'],['holiday','20261128','1']],
    'trips.txt':[['trip_id','route_id','service_id','trip_headsign','direction_id'],['t','1','d','Downtown','0']],
    'stop_times.txt':[['trip_id','stop_id','stop_sequence','departure_time','pickup_type'],['t','s','1','25:02:00','0']]}
    if extra:rows['stops.txt'].append(['future-stop','future-stop','New stop','44.66','-63.58','0']);rows['stop_times.txt'].append(['t','future-stop','2','25:03:00','0'])
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        for name,table in rows.items():
            s=io.StringIO();csv.writer(s).writerows(table);z.writestr(name,s.getvalue())
    return b.getvalue()

class CollectorTests(unittest.TestCase):
    def test_service_day_time_and_bad_times(self):
        self.assertEqual(seconds(' 25:02:00'),90120)
        for s in ['49:00:00','1:60:00','abc']:
            with self.assertRaises(ValueError):seconds(s)
    def test_expansion_without_starter_count_assumptions(self):
        for extra,count in [(False,1),(True,2)]:
            i,b=collect(archive(extra),{'bucket_count':2},'2026-11-25T01:00:00Z')
            self.assertEqual(len(i['stops']),count);self.assertEqual(i['services']['holiday']['exceptions']['2026-11-28'],1)
            self.assertEqual(sum(len(v) for bucket in b for v in bucket.values()),count)
    def test_bad_zip_does_not_produce_a_capture(self):
        with self.assertRaises(zipfile.BadZipFile):collect(b'broken',{})
