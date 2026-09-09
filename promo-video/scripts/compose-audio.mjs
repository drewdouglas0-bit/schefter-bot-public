// Original score and UI sounds. No recordings, third-party music, or API calls.
import {mkdirSync, writeFileSync, unlinkSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const rate=48000,seconds=54,len=rate*seconds;
const left=new Float64Array(len),right=new Float64Array(len);
let seed=9302026;
const noise=()=>{seed=(Math.imul(1664525,seed)+1013904223)>>>0;return seed/2147483648-1;};
const tau=Math.PI*2;
const smooth=(x)=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
function sound(start,duration,gain,pan,fn) {
  const first=Math.floor(start*rate),count=Math.floor(duration*rate);
  const l=Math.sqrt((1-pan)*.5),r=Math.sqrt((1+pan)*.5);
  for(let j=0;j<count&&first+j<len;j++){
    if(first+j<0)continue;
    const v=fn(j/rate,j/count)*gain;
    left[first+j]+=v*l;right[first+j]+=v*r;
  }
}
function kick(t,gain=.65){sound(t,.48,gain,0,(s)=>Math.sin(tau*(48*s+4.8*(1-Math.exp(-s*37))))*Math.exp(-s*11)+noise()*.025*Math.exp(-s*220));}
function snare(t,gain=.15){let last=0; sound(t,.21,gain,.1,(s)=>{const n=noise();const hp=n-last;last=n;return (.64*hp+.4*Math.sin(tau*184*s))*Math.exp(-s*24);});}
function hat(t,gain=.06,pan=.3){let last=0;sound(t,.065,gain,pan,(s)=>{const n=noise();const hp=n-last;last=n;return hp*Math.exp(-s*76);});}
function bass(t,freq,duration=.41,gain=.17){sound(t,duration,gain,-.05,(s,p)=>{
  const wave=Math.sin(tau*freq*s)+.27*Math.sin(tau*freq*2*s)+.08*Math.sin(tau*freq*3*s);
  return wave*smooth(s/.008)*smooth((duration-s)/.06)*Math.exp(-p*2.1);
});}
function bell(t,freq,gain=.055,pan=-.3){sound(t,1.1,gain,pan,(s)=>
  (Math.sin(tau*freq*s)+.18*Math.sin(tau*freq*3*s))*Math.exp(-s*5.5)*smooth(s/.005));}
function swell(t,duration=1.2,gain=.045){let low=0;sound(t,duration,gain,0,(s,p)=>{
  low=.86*low+.14*noise();return low*Math.sin(Math.PI*p)**2;
});}
function ping(t,self=false){const f=self?783.99:1046.5;bell(t,f,.092,self?.3:-.35);bell(t+.085,f*1.25,.065,self?.2:-.2);}

// Four-bar D minor / Bb / F / C progression, restrained beat under readable chat.
const roots=[73.416,58.270,87.307,65.406];
const chords=[[293.665,349.228,440,523.251],[233.082,293.665,349.228,440],
  [261.626,349.228,440,523.251],[261.626,329.628,391.995,493.883]];
for(let t=0;t<seconds;t+=4){
  const ci=(Math.floor(t/4))%4;
  for(let n=0;n<4;n++) sound(t,4.3,.014,n%2?-.55:.55,(s,p)=>
    (Math.sin(tau*chords[ci][n]*s)+.12*Math.sin(tau*(chords[ci][n]*1.002)*s))*smooth(s/.3)*smooth((4.3-s)/.9));
}
kick(.08,.58);swell(2.7,1.3,.085);
for(let beat=8;beat<104;beat++){
  const t=beat*.5;
  const final=t>=48;const energy=t>=40&&t<48?1.15:.86;
  if(beat%8===0||beat%8===3||beat%8===4||(!final&&beat%8===6))kick(t,energy*.52);
  if(!final&&beat%4===2)snare(t,energy*.125);
  if(!final){hat(t,energy*(beat%2?.04:.062),beat%2?.4:-.35);if(beat%8===7)hat(t+.25,.03,.5);}
  if(beat%2===0)bass(t,roots[Math.floor(t/4)%4],.4,energy*.14);
  if(beat%2===1){const notes=chords[Math.floor(t/4)%4];bell(t+.25,notes[(beat>>1)%4]*2,.025,(beat%4-1.5)*.25);}
}
// Natural conversation arrivals, aligned exactly to the frame timeline.
for(const t of [5.467,13.267,19.967,29.533])ping(t);
for(const t of [8.433,17.533,38])ping(t,true);
for(const t of [4.333,10.367,24.1,26.333,36.033])bell(t,659.255,.05,-.3);
for(const t of [16.5,28.5,39.5,47.5])swell(t,.8,.08);
kick(48,.72);bell(48.1,587.33,.07,-.3);bell(48.25,880,.045,.3);bell(48.42,1174.66,.03,0);

// Modest stereo reflections and a gentle master fade. Keep peak below -2 dBFS.
const echo=Math.round(.1875*rate);
for(let i=len-1;i>=echo;i--){left[i]+=right[i-echo]*.075;right[i]+=left[i-echo]*.075;}
let peak=0;
for(let i=0;i<len;i++){
  const t=i/rate,fade=smooth(t/.035)*smooth((seconds-t)/1.3);
  left[i]=Math.tanh(left[i]*1.15)*fade;right[i]=Math.tanh(right[i]*1.15)*fade;
  peak=Math.max(peak,Math.abs(left[i]),Math.abs(right[i]));
}
const factor=.78/peak;
const data=Buffer.alloc(44+len*4);
data.write('RIFF',0);data.writeUInt32LE(36+len*4,4);data.write('WAVEfmt ',8);
data.writeUInt32LE(16,16);data.writeUInt16LE(1,20);data.writeUInt16LE(2,22);
data.writeUInt32LE(rate,24);data.writeUInt32LE(rate*4,28);data.writeUInt16LE(4,32);data.writeUInt16LE(16,34);
data.write('data',36);data.writeUInt32LE(len*4,40);
for(let i=0;i<len;i++){data.writeInt16LE(Math.round(left[i]*factor*32767),44+i*4);data.writeInt16LE(Math.round(right[i]*factor*32767),46+i*4);}
mkdirSync(path.join(root,'public/audio'),{recursive:true});
const rawPath=path.join(root,'public/audio/score-raw.wav');
writeFileSync(rawPath,data);
const master=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-i',rawPath,
  '-af','loudnorm=I=-16:TP=-1.5:LRA=9','-ar','48000','-c:a','pcm_s16le',
  path.join(root,'public/audio/score.wav')],{stdio:'inherit'});
if(master.error)throw new Error('Install FFmpeg to master the original score.',{cause:master.error});
if(master.status!==0)throw new Error(`Audio mastering failed: ${master.status}`);
unlinkSync(rawPath);
console.log('Composed original 54-second stereo score: public/audio/score.wav');
