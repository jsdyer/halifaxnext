export const ZONE='America/Halifax';
export function localDate(ms=Date.now()){return new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(ms)}
export function addDay(date,n){return new Date(Date.parse(date+'T12:00:00Z')+n*86400000).toISOString().slice(0,10)}
// GTFS service-day times are measured from local noon minus twelve hours.
export function serviceEpoch(date){const guess=Date.parse(date+'T12:00:00Z'),parts=new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,hourCycle:'h23',hour:'2-digit',minute:'2-digit'}).formatToParts(guess);const h=+parts.find(p=>p.type==='hour').value,m=+parts.find(p=>p.type==='minute').value;return guess+(12-h)*3600000-m*60000-12*3600000}
export function activeService(service,date){if(!service)return false;const exception=service.exceptions?.[date];if(exception)return exception===1;return date>=service.start&&date<=service.end&&service.days[new Date(date+'T12:00Z').getUTCDay()]===1}
export function matchingStops(index,query='',route=''){const terms=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);return index.stops.filter(s=>(!route||s.routes.includes(route))&&terms.every(t=>(s.name+' '+s.id+' '+s.code).toLocaleLowerCase().includes(t))).sort((a,b)=>Number(b.id===query)-Number(a.id===query)||a.name.localeCompare(b.name))}
export function feedState(result,now=Date.now(),maxAge=180){if(!result?.data||!Array.isArray(result.data.entities)||!Number.isFinite(result.data.timestamp))return 'unavailable';const age=now/1000-result.data.timestamp;return age>maxAge||age< -60?'stale':result.data.entities.length?'live':'empty'}
export function scheduled(index,stopRows,date,route=''){const epoch=serviceEpoch(date);return stopRows.filter(row=>row[3]!==1).flatMap(row=>{const [tripIndex,seconds,sequence]=row,t=index.trips[tripIndex];if(!t||route&&t[1]!==route||!activeService(index.services[t[2]],date))return [];return [{trip:t[0],route:t[1],headsign:t[3],date,sequence,scheduled:epoch+seconds*1000,time:epoch+seconds*1000,kind:'scheduled',seconds}]})}
export function withLive(rows,stop,result,now=Date.now(),maxAge=180){if(!['live','empty'].includes(feedState(result,now,maxAge)))return rows;return rows.map(row=>{const update=result.data.entities.find(e=>e.trip.id===row.trip&&(!e.trip.date||e.trip.date===row.date.replaceAll('-','')));if(!update)return row;
  const stopUpdate=r=>update.stops.find(s=>s.sequence!==null&&s.sequence!==undefined?s.sequence===r.sequence&&(!s.id||s.id===stop):s.id===stop);
  const s=stopUpdate(row);
  // An optional start_date must not apply one prediction to several service days.
  if(!update.trip.date){
    const candidates=rows.filter(r=>r.trip===row.trip&&r.sequence===row.sequence);
    if(candidates.length>1){const absolute=s?.departure?.time??s?.arrival?.time;
      if(!Number.isFinite(absolute))return row;
      const distances=candidates.map(r=>({r,d:Math.abs(r.scheduled-absolute*1000)})).sort((a,b)=>a.d-b.d);
      if(distances[0].d>12*3600000||distances[1]?.d===distances[0].d||distances[0].r.date!==row.date)return row;
    }
  }
  // Cancellation/deletion is retained in the fresh full feed even when announced earlier.
  if(update.trip.relationship===7)return {...row,kind:'deleted'};
  if(update.trip.relationship===3)return {...row,kind:'cancelled'};
  if(update.timestamp&&Math.abs(now/1000-update.timestamp)>maxAge)return row;
  if(s?.relationship===1)return {...row,kind:'skipped'};
  if(s?.relationship===2)return row;
  const event=s?.departure?.time!==null&&s?.departure?.time!==undefined||s?.departure?.delay!==null&&s?.departure?.delay!==undefined?s.departure:s?.arrival;
  const time=Number.isFinite(event?.time)?event.time*1000:Number.isFinite(event?.delay)?row.scheduled+event.delay*1000:Number.isFinite(update.delay)?row.scheduled+update.delay*1000:null;
  return time===null?row:{...row,time,kind:'live',uncertainty:event?.uncertainty??null};
})}
export function departures(index,stopRows,stop,date,route,live,now=Date.now(),maxAge=180){const today=localDate(now),days=date===today?[addDay(date,-1),date,addDay(date,1)]:[date];const rows=days.flatMap(d=>d>=index.start&&d<=index.through?scheduled(index,stopRows,d,route):[]);const updated=date===today?withLive(rows,stop,live,now,maxAge):rows;return updated.filter(r=>r.kind!=='deleted'&&(date!==today||(r.kind==='live'?r.time:r.scheduled)>=now-30000)).sort((a,b)=>a.time-b.time||a.route.localeCompare(b.route))}
export function activeAlerts(result,stop,routes,now=Date.now()){if(!result?.data?.entities)return [];const t=now/1000;return result.data.entities.filter(a=>(!a.periods.length||a.periods.some(p=>(p.start===null||p.start<=t)&&(p.end===null||p.end>t)))&&(!a.targets.length||a.targets.some(x=>(!x.stop||x.stop===stop)&&(!x.route||routes.includes(x.route)))))}
export function safeLink(value){try{const u=new URL(value);return u.protocol==='https:'?u.href:null}catch{return null}}
export function mercator(lat,lon,zoom){const n=2**zoom*256,clamped=Math.max(-85,Math.min(85,lat)),s=Math.sin(clamped*Math.PI/180);return {x:(lon+180)/360*n,y:(.5-Math.log((1+s)/(1-s))/(4*Math.PI))*n}}
