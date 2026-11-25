// Bounded GTFS-realtime decoder; official field schema: https://github.com/google/transit/blob/master/gtfs-realtime/proto/gtfs-realtime.proto
const halifaxFeeds = Object.freeze({vehicles:'Vehicle/VehiclePositions.pb',trips:'TripUpdate/TripUpdates.pb',alerts:'Alert/Alerts.pb'});
export function halifaxDecode(bytes, feed) {
  if (!(bytes instanceof Uint8Array) || bytes.length > 5000000 || !halifaxFeeds[feed]) throw new Error('Invalid GTFS-realtime input');
  let fieldsRead=0;
  function parse(buf,depth=0) {
    if(depth>10)throw new Error('GTFS nesting exceeds bound');
    const fields=new Map();let at=0;
    function vint(){let n=0,multiplier=1;for(let i=0;i<7;i++){if(at>=buf.length)throw new Error('Truncated GTFS varint');const b=buf[at++];n+=(b&127)*multiplier;if(!(b&128))return n;multiplier*=128}let big=BigInt(n),shift=49n;for(let i=7;i<10;i++){if(at>=buf.length)throw new Error('Truncated GTFS varint');const b=buf[at++];big|=BigInt(b&127)<<shift;if(!(b&128)){if(i===9&&b>1)throw new Error('Oversized GTFS integer');return big}shift+=7n}throw new Error('Oversized GTFS varint')}
    while(at<buf.length){if(++fieldsRead>1000000)throw new Error('Too many GTFS fields');const key=Number(vint()),field=key>>>3,wire=key&7;let value;if(!field||!Number.isSafeInteger(key)||key>4294967295)throw new Error('Invalid GTFS field');
      if(wire===0)value=vint();
      else if(wire===2){const length=Number(vint());if(!Number.isSafeInteger(length)||length<0||at+length>buf.length)throw new Error('Truncated GTFS message');value=buf.subarray(at,at+length);at+=length}
      else if(wire===5||wire===1){const length=wire===5?4:8;if(at+length>buf.length)throw new Error('Truncated GTFS fixed field');value=new DataView(buf.buffer,buf.byteOffset+at,length);at+=length}
      else throw new Error('Unsupported GTFS wire type');
      if(!fields.has(field))fields.set(field,[]);fields.get(field).push(value);
    }
    return fields;
  }
  const num=(f,k,signed=false)=>{const v=f.get(k)?.[0];if(typeof v!=='bigint'&&typeof v!=='number')return null;const n=typeof v==='number'?(signed?v|0:v):Number(signed?BigInt.asIntN(32,v):v);if(!Number.isSafeInteger(n))throw new Error('GTFS integer outside safe range');return n};
  const str=(f,k,max=512)=>{const v=f.get(k)?.[0];if(v===undefined)return '';if(!(v instanceof Uint8Array)||v.length>max*4)throw new Error('Invalid GTFS text');const s=new TextDecoder('utf-8',{fatal:true,ignoreBOM:false}).decode(v);if(s.length>max)throw new Error('GTFS text too long');return s};
  const sub=(f,k)=>{const v=f.get(k)?.[0];return v instanceof Uint8Array?parse(v,1):new Map()};
  const many=(f,k)=>{const a=f.get(k)||[];return a.map(v=>{if(!(v instanceof Uint8Array))throw new Error('Invalid GTFS child');return parse(v,1)})};
  const trip=f=>({id:str(f,1),date:str(f,3),route:str(f,5),relationship:num(f,4)??0});
  const event=f=>({time:num(f,2),delay:num(f,1,true),uncertainty:num(f,3,true)});
  const translated=f=>{const a=many(f,1);return str(a.find(t=>str(t,2).startsWith('en'))||a[0]||new Map(),1,16000)};
  const root=parse(bytes),header=sub(root,1),timestamp=num(header,3);
  if(!str(header,1)||num(header,2)===1||!timestamp||timestamp<946684800)throw new Error('Missing full-feed header or source timestamp');
  const entities=many(root,2);if(entities.length>12000)throw new Error('Too many GTFS entities');
  const rows=[];
  for(const entity of entities){if(num(entity,2))continue;const id=str(entity,1);if(!id)throw new Error('Missing GTFS entity ID');
    if(feed==='vehicles'&&entity.has(4)){const v=sub(entity,4),p=sub(v,2),d=sub(v,8),x=p.get(1)?.[0],y=p.get(2)?.[0];const lat=x instanceof DataView?x.getFloat32(0,true):null,lon=y instanceof DataView?y.getFloat32(0,true):null;
      if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)continue;
      rows.push({id,trip:trip(sub(v,1)),vehicle:str(d,2)||str(d,1),lat,lon,timestamp:num(v,5),stop:str(v,7)});
    } else if(feed==='trips'&&entity.has(3)){const v=sub(entity,3),t=trip(sub(v,1));if(!t.id)continue;
      rows.push({id,trip:t,timestamp:num(v,4),delay:num(v,5,true),stops:many(v,2).map(s=>({id:str(s,4),sequence:num(s,1),relationship:num(s,5)??0,arrival:event(sub(s,2)),departure:event(sub(s,3))}))});
    } else if(feed==='alerts'&&entity.has(5)){const a=sub(entity,5);rows.push({id,header:translated(sub(a,10)),description:translated(sub(a,11)),url:translated(sub(a,8)),periods:many(a,1).map(p=>({start:num(p,1),end:num(p,2)})),targets:many(a,5).map(t=>({route:str(t,2),stop:str(t,5),trip:trip(sub(t,4)).id})),cause:num(a,6),effect:num(a,7)})}
  }
  return {schema:1,feed,timestamp,version:str(header,4),entities:rows};
}

export function stopPredictions(data,stop){if(data.feed!=='trips')return data;return {...data,entities:data.entities.filter(e=>e.stops.some(s=>s.id===stop||!s.id)||e.trip.relationship===3||e.trip.relationship===7||e.delay!==null).map(e=>({...e,stops:e.stops.filter(s=>s.id===stop||!s.id)}))}}
