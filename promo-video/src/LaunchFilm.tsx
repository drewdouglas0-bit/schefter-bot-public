import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, Img, Sequence, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame} from 'remotion';
import {ChatPhone} from './ChatPhone';
import {C, CornerBrand, Display, Fonts, Icon, Mark, lerp, unit} from './design';
import {days, stages} from './story';

const Stadium:React.FC<{f:number;shade?:number}> = ({f,shade=.3}) => <AbsoluteFill style={{overflow:'hidden',background:C.dark}}>
  <Img src={staticFile('images/stadium.png')} style={{width:'100%',height:'100%',objectFit:'cover',
    transform:`scale(${1.04+f*.00011}) translateY(${-f*.025}px)`}}/>
  <AbsoluteFill style={{background:`linear-gradient(180deg,rgba(4,19,14,${shade+.17}),rgba(4,19,14,${shade*.4}) 52%,rgba(4,19,14,.88))`}}/>
  <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 20%,transparent 35%,#00150b77)',mixBlendMode:'multiply'}}/>
</AbsoluteFill>;

const Reveal:React.FC<React.PropsWithChildren<{f:number;at?:number;style?:React.CSSProperties}>> = ({f,at=0,children,style}) => {
  const p=unit(f,at,20);
  return <div style={{opacity:p,transform:`translateY(${lerp(35,0,p)}px)`,...style}}>{children}</div>;
};

const Intro:React.FC<{feed:boolean}> = ({feed}) => {
  const f=useCurrentFrame();
  return <AbsoluteFill style={{color:C.ivory}}>
    <Stadium f={f} shade={.15}/><CornerBrand light feed={feed}/>
    <div style={{position:'absolute',left:66,right:50,top:feed?250:435}}>
      <Reveal f={f} at={0}><div style={{fontSize:22,letterSpacing:4,fontWeight:600,color:C.lime,marginBottom:36}}>THE WAIT IS OVER.</div></Reveal>
      <Reveal f={f} at={5}><Display style={{fontSize:feed?170:183}}>FOOTBALL'S</Display></Reveal>
      <Reveal f={f} at={13}><Display style={{fontSize:feed?230:266,color:C.lime}}>BACK.</Display></Reveal>
      <Reveal f={f} at={45}><div style={{fontSize:feed?41:47,lineHeight:1.12,fontWeight:600,letterSpacing:-1.4,marginTop:36}}>So is the group chat.</div></Reveal>
    </div>
    <Reveal f={f} at={66} style={{position:'absolute',left:66,bottom:feed?120:178,display:'flex',alignItems:'center',gap:16}}>
      <span style={{width:9,height:9,background:C.lime,borderRadius:'50%',boxShadow:`0 0 22px ${C.lime}`}}/>
      <span style={{fontSize:22,letterSpacing:2}}>MEET YOUR LEAGUE'S NEWS DESK</span>
    </Reveal>
    <div style={{position:'absolute',bottom:0,left:0,height:6,width:`${unit(f,0,116)*100}%`,background:C.lime}}/>
  </AbsoluteFill>;
};

const activityLabel=(index:number,f:number)=>{
  if(index===0) {
    if(f<44)return 'ESPN league connected';
    if(f<191)return 'New waiver claim → group chat';
    if(f<278)return 'Mention received · checking transactions';
    return 'League data → sourced reply';
  }
  if(index===1) {
    if(f<89)return 'Mention received · checking matchups';
    return 'ESPN matchup data → group reply';
  }
  return f<211?'Weekly recap → automatically delivered':'Football talk stays in the group';
};

const ChatScene:React.FC<{index:number;feed:boolean}> = ({index,feed}) => {
  const f=useCurrentFrame();
  const stage=stages[index];
  const pop=unit(f,0,18);
  const scale=feed?1.46:1.88;
  return <AbsoluteFill style={{background:C.ivory,color:C.ink,overflow:'hidden'}}>
    <AbsoluteFill style={{background:'radial-gradient(ellipse at 65% 58%,#e3e9d9 0%,transparent 62%)'}}/>
    <svg viewBox="0 0 1080 1920" style={{position:'absolute',height:'100%',width:'100%',opacity:.055}}>
      {[0,1,2,3,4].map(i=><path key={i} d={`M-200 ${650+i*240}L1400 ${220+i*240}`} stroke={C.ink} strokeWidth="2"/>)}
      <circle cx="1040" cy="1670" r="550" fill="none" stroke={C.ink} strokeWidth="2"/>
    </svg>
    <CornerBrand feed={feed}/>
    <Reveal f={f} at={0} style={{position:'absolute',left:64,top:feed?225:137}}>
      <div style={{fontSize:feed?17:18,fontWeight:650,letterSpacing:2,color:C.green,marginBottom:feed?30:16}}>{feed?stage.kicker.replace(' / ',' /\n'):stage.kicker}</div>
      <Display style={{fontSize:feed?89:83,lineHeight:.99}}>{feed?stage.feedTitle.map(t=><div key={t}>{t}</div>):stage.title}</Display>
      {feed&&<div style={{fontSize:25,lineHeight:1.4,whiteSpace:'pre-line',marginTop:28,color:'#5d6c61'}}>{stage.side}</div>}
    </Reveal>
    <div style={{position:'absolute',top:feed?142:294,left:feed?450:164,transformOrigin:'top left',
      transform:`translateY(${lerp(36,0,pop)}px) scale(${scale*(.986+.014*pop)})`,opacity:pop}}>
      <ChatPhone day={days[index]} f={f} compact={feed}/>
    </div>
    <div style={{position:'absolute',left:feed?64:100,right:feed?665:100,top:feed?940:1801,
      display:'flex',alignItems:feed?'flex-start':'center',justifyContent:feed?'flex-start':'center',gap:10}}>
      <div style={{width:7,height:7,borderRadius:9,background:C.green,marginTop:feed?9:0,flexShrink:0,
        opacity:.5+.5*Math.sin(f*.11)**2}}/>
      <span style={{fontSize:feed?21:22,lineHeight:1.4,color:'#5b6d61'}}>{activityLabel(index,f)}</span>
    </div>
    <div style={{position:'absolute',bottom:feed?44:39,left:64,right:64,display:'flex',justifyContent:'space-between',alignItems:'center',color:'#7b847d',fontSize:feed?16:18}}>
      <span>Illustrative demo · fictional league events</span><span style={{letterSpacing:2}}>{index+1} / 3</span>
    </div>
    <div style={{position:'absolute',left:64,right:64,bottom:feed?24:18,height:3,display:'flex',gap:8}}>
      {[0,1,2].map(i=><div key={i} style={{flex:1,background:'#dbe0d5',overflow:'hidden'}}><div style={{height:'100%',background:C.green,
        width:`${i<index?100:i===index?Math.min(100,f/(stage.end-stage.start)*100):0}%`}}/></div>)}
    </div>
  </AbsoluteFill>;
};

const FlowLane:React.FC<{f:number;at:number;top:number;label:string;detail:string;nodes:string[]}> = ({f,at,top,label,detail,nodes}) => {
  const active=unit(f,at,60);
  return <div style={{position:'absolute',left:64,right:64,top}}>
    <Reveal f={f} at={at}><div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:20}}>
      <span style={{fontSize:22,color:C.lime,letterSpacing:2,fontWeight:600}}>{label}</span><span style={{fontSize:19,color:'#c2d1c5'}}>{detail}</span>
    </div></Reveal>
    <div style={{position:'relative',height:165,display:'flex',justifyContent:'space-between'}}>
      <svg width="952" height="165" style={{position:'absolute',inset:0}}>
        <path d="M240 80H712" stroke="#526b58" strokeWidth="2"/>
        <path d="M300 74l8 6-8 6M643 74l8 6-8 6" stroke="#acc0a8" fill="none" strokeWidth="2"/>
        <path d="M240 80H712" stroke={C.lime} strokeWidth="3" strokeDasharray="472" strokeDashoffset={472*(1-active)}/>
      </svg>
      {nodes.map((n,i)=><Reveal key={n} f={f} at={at+i*11} style={{width:264,height:165,position:'relative'}}>
        <div style={{height:'100%',borderRadius:18,border:'1px solid #77917877',background:i===1?'#254233f5':'#10291eea',
          display:'flex',alignItems:'center',justifyContent:'center',boxShadow:i===1?'0 14px 40px #0003':undefined}}>
          <Display style={{fontSize:45,textAlign:'center',whiteSpace:'pre-line',lineHeight:1.04,color:i===1?C.lime:'#f4f5ea'}}>{n}</Display>
        </div>
      </Reveal>)}
    </div>
  </div>;
};

const Architecture:React.FC<{feed:boolean}> = ({feed}) => {
  const f=useCurrentFrame();
  return <AbsoluteFill style={{color:C.ivory}}>
    <Stadium f={f+240} shade={.65}/><CornerBrand light feed={feed}/>
    <Reveal f={f} at={0} style={{position:'absolute',left:64,top:feed?180:255}}>
      <div style={{fontSize:21,letterSpacing:3,color:C.lime,marginBottom:27}}>UNDER THE HOOD</div>
      <Display style={{fontSize:feed?123:143}}>TWO WAYS TO<br/>STAY IN THE KNOW.</Display>
    </Reveal>
    <FlowLane f={f} at={21} top={feed?540:770} label="01 / AUTOMATIC" detail="League checked every 5 minutes"
      nodes={['ESPN','CHECK +\nDEDUPE','GROUP\nCHAT']}/>
    <FlowLane f={f} at={77} top={feed?823:1138} label="02 / WHEN YOU ASK" detail="BlueBubbles → guardrails → agent"
      nodes={['YOUR\nMENTION','AGENT +\nLEAGUE TOOLS','GROUP\nREPLY']}/>
    <Reveal f={f} at={134} style={{position:'absolute',left:64,right:64,bottom:feed?125:195,display:'flex',alignItems:'center',gap:24}}>
      <div style={{width:3,height:70,background:C.lime}}/>
      <div style={{fontSize:feed?29:35,lineHeight:1.4,color:'#e0e8dd'}}>Runs on your Mac.<br/>Lives in your league's chat.</div>
    </Reveal>
  </AbsoluteFill>;
};

const EndCard:React.FC<{feed:boolean}> = ({feed}) => {
  const f=useCurrentFrame();
  return <AbsoluteFill style={{color:C.ivory}}>
    <Stadium f={f+450} shade={.53}/><CornerBrand light feed={feed}/>
    <Reveal f={f} at={0} style={{position:'absolute',left:66,top:feed?190:325}}><Mark size={feed?78:100} dark/></Reveal>
    <Reveal f={f} at={8} style={{position:'absolute',left:62,top:feed?300:478}}>
      <Display style={{fontSize:feed?166:195}}>SCHEFTER<br/><span style={{color:C.lime}}>BOT.</span></Display>
    </Reveal>
    <Reveal f={f} at={25} style={{position:'absolute',left:66,top:feed?674:942}}>
      <div style={{fontSize:feed?42:56,lineHeight:1.13,fontWeight:550,letterSpacing:-1.7}}>Your league.<br/>Your news desk.</div>
    </Reveal>
    <Reveal f={f} at={43} style={{position:'absolute',left:64,right:64,top:feed?887:1310}}>
      <div style={{background:C.lime,color:C.ink,borderRadius:20,padding:'29px 30px',display:'flex',alignItems:'center',gap:26}}>
        <Icon name="github" size={48}/>
        <div><div style={{fontSize:18,fontWeight:750,letterSpacing:2.5,marginBottom:9}}>GET THE CODE</div><div style={{fontSize:28,fontWeight:600,letterSpacing:-.6}}>drewdouglas0-bit / schefter-bot-public</div></div>
        <div style={{marginLeft:'auto',transform:'rotate(45deg)'}}><Icon name="arrow" size={38}/></div>
      </div>
    </Reveal>
    <Reveal f={f} at={58} style={{position:'absolute',left:66,top:feed?1114:1590,fontSize:24,color:'#d6e0d4'}}>Built by Andrew Shaw</Reveal>
    <div style={{position:'absolute',left:66,right:50,bottom:feed?42:72,fontSize:17,lineHeight:1.6,color:'#a8b5a6'}}>Independent project. Not affiliated with Adam Schefter, ESPN or the NFL.</div>
    <AbsoluteFill style={{background:'#05130b',opacity:unit(f,169,11),pointerEvents:'none'}}/>
  </AbsoluteFill>;
};

export const LaunchFilm:React.FC<{feed:boolean}> = ({feed}) => {
  const [fontHandle]=useState(()=>delayRender('Load the bundled film fonts'));
  useEffect(()=>{
    Promise.all([document.fonts.load('700 80px Barlow'),document.fonts.load('400 20px Inter'),document.fonts.load('650 20px Inter')])
      .then(()=>continueRender(fontHandle)).catch(cancelRender);
  },[fontHandle]);
  return <AbsoluteFill style={{fontFamily:'Inter, sans-serif',background:C.dark}}>
    <Fonts/>
    <Audio src={staticFile('audio/score.wav')}/>
    <Sequence durationInFrames={120}><Intro feed={feed}/></Sequence>
    {stages.map((s,i)=><Sequence key={s.start} from={s.start} durationInFrames={s.end-s.start}><ChatScene index={i} feed={feed}/></Sequence>)}
    <Sequence from={1200} durationInFrames={240}><Architecture feed={feed}/></Sequence>
    <Sequence from={1440} durationInFrames={180}><EndCard feed={feed}/></Sequence>
  </AbsoluteFill>;
};
