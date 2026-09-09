import React from 'react';
import {spring} from 'remotion';
import {C, Icon, Mark, unit} from './design';

export type Message = {at:number;who:'Jake'|'Maya'|'Drew'|'Schefter Bot';lines:string[];reaction?:string;reactionAt?:number};
export type ChatDay = {time:string;date:string;messages:Message[]};

const people = {Jake:{letters:'JK',color:'#bb7758'},Maya:{letters:'MP',color:'#7976ac'},Drew:{letters:'DS',color:'#6b92b0'}};
const Avatar:React.FC<{who:Message['who'];size?:number}> = ({who,size=25}) => who==='Schefter Bot'?<Mark size={size}/>:<div style={{width:size,height:size,borderRadius:'50%',background:people[who].color,
  color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontSize:size*.35,fontWeight:650,flexShrink:0}}>{people[who].letters}</div>;

export const messageHeight = (m:Message) => m.lines.length*24 + 22 + (m.who==='Drew'?0:21) + 16;

const MessageRow:React.FC<{message:Message;f:number;staticRow?:boolean}> = ({message:m,f,staticRow=false}) => {
  const self=m.who==='Drew';
  const p=staticRow?1:spring({frame:Math.max(0,f-m.at),fps:30,config:{damping:19,stiffness:215,mass:.78}});
  const opacity=staticRow?1:unit(f,m.at,5);
  const r=unit(f,m.reactionAt??9999,12);
  return <div data-chat-row={m.who} style={{height:messageHeight(m),display:'flex',alignItems:'flex-end',gap:7,
    justifyContent:self?'flex-end':'flex-start',paddingBottom:16,opacity,
    transform:`translateY(${(1-p)*17}px) scale(${.94+.06*p})`,transformOrigin:self?'bottom right':'bottom left'}}>
    {!self&&<div style={{marginBottom:2}}><Avatar who={m.who}/></div>}
    <div style={{position:'relative',maxWidth:292}}>
      {!self&&<div style={{fontSize:11.5,color:'#77777d',marginLeft:11,height:21,display:'flex',alignItems:'center',gap:5}}>
        {m.who}{m.who==='Schefter Bot'&&<span style={{fontSize:8.5,letterSpacing:.5,color:'#617667'}}>BOT</span>}
      </div>}
      <div data-chat-bubble style={{position:'relative',padding:'10px 12px 12px',borderRadius:20,
        borderBottomRightRadius:self?6:20,borderBottomLeftRadius:self?20:6,
        background:self?C.blue:C.bubble,color:self?'white':'#18181b',fontSize:18.3,lineHeight:'24px',letterSpacing:'-.038em'}}>
        {m.lines.map((line,i)=><div key={i} data-chat-line style={{height:24,whiteSpace:'pre'}}>{line||' '}</div>)}
      </div>
      {m.reaction&&r>0&&<div style={{position:'absolute',top:self?-16:4,right:-6,background:'#e3e3e9',border:'2px solid #fff',borderRadius:16,
        padding:'3px 8px',fontSize:18,transform:`scale(${r}) rotate(${-8*(1-r)}deg)`}}>{m.reaction}</div>}
    </div>
  </div>;
};

export const ChatPhone:React.FC<{day:ChatDay;f:number;compact?:boolean}> = ({day,f,compact=false}) => {
  const height=compact?720:790;
  const visibleHeight=height-228;
  const topPad=56;
  let total=topPad;
  let previousTarget=0;
  let scroll=0;
  for (const m of day.messages) {
    total+=messageHeight(m);
    const nextTarget=Math.max(0,total-visibleHeight+5);
    if(f>=m.at) scroll += (nextTarget-previousTarget)*unit(f,m.at,20);
    previousTarget=nextTarget;
  }
  // Keep late bubbles in view without putting an artificial bot typing state in Messages.
  const latest=day.messages.filter(m=>f>=m.at).at(-1);
  return <div style={{position:'relative',width:400,height,borderRadius:59,padding:12,
    background:'linear-gradient(115deg,#797b76 0%,#20221f 3%,#020402 8%,#181b16 91%,#878780 96%,#34362f 100%)',
    boxShadow:'0 35px 60px -32px rgba(12,31,22,.45), 0 4px 6px #0004, inset 0 0 0 1px #777'}}>
    <div style={{position:'absolute',left:-2,top:148,width:3,height:30,background:'#44463f',borderRadius:2}}/>
    <div style={{position:'absolute',left:-2,top:200,width:3,height:57,background:'#44463f',borderRadius:2}}/>
    <div style={{position:'absolute',left:-2,top:271,width:3,height:57,background:'#44463f',borderRadius:2}}/>
    <div style={{position:'absolute',right:-2,top:224,width:3,height:78,background:'#44463f',borderRadius:2}}/>
    <div style={{position:'relative',height:'100%',borderRadius:47,background:'#fff',overflow:'hidden',border:'1px solid #080a07'}}>
      <div style={{height:47,display:'flex',alignItems:'center',padding:'0 28px',justifyContent:'space-between',fontSize:14,fontWeight:650,color:'#151515'}}>
        <span style={{marginTop:1}}>{day.time}</span>
        <div style={{position:'absolute',left:133,top:10,width:110,height:29,background:'#030504',borderRadius:30,display:'flex',alignItems:'center',justifyContent:'flex-end',paddingRight:9}}>
          <div style={{width:9,height:9,borderRadius:'50%',background:'radial-gradient(circle at 35% 30%,#16414a,#080e12 60%)'}}/>
        </div>
        <svg width="65" height="16" viewBox="0 0 65 16" fill="#131515"><rect x="0" y="10" width="3" height="4" rx=".7"/><rect x="5" y="7" width="3" height="7" rx=".7"/><rect x="10" y="4" width="3" height="10" rx=".7"/><rect x="15" y="1" width="3" height="13" rx=".7"/><path d="M23 5Q30-1 37 5L35 7Q30 3 25 7ZM27 9Q30 6 33 9L30 13Z"/><rect x="42" y="2" width="20" height="11" rx="3" fill="none" stroke="#555" strokeWidth="1"/><rect x="44" y="4" width="16" height="7" rx="1.5"/><rect x="63" y="5" width="2" height="5" rx=".5"/></svg>
      </div>
      <div style={{position:'relative',height:94,background:'#fafafa',borderBottom:'1px solid #efeff0',display:'flex',alignItems:'center',flexDirection:'column'}}>
        <div style={{position:'absolute',left:12,top:25,color:C.blue,display:'flex',alignItems:'center',gap:0}}><Icon name="chevron" size={25}/><span style={{fontSize:15}}>8</span></div>
        <div style={{display:'flex',paddingTop:5,height:46,alignItems:'center',paddingLeft:8}}>
          {(['Drew','Jake','Maya','Schefter Bot'] as const).map(w=><div key={w} style={{marginLeft:-8,padding:2,borderRadius:'50%',background:'#fafafa'}}><Avatar who={w} size={30}/></div>)}
        </div>
        <div style={{fontSize:16,fontWeight:650,marginTop:2}}>Waiver Wire <span style={{fontWeight:400,color:'#a0a0a6'}}>›</span></div>
        <div style={{fontSize:10.5,color:'#85858a',marginTop:3}}>4 people</div>
        <div style={{position:'absolute',right:18,top:26,color:C.blue}}><Icon name="video" size={23}/></div>
      </div>
      <div style={{position:'absolute',left:0,right:0,top:141,height:visibleHeight,overflow:'hidden',padding:'0 10px'}}>
        <div style={{transform:`translateY(${-scroll}px)`}}>
          <div style={{height:topPad,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:5,color:'#8b8b91',fontSize:10.5}}>
            <span>iMessage</span><span style={{fontWeight:650}}>{day.date}</span>
          </div>
          {day.messages.map((m,i)=>f>=m.at&&<MessageRow key={i} message={m} f={f}/>)}
          {latest?.who==='Drew'&&<div style={{textAlign:'right',fontSize:9,color:'#8a8a90',marginTop:-12,paddingRight:5}}>Delivered</div>}
        </div>
      </div>
      <div style={{position:'absolute',left:0,right:0,bottom:0,height:63,background:'#fff',padding:'7px 13px 0',display:'flex',alignItems:'flex-start',gap:10,borderTop:'1px solid #f8f8f8'}}>
        <div style={{color:'#9a9a9e',fontSize:30,fontWeight:300,lineHeight:'31px'}}>+</div>
        <div style={{height:33,border:'1px solid #d8d8dd',borderRadius:20,display:'flex',flex:1,justifyContent:'space-between',alignItems:'center',padding:'0 10px 0 13px',color:'#a4a4a9',fontSize:14}}>
          <span>iMessage</span><Icon name="mic" size={17} color="#77777c"/>
        </div>
        <div style={{position:'absolute',bottom:7,left:128,width:120,height:4.5,borderRadius:6,background:'#090a09'}}/>
      </div>
    </div>
  </div>;
};
