import {bundle} from '@remotion/bundler';
import {openBrowser,renderMedia,renderStill,selectComposition} from '@remotion/renderer';
import {existsSync,mkdirSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(root);
const mode=process.argv[2]||'video';
if(!['video','feed','stills','clean-video','clean-feed','clean-stills','trade-video','trade-feed','trade-stills'].includes(mode))throw new Error(`Unknown mode: ${mode}`);
const clean=mode.startsWith('clean-');
const trade=mode.startsWith('trade-');
const stills=mode.endsWith('stills');
const out=path.join(root,'out');mkdirSync(out,{recursive:true});
const macChrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const executable=process.env.REMOTION_BROWSER_EXECUTABLE||(existsSync(macChrome)?macChrome:undefined);
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts'),outDir:path.join(root,'.bundle')});
const browser=await openBrowser('chrome',{browserExecutable:executable});
try {
  const ids=trade?(stills?['SchefterTradePortrait','SchefterTradeFeed']:[mode==='trade-feed'?'SchefterTradeFeed':'SchefterTradePortrait']):
    clean?(stills?['SchefterCleanPortrait','SchefterCleanFeed']:[mode==='clean-feed'?'SchefterCleanFeed':'SchefterCleanPortrait']):
    (stills?['SchefterPortrait','SchefterFeed']:[mode==='feed'?'SchefterFeed':'SchefterPortrait']);
  for(const id of ids){
    const composition=await selectComposition({serveUrl,id,puppeteerInstance:browser});
    if(stills){
      for(const frame of trade?[0,75,210,350,510,660,735]:clean?[0,100,330,530,710,900,1140]:[85,240,440,660,800,1050,1160,1400,1550]){
        await renderStill({serveUrl,composition,puppeteerInstance:browser,frame,
          output:path.join(out,`${id}-${frame}.png`),imageFormat:'png'});
        console.log(`${id}: frame ${frame}`);
      }
    }else{
      const outputLocation=path.join(out,trade?(id==='SchefterTradeFeed'?'schefter-bot-linkedin-trade-v3.mp4':'schefter-bot-vertical-trade-v3.mp4'):
        clean?(id==='SchefterCleanFeed'?'schefter-bot-linkedin-clean-v2.mp4':'schefter-bot-vertical-clean-v2.mp4'):
        (id==='SchefterFeed'?'schefter-bot-linkedin.mp4':'schefter-bot-vertical.mp4'));
      let last=-1;
      await renderMedia({serveUrl,composition,puppeteerInstance:browser,codec:'h264',audioCodec:'aac',
        crf:18,pixelFormat:'yuv420p',audioBitrate:'256k',concurrency:4,outputLocation,
        metadata:trade?{title:'Schefter Bot — 25-second illustrative trade demo',
          comment:'Fictional group chat, not Adam Schefter or an endorsement. Real trade code with mocked ESPN responses; no live trade. Photo: All-Pro Reels / Joe Glorioso, CC BY-SA 2.0, via Wikimedia Commons; circular crop. Native macOS Messages sounds used in local preview.',
          copyright:'Photo and visual adaptation: CC BY-SA 2.0 (https://creativecommons.org/licenses/by-sa/2.0/). Apple system audio is excluded; no audio redistribution rights are asserted.'}:
          clean?{title:'Schefter Bot — unofficial illustrative group-chat demo',
          comment:'Fictional conversations. Not Adam Schefter, not endorsed by him. Contact photo: All-Pro Reels / Joe Glorioso, CC BY-SA 2.0, via Wikimedia Commons. Avatar displayed as a circular crop.',
          copyright:'Clean v2 video: CC BY-SA 2.0. https://creativecommons.org/licenses/by-sa/2.0/'}:undefined,
        onProgress:({progress})=>{const bucket=Math.floor(progress*10);if(bucket!==last){last=bucket;console.log(`Rendering ${id}: ${bucket*10}%`);}}});
      console.log(`Rendered ${outputLocation}`);
    }
  }
}finally{await browser.close({silent:true});}
