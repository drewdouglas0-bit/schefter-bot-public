import React from 'react';
import {Easing, interpolate, staticFile} from 'remotion';

export const C = {ink: '#10251f', ivory: '#f5f3ed', muted: '#748078', lime: '#d7f768',
  green: '#164d3d', blue: '#1688fc', bubble: '#e9e9eb', dark: '#071811'};
export const ease = Easing.bezier(0.2, 0.75, 0.2, 1);
export const unit = (f: number, start: number, duration = 18) =>
  interpolate(f, [start, start + duration], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
export const Display: React.FC<React.PropsWithChildren<{style?: React.CSSProperties}>> = ({children,style}) =>
  <div style={{fontFamily: 'Barlow', fontWeight: 700, lineHeight: 0.94, letterSpacing: '-0.018em', ...style}}>{children}</div>;
export const Fonts: React.FC = () => <style>{`
  @font-face {font-family:Inter;src:url('${staticFile('fonts/Inter.ttf')}') format('truetype');font-weight:100 900;font-display:block;}
  @font-face {font-family:Barlow;src:url('${staticFile('fonts/BarlowCondensed-Bold.ttf')}') format('truetype');font-weight:700;font-display:block;}
  * {box-sizing:border-box;}
`}</style>;

export const Mark: React.FC<{size?:number;dark?:boolean}> = ({size=64,dark=false}) =>
  <div style={{width:size,height:size,borderRadius:size*.27,background:dark?C.lime:C.green,
    color:dark?C.ink:C.lime,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
    <svg width={size*.69} height={size*.69} viewBox="0 0 64 64" fill="none">
      <path d="M11 30C14 14 30 7 49 10C55 28 46 46 29 52C18 48 12 40 11 30Z" stroke="currentColor" strokeWidth="3.6"/>
      <path d="M21 42L43 20M25 28L36 39M31 22L42 33M20 34L30 44" stroke="currentColor" strokeWidth="3.6" strokeLinecap="round"/>
    </svg>
  </div>;

export const Icon: React.FC<{name:'arrow'|'chevron'|'video'|'mic'|'github'|'ball';size?:number; color?:string}> = ({name,size=24,color='currentColor'}) => {
  const paths = {
    arrow: <><path d="M12 19V5M6 11l6-6 6 6"/></>,
    chevron: <path d="M15 5l-7 7 7 7"/>,
    video: <><rect x="3" y="6" width="12" height="12" rx="3"/><path d="M15 10l6-3v10l-6-3"/></>,
    mic: <><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M6 11v1a6 6 0 0012 0v-1M12 18v4M9 22h6"/></>,
    github: <path d="M9 19c-4 1-4-2-6-2m12 5v-4c0-1 .1-1.7-.6-2.4 3-.3 6.1-1.5 6.1-6.9 0-1.4-.5-2.5-1.3-3.4.1-.3.6-1.6-.1-3.3 0 0-1.1-.4-3.6 1.3a12.3 12.3 0 00-6.5 0C6.5 1.6 5.4 2 5.4 2c-.7 1.7-.2 3-.1 3.3C4.5 6.2 4 7.3 4 8.7c0 5.4 3.1 6.6 6.1 6.9-.5.4-.8 1-.8 2V22"/>,
    ball: <><path d="M5 19C0 5 9 0 21 3c3 12-2 21-16 16Z"/><path d="M7 17L17 7M8 9l7 7M11 6l7 7"/></>
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
};

export const CornerBrand: React.FC<{light?:boolean;feed?:boolean}> = ({light=false,feed=false}) => <div style={{position:'absolute',top:feed?42:62,left:64,right:64,display:'flex',justifyContent:'space-between',alignItems:'center',color:light?'#fff':C.ink}}>
  <div style={{display:'flex',gap:13,alignItems:'center'}}><Mark size={36} dark={light}/><span style={{fontSize:21,fontWeight:750,letterSpacing:1}}>SCHEFTER BOT</span></div>
  <span style={{fontSize:17,letterSpacing:2.4,opacity:.6}}>SEASON 2026</span>
</div>;
