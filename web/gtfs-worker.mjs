import {halifaxDecode,stopPredictions} from './gtfs-realtime.mjs';
self.addEventListener('message',({data})=>{try{const decoded=halifaxDecode(new Uint8Array(data.bytes),data.feed);self.postMessage({id:data.id,data:stopPredictions(decoded,data.stop)})}catch{self.postMessage({id:data.id,error:'The live source could not be decoded. Scheduled times remain available.'})}});
