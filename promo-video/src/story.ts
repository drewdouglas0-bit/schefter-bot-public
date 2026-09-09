import type {ChatDay} from './ChatPhone';
import demo from './demo.json';

export const days:ChatDay[]=[
  {time:'9:41',date:'Wednesday 9:41 AM',messages:[
    {at:10,who:'Jake',lines:['waivers are gonna be quiet']},
    {at:44,who:'Schefter Bot',lines:["Waiver claim: Jake's Rebuild",'gets RB Jaylen Warren (PIT)','for $31 of FAAB.']},
    {at:133,who:'Drew',lines:['$31????'],reaction:'‼',reactionAt:167},
    {at:191,who:'Maya',lines:['Schefter, who did Jake drop?']},
    {at:278,who:'Schefter Bot',lines:["Jake's Rebuild released",'RB Jerome Ford in a separate','move, per ESPN.']},
  ]},
  {time:'4:18',date:'Sunday 4:18 PM',messages:[
    {at:16,who:'Drew',lines:["Schefter, how's Jake doing?"]},
    {at:89,who:'Schefter Bot',lines:['Sunday Scaries leads',"Jake's Rebuild, 128.4-96.2",'in Week 1, per ESPN.']},
    {at:213,who:'Maya',lines:["that's my team btw"],reaction:'♥',reactionAt:247},
    {at:280,who:'Jake',lines:["it's a rebuilding year"]},
  ]},
  {time:'9:00',date:'Tuesday 9:00 AM',messages:[
    {at:16,who:'Schefter Bot',lines:['📋 WEEK 1 FINAL','',
      'Sunday Scaries def.',"Jake's Rebuild, 128.4-96.2",'',
      'High scorer:', 'Sunday Scaries (128.4)','',
      "Jake's Rebuild left 42.7",'points on the bench, including',
      'WR Chris Olave (NO) at 28.1,','league records show.']},
    {at:211,who:'Maya',lines:['42 on the bench 😭']},
    {at:270,who:'Drew',lines:['football is so back']},
  ]}
];

// Fail a render if editorial copy drifts from the actual fixture or scripted source.
const normalize=(s:string)=>s.replace(/\s+/g,' ').trim();
const equivalence:[string,string][]=[
  [days[0].messages[1].lines.join(' '),demo.waiver],
  [days[0].messages[4].lines.join(' '),demo.scriptedAnswers.drop],
  [days[1].messages[1].lines.join(' '),demo.scriptedAnswers.matchup],
  [days[2].messages[0].lines.join(' '),demo.recapExcerpt],
];
for(const [shown,source] of equivalence) {
  if(normalize(shown)!==normalize(source)) throw new Error(`Demo copy drift: ${shown}`);
}

export const stages=[
  {start:120,end:510,kicker:'01 / WAIVER WEDNESDAY',title:'YOUR LEAGUE. LIVE.',feedTitle:['YOUR','LEAGUE.','LIVE.'],caption:'Every move. Straight to the group chat.',side:'Every move.\nStraight to the\ngroup chat.'},
  {start:510,end:870,kicker:'02 / SUNDAY FOOTBALL',title:'ASK. GET THE FACTS.',feedTitle:['ASK.','GET THE','FACTS.'],caption:'Mention Schefter. Get the league context.',side:'Mention Schefter.\nGet the league\ncontext.'},
  {start:870,end:1200,kicker:'03 / TUESDAY RECEIPTS',title:'RECEIPTS. EVERY WEEK.',feedTitle:['RECEIPTS.','EVERY','WEEK.'],caption:'Final scores. Bench blunders. No escape.',side:'Final scores.\nBench blunders.\nNo escape.'},
];
