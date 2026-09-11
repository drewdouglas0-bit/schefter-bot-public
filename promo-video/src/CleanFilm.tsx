import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, Img, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {unit} from './design';
import {days} from './story';
import timeline from './clean-timeline.json';
import tradeDemo from './trade-demo.json';
import type {Message} from './ChatPhone';

// Rebuilt interface; no footage or assets taken from the reference film.
// The saved contact name is illustrative. This is an unofficial bot, not Adam.
const BG='#efeeeb', SCREEN='#fafafa', BLUE='#32a3eb', GRAY='#e3e3e5';
const WIDTH=400, HEIGHT=840, BODY_TOP=154, BODY_HEIGHT=587;
export const CLEAN_DURATION=timeline.reduce((sum,scene)=>sum+scene.duration,0);
export const TRADE_DURATION=tradeDemo.durationInFrames;
const normal=(text:string)=>text.replace(/\s+/g,' ').trim();
const reflow:Record<string,string[]>={
  '0-1':["Waiver claim: Jake's Rebuild gets",'RB Jaylen Warren (PIT) for $31','of FAAB.'],
  '0-4':["Jake's Rebuild released RB Jerome",'Ford in a separate move, per ESPN.'],
  '1-1':['Sunday Scaries leads Jake\'s','Rebuild, 128.4-96.2 in Week 1,','per ESPN.'],
  '2-0':['📋 WEEK 1 FINAL','','Sunday Scaries def. Jake\'s Rebuild,','128.4-96.2','',
    'High scorer: Sunday Scaries (128.4)','',"Jake's Rebuild left 42.7 points on",'the bench, including WR Chris',
    'Olave (NO) at 28.1, league records','show.'],
};
type Row={at:number;y:number;height:number;date?:string;message?:Message;key:string};
type Layout={rows:Row[];sceneStarts:number[];times:string[];audioPath:string};
const rows:Row[]=[];
const sceneStarts:number[]=[];
let sceneStart=0,cursor=0;
for(const [sceneIndex,scene] of timeline.entries()){
  sceneStarts.push(sceneStart);
  if(scene.messageFrames.length!==days[sceneIndex].messages.length)throw new Error('Chat timing does not match source');
  const dateHeight=sceneIndex===0?78:53;
  rows.push({at:sceneStart,y:cursor,height:dateHeight,date:days[sceneIndex].date,key:`date-${sceneIndex}`});
  cursor+=dateHeight;
  for(const [messageIndex,source] of days[sceneIndex].messages.entries()){
    const lines=reflow[`${sceneIndex}-${messageIndex}`]??source.lines;
    if(normal(lines.join(' '))!==normal(source.lines.join(' ')))throw new Error('Clean layout changed the demo copy');
    const message={...source,lines,at:sceneStart+scene.messageFrames[messageIndex],reactionAt:undefined,reaction:undefined};
    const height=lines.length*18+18+(source.who==='Drew'?0:16)+17;
    rows.push({at:message.at,y:cursor,height,message,key:`message-${sceneIndex}-${messageIndex}`});
    cursor+=height;
  }
  sceneStart+=scene.duration;
}
const cleanLayout:Layout={rows,sceneStarts,times:days.map(day=>day.time),audioPath:'audio/chat-sounds.wav'};
const tradeRows:Row[]=[{at:0,y:0,height:78,date:tradeDemo.date,key:'trade-date'}];
let tradeCursor=78,previousFrame=-1;
const isPerson=(who:string):who is Message['who']=>['Jake','Maya','Drew','Schefter Bot'].includes(who);
for(const [index,source] of tradeDemo.messages.entries()){
  if(!isPerson(source.who))throw new Error(`Unknown trade participant: ${source.who}`);
  if(source.at<=previousFrame||source.at>=TRADE_DURATION)throw new Error('Invalid trade timeline');
  const message:Message={...source,who:source.who};
  const height=message.lines.length*18+18+(message.who==='Drew'?0:16)+17;
  tradeRows.push({at:message.at,y:tradeCursor,height,message,key:`trade-message-${index}`});
  tradeCursor+=height;
  previousFrame=message.at;
}
const tradeLayout:Layout={rows:tradeRows,sceneStarts:[0],times:[tradeDemo.time],audioPath:'audio/trade-imessage.wav'};

const Glyph:React.FC<{kind:'back'|'video'|'wave'|'plus'|'chevron';size?:number}>=({kind,size=24})=><svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
  {kind==='back'?<path d="M15 4l-8 8 8 8"/>:kind==='video'?<><rect x="2" y="5" width="13" height="14" rx="3"/><path d="M15 10l7-4v12l-7-4"/></>:kind==='plus'?<path d="M12 3v18M3 12h18"/>:kind==='chevron'?<path d="M9 5l5 7-5 7"/>:<path d="M3 10v4M7 6v12M12 3v18M17 6v12M21 10v4"/>}
</svg>;

const Avatar:React.FC<{who:Message['who'];size?:number}>=({who,size=22})=>{
  const initials={Jake:'JK',Maya:'MP',Drew:'DS','Schefter Bot':'AS'};
  return <div style={{width:size,height:size,borderRadius:'50%',overflow:'hidden',flexShrink:0,
    background:'linear-gradient(#b6b6b9,#9e9ea2)',display:'flex',alignItems:'center',justifyContent:'center',
    fontSize:size*.34,fontWeight:500,color:'white'}}>
    {who==='Schefter Bot'?<Img src={staticFile('images/adam-schefter.jpg')} alt="Adam Schefter contact photo"
      style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'50% 18%'}}/>:initials[who]}
  </div>;
};

const Bubble:React.FC<{row:Row;frame:number}>=({row,frame})=>{
  const m=row.message!;
  const self=m.who==='Drew',p=unit(frame,m.at,9);
  return <div data-message={m.who} style={{position:'absolute',top:row.y,left:0,right:0,height:row.height,
    display:'flex',alignItems:'flex-end',justifyContent:self?'flex-end':'flex-start',gap:5,paddingBottom:17,
    opacity:unit(frame,m.at,4),transform:`translateY(${(1-p)*8}px)`}}>
    {!self?<div style={{marginBottom:0}}><Avatar who={m.who}/></div>:null}
    <div style={{position:'relative',maxWidth:306}}>
      {!self?<div style={{fontSize:10,color:'#8b8b90',height:16,marginLeft:10}}>{m.who==='Schefter Bot'?'Adam Schefter':m.who}</div>:null}
      <div style={{position:'relative',padding:'8px 11px 10px',borderRadius:17,background:self?BLUE:GRAY,
        color:self?'#fff':'#101011',fontSize:14.4,lineHeight:'18px',letterSpacing:'-.023em'}}>
        <svg width="13" height="15" viewBox="0 0 13 15" style={{position:'absolute',bottom:-1,[self?'right':'left']:-5,transform:self?undefined:'scaleX(-1)'}}>
          <path d="M0 0H9C7 5 7 10 13 15C5 13 1 10 0 7Z" fill={self?BLUE:GRAY}/>
        </svg>
        <div style={{position:'relative'}}>{m.lines.map((line,index)=><div data-line key={index} style={{height:18,whiteSpace:'pre'}}>{line||' '}</div>)}</div>
      </div>
    </div>
  </div>;
};

const ReferencePhone:React.FC<{frame:number;layout:Layout}>=({frame,layout})=>{
  const {rows,sceneStarts,times}=layout;
  let scroll=0,previous=0;
  for(const row of rows){
    const target=Math.max(0,row.y+row.height-BODY_HEIGHT+9);
    if(frame>=row.at)scroll+=(target-previous)*unit(frame,row.at,17);
    previous=target;
  }
  const scene=sceneStarts.filter(start=>frame>=start).length-1;
  const latest=rows.filter(row=>row.message&&frame>=row.at).at(-1);
  return <div style={{width:WIDTH,height:HEIGHT,borderRadius:65,padding:12,position:'relative',
    background:'#080808',boxShadow:'0 0 0 1.5px #73736f, inset 0 0 0 2.5px #252523'}}>
    {[{top:153,height:25},{top:210,height:46},{top:270,height:46}].map((button,index)=><div key={index} style={{position:'absolute',left:-4,width:3.5,borderRadius:2,background:'#555650',...button}}/>)}
    <div style={{position:'absolute',right:-4,top:230,width:3.5,height:72,borderRadius:2,background:'#555650'}}/>
    <div style={{height:'100%',borderRadius:53,background:SCREEN,position:'relative',overflow:'hidden'}}>
      <div style={{height:54,padding:'24px 41px 0',display:'flex',justifyContent:'space-between',fontSize:14.2,fontWeight:650,lineHeight:1}}>
        <span>{times[Math.max(0,scene)]}</span>
        <div style={{position:'absolute',top:18,left:128,width:118,height:33,borderRadius:22,background:'#000'}}/>
        <svg width="77" height="15" viewBox="0 0 77 15"><g fill="#111"><rect x="0" y="10" width="3" height="4" rx="1"/><rect x="5" y="7" width="3" height="7" rx="1"/><rect x="10" y="4" width="3" height="10" rx="1"/><rect x="15" y="1" width="3" height="13" rx="1"/><path d="M25 5Q33-1 41 5L39 7Q33 3 27 7ZM29 9Q33 6 37 9L33 13Z"/><rect x="49" y="1" width="25" height="13" rx="4" fill="#aaa"/><rect x="49" y="1" width="8" height="13" rx="4"/><rect x="75" y="5" width="2" height="5" rx="1" fill="#aaa"/></g><text x="62" y="11" textAnchor="middle" fontSize="11" fontWeight="650" fill="#fff">31</text></svg>
      </div>
      <div style={{height:100,position:'relative',display:'flex',alignItems:'center',flexDirection:'column'}}>
        <div style={{position:'absolute',left:18,top:7,width:40,height:40,borderRadius:30,border:'1px solid #e3e3e4',boxShadow:'inset 0 1px 2px white,0 2px 4px #00000004',display:'flex',alignItems:'center',justifyContent:'center'}}><Glyph kind="back" size={21}/></div>
        <div style={{height:53,width:65,position:'relative',marginTop:0}}>
          <div style={{position:'absolute',top:1,left:3,border:`2px solid ${SCREEN}`,borderRadius:30}}><Avatar who="Jake" size={30}/></div>
          <div style={{position:'absolute',top:1,right:1,border:`2px solid ${SCREEN}`,borderRadius:30}}><Avatar who="Maya" size={30}/></div>
          <div style={{position:'absolute',bottom:0,left:16,border:`2px solid ${SCREEN}`,borderRadius:30}}><Avatar who="Schefter Bot" size={34}/></div>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:2,height:29,padding:'0 10px 0 13px',borderRadius:22,border:'1px solid #dfdfe0',
          boxShadow:'inset 0 1px 2px white,0 2px 3px #00000003',fontSize:14.5,fontWeight:600,marginTop:3}}>
          Waiver Wire <span style={{color:'#aaa',display:'flex'}}><Glyph kind="chevron" size={13}/></span>
        </div>
        <div style={{position:'absolute',right:18,top:7,width:40,height:40,borderRadius:30,border:'1px solid #e3e3e4',boxShadow:'inset 0 1px 2px white,0 2px 4px #00000004',display:'flex',alignItems:'center',justifyContent:'center'}}><Glyph kind="video" size={24}/></div>
      </div>
      <div style={{position:'absolute',top:BODY_TOP,left:17,right:18,height:BODY_HEIGHT,overflow:'hidden'}}>
        <div style={{position:'relative',transform:`translateY(${-scroll}px)`}}>
          {rows.map(row=>frame<row.at?null:row.date?<div key={row.key} style={{position:'absolute',top:row.y,left:0,right:0,height:row.height,
            color:'#8c8c90',fontSize:10,lineHeight:'14px',textAlign:'center',paddingTop:row.y===0?0:24}}>
            {row.y===0?<><div>iMessage</div><div style={{fontSize:9.5,display:'flex',alignItems:'center',justifyContent:'center',gap:2}}>
              <svg width="6" height="9" viewBox="0 0 8 12" fill="currentColor"><rect x="1" y="5" width="6" height="6" rx="1"/><path d="M2 5V3a2 2 0 014 0v2" fill="none" stroke="currentColor" strokeWidth="1.2"/></svg>
              Encrypted</div></>:null}
            <div style={{fontWeight:600,marginTop:row.y===0?14:0}}>{row.date}</div>
          </div>:<Bubble key={row.key} row={row} frame={frame}/>)}
          {latest?.message?.who==='Drew'?<div style={{position:'absolute',top:latest.y+latest.height-12,right:10,color:'#8b8b90',fontSize:9.5,fontWeight:500}}>Delivered</div>:null}
        </div>
      </div>
      <div style={{position:'absolute',bottom:23,left:25,right:25,height:38,display:'flex',gap:9,alignItems:'center',background:SCREEN}}>
        <div style={{width:38,height:38,borderRadius:25,border:'1px solid #dddde0',boxShadow:'inset 0 1px 2px white,0 2px 2px #00000003',display:'flex',alignItems:'center',justifyContent:'center',color:'#252527'}}><Glyph kind="plus" size={25}/></div>
        <div style={{height:38,flex:1,display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 13px',border:'1px solid #dddde0',
          borderRadius:26,boxShadow:'inset 0 1px 2px white,0 2px 2px #00000003',fontSize:14,color:'#aaa'}}><span>iMessage</span><Glyph kind="wave" size={18}/></div>
      </div>
      <div style={{position:'absolute',bottom:6,left:126,width:124,height:4,borderRadius:5,background:'#0b0b0b'}}/>
    </div>
  </div>;
};

export const CleanFilm:React.FC<{variant?:'clean'|'trade'}>=({variant='clean'})=>{
  const frame=useCurrentFrame();
  const layout=variant==='trade'?tradeLayout:cleanLayout;
  const {width,height}=useVideoConfig();
  const scale=height===1920?2.08:1.47;
  const [handle]=useState(()=>delayRender('Load chat fallback font'));
  useEffect(()=>{document.fonts.load('400 14px Inter').then(()=>continueRender(handle)).catch(cancelRender);},[handle]);
  return <AbsoluteFill style={{background:BG,fontFamily:'-apple-system, BlinkMacSystemFont, Inter, sans-serif',color:'#111'}}>
    <style>{`@font-face{font-family:Inter;src:url('${staticFile('fonts/Inter.ttf')}') format('truetype');font-weight:100 900;font-display:block;}*{box-sizing:border-box;}`}</style>
    <Audio src={staticFile(layout.audioPath)}/>
    <div style={{position:'absolute',left:(width-WIDTH*scale)/2,top:(height-HEIGHT*scale)/2,transform:`scale(${scale})`,transformOrigin:'top left'}}>
      <ReferencePhone frame={frame} layout={layout}/>
    </div>
  </AbsoluteFill>;
};
