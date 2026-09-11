// Original, restrained message sounds. No music and no copied Apple recordings.
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const timeline=JSON.parse(readFileSync(path.join(root,'src/clean-timeline.json'),'utf8'));
const rate=48000,duration=timeline.reduce((n,s)=>n+s.duration,0)/30,len=Math.round(rate*duration);
const samples=new Float64Array(len);
let seed=18467;
const noise=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2147483648-1;};
let from=0;
for(const scene of timeline){
  for(const [index,frame] of scene.messageFrames.entries()){
    const sent=scene.sentIndices.includes(index),start=Math.round((from+frame)/30*rate),length=Math.round((sent?.17:.13)*rate);
    let phase=0,low=0;
    for(let j=0;j<length&&start+j<len;j++){
      const t=j/rate,p=j/length;
      const frequency=sent?430+700*(1-p)**3:320+950*Math.exp(-t*39);
      phase+=Math.PI*2*frequency/rate;
      low=.75*low+.25*noise();
      const envelope=Math.min(1,t/.004)*Math.exp(-t*(sent?27:35))*(1-p)**2;
      samples[start+j]+=(Math.sin(phase)*.27+low*(sent?.18:.07))*envelope;
    }
  }
  from+=scene.duration;
}
const wav=Buffer.alloc(44+len*4);
wav.write('RIFF',0);wav.writeUInt32LE(36+len*4,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);
wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*4,28);
wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(len*4,40);
for(let i=0;i<len;i++){const value=Math.round(samples[i]*32767);wav.writeInt16LE(value,44+i*4);wav.writeInt16LE(value,46+i*4);}
mkdirSync(path.join(root,'public/audio'),{recursive:true});
writeFileSync(path.join(root,'public/audio/chat-sounds.wav'),wav);
console.log(`Created ${duration}s of message sounds: ${timeline.reduce((n,s)=>n+s.messageFrames.length,0)} arrivals; digital silence between them.`);
