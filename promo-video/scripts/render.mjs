import {bundle} from '@remotion/bundler';
import {openBrowser,renderMedia,renderStill,selectComposition} from '@remotion/renderer';
import {existsSync,mkdirSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(root);
const mode=process.argv[2]||'video';
const out=path.join(root,'out');mkdirSync(out,{recursive:true});
const macChrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const executable=process.env.REMOTION_BROWSER_EXECUTABLE||(existsSync(macChrome)?macChrome:undefined);
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),outDir:path.join(root,'.bundle')});
const browser=await openBrowser('chrome',{browserExecutable:executable});
try {
  const ids=mode==='stills'?['SchefterPortrait','SchefterFeed']:[mode==='feed'?'SchefterFeed':'SchefterPortrait'];
  for(const id of ids){
    const composition=await selectComposition({serveUrl,id,puppeteerInstance:browser});
    if(mode==='stills'){
      for(const frame of [85,240,440,660,800,1050,1160,1400,1550]){
        await renderStill({serveUrl,composition,puppeteerInstance:browser,frame,
          output:path.join(out,`${id}-${frame}.png`),imageFormat:'png'});
        console.log(`${id}: frame ${frame}`);
      }
    }else{
      const outputLocation=path.join(out,id==='SchefterFeed'?'schefter-bot-linkedin.mp4':'schefter-bot-vertical.mp4');
      let last=-1;
      await renderMedia({serveUrl,composition,puppeteerInstance:browser,codec:'h264',audioCodec:'aac',
        crf:18,pixelFormat:'yuv420p',audioBitrate:'256k',concurrency:4,outputLocation,
        onProgress:({progress})=>{const bucket=Math.floor(progress*10);if(bucket!==last){last=bucket;console.log(`Rendering ${id}: ${bucket*10}%`);}}});
      console.log(`Rendered ${outputLocation}`);
    }
  }
}finally{await browser.close({silent:true});}
