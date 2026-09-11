// Local preview only: read native Messages sounds from this Mac, never bundle
// their source recordings in the repository. Override paths for licensed assets.
import {existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const story=JSON.parse(readFileSync(path.join(root,'src/trade-demo.json'),'utf8'));
const rate=48000,channels=2,length=Math.round(story.durationInFrames/story.fps*rate);
const paths={
  sent:process.env.IMESSAGE_SENT_SOUND||'/System/Library/PrivateFrameworks/IMDaemonCore.framework/Versions/A/Resources/Sent Message.aiff',
  received:process.env.IMESSAGE_RECEIVED_SOUND||'/System/Library/PrivateFrameworks/ToneLibrary.framework/Versions/A/Resources/AlertTones/ReceivedMessage.caf',
};
const sounds=Object.fromEntries(Object.entries(paths).map(([kind,file])=>{
  if(!existsSync(file))throw new Error(`Native ${kind} sound unavailable: ${file}. Supply IMESSAGE_${kind.toUpperCase()}_SOUND with a permitted recording.`);
  const result=spawnSync('ffmpeg',['-v','error','-i',file,'-f','f32le','-ar',String(rate),'-ac',String(channels),'pipe:1'],{maxBuffer:10*1024*1024});
  if(result.error||result.status!==0)throw new Error(result.error?.message||result.stderr.toString());
  const pcm=new Float32Array(result.stdout.length/4);
  for(let i=0;i<pcm.length;i++)pcm[i]=result.stdout.readFloatLE(i*4);
  return [kind,pcm];
}));
const samples=new Float64Array(length*channels),events=[];
for(const message of story.messages){
  const kind=message.who==='Drew'?'sent':'received',sound=sounds[kind];
  const start=Math.round(message.at/story.fps*rate)*channels;
  if(start+sound.length>samples.length)throw new Error('Sound would be cut off at end of film');
  for(let i=0;i<sound.length;i++)samples[start+i]+=sound[i];
  events.push({frame:message.at,seconds:message.at/story.fps,kind,duration:sound.length/channels/rate});
}
let peak=0;
for(const value of samples)peak=Math.max(peak,Math.abs(value));
const gain=peak>0?Math.min(0.72,0.5/peak):1; // Leave at least 6 dB of peak headroom.
const wav=Buffer.alloc(44+samples.length*2);
wav.write('RIFF',0);wav.writeUInt32LE(36+samples.length*2,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);
wav.writeUInt16LE(1,20);wav.writeUInt16LE(channels,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*channels*2,28);
wav.writeUInt16LE(channels*2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(samples.length*2,40);
for(let i=0;i<samples.length;i++)wav.writeInt16LE(Math.round(samples[i]*gain*32767),44+i*2);
mkdirSync(path.join(root,'public/audio'),{recursive:true});
mkdirSync(path.join(root,'out'),{recursive:true});
writeFileSync(path.join(root,'public/audio/trade-imessage.wav'),wav);
writeFileSync(path.join(root,'out/trade-v3-audio-report.json'),JSON.stringify({
  durationSeconds:length/rate,sampleRate:rate,channels,peakDbFS:20*Math.log10(peak*gain),
  gain,events,source:'Native macOS Messages recordings; local preview, no music or synthetic effects',
},null,2)+'\n');
console.log(`Created ${length/rate}s native Messages track: ${events.length} arrivals, peak ${(20*Math.log10(peak*gain)).toFixed(2)} dBFS, silence between events.`);
