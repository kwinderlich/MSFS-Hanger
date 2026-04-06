
const {useState,useEffect,useRef,useMemo,useCallback}=React;
let qtBridgeReadyPromise=null;
function ensureQtBridge(){
  if(window.hangarBridge) return Promise.resolve(window.hangarBridge);
  if(qtBridgeReadyPromise) return qtBridgeReadyPromise;
  qtBridgeReadyPromise=new Promise(resolve=>{
    try{
      if(!(window.qt && window.qt.webChannelTransport)){ resolve(null); return; }
      function setup(){
        try{
          if(!(window.QWebChannel && window.qt && window.qt.webChannelTransport)){ resolve(null); return; }
          new window.QWebChannel(window.qt.webChannelTransport, channel=>{
            window.hangarBridge=channel && channel.objects ? channel.objects.bridge : null;
            resolve(window.hangarBridge||null);
          });
        }catch(e){ resolve(null); }
      }
      if(window.QWebChannel){ setup(); return; }
      const existing=document.querySelector('script[data-hangar-qwebchannel="1"]');
      if(existing){ existing.addEventListener('load', setup, {once:true}); existing.addEventListener('error', ()=>resolve(null), {once:true}); return; }
      const s=document.createElement('script');
      s.src='qrc:///qtwebchannel/qwebchannel.js';
      s.async=true;
      s.dataset.hangarQwebchannel='1';
      s.onload=setup;
      s.onerror=()=>resolve(null);
      document.head.appendChild(s);
    }catch(e){ resolve(null); }
  });
  return qtBridgeReadyPromise;
}
async function openNativePathPicker(detail){
  try{
    const bridge=await ensureQtBridge();
    if(!bridge) return null;
    const label=String((detail&&detail.label)||'Select Path');
    const current=String((detail&&detail.current)||'');
    const pattern=String((detail&&detail.pattern)||'');
    if((detail&&detail.mode)==='file' && bridge.pickFile){
      return await new Promise(resolve=>{
        try{ bridge.pickFile(label,current,pattern, value=>resolve(value||'')); }catch(e){ resolve(''); }
      });
    }
    if(bridge.pickFolder){
      return await new Promise(resolve=>{
        try{ bridge.pickFolder(label,current, value=>resolve(value||'')); }catch(e){ resolve(''); }
      });
    }
    return null;
  }catch(e){ return null; }
}
/* Restore saved theme on load */
(function(){
  const t=localStorage.getItem("hangar-theme");
  if(t==="light"){const r=document.documentElement;r.style.setProperty("--bg0","#F8FAFC");r.style.setProperty("--bg1","#FFFFFF");r.style.setProperty("--bg2","#F1F5F9");r.style.setProperty("--bg3","#E2E8F0");r.style.setProperty("--card","#FFFFFF");r.style.setProperty("--cardH","#F1F5F9");r.style.setProperty("--bdr","rgba(0,0,0,0.1)");r.style.setProperty("--bdrH","rgba(0,0,0,0.2)");r.style.setProperty("--t0","#0F172A");r.style.setProperty("--t1","#334155");r.style.setProperty("--t2","#64748B");r.style.setProperty("--t3","#94A3B8");}
})();

const CC={Airport:"#38BDF8",Aircraft:"#34D399",Scenery:"#FBBF24",Utility:"#A78BFA",Vehicles:"#F97316",Boats:"#06B6D4",Mod:"#FB923C"};
const CI={Airport:"[A]",Aircraft:"[P]",Scenery:"[S]",Utility:"[U]",Vehicles:"[V]",Boats:"[B]",Mod:"[M]"};
const CABBR={"United States":"US","United Kingdom":"UK","Australia":"AUS","Canada":"CAN","Germany":"GER","France":"FRA","Japan":"JPN","Netherlands":"NLD","United Arab Emirates":"UAE","Singapore":"SGP","New Zealand":"NZL","Spain":"ESP","Italy":"ITA","Switzerland":"CHE"};
const CANADA_PROVINCES={AB:'Alberta',BC:'British Columbia',MB:'Manitoba',NB:'New Brunswick',NL:'Newfoundland and Labrador',NS:'Nova Scotia',NT:'Northwest Territories',NU:'Nunavut',ON:'Ontario',PE:'Prince Edward Island',QC:'Quebec',SK:'Saskatchewan',YT:'Yukon'};
const ADDON_TYPE_OPTIONS=["Aircraft","Airport","Scenery","Utility","Vehicles","Boats","Mod"];
const DEFAULT_SUBTYPE_OPTIONS={Aircraft:["Airliner","General Aviation","Business Jet","Helicopter","Military","Regional"],Airport:["Large Commercial","Medium Commercial","General Aviation","Heliport","Seaplane Base","Closed"],Scenery:["City","Region","Landmark","Mesh","Airport scenery"],Utility:["Navigation","Tool","Weather","Mission","Air Traffic Control","Mapping","Flight Planning","Launcher","Sim Platform","Other"],Vehicles:["Car","Truck","Offroad"],Boats:["Pleasure","Military","Cargo"],Mod:["Livery","Enhancement","Other"]};
function abbr(c){return CABBR[c]||c;}
function fullCanadaProvince(v){ const s=String(v||'').trim(); return CANADA_PROVINCES[s.toUpperCase()]||s; }
function regionDisplayFor(country,value){ if(!value) return ''; return country==='Canada'?fullCanadaProvince(value):value; }

const DEMO_PDF="https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf";
const PDF_PHAK="https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak/media/pilot_handbook.pdf";
const PDF_AFH="https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/airplane_handbook/media/airplane_flying_handbook.pdf";
const PDF_IPH="https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/media/instrument_procedures_handbook.pdf";
const PDF={SAMPLE:DEMO_PDF,PHAK:PDF_PHAK,AFH:PDF_AFH,IPH:PDF_IPH};
function mkUsr(){return {fav:false,rating:0,notes:"",tags:[],paid:0,source_store:"",features:"",resources:[],research_resources:[],data_resources:[]};}
const U="https://images.unsplash.com/photo-";
const IMGS={
  KJFK:[U+"1436491865332-7a61a109cc05?w=900&q=80",U+"1529074963764-98f45c47344b?w=900&q=80"],
  EGLL:[U+"1526182879730-c4f8cf4b2fd7?w=900&q=80",U+"1570710891565-69d3df3e2ae6?w=900&q=80"],
  KSFO:[U+"1501594907352-04cda38ebc29?w=900&q=80"],
  KORD:[U+"1474302770737-173ee21bab63?w=900&q=80"],
  A320:[U+"1540979388789-6cee28a1cdc9?w=900&q=80",U+"1569629743817-70d8db6c323b?w=900&q=80"],
  B737:[U+"1583373834259-46cc92173cb7?w=900&q=80"],
  C172:[U+"1559674145-e9aed5b9a773?w=900&q=80"],
  PNW: [U+"1464822759023-fed622ff2c3b?w=900&q=80"],
};
const PICSUMS={KJFK:"https://picsum.photos/seed/kjfk/900/500",EGLL:"https://picsum.photos/seed/lhr/900/500",KSFO:"https://picsum.photos/seed/sfo/900/500",KORD:"https://picsum.photos/seed/ord/900/500",A320:"https://picsum.photos/seed/a320/900/500",B737:"https://picsum.photos/seed/b737/900/500",C172:"https://picsum.photos/seed/c172/900/500",PNW:"https://picsum.photos/seed/pnw/900/500"};
const ADDONS=[];  // populated from backend API

function locDisplay(a){
  const r=a.rw||{};
  if(a.type==="Airport"||a.type==="Scenery"){
    const c=r.country||"",ca=abbr(c);
    if(c==="United States") return (r.state?r.state+", ":"")+ca;
    if(c==="Canada") return (r.province?regionDisplayFor(c,r.province)+", ":"")+ca;
    return (r.region?r.region+", ":"")+ca;
  }
  return "";
}
function useIsMobile(){
  const [m,setM]=useState(()=>window.innerWidth<=900);
  useEffect(()=>{const h=()=>setM(window.innerWidth<=900);window.addEventListener("resize",h);return ()=>window.removeEventListener("resize",h);},[]);
  return m;
}

const ARTICLE_CATEGORIES=["Product Info","Reviews","Reference","Videos"];
function ensureArticleCategory(item){
  if(!item) return item;
  if(item.category) return item;
  const u=String(item.url||""), t=(String(item.title||"")+" "+u).toLowerCase();
  let category="Reference";
  if(t.includes("youtube.com")||t.includes("youtu.be")||t.includes(" video")||t.includes(" trailer")) category="Videos";
  else if(t.includes("review")||t.includes("preview")||t.includes("first look")) category="Reviews";
  else if(t.includes("store")||t.includes("product")||t.includes("flightsim.to")||t.includes("justflight")||t.includes("inibuilds")||t.includes("aerosoft")) category="Product Info";
  return {...item,category};
}
function sanitizeHtmlForTheme(html){
  if(!html) return "";
  const tmp=document.createElement('div');
  tmp.innerHTML=String(html);
  tmp.querySelectorAll('script,style,meta,link,head,nav,footer,header,aside,noscript').forEach(el=>el.remove());
  tmp.querySelectorAll('*').forEach(el=>{
    [...el.attributes].forEach(attr=>{
      const n=attr.name.toLowerCase();
      if(n.startsWith('on')) el.removeAttribute(attr.name);
    });
    const s=(el.getAttribute('style')||'')
      .replace(/color\s*:[^;]+;?/gi,'')
      .replace(/background(?:-color)?\s*:[^;]+;?/gi,'')
      .replace(/border(?:-color)?\s*:[^;]+;?/gi,'')
      .replace(/caret-color\s*:[^;]+;?/gi,'')
      .replace(/text-decoration-color\s*:[^;]+;?/gi,'')
      .replace(/-webkit-text-fill-color\s*:[^;]+;?/gi,'')
      .replace(/font-family\s*:[^;]+;?/gi,'');
    if(s.trim()) el.setAttribute('style', s); else el.removeAttribute('style');
    if(el.tagName==='FONT'){
      const span=document.createElement('span');
      span.innerHTML=el.innerHTML;
      el.replaceWith(span);
    }
  });
  return tmp.innerHTML;
}
function applyThemedHtml(el, html){
  if(!el) return;
  el.innerHTML=sanitizeHtmlForTheme(html||'');
}
function reformatReadableHtml(html, opts={}){
  const {stripImages=false}=opts;
  const tmp=document.createElement('div');
  tmp.innerHTML=sanitizeHtmlForTheme(html||'');
  tmp.querySelectorAll('script,style,meta,link,noscript,iframe,svg,canvas,form,button,input,select,textarea').forEach(el=>el.remove());
  tmp.querySelectorAll('*').forEach(el=>{
    const cls=((el.getAttribute('class')||'')+' '+(el.getAttribute('id')||'')).toLowerCase();
    if(/\b(ad|ads|advert|banner|cookie|popup|subscribe|sponsor|social|share)\b/.test(cls)){
      if(el.textContent && el.textContent.trim().length<180) el.remove();
    }
    if(stripImages && el.tagName==='IMG') el.remove();
    if(['SECTION','ARTICLE','MAIN'].includes(el.tagName)){
      const div=document.createElement('div');
      div.innerHTML=el.innerHTML;
      el.replaceWith(div);
    }
  });
  const blockify=(el)=>{
    const raw=(el.textContent||'').split(/\n+/).map(s=>s.trim()).filter(Boolean);
    if(raw.length<3) return false;
    const bulletLines=raw.filter(line=>/^(?:[-*•]|\d+[\.)])\s+/.test(line));
    if(bulletLines.length<2) return false;
    const wrapper=document.createElement('div');
    let list=null;
    raw.forEach(line=>{
      const bullet=line.match(/^(?:[-*•]|(\d+)[\.)])\s+(.*)$/);
      if(bullet){
        if(!list){ list=document.createElement(bullet[1]?'ol':'ul'); wrapper.appendChild(list); }
        const li=document.createElement('li');
        li.textContent=bullet[2];
        list.appendChild(li);
      }else{
        list=null;
        const p=document.createElement('p');
        p.textContent=line;
        wrapper.appendChild(p);
      }
    });
    el.replaceWith(wrapper);
    return true;
  };
  [...tmp.querySelectorAll('p,div')].forEach(el=>blockify(el));
  tmp.querySelectorAll('a').forEach(a=>{ a.setAttribute('target','_blank'); a.setAttribute('rel','noreferrer'); });
  return sanitizeHtmlForTheme(tmp.innerHTML);
}
function applyReformatToEditor(editor, opts={}){
  if(!editor) return '';
  const html=reformatReadableHtml(editor.innerHTML||'', opts);
  editor.innerHTML=html;
  return html;
}
function groupArticleResources(items){
  const groups={}; ARTICLE_CATEGORIES.forEach(c=>groups[c]=[]);
  (items||[]).map(ensureArticleCategory).forEach(it=>{ groups[it.category||"Reference"]=(groups[it.category||"Reference"]||[]).concat([it]); });
  return groups;
}
function currentLanguage(){ return localStorage.getItem('hangar_language')||'English'; }
function currentCurrency(){ return localStorage.getItem('hangar_currency')||'$'; }
function currentCalendarFormat(){ return localStorage.getItem('hangar_calendar_format')||localStorage.getItem('hangar_calendar')||'MM/DD/YYYY'; }
function currentSearchProvider(){
  const raw=(localStorage.getItem('hangar_search_provider')||'bing').toLowerCase();
  return raw==='google'?'google':'bing';
}
function searchProviderLabel(v){ return (String(v||'').toLowerCase()==='google')?'Google':'Bing'; }
function googleLocaleParams(){
  const lang=currentLanguage();
  const table={English:{hl:'en',gl:'us'},Spanish:{hl:'es',gl:'es'},French:{hl:'fr',gl:'fr'},German:{hl:'de',gl:'de'},Italian:{hl:'it',gl:'it'},Portuguese:{hl:'pt',gl:'pt'},Dutch:{hl:'nl',gl:'nl'}};
  return table[lang]||table.English;
}
function googleSearchUrl(term, opts={}){
  const {hl,gl}=googleLocaleParams();
  const value=String(term||'').trim();
  const lang=(hl||'en').toLowerCase();
  const cc=(gl||'us').toLowerCase();
  const provider=currentSearchProvider();
  if(provider==='google'){
    if(opts.images){
      return 'https://www.google.com/search?tbm=isch&hl='+encodeURIComponent(lang)+'&gl='+encodeURIComponent(cc)+'&q='+encodeURIComponent(value);
    }
    return 'https://www.google.com/search?hl='+encodeURIComponent(lang)+'&gl='+encodeURIComponent(cc)+'&pws=0&q='+encodeURIComponent(value);
  }
  if(opts.images){
    return 'https://www.bing.com/images/search?setlang='+encodeURIComponent(lang)+'&cc='+encodeURIComponent(cc)+'&q='+encodeURIComponent(value);
  }
  return 'https://www.bing.com/search?setlang='+encodeURIComponent(lang)+'&cc='+encodeURIComponent(cc)+'&q='+encodeURIComponent(value);
}
function withBrowserResetNonce(url){
  return String(url||'').trim();
}
function formatWholeNumber(value){
  if(value===null||value===undefined||value==="") return '—';
  const num=Number(value);
  if(Number.isNaN(num)) return String(value);
  return new Intl.NumberFormat(undefined,{maximumFractionDigits:0}).format(Math.round(num));
}
function formatCurrencyWhole(value){
  if(value===null||value===undefined||value==="") return '—';
  const num=Number(value);
  if(Number.isNaN(num)) return String(value);
  const symbol=currentCurrency();
  try{
    if(symbol==='€') return new Intl.NumberFormat(undefined,{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(num);
    if(symbol==='£') return new Intl.NumberFormat(undefined,{style:'currency',currency:'GBP',maximumFractionDigits:0}).format(num);
    return new Intl.NumberFormat(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0}).format(num).replace('$',symbol);
  }catch(e){ return symbol+Math.round(num).toLocaleString(); }
}
function formatCurrencyValue(value){
  if(value===null||value===undefined||value==="") return '—';
  const num=Number(value);
  if(Number.isNaN(num)) return String(value);
  const symbol=currentCurrency();
  try{
    if(symbol==='€') return new Intl.NumberFormat(undefined,{style:'currency',currency:'EUR'}).format(num);
    if(symbol==='£') return new Intl.NumberFormat(undefined,{style:'currency',currency:'GBP'}).format(num);
    return new Intl.NumberFormat(undefined,{style:'currency',currency:'USD'}).format(num).replace('$',symbol);
  }catch(e){ return symbol+num.toFixed(2); }
}
function formatDateValue(value){
  if(!value) return '';
  const s=String(value).trim();
  const m=s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const fmt=currentCalendarFormat();
  if(!m) return s;
  const [,y,mo,d]=m;
  if(fmt==='DD/MM/YYYY') return `${d}/${mo}/${y}`;
  if(fmt==='YYYY-MM-DD') return `${y}-${mo}-${d}`;
  return `${mo}/${d}/${y}`;
}
function normalizeDateValue(value){
  if(!value) return '';
  const s=String(value).trim();
  let m=s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if(m) return `${m[1]}-${m[2]}-${m[3]}`;
  m=s.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if(m){
    const fmt=currentCalendarFormat();
    if(fmt==='DD/MM/YYYY') return `${m[3]}-${m[2]}-${m[1]}`;
    return `${m[3]}-${m[1]}-${m[2]}`;
  }
  const parsed=new Date(s);
  if(!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0,10);
  return s;
}
function shortUrlLabel(value){
  const s=String(value||'').trim();
  if(!s) return '';
  if(s.toLowerCase().includes('vertexaisearch.cloud.google.com')) return 'vertexaisearch.cloud.google.com';
  try{ const u=new URL(s); return u.hostname||s; }catch(e){ return s; }
}
function valueToDisplay(value){
  if(value===null||value===undefined) return '';
  if(Array.isArray(value)) return value.map(v=>valueToDisplay(v)).filter(Boolean).join(', ');
  if(typeof value==='object') return Object.entries(value).map(([k,v])=>`${k}: ${valueToDisplay(v)}`).join(' · ');
  const s=String(value);
  if(/^https?:\/\//i.test(s)) return shortUrlLabel(s);
  return s;
}
function providerLabel(provider){
  return provider==='gemini'?'Google Gemini':provider==='claude'?'Claude':'OpenAI';
}
async function fetchJsonSafe(url, options){
  const res=await fetch(url, options);
  const raw=await res.text();
  let data={};
  try{ data=raw?JSON.parse(raw):{}; }catch(e){ data={detail:raw||res.statusText||'Request failed'}; }
  if(!res.ok){ throw new Error(data.detail||raw||('HTTP '+res.status)); }
  return data;
}
function NotificationOverlay({notice,onDismiss}){
  if(!notice) return null;
  const color=notice.kind==='error'?'var(--red)':notice.kind==='success'?'var(--grn)':'var(--acc)';
  return <div style={{position:'fixed',right:18,bottom:18,zIndex:99999,maxWidth:420,width:'min(420px, calc(100vw - 28px))'}}><div style={{background:'var(--bg1)',border:'1px solid '+color,borderRadius:14,boxShadow:'0 22px 60px rgba(0,0,0,.55)',padding:'14px 16px'}}><div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:10}}><div style={{flex:1,minWidth:0}}><div style={{fontSize:12,fontWeight:800,color,marginBottom:4}}>{notice.title||'Notification'}</div><div style={{fontSize:12,color:'var(--t1)',lineHeight:1.65,whiteSpace:'pre-wrap'}}>{notice.message}</div></div><button onClick={onDismiss} style={{background:'none',border:'none',color:'var(--t2)',fontSize:18,cursor:'pointer',lineHeight:1}}>×</button></div></div></div>;
}

function HelpIcon({onClick,title}){
  return <button title={title||'Help'} onClick={onClick} style={{width:28,height:28,display:'inline-flex',alignItems:'center',justifyContent:'center',borderRadius:999,border:'1px solid var(--accB)',background:'var(--accD)',color:'var(--acc)',fontWeight:800,fontSize:14,cursor:'pointer',flexShrink:0}}>?</button>;
}

function HelpOverlay({help,onDismiss}){
  if(!help) return null;
  const rows=(help.actions||[]).concat(help.workflows||[]);
  return <div style={{position:'fixed',inset:0,zIndex:100000,pointerEvents:'none'}}>
    <div style={{position:'absolute',top:20,right:20,width:'min(560px, calc(100vw - 32px))',maxHeight:'calc(100vh - 40px)',overflow:'auto',pointerEvents:'auto',background:'rgba(10,22,40,.98)',border:'1px solid var(--accB)',borderRadius:18,boxShadow:'0 28px 80px rgba(0,0,0,.6)',padding:'18px 18px 16px'}}>
      <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:12,marginBottom:10}}>
        <div>
          <div style={{fontSize:11,color:'var(--acc)',fontWeight:800,textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:5}}>Contextual Help</div>
          <div style={{fontSize:19,fontWeight:800,color:'var(--t0)'}}>{help.title||'Help'}</div>
        </div>
        <button onClick={onDismiss} style={{background:'none',border:'none',color:'var(--t2)',fontSize:22,cursor:'pointer',lineHeight:1}}>×</button>
      </div>
      {help.purpose&&<div style={{fontSize:13,color:'var(--t1)',lineHeight:1.7,marginBottom:12}}>{help.purpose}</div>}
      {help.when&&<div style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'11px 12px',marginBottom:12}}><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:5}}>When to use this</div><div style={{fontSize:12,color:'var(--t1)',lineHeight:1.65}}>{help.when}</div></div>}
      {rows.length>0&&<div style={{marginBottom:12}}><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:8}}>Workflows and actions</div><div style={{display:'grid',gap:8}}>{rows.map((row,idx)=><div key={idx} style={{display:'flex',gap:9,alignItems:'flex-start',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'10px 12px'}}><div style={{color:'var(--acc)',fontWeight:800,marginTop:1}}>•</div><div style={{fontSize:12,color:'var(--t1)',lineHeight:1.65}}>{row}</div></div>)}</div></div>}
      {help.tips&&help.tips.length>0&&<div><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:8}}>Tips</div><div style={{display:'grid',gap:8}}>{help.tips.map((tip,idx)=><div key={idx} style={{fontSize:12,color:'var(--t1)',lineHeight:1.65,background:'rgba(167,139,250,0.08)',border:'1px solid rgba(167,139,250,0.18)',borderRadius:12,padding:'10px 12px'}}>{tip}</div>)}</div></div>}
    </div>
  </div>;
}

function ConfirmOverlay({dialog,onCancel,onConfirm}){
  if(!dialog) return null;
  return <div style={{position:'fixed',inset:0,zIndex:100001,background:'rgba(3,8,20,.62)',backdropFilter:'blur(4px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
    <div style={{width:'min(640px, calc(100vw - 24px))',maxHeight:'calc(100vh - 32px)',overflow:'auto',background:'rgba(10,22,40,.98)',border:'1px solid var(--accB)',borderRadius:18,boxShadow:'0 28px 80px rgba(0,0,0,.6)',padding:'18px 18px 16px'}}>
      <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:12,marginBottom:10}}>
        <div>
          <div style={{fontSize:11,color:'var(--amb)',fontWeight:800,textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:5}}>{dialog.eyebrow||'Please confirm'}</div>
          <div style={{fontSize:19,fontWeight:800,color:'var(--t0)'}}>{dialog.title||'Confirm action'}</div>
        </div>
        <button onClick={onCancel} style={{background:'none',border:'none',color:'var(--t2)',fontSize:22,cursor:'pointer',lineHeight:1}}>×</button>
      </div>
      <div style={{fontSize:12,color:'var(--t1)',lineHeight:1.7,whiteSpace:'pre-wrap'}}>{dialog.message||''}</div>
      <div style={{display:'flex',justifyContent:'flex-end',gap:8,marginTop:16,flexWrap:'wrap'}}>
        <Btn label={dialog.cancelLabel||'Cancel'} color='var(--t2)' onClick={onCancel}/>
        <Btn label={dialog.confirmLabel||'Confirm'} color={dialog.confirmColor||'var(--red)'} onClick={onConfirm}/>
      </div>
    </div>
  </div>;
}

function ActivityOverlay({state,onDismiss}){
  if(!state) return null;
  const pct=Math.max(0, Math.min(100, Number(state.pct||0)));
  const color=state.kind==='error'?'var(--red)':state.done?'var(--grn)':'var(--vio)';
  return <div style={{position:'fixed',inset:0,zIndex:100002,background:'rgba(3,8,20,.62)',backdropFilter:'blur(4px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
    <div style={{width:'min(560px, calc(100vw - 24px))',background:'rgba(10,22,40,.98)',border:'1px solid var(--accB)',borderRadius:18,boxShadow:'0 28px 80px rgba(0,0,0,.6)',padding:'18px 18px 16px'}}>
      <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:12,marginBottom:10}}>
        <div>
          <div style={{fontSize:11,color:color,fontWeight:800,textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:5}}>{state.eyebrow||'Working'}</div>
          <div style={{fontSize:19,fontWeight:800,color:'var(--t0)'}}>{state.title||'Please wait'}</div>
        </div>
        {(state.done||state.kind==='error')&&<button onClick={onDismiss} style={{background:'none',border:'none',color:'var(--t2)',fontSize:22,cursor:'pointer',lineHeight:1}}>×</button>}
      </div>
      {state.message&&<div style={{fontSize:12,color:'var(--t1)',lineHeight:1.7,whiteSpace:'pre-wrap',marginBottom:12}}>{state.message}</div>}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}><span style={{fontSize:11,color:'var(--t2)'}}>{state.current||''}</span><span style={{fontSize:11,color:color,fontWeight:800}}>{pct}%</span></div>
      <div style={{height:8,background:'var(--bg3)',borderRadius:999,overflow:'hidden',marginBottom:10}}><div style={{height:'100%',width:pct+'%',background:color,borderRadius:999,transition:'width .25s'}}/></div>
      {(state.done||state.kind==='error')&&<div style={{display:'flex',justifyContent:'flex-end',gap:8,marginTop:12}}><Btn label='Close' color={color} onClick={onDismiss}/></div>}
    </div>
  </div>;
}

function Stars({v,sz,edit,onChange}){
  const s=sz||12,[hov,setHov]=useState(null),d=hov!=null?hov:(v||0);
  return <span style={{display:"inline-flex",gap:2}}>
    {[1,2,3,4,5].map(i=>(
      <svg key={i} width={s} height={s} viewBox="0 0 20 20" fill={i<=d?"#FBBF24":"#1E2D3D"}
        style={{cursor:edit?"pointer":"default"}}
        onMouseEnter={()=>edit&&setHov(i)} onMouseLeave={()=>edit&&setHov(null)}
        onClick={()=>edit&&onChange&&onChange(i)}>
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
      </svg>
    ))}
  </span>;
}
function Chip({label,color,sm,onClick}){
  const c=color||"var(--acc)";
  return <span onClick={onClick} style={{background:c+"1A",color:c,border:"1px solid "+c+"35",borderRadius:5,padding:sm?"1px 7px":"3px 10px",fontSize:sm?10:11,fontWeight:600,letterSpacing:"0.04em",textTransform:"uppercase",whiteSpace:"nowrap",cursor:onClick?"pointer":"default",userSelect:"none",display:"inline-block"}}>{label}</span>;
}
function Btn({label,color,onClick,style:sx,sm,full,disabled,title}){
  const c=color||"var(--acc)",[h,setH]=useState(false);
  return <button title={title||''} disabled={disabled} onClick={onClick} onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
    style={{background:h?c+"30":c+"18",border:"1px solid "+c+(h?"55":"35"),color:c,borderRadius:8,padding:sm?"5px 11px":"9px 18px",fontSize:sm?11:12,fontWeight:600,transition:"all 0.15s",width:full?"100%":"auto",opacity:disabled?0.5:1,display:"inline-flex",alignItems:"center",gap:6,cursor:disabled?"not-allowed":"pointer",...(sx||{})}}>
    {label}
  </button>;
}

function ClearIconButton({onClick,title,style:sx}){
  return <button type='button' title={title||'Clear'} onClick={e=>{e.preventDefault();e.stopPropagation();onClick&&onClick();}}
    style={{position:'absolute',right:10,top:'50%',transform:'translateY(-50%)',width:20,height:20,borderRadius:999,border:'1px solid var(--bdr)',background:'var(--bg3)',color:'var(--t1)',display:'inline-flex',alignItems:'center',justifyContent:'center',cursor:'pointer',fontSize:13,lineHeight:1,padding:0,...(sx||{})}}>×</button>;
}
function ClearableInput({value,setValue,placeholder,style:sx,inputStyle,onChange,...rest}){
  return <div style={{position:'relative',...(sx||{})}}>
    <input {...rest} value={value} onChange={e=>{ setValue&&setValue(e.target.value); onChange&&onChange(e); }} placeholder={placeholder||''}
      style={{width:'100%',background:'linear-gradient(180deg,var(--bg2),var(--bg1))',border:'1px solid var(--bdr)',borderRadius:12,padding:'10px 14px',paddingRight:(value?38:14),color:'var(--t0)',fontSize:14,outline:'none',fontWeight:600,minHeight:48,...(inputStyle||{})}}/>
    {!!value&&<ClearIconButton onClick={()=>setValue&&setValue('')} title='Clear text'/>}
  </div>;
}
function ClearableSelect({value,setValue,defaultValue='All',children,wrapStyle,selectStyle,title}){
  const clearable=value!=null && value!=='' && value!==defaultValue;
  return <div style={{position:'relative',display:'inline-flex',alignItems:'center',...(wrapStyle||{})}} title={title||''}>
    <select value={value} onChange={e=>setValue&&setValue(e.target.value)} style={{...(selectStyle||{}),paddingRight:clearable?50:((selectStyle&&selectStyle.paddingRight)||28)}}>{children}</select>
    {clearable&&<ClearIconButton onClick={()=>setValue&&setValue(defaultValue)} title='Reset filter' style={{right:8}}/>}
  </div>;
}
function ClearableDatalistInput({value,setValue,placeholder,list,style:sx,inputStyle,onChange,...rest}){
  return <div style={{position:'relative',...(sx||{})}}>
    <input {...rest} value={value} list={list} onChange={e=>{ setValue&&setValue(e.target.value); onChange&&onChange(e); }} placeholder={placeholder||''}
      style={{width:'100%',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 11px',paddingRight:(value?38:11),color:'var(--t0)',fontSize:12,outline:'none',...(inputStyle||{})}}/>
    {!!value&&<ClearIconButton onClick={()=>setValue&&setValue('')} title='Clear value'/>}
  </div>;
}

function FavBtn({on,onChange,sz}){
  return <span onClick={e=>{e.stopPropagation();onChange(!on);}} style={{cursor:"pointer",fontSize:sz||16,lineHeight:1,userSelect:"none",color:on?"#FBBF24":"var(--t3)",transition:"all 0.15s",display:"inline-block"}}>{on?"★":"☆"}</span>;
}
function DL({label,color}){
  return <div style={{fontSize:9,color,textTransform:"uppercase",letterSpacing:"0.1em",fontWeight:700,marginBottom:8,display:"flex",alignItems:"center",gap:7}}>
    <span style={{width:14,height:1,background:color,display:"inline-block",flexShrink:0}}/>
    {label}
    <span style={{flex:1,height:1,background:color+"25",display:"inline-block"}}/>
  </div>;
}
function KVG({pairs,cols}){
  const nc=cols||2,valid=(pairs||[]).filter(p=>p[1]!=null&&p[1]!=="");
  if(!valid.length) return null;
  return <div style={{display:"grid",gridTemplateColumns:"repeat("+nc+",1fr)",gap:5}}>
    {valid.map(([k,v,c])=>{
      const display=valueToDisplay(v);
      return (
      <div key={k} style={{background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:7,padding:"8px 10px"}}>
        <div style={{fontSize:10,color:'#C8D8EA',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:2,fontWeight:700}}>{k}</div>
        <div style={{fontSize:12,color:c||"var(--t0)",fontWeight:600,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={display}>{display}</div>
      </div>
    );})}
  </div>;
}
function AddonImg({a,h,style:sx}){
  const ht=h||155,cc=CC[a.type]||"#64748B";
  // API mode: use /thumb/{id} served by backend; standalone: use IMGS[]
  const apiSrc=a.thumbnail_path?("/thumb/"+a.id+"?v="+encodeURIComponent(a.thumbnail_path||"")):null;
  const srcs=apiSrc?[apiSrc]:((IMGS&&IMGS[a.imgKey])||[]);
  const [idx,setIdx]=useState(0),[failed,setFailed]=useState(false),[loaded,setLoaded]=useState(false);
  useEffect(()=>{setIdx(0);setFailed(false);setLoaded(false);},[a.id,a.thumbnail_path]);
  const src=srcs[idx]||(!apiSrc&&a.imgKey&&PICSUMS&&PICSUMS[a.imgKey])||null;
  if(!src||failed){
    return <div style={{height:ht,background:"linear-gradient(140deg,"+cc+"22,var(--bg0) 65%)",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",position:"relative",overflow:"hidden",...(sx||{})}}>
      <div style={{position:"absolute",inset:0,opacity:0.05,backgroundImage:"linear-gradient("+cc+" 1px,transparent 1px),linear-gradient(90deg,"+cc+" 1px,transparent 1px)",backgroundSize:"24px 24px"}}/>
      <div style={{fontSize:32,opacity:0.15,fontFamily:"monospace",color:cc}}>{a.rw&&a.rw.icao||a.type}</div>
    </div>;
  }
  return <div style={{height:ht,overflow:"hidden",position:"relative",...(sx||{})}}>
    {!loaded&&<div className="shimmer" style={{position:"absolute",inset:0}}/>}
    <img src={src} crossOrigin="anonymous" alt={a.title}
      onLoad={()=>setLoaded(true)}
      onError={()=>{if(idx<srcs.length-1){setIdx(i=>i+1);setLoaded(false);}else setFailed(true);}}
      style={{width:"100%",height:"100%",objectFit:"cover",display:"block",opacity:loaded?1:0,transition:"opacity 0.35s"}}/>
  </div>;
}
function CardData({a}){
  const cc=CC[a.type]||"#64748B";
  const G=({pairs})=>{
    const valid=(pairs||[]).filter(([,v])=>v!=null&&v!=="");
    if(!valid.length) return null;
    return <div style={{display:"grid",gridTemplateColumns:"auto 1fr",gap:"3px 9px",background:"var(--bg2)",borderRadius:8,padding:"7px 10px",border:"1px solid var(--bdr)",minHeight:78,alignContent:'start',width:'100%'}}>
      {valid.map(([k,v,c])=>[
        <span key={k+"k"} style={{fontSize:10,color:"var(--t2)"}}>{k}</span>,
        <span key={k+"v"} style={{fontSize:11,color:c||"var(--t1)",fontWeight:c?"600":"400",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={String(v||"")}>{v}</span>
      ])}
    </div>;
  };
  if(a.type==="Airport") return <G pairs={[["ICAO",a.rw&&a.rw.icao,cc],["Municipality",(a.rw&&a.rw.municipality)||(a.rw&&a.rw.city)],["Runways",a.rw&&a.rw.runways&&a.rw.runways.length+" rwys"],["Elev",a.rw&&a.rw.elev]]}/>;
  if(a.type==="Aircraft") return <G pairs={[["Manufacturer",a.rw&&a.rw.mfr,cc],["Model",a.rw&&a.rw.model],["Range (NM)",a.rw&&a.rw.range_nm],["Cruise",a.rw&&a.rw.cruise]]}/>;
  if(a.type==="Scenery") return <G pairs={[["Region",a.rw&&(a.rw.region||locDisplay(a))],["Country",a.rw&&a.rw.country&&abbr(a.rw.country),cc],["Type",a.sub||(a.rw&&a.rw.scenery_type)]]}/>;
  if(a.type==="Utility") return <G pairs={[["Category",(a.rw&&a.rw.util_cat)||a.sub,cc],["Version",a.pr&&a.pr.ver&&"v"+a.pr.ver]]}/>;
  return null;
}

function entryAccent(a){
  if(!a) return null;
  if(a.entry_kind==='tool') return '#F59E0B';
  if(a.entry_kind==='community') return '#14B8A6';
  if(a.entry_kind==='official') return '#F97316';
  return null;
}
function entryBadgeLabel(a){
  if(!a) return '';
  if(a.entry_kind==='tool') return 'Local';
  if(a.entry_kind==='community') return 'Community Only';
  if(a.entry_kind==='official') return 'Marketplace';
  return '';
}
function entryGridBadgeLabel(a){
  if(!a) return '';
  if(a.entry_kind==='community') return 'Community Only';
  if(a.entry_kind==='tool') return 'Local';
  return '';
}
function entryCardTone(a){
  if(!a) return null;
  if(a.entry_kind==='tool') return 'linear-gradient(180deg, rgba(34,197,94,0.09), rgba(34,197,94,0.03))';
  if(a.entry_kind==='community') return 'linear-gradient(180deg, rgba(59,130,246,0.10), rgba(59,130,246,0.03))';
  if(a.entry_kind==='official') return 'linear-gradient(180deg, rgba(249,115,22,0.10), rgba(249,115,22,0.03))';
  return null;
}
function sourceCategoryFor(a){
  if(!a) return 'Community';
  if(a.entry_kind==='official') return 'Marketplace';
  if(a.entry_kind==='tool') return 'Local';
  return 'Community';
}
function sourceOptionsFor(addons){
  const base=['All'];
  const seen=new Set();
  (addons||[]).forEach(a=>seen.add(sourceCategoryFor(a)));
  ['Community','Marketplace','Local'].forEach(label=>{ if(seen.has(label)) base.push(label); });
  return base;
}
function storedObtainedFromOptions(){
  try{
    const raw=JSON.parse(localStorage.getItem('hangar_sources')||'null');
    if(Array.isArray(raw)&&raw.length){
      return ['All',...Array.from(new Set(raw.map(v=>String(v||'').trim()).filter(Boolean))).sort((a,b)=>String(a).localeCompare(String(b)))];
    }
  }catch(e){}
  return ['All'];
}
function addonCoordinates(a){
  if(!a) return null;
  const lat=Number((a.usr&&a.usr.map_lat)!=null?(a.usr&&a.usr.map_lat):(a.lat!=null?a.lat:(a.rw&&a.rw.lat)));
  const lon=Number((a.usr&&a.usr.map_lon)!=null?(a.usr&&a.usr.map_lon):(a.lon!=null?a.lon:(a.rw&&a.rw.lon)));
  return Number.isFinite(lat)&&Number.isFinite(lon)&&lat>=-90&&lat<=90&&lon>=-180&&lon<=180?{lat,lon}:null;
}
const US_STATE_NAME_TO_ABBR={alabama:'AL',alaska:'AK',arizona:'AZ',arkansas:'AR',california:'CA',colorado:'CO',connecticut:'CT',delaware:'DE',florida:'FL',georgia:'GA',hawaii:'HI',idaho:'ID',illinois:'IL',indiana:'IN',iowa:'IA',kansas:'KS',kentucky:'KY',louisiana:'LA',maine:'ME',maryland:'MD',massachusetts:'MA',michigan:'MI',minnesota:'MN',mississippi:'MS',missouri:'MO',montana:'MT',nebraska:'NE',nevada:'NV','new hampshire':'NH','new jersey':'NJ','new mexico':'NM','new york':'NY','north carolina':'NC','north dakota':'ND',ohio:'OH',oklahoma:'OK',oregon:'OR',pennsylvania:'PA','rhode island':'RI','south carolina':'SC','south dakota':'SD',tennessee:'TN',texas:'TX',utah:'UT',vermont:'VT',virginia:'VA',washington:'WA','west virginia':'WV',wisconsin:'WI',wyoming:'WY','district of columbia':'DC'};
function normalizeUSStateAbbr(country,state){
  const c=String(country||'').trim();
  const s=String(state||'').trim();
  if(c!=='United States' || !s) return s;
  if(/^[A-Z]{2}$/.test(s)) return s;
  return US_STATE_NAME_TO_ABBR[s.toLowerCase()]||s;
}
function defaultAirportSiteEntries(){
  return [
    {name:'SkyVector',url:'https://skyvector.com'},
    {name:'Airportdata.com',url:'https://www.airportdata.com'},
    {name:'AVIPages',url:'https://aviapages.com'},
    {name:'Wikipedia',url:'https://wikipedia.org'},
    {name:'AIRNAV',url:'https://www.airnav.com'},
  ];
}
function defaultAircraftSiteEntries(){
  return [
    {name:'Wikipedia',url:'https://wikipedia.org'},
    {name:'PlaneSpotters',url:'https://www.planespotters.net'},
    {name:'SKYbrary',url:'https://skybrary.aero'},
    {name:'Airliners.net',url:'https://www.airliners.net'},
    {name:'Simple Flying',url:'https://simpleflying.com'},
    {name:'FlightGlobal',url:'https://www.flightglobal.com'},
  ];
}
function loadSiteEntries(key,defaults){
  try{
    const raw=JSON.parse(localStorage.getItem(key)||'null');
    if(Array.isArray(raw) && raw.length){
      return raw.map(x=>({name:String((x&&x.name)||'').trim(),url:String((x&&x.url)||'').trim()})).filter(x=>x.name&&x.url);
    }
  }catch(e){}
  return defaults;
}
function siteSearchUrl(site,query){
  const raw=String((site&&site.url)||'').trim();
  let host='';
  try{ host=(new URL(raw.startsWith('http')?raw:'https://'+raw)).hostname.replace(/^www\./i,''); }catch(e){ host=raw.replace(/^https?:\/\//i,'').replace(/^www\./i,'').split('/')[0]; }
  return googleSearchUrl((host?`site:${host} `:'')+String(query||'').trim());
}

function addonTypeFor(a){
  if(!a) return '';
  return a.entry_kind==='tool' ? ((a.type&&a.type!=='External Tool')?a.type:'Utility') : (a.type||'');
}

function EnableToggle({addon,onToggled,onToggleError}){
  const [on,setOn]=useState(addon.enabled||false);
  const supported=!!(addon && addon.managed!==false && addon.entry_kind==='addon');
  const [busy,setBusy]=useState(false);
  useEffect(()=>{setOn(addon.enabled||false);},[addon.enabled, addon.id]);
  async function toggle(e){
    e.stopPropagation();
    if(busy) return;
    const requested=!on;
    setBusy(true);
    try{
      const d=await fetchJsonSafe("/api/addons/"+addon.id+"/toggle",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({enabled:requested})
      });
      const actual=!!d.enabled;
      setOn(actual);
      onToggled&&onToggled(addon.id, actual, d);
    }catch(err){
      onToggleError&&onToggleError(err, addon);
    }finally{
      setBusy(false);
    }
  }
  if(!supported){
    const label=addon&&addon.entry_kind==='tool'?'Local app':(addon&&addon.entry_kind==='community'?'Already in Community':'Inventory only');
    return <div title={label} style={{display:'inline-flex',alignItems:'center',gap:6,opacity:.9}}><span style={{fontSize:9,color:'var(--t3)',fontWeight:800,textTransform:'uppercase',letterSpacing:'0.06em'}}>{label}</span></div>;
  }
  return <div onClick={toggle} title={on?"Activated in Community folder":"Not in Community folder"}
    style={{display:"inline-flex",alignItems:"center",gap:5,cursor:busy?"wait":"pointer",userSelect:"none"}}>
    <div style={{width:34,height:18,borderRadius:9,background:on?"var(--acc)":"var(--t3)",position:"relative",transition:"background 0.2s",flexShrink:0,opacity:busy?0.6:1}}>
      <div style={{position:"absolute",top:2,left:on?16:2,width:14,height:14,borderRadius:"50%",background:"white",transition:"left 0.18s",boxShadow:"0 1px 3px rgba(0,0,0,0.3)"}}/>
    </div>
    <span style={{fontSize:9,color:on?"var(--acc)":"var(--t3)",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.06em",whiteSpace:"nowrap"}}>{on?"Active":"Off"}</span>
  </div>;
}
function AddonCard({a,selected,onClick,onFav,onTogglePick,picked,scale,onToggleEnabled,onToggleEnabledError}){
  const [hov,setHov]=useState(false),cc=(entryAccent(a)||CC[a.type]||"#64748B");
  const versionText=(a.pr&&a.pr.ver)?`Version: ${a.pr.ver}`:'';
  const imgHeight=scale==='small'?126:(scale==='large'?174:148);
  const cardHeight=scale==='small'?340:(scale==='large'?392:366);
  const dataBlock=CardData({a});
  return <div id={"addon-card-"+a.id} onClick={()=>onClick(a)} onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
    style={{background:selected?cc+"0D":hov?"var(--cardH)":(entryCardTone(a)||"var(--card)"),border:"1px solid "+(selected?cc+"50":hov?"var(--bdrH)":"var(--bdr)"),borderRadius:14,cursor:"pointer",overflow:"hidden",transition:"all 0.18s",transform:hov&&!selected?"translateY(-2px)":"none",boxShadow:selected?"0 0 0 1px "+cc+"40,0 8px 24px rgba(0,0,0,.4)":hov?"0 8px 28px rgba(0,0,0,.35)":"none",display:'flex',flexDirection:'column',height:cardHeight,minHeight:cardHeight,maxHeight:cardHeight}}>
    <div style={{position:"relative"}}>
      <AddonImg a={a} h={imgHeight}/>
      <div style={{position:"absolute",top:8,left:9,right:9,display:"flex",alignItems:"flex-start",justifyContent:"space-between",gap:8}}>
        <label onClick={e=>e.stopPropagation()} style={{display:'inline-flex',alignItems:'center',gap:6,background:'rgba(0,0,0,.62)',backdropFilter:'blur(8px)',borderRadius:18,padding:'4px 9px',fontSize:10,color:'var(--t0)',border:'1px solid var(--bdr)',cursor:'pointer'}}>
          <input type='checkbox' checked={!!picked} onChange={()=>onTogglePick&&onTogglePick(a.id)} style={{accentColor:cc}}/>
          Select
        </label>
        <div style={{display:'flex',gap:6,alignItems:'center'}}>
          <div onClick={e=>e.stopPropagation()} style={{background:'rgba(0,0,0,.64)',backdropFilter:'blur(8px)',borderRadius:18,padding:'3px 7px'}}><EnableToggle addon={a} onToggled={onToggleEnabled} onToggleError={onToggleEnabledError}/></div>
          <div onClick={e=>e.stopPropagation()} style={{background:'rgba(0,0,0,.64)',backdropFilter:'blur(8px)',borderRadius:18,padding:'4px 9px'}}><FavBtn on={a.usr.fav} onChange={v=>onFav(a.id,v)}/></div>
        </div>
      </div>
      {a.hasUpdate&&<div style={{position:'absolute',bottom:10,right:10,background:'#FBBF24',color:'#111827',borderRadius:16,padding:'3px 8px',fontSize:10,fontWeight:800}}>UPDATE</div>}
    </div>
    <div style={{padding:"11px 12px 12px",display:'flex',flexDirection:'column',flex:1,minHeight:0}}>
      <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:6,alignContent:'flex-start',minHeight:22}}><Chip label={addonTypeFor(a)} color={cc} sm/>{a.sub&&<Chip label={a.sub} color={cc} sm/>}{entryGridBadgeLabel(a)&&<Chip label={entryGridBadgeLabel(a)} color={cc} sm/>}</div>
      <div style={{fontSize:13,fontWeight:800,color:"var(--t0)",lineHeight:1.3,marginBottom:4,overflow:"hidden",display:"-webkit-box",WebkitLineClamp:2,WebkitBoxOrient:"vertical",minHeight:34}}>{a.title}</div>
      <div style={{background:'rgba(6,14,28,.35)',border:'1px solid rgba(255,255,255,.08)',borderRadius:10,padding:'8px 9px',marginBottom:dataBlock?8:10}}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:4,flexWrap:'wrap'}}>
          <div style={{fontSize:11,color:'#D6E3F3',fontWeight:700,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{a.publisher||'Unknown publisher'}</div>
          {versionText&&<div style={{fontSize:10,color:'#C2D3E8',fontWeight:700}}>{versionText}</div>}
        </div>
        {a.addon_path&&<div title={a.addon_path} style={{fontSize:10,color:'#B8CAE0',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',fontFamily:'monospace'}}>{a.addon_path}</div>}
      </div>
      {dataBlock&&<div style={{minHeight:82,display:'flex',alignItems:'stretch',marginBottom:2}}>{dataBlock}</div>}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginTop:'auto',paddingTop:dataBlock?9:0,gap:8,minHeight:18}}>
        <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>{(a.usr.tags||[]).slice(0,2).map(t=><Chip key={t} label={t} color="var(--t3)" sm/>)}</div>
        {a.usr.rating>0&&<Stars v={a.usr.rating} sz={11}/>}
      </div>
    </div>
  </div>;
}

function CompactAddonRow({a,picked,onTogglePick,onOpen,onActionLabel,onAction,onActionColor}){
  const cc=entryAccent(a)||CC[a.type]||'var(--acc)';
  return <div onClick={()=>onOpen&&onOpen(a)} style={{display:'grid',gridTemplateColumns:'70px 1fr auto',gap:10,alignItems:'center',padding:'9px 10px',background:(entryCardTone(a)||'var(--bg1)'),border:'1px solid var(--bdr)',borderRadius:12,cursor:'pointer'}}>
    <div style={{width:70,height:42,borderRadius:9,overflow:'hidden',border:'1px solid var(--bdr)',flexShrink:0}}><AddonImg a={a} h={42}/></div>
    <div style={{minWidth:0}}>
      <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap',marginBottom:3}}><Chip label={addonTypeFor(a)} color={cc} sm/>{a.sub&&<Chip label={a.sub} color={cc} sm/>}{entryBadgeLabel(a)&&<Chip label={entryBadgeLabel(a)} color={cc} sm/>}</div>
      <div style={{fontSize:12,fontWeight:800,color:'var(--t0)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{a.title}</div>
      <div style={{fontSize:11,color:'var(--t2)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{a.publisher||'Unknown publisher'}{a.pr&&a.pr.ver?` • v${a.pr.ver}`:''}</div>
    </div>
    <div onClick={e=>e.stopPropagation()} style={{display:'flex',alignItems:'center',gap:8,justifyContent:'flex-end'}}>
      <label style={{display:'inline-flex',alignItems:'center',gap:6,fontSize:11,color:'var(--t1)',cursor:'pointer'}}>
        <input type='checkbox' checked={!!picked} onChange={()=>onTogglePick&&onTogglePick(a.id)}/>
        Select
      </label>
      {onAction&&<Btn label={onActionLabel||'Action'} color={onActionColor||'var(--acc)'} sm onClick={()=>onAction(a)}/>}    
    </div>
  </div>;
}

function CompactAddonTile({a,picked,onTogglePick,onOpen,imageHeight=78}){
  const cc=entryAccent(a)||CC[a.type]||'var(--acc)';
  const diskMb=formatWholeNumber((a.pr&&Number(a.pr.size_mb))||0);
  const tileHeight=Math.max(imageHeight+154,236);
  return <div onClick={()=>onOpen&&onOpen(a)} style={{background:(entryCardTone(a)||'var(--bg1)'),border:'1px solid var(--bdr)',borderRadius:14,padding:10,cursor:'pointer',display:'flex',flexDirection:'column',gap:8,height:tileHeight,minHeight:tileHeight,maxHeight:tileHeight,boxSizing:'border-box',alignSelf:'start',overflow:'hidden'}}>
    <div style={{width:'100%',height:imageHeight,borderRadius:10,overflow:'hidden',border:'1px solid var(--bdr)',flexShrink:0}}><AddonImg a={a} h={imageHeight}/></div>
    <div style={{display:'flex',gap:6,flexWrap:'wrap'}}><Chip label={addonTypeFor(a)} color={cc} sm/>{a.sub&&<Chip label={a.sub} color={cc} sm/>}{entryBadgeLabel(a)&&<Chip label={entryBadgeLabel(a)} color={cc} sm/>}</div>
    <div style={{fontSize:12,fontWeight:800,color:'var(--t0)',lineHeight:1.35,display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden'}}>{a.title}</div>
    <div style={{fontSize:10,color:'var(--t1)',fontWeight:600,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{a.publisher||'Unknown publisher'}{a.pr&&a.pr.ver?` • v${a.pr.ver}`:''}</div>
    <div style={{display:'flex',justifyContent:'space-between',gap:8,alignItems:'center'}}>
      <div style={{fontSize:10,color:'var(--t3)'}}>{diskMb} MB</div>
      {a.usr&&a.usr.rating>0&&<Stars v={a.usr.rating} sz={10}/>}
    </div>
    <label onClick={e=>e.stopPropagation()} style={{display:'inline-flex',alignItems:'center',gap:6,fontSize:11,color:'var(--t1)',cursor:'pointer',alignSelf:'flex-end'}}>
      <input type='checkbox' checked={!!picked} onChange={()=>onTogglePick&&onTogglePick(a.id)}/>
      Select
    </label>
  </div>;
}

function QuickPanel({a,onOpen,onFav,onNote,onLitePopulate,onRemoveSingle,onLaunch,removeFolders,setRemoveFolders,ignoreOnRemove,setIgnoreOnRemove,aiPopulateStatus,collectionMemberships,onRemoveMembership,onToggleEnabled,onToggleEnabledError}){
  const cc=(entryAccent(a)||CC[a.type]||"#64748B"),pr=a.pr||{}; const launchable=a.entry_kind==='tool' && !!(a.launch_path||a.addon_path);
  const priceStr=pr.price===0?"Free":pr.price?formatCurrencyValue(pr.price):"—";
  const aiStatus=aiPopulateStatus&&aiPopulateStatus.addonId===a.id?aiPopulateStatus:null;
  const sectionCard={background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:14,padding:'13px 14px',marginBottom:12};
  return <div className="qp-wrap" style={{background:'linear-gradient(180deg,var(--bg1),var(--bg0))'}}>
    <div style={{position:'relative',flexShrink:0,borderBottom:'1px solid var(--bdr)'}}>
      <AddonImg a={a} h={164}/>
      <div style={{position:'absolute',inset:0,background:'linear-gradient(180deg,rgba(5,12,24,.05),rgba(5,12,24,.82))'}}/>
      <div style={{position:'absolute',top:12,left:12,right:12,display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:8}}>
        <div style={{display:'flex',gap:6,flexWrap:'wrap'}}><Chip label={addonTypeFor(a)} color={cc} sm/>{a.sub&&<Chip label={a.sub} color={cc} sm/>}</div>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <EnableToggle addon={a} onToggled={onToggleEnabled} onToggleError={onToggleEnabledError}/>
          <div style={{background:'rgba(0,0,0,.42)',backdropFilter:'blur(10px)',border:'1px solid rgba(255,255,255,.12)',borderRadius:18,padding:'4px 9px'}}><FavBtn on={a.usr.fav} onChange={v=>onFav(a.id,v)} sz={18}/></div>
        </div>
      </div>
      <div style={{position:'absolute',left:14,right:14,bottom:14}}>
        <div style={{fontSize:18,fontWeight:800,color:'#fff',lineHeight:1.22,marginBottom:7,textShadow:'0 2px 10px rgba(0,0,0,.45)'}}>{a.title}</div>
        <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
          <Stars v={a.usr&&a.usr.rating?a.usr.rating:0} sz={13}/>
          <span style={{fontSize:11,color:'rgba(255,255,255,.82)'}}>{a.usr&&a.usr.rating?`${a.usr.rating}/5`:'Not rated yet'}</span>
          {a.hasUpdate&&<span style={{color:'#FDE68A',fontWeight:800,fontSize:11}}>Update available</span>}
        </div>
      </div>
    </div>
    <div className="qp-body" style={{padding:'14px'}}>
      <div style={sectionCard}>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:8}}>
          <Btn label="Open Full Detail" color="var(--acc)" onClick={()=>onOpen(a)} style={{justifyContent:'center',fontWeight:700,minHeight:38}}/>
          <Btn label="Notes" color="var(--amb)" onClick={()=>onNote(a)} style={{justifyContent:'center',fontWeight:700,minHeight:38}}/>
        </div>
        <Btn label="Populate with AI Data" color="var(--vio)" onClick={()=>onLitePopulate&&onLitePopulate(a)} full style={{justifyContent:'center',fontWeight:800,minHeight:40,marginBottom:aiStatus?10:0}}/>
        {aiStatus&&<div style={{background:'var(--bg0)',border:'1px solid '+(aiStatus.kind==='error'?'rgba(248,113,113,.35)':'var(--bdr)'),borderRadius:12,padding:'10px 11px'}}>
          <div style={{display:'flex',justifyContent:'space-between',gap:8,marginBottom:6}}><span style={{fontSize:11,color:'var(--t1)',fontWeight:700}}>{aiStatus.message||'Working…'}</span><span style={{fontSize:11,color:aiStatus.kind==='error'?'var(--red)':aiStatus.pct===100?'var(--grn)':'var(--vio)',fontWeight:800}}>{aiStatus.pct||0}%</span></div>
          <div style={{height:7,background:'var(--bg3)',borderRadius:999,overflow:'hidden'}}><div style={{height:'100%',width:(aiStatus.pct||0)+'%',background:aiStatus.kind==='error'?'var(--red)':aiStatus.pct===100?'var(--grn)':'var(--vio)',borderRadius:999,transition:'width .25s'}}/></div>
          {aiStatus.pct===100&&aiStatus.kind!=='error'&&<div style={{fontSize:10,color:'var(--grn)',marginTop:6,fontWeight:700}}>Completed</div>}
        </div>}
      </div>
      <div style={sectionCard}>
        <div style={{fontSize:11,fontWeight:800,color:'var(--grn)',marginBottom:8,textTransform:'uppercase',letterSpacing:'0.08em'}}>Overview</div>
        <KVG pairs={[
          ["Installed Version",pr.ver||null],
          ["Current Version",pr.latest_ver||null],
          ["Initial Release Date",formatDateValue(normalizeDateValue(pr.released||''))],
          ["Current Version Date",formatDateValue(normalizeDateValue(pr.latest_ver_date||''))],
          ["List Price",priceStr,pr.price===0?"var(--grn)":null],
          ["Store",pr.source_store],
          ["Publisher",a.publisher],
          ["Library Source",sourceCategoryFor(a)],
          ["Obtained From",a.usr&&a.usr.source_store]
        ]}/>
      </div>
      <div style={sectionCard}>
        <div style={{fontSize:11,fontWeight:800,color:'var(--acc)',marginBottom:8,textTransform:'uppercase',letterSpacing:'0.08em'}}>Overview Summary</div>
        <div style={{fontSize:12,color:'var(--t1)',lineHeight:1.75,maxHeight:228,overflowY:'auto',paddingRight:4,marginBottom:10}} dangerouslySetInnerHTML={{__html:sanitizeHtmlForTheme(a.summary||'')}}/>
        {a.type==='Airport'&&<KVG cols={2} pairs={[["Country",a.rw&&a.rw.country],["State / Province / Region",(a.rw&&a.rw.country)==='United States'?(a.rw&&a.rw.state):((a.rw&&a.rw.country)==='Canada'?fullCanadaProvince((a.rw&&a.rw.province)||''):(a.rw&&a.rw.region||a.rw&&a.rw.state||a.rw&&a.rw.province))]]}/>}
        {a.type==='Aircraft'&&<KVG cols={2} pairs={[["Manufacturer",a.rw&&((a.rw.manufacturer_full_name)||a.rw.mfr)],["Model",a.rw&&a.rw.model],["Country of Origin",a.rw&&a.rw.country_of_origin]]}/>}
        {a.usr&&a.usr.notes&&<div style={{marginTop:10,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:10,padding:'10px 11px'}}><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:4}}>Note</div><div style={{fontSize:12,color:'var(--t1)',lineHeight:1.65,whiteSpace:'pre-wrap'}}>{a.usr.notes}</div></div>}
        {collectionMemberships&&collectionMemberships.length>0&&<div style={{marginTop:10}}><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:6}}>Collections</div><div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{collectionMemberships.map(p=><div key={p.id} style={{display:'inline-flex',alignItems:'center',gap:7,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:18,padding:'4px 10px'}}><span style={{fontSize:11,color:'var(--t1)'}}>{p.name}</span><button onClick={()=>onRemoveMembership&&onRemoveMembership(p,a.id)} style={{background:'none',border:'none',color:'var(--red)',cursor:'pointer',fontSize:14,lineHeight:1}}>×</button></div>)}</div></div>}
      </div>
    </div>
    <div className="qp-foot" style={{display:'block',padding:'14px',borderTop:'1px solid var(--bdr)',background:'var(--bg1)'}}>
      <div style={{background:'rgba(248,113,113,.06)',border:'1px solid rgba(248,113,113,.24)',borderRadius:14,padding:'13px 14px'}}>
        <div style={{fontSize:11,fontWeight:800,color:'var(--red)',marginBottom:8,textTransform:'uppercase',letterSpacing:'0.08em'}}>Remove Add-on</div>
        <label style={{display:'flex',alignItems:'center',gap:8,fontSize:12,color:'var(--t1)',marginBottom:8}}><input type='checkbox' checked={removeFolders} onChange={e=>{ setRemoveFolders(e.target.checked); if(e.target.checked && setIgnoreOnRemove) setIgnoreOnRemove(false); }}/> Also remove the add-on folder from disk</label>
        {!removeFolders&&<label style={{display:'flex',alignItems:'center',gap:8,fontSize:12,color:'var(--t1)',marginBottom:10}}><input type='checkbox' checked={!!ignoreOnRemove} onChange={e=>setIgnoreOnRemove&&setIgnoreOnRemove(e.target.checked)}/> Exclude from future scans if the folder stays on disk</label>}
        <Btn label='Remove Add-on from Library' color='var(--red)' full onClick={()=>onRemoveSingle&&onRemoveSingle(a)} style={{justifyContent:'center',fontWeight:800,minHeight:40}}/>
      </div>
    </div>
  </div>;
}


function CollectionStrip({profiles=[],collectionStatsById={},activeFilterIds=[],onToggle,onClear,stripRef,actionScope,setActionScope,actionMode,setActionMode,onExecuteAction,onScrollLeft,onScrollRight}){
  const activeSet=new Set(activeFilterIds||[]);
  const Chip=({profile})=>{
    const count=(collectionStatsById&&collectionStatsById[profile.id]&&collectionStatsById[profile.id].count)||profile.addon_ids?.length||0;
    const active=activeSet.has(profile.id);
    return (
      <button onClick={()=>onToggle&&onToggle(profile)} style={{display:'flex',alignItems:'center',gap:8,padding:'8px 12px',borderRadius:999,border:`1px solid ${active?'rgba(56,189,248,0.45)':'var(--bdr)'}`,background:active?'rgba(56,189,248,0.14)':'rgba(255,255,255,0.04)',color:'var(--t0)',cursor:'pointer',whiteSpace:'nowrap',fontSize:'var(--fs-sm)',fontWeight:600}}>
        <span>{profile.name||'Collection'}</span>
        <span style={{padding:'2px 7px',borderRadius:999,background:'rgba(255,255,255,0.08)',color:'var(--t1)',fontSize:'var(--fs-xs)'}}>{count}</span>
      </button>
    );
  };
  return (
    <div style={{display:'grid',gridTemplateColumns:'auto 1fr auto',gap:10,alignItems:'center',margin:'10px 18px 12px 18px',padding:'10px 12px',border:'1px solid var(--bdr)',borderRadius:14,background:'rgba(255,255,255,0.03)'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,whiteSpace:'nowrap'}}>
        <div style={{fontSize:'var(--fs-sm)',fontWeight:700,color:'var(--t1)'}}>Collections</div>
        {!!activeFilterIds?.length && <button onClick={()=>onClear&&onClear()} style={{padding:'6px 10px',borderRadius:10,border:'1px solid var(--bdr)',background:'transparent',color:'var(--t1)',cursor:'pointer',fontSize:'var(--fs-xs)'}}>Clear</button>}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'32px 1fr 32px',gap:8,alignItems:'center',minWidth:0}}>
        <button onClick={()=>onScrollLeft&&onScrollLeft()} style={{height:32,borderRadius:10,border:'1px solid var(--bdr)',background:'transparent',color:'var(--t1)',cursor:'pointer'}}>‹</button>
        <div ref={stripRef} style={{display:'flex',gap:8,overflowX:'auto',scrollbarWidth:'thin',paddingBottom:2}}>
          {(profiles||[]).map(profile=><Chip key={profile.id} profile={profile}/>) }
        </div>
        <button onClick={()=>onScrollRight&&onScrollRight()} style={{height:32,borderRadius:10,border:'1px solid var(--bdr)',background:'transparent',color:'var(--t1)',cursor:'pointer'}}>›</button>
      </div>
      <div style={{display:'flex',alignItems:'center',gap:8,justifyContent:'flex-end',flexWrap:'wrap'}}>
        <select value={actionScope||'selected'} onChange={e=>setActionScope&&setActionScope(e.target.value)} style={{padding:'7px 10px',minWidth:120}}>
          <option value='selected'>Selected Collections</option>
          <option value='all'>All Collections</option>
        </select>
        <select value={actionMode||'preview'} onChange={e=>setActionMode&&setActionMode(e.target.value)} style={{padding:'7px 10px',minWidth:110}}>
          <option value='preview'>Preview</option>
          <option value='apply'>Apply</option>
        </select>
        <button onClick={()=>onExecuteAction&&onExecuteAction()} style={{padding:'8px 12px',borderRadius:10,border:'1px solid rgba(56,189,248,0.35)',background:'rgba(56,189,248,0.12)',color:'var(--t0)',cursor:'pointer',fontWeight:700,fontSize:'var(--fs-sm)'}}>Execute</button>
      </div>
    </div>
  );
}

function MultiSelectPanel({items,removeFolders,setRemoveFolders,ignoreOnRemove,setIgnoreOnRemove,onRemove,onCreateProfile,onAddToExistingCollection,profiles,onClearSelection,onBulkUpdate,activeCollection,onRemoveFromActiveCollection}){
  const [collectionName,setCollectionName]=useState('');
  const [targetCollectionId,setTargetCollectionId]=useState('');
  const [bulkType,setBulkType]=useState('');
  const [bulkSubtype,setBulkSubtype]=useState('');
  const subtypeOptions=bulkType?(DEFAULT_SUBTYPE_OPTIONS[bulkType]||[]):[];
  useEffect(()=>{ if(subtypeOptions.length && bulkSubtype && !subtypeOptions.includes(bulkSubtype)) setBulkSubtype(''); },[bulkType]);
  return <div className='qp-wrap'>
    <div style={{padding:'14px 16px',borderBottom:'1px solid var(--bdr)',display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:10}}>
      <div><div style={{fontSize:15,fontWeight:800,color:'var(--t0)',marginBottom:4}}>Selected Add-ons</div><div style={{fontSize:12,color:'var(--t2)'}}>{items.length} add-on(s) selected for batch actions.</div></div>
      <Btn label='Clear All' color='var(--t2)' sm onClick={onClearSelection}/>
    </div>
    <div className='qp-body'>
      <div style={{display:'flex',flexDirection:'column',gap:8,marginBottom:14}}>
        {items.map(it=><div key={it.id} style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:10,padding:'10px 12px'}}><div style={{fontSize:12,fontWeight:700,color:'var(--t0)'}}>{it.title}</div><div style={{fontSize:11,color:'var(--t2)'}}>{it.publisher}{it.pr&&it.pr.ver?` • v${it.pr.ver}`:''}</div></div>)}
      </div>
      {activeCollection&&<div style={{background:'rgba(167,139,250,0.08)',border:'1px solid rgba(167,139,250,0.22)',borderRadius:12,padding:'12px 13px',marginBottom:14}}><div style={{fontSize:11,fontWeight:800,color:'var(--vio)',marginBottom:6,textTransform:'uppercase',letterSpacing:'0.08em'}}>Active Collection Filter</div><div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:8}}>The library is currently filtered to <strong style={{color:'var(--t0)'}}>{activeCollection.name}</strong>. You can remove the selected add-ons from that collection directly.</div><Btn label='Remove Selected from Current Collection' color='var(--vio)' onClick={()=>onRemoveFromActiveCollection&&onRemoveFromActiveCollection(activeCollection)} full style={{justifyContent:'center',fontWeight:700}}/></div>}
      <div style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 13px',marginBottom:14}}>
        <div style={{fontSize:11,fontWeight:800,color:'var(--vio)',marginBottom:6,textTransform:'uppercase',letterSpacing:'0.08em'}}>Collections</div>
        <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:8}}>Save this selection as a new collection or add it to an existing one for later filtering and symbolic-link management.</div>
        <input value={collectionName} onChange={e=>setCollectionName(e.target.value)} placeholder='New collection name' style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12,marginBottom:8}}/>
        <Btn label='Create Collection from Selection' color='var(--vio)' onClick={()=>{ if(collectionName.trim()) onCreateProfile&&onCreateProfile(collectionName.trim()); }} full style={{justifyContent:'center',fontWeight:700,marginBottom:10}}/>
        <div style={{height:1,background:'var(--bdr)',margin:'10px 0'}}/>
        <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
          <select value={targetCollectionId} onChange={e=>setTargetCollectionId(e.target.value)} style={{flex:1,minWidth:0,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}>
            <option value=''>Add to existing collection…</option>
            {(profiles||[]).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <Btn label='Add Selection' color='var(--grn)' sm disabled={!targetCollectionId} onClick={()=>{ const p=(profiles||[]).find(x=>x.id===targetCollectionId); if(p&&onAddToExistingCollection) onAddToExistingCollection(p); }}/>
        </div>
      </div>
      <div style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 13px',marginBottom:14}}>
        <div style={{fontSize:11,fontWeight:800,color:'var(--acc)',marginBottom:6,textTransform:'uppercase',letterSpacing:'0.08em'}}>Bulk Change Data</div>
        <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:8}}>Apply a Type and optional Subtype to every selected add-on.</div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:8}}>
          <select value={bulkType} onChange={e=>{setBulkType(e.target.value);setBulkSubtype('');}} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',color:'var(--t1)',borderRadius:8,padding:'8px 10px',fontSize:12}}><option value=''>Choose type</option>{ADDON_TYPE_OPTIONS.map(t=><option key={t} value={t}>{t}</option>)}</select>
          <ClearableDatalistInput value={bulkSubtype} setValue={setBulkSubtype} list='bulk-subtype-opts' placeholder='Subtype (optional)' inputStyle={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,color:'var(--t0)',fontSize:12}}/>
          <datalist id='bulk-subtype-opts'>{subtypeOptions.map(s=><option key={s} value={s}/>)}</datalist>
        </div>
        <Btn label='Apply Type / Subtype to Selected' color='var(--acc)' onClick={()=>bulkType&&onBulkUpdate&&onBulkUpdate(bulkType,bulkSubtype)} full style={{justifyContent:'center',fontWeight:700}}/>
      </div>
      <div style={{background:'rgba(248,113,113,0.08)',border:'1px solid rgba(248,113,113,0.22)',borderRadius:12,padding:'12px 13px'}}>
        <div style={{fontSize:11,fontWeight:800,color:'var(--red)',marginBottom:6,textTransform:'uppercase',letterSpacing:'0.08em'}}>Remove Selected Add-ons</div>
        <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:8}}>This removes the selected items from the library. Folder deletion is optional and kept separate on purpose.</div>
        <label style={{display:'inline-flex',alignItems:'center',gap:8,fontSize:12,color:'var(--t1)',marginBottom:8}}><input type='checkbox' checked={removeFolders} onChange={e=>{ setRemoveFolders(e.target.checked); if(e.target.checked && setIgnoreOnRemove) setIgnoreOnRemove(false); }}/> Also remove local add-on folders</label>
        {!removeFolders&&<label style={{display:'inline-flex',alignItems:'center',gap:8,fontSize:12,color:'var(--t1)',marginBottom:12}}><input type='checkbox' checked={!!ignoreOnRemove} onChange={e=>setIgnoreOnRemove&&setIgnoreOnRemove(e.target.checked)}/> Exclude from future scans if the folders stay on disk</label>}
        <Btn label='Remove Selected Add-ons from Library' color='var(--red)' onClick={onRemove} full style={{justifyContent:'center',fontWeight:700}}/>
      </div>
    </div>
  </div>;
}

function NotesModal({a,onSave,onClose}){
  const [txt,setTxt]=useState(a.usr.notes||"");
  return <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.8)",backdropFilter:"blur(6px)",zIndex:9999,display:"flex",alignItems:"center",justifyContent:"center"}} onClick={onClose}>
    <div onClick={e=>e.stopPropagation()} style={{background:"var(--bg1)",border:"1px solid var(--bdr)",borderRadius:14,width:500,maxWidth:"94vw",boxShadow:"0 24px 64px rgba(0,0,0,.6)"}}>
      <div style={{padding:"16px 20px",borderBottom:"1px solid var(--bdr)",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div><div style={{fontSize:14,fontWeight:700,color:"var(--t0)"}}>Edit Notes</div><div style={{fontSize:11,color:"var(--t2)"}}>{a.title}</div></div>
        <button onClick={onClose} style={{background:"none",border:"none",color:"var(--t2)",fontSize:20,cursor:"pointer",lineHeight:1}}>x</button>
      </div>
      <div style={{padding:20}}>
        <textarea value={txt} onChange={e=>setTxt(e.target.value)} placeholder="Tips, impressions, settings, known issues..."
          style={{width:"100%",height:160,background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:8,padding:"10px 12px",color:"var(--t0)",fontSize:13,resize:"vertical",outline:"none",lineHeight:1.65}}/>
        <div style={{display:"flex",gap:8,marginTop:12}}>
          <Btn label="Save Notes" color="var(--grn)" onClick={()=>onSave(a.id,txt)} style={{flex:1,justifyContent:"center"}}/>
          <Btn label="Cancel" color="var(--t2)" onClick={onClose}/>
        </div>
      </div>
    </div>
  </div>;
}

function OverviewTab({a,onSave,injected,onInjected}){
  const editorRef=useRef(null);
  const fieldStyle={width:"100%",background:"var(--bg0)",border:"1px solid var(--bdr)",borderRadius:7,padding:"8px 11px",color:"var(--t0)",fontSize:12,outline:"none"};
  const [title,setTitle]=useState(a.title||"");
  const [publisher,setPublisher]=useState(a.publisher||"");
  const [version,setVersion]=useState((a.pr&&a.pr.ver)||"");
  const [latestVersion,setLatestVersion]=useState((a.pr&&a.pr.latest_ver)||"");
  const [released,setReleased]=useState(formatDateValue((a.pr&&a.pr.released)||""));
  const [latestVersionDate,setLatestVersionDate]=useState(formatDateValue((a.pr&&a.pr.latest_ver_date)||""));
  const [listPrice,setListPrice]=useState((a.pr&&a.pr.price)!==undefined && (a.pr&&a.pr.price)!==null ? formatCurrencyValue(a.pr.price) : "");
  const [packageName,setPackageName]=useState(a.package_name||"");
  const [manufacturer,setManufacturer]=useState((a.rw&&a.rw.mfr)||(a.pr&&a.pr.manufacturer)||"");
  const [icao,setIcao]=useState((a.rw&&a.rw.icao)||"");
  const [saved,setSaved]=useState(false);
  const [lookuping,setLookuping]=useState(false);
  const [lookupMsg,setLookupMsg]=useState("");
  useEffect(()=>{
    setTitle(a.title||""); setPublisher(a.publisher||""); setVersion((a.pr&&a.pr.ver)||""); setLatestVersion((a.pr&&a.pr.latest_ver)||""); setReleased(formatDateValue((a.pr&&a.pr.released)||"")); setLatestVersionDate(formatDateValue((a.pr&&a.pr.latest_ver_date)||"")); setListPrice((a.pr&&a.pr.price)!==undefined && (a.pr&&a.pr.price)!==null ? formatCurrencyValue(a.pr.price) : ""); setPackageName(a.package_name||"");
    setManufacturer((a.rw&&a.rw.mfr)||(a.pr&&a.pr.manufacturer)||""); setIcao((a.rw&&a.rw.icao)||""); setLookupMsg("");
    if(editorRef.current) applyThemedHtml(editorRef.current,a.summary||"");
  },[a.id]);
  useEffect(()=>{ if(injected&&editorRef.current){ applyThemedHtml(editorRef.current,injected); if(onInjected)onInjected(); } },[injected]);
  async function populateWithGemini(){
    try{
      setLookuping(true); setLookupMsg("");
      const data=await fetchJsonSafe('/api/ai/populate-lite/'+a.id,{method:'POST'});
      if(data.latest_version) setLatestVersion(String(data.latest_version));
      if(data.latest_version_date) setLatestVersionDate(formatDateValue(data.latest_version_date));
      if(data.released) setReleased(formatDateValue(data.released));
      if(data.price!==undefined && data.price!==null) setListPrice(formatCurrencyValue(data.price));
      if(data.summary_html && editorRef.current) applyThemedHtml(editorRef.current,data.summary_html);
      const sourceLabel=shortUrlLabel((data.source_url||((data.sources&&data.sources[0])||'')));
      const sourceTxt=sourceLabel?(' Source: '+sourceLabel+'.'):'';
      const retryTxt=data.search_candidate?(' Using search: '+data.search_candidate):'';
      const providerTxt=data.provider_name?(' using '+data.provider_name):'';
      setLookupMsg('Populate complete'+providerTxt+(sourceTxt?(' '+sourceTxt):'.')+retryTxt);
    }catch(e){ setLookupMsg((e&&e.message)||'Lookup failed.'); }
    finally{ setLookuping(false); }
  }
  function save(){
    const payload={summary:editorRef.current?sanitizeHtmlForTheme(editorRef.current.innerHTML):"",title,publisher,version,latest_version:latestVersion,latest_version_date:normalizeDateValue(latestVersionDate),released:normalizeDateValue(released),package_name:packageName};
    const parsedPrice=String(listPrice||"").trim()==="" ? undefined : Number(String(listPrice).replace(/[^0-9.]/g,''));
    if(parsedPrice!==undefined && !Number.isNaN(parsedPrice)) payload.price=parsedPrice;
    if(a.type==="Aircraft") payload.manufacturer=manufacturer;
    if(a.type==="Airport") payload.rw_override={icao};
    onSave&&onSave(a.id,payload);
    setSaved(true); setTimeout(()=>setSaved(false),1800);
  }
  return <div style={{display:"flex",flexDirection:"column",gap:14,minHeight:0}}>
    <div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:14}}>
      <div><DL label="Product Data" color="var(--grn)"/><div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        <div style={{gridColumn:"1 / -1"}}><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Title</div><input value={title} onChange={e=>setTitle(e.target.value)} style={fieldStyle}/></div>
        {a.type==="Aircraft"&&<div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Manufacturer</div><input value={manufacturer} onChange={e=>setManufacturer(e.target.value)} style={fieldStyle}/></div>}
        {a.type==="Airport"&&<div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>ICAO</div><input value={icao} onChange={e=>setIcao(e.target.value.toUpperCase())} style={fieldStyle}/></div>}
        <div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Publisher</div><input value={publisher} onChange={e=>setPublisher(e.target.value)} style={fieldStyle}/></div>
        <div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Installed Version</div><input value={version} onChange={e=>setVersion(e.target.value)} style={fieldStyle}/></div>
        <div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Current Version</div><input value={latestVersion} onChange={e=>setLatestVersion(e.target.value)} style={fieldStyle}/></div>
        <div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Initial Release Date</div><input value={released} onChange={e=>setReleased(e.target.value)} style={fieldStyle}/></div>
        <div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Current Version Date</div><input value={latestVersionDate} onChange={e=>setLatestVersionDate(e.target.value)} style={fieldStyle}/></div>
        <div><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>List Price</div><input value={listPrice} onChange={e=>setListPrice(e.target.value)} style={fieldStyle}/></div>
        <div style={{gridColumn:"1 / -1"}}><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Package Name</div><input value={packageName} onChange={e=>setPackageName(e.target.value)} style={fieldStyle}/></div>
        <div style={{gridColumn:"1 / -1"}}><div style={{fontSize:10,color:"var(--t2)",marginBottom:4}}>Addon Path</div><input value={a.addon_path||""} readOnly style={{...fieldStyle,color:"var(--t2)"}}/></div>
      </div></div>
      <div><DL label="Current Classification" color="var(--amb)"/><KVG pairs={[["Type",addonTypeFor(a)],["Subtype",a.sub],["Library Source",sourceCategoryFor(a)],["Obtained From",a.usr&&a.usr.source_store],["Rating",a.usr&&a.usr.rating?`${a.usr.rating}/5`:""]]} cols={1}/><div style={{marginTop:12,fontSize:11,color:"var(--t2)",lineHeight:1.6}}>Type, subtype, notes, tags, rating, and <strong style={{color:"var(--t1)"}}>Obtained From</strong> are editable in <strong style={{color:"var(--t1)"}}>Your Data</strong>. <strong style={{color:"var(--t1)"}}>Library Source</strong> is read-only and shows how the add-on entered the library.</div></div>
    </div>
    <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center'}}><Btn label={lookuping?"Populating with selected AI…":"Populate with selected AI"} color="var(--vio)" onClick={populateWithGemini} disabled={lookuping}/><Btn label='Reformat Overview' color='var(--t2)' onClick={()=>{if(editorRef.current) applyReformatToEditor(editorRef.current,{stripImages:true});}}/><Btn label={saved?"Saved!":"Save Overview"} color={saved?"var(--grn)":"var(--acc)"} onClick={save}/>{lookupMsg&&<span style={{fontSize:11,color:"var(--t2)"}}>{lookupMsg}</span>}</div>
    <div style={{fontSize:10,color:'var(--t3)',marginTop:-6}}>Reformat Overview cleans pasted HTML into a darker-theme-friendly reading layout, strips most page chrome, and fixes bullet/list indentation.</div>
    <div><DL label="Overview Summary" color="var(--acc)"/><style>{".overview-editor:empty:before{content:attr(data-placeholder);color:var(--t3);pointer-events:none;}"}</style><div ref={editorRef} className="overview-editor theme-html" contentEditable suppressContentEditableWarning data-placeholder="Paste HTML-enabled summary here..." style={{width:"100%",minHeight:"48vh",height:"58vh",maxHeight:"82vh",overflowY:"auto",resize:"vertical",background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:8,padding:"12px 14px",color:"var(--t0)",fontSize:13,outline:"none",lineHeight:1.7}}/></div>
  </div>;
}

function DocsTab({a}){
  const docs=(a.docs||[]);
  const [sel,setSel]=useState(0);
  useEffect(()=>{setSel(0);},[a.id]);
  if(!docs.length) return <div style={{textAlign:"center",padding:"40px 0",color:"var(--t2)",fontSize:13}}>No documentation files were found for this addon.</div>;
  const current=docs[Math.min(sel,docs.length-1)]||docs[0];
  const url="/api/docs/"+a.id+"/"+Math.min(sel,docs.length-1);
  const isPdf=((current&&current.name)||"").toLowerCase().endsWith(".pdf");
  return <div style={{display:"grid",gridTemplateColumns:"320px 1fr",gap:14,height:"calc(100vh - 220px)",minHeight:480}}>
    <div style={{background:"var(--bg1)",border:"1px solid var(--bdr)",borderRadius:12,overflow:"hidden",display:"flex",flexDirection:"column",minHeight:0}}>
      <div style={{padding:"12px 14px",borderBottom:"1px solid var(--bdr)",fontSize:12,fontWeight:700,color:"var(--t0)"}}>Documentation</div>
      <div style={{flex:1,overflowY:"auto",padding:10}}>
        {docs.map((d,i)=><div key={d.path||i} onClick={()=>setSel(i)} style={{background:i===sel?"var(--accD)":"transparent",border:"1px solid "+(i===sel?"var(--accB)":"var(--bdr)"),borderRadius:10,padding:"10px 12px",marginBottom:8,cursor:"pointer"}}><div style={{fontSize:12,color:i===sel?"var(--t0)":"var(--t1)",fontWeight:600,wordBreak:"break-word"}}>{d.name}</div><div style={{fontSize:10,color:"var(--t3)",marginTop:4,wordBreak:"break-all"}}>{d.path}</div></div>)}
      </div>
    </div>
    <div style={{background:"var(--bg1)",border:"1px solid var(--bdr)",borderRadius:12,overflow:"hidden",display:"flex",flexDirection:"column",minHeight:0}}>
      <div style={{padding:"12px 14px",borderBottom:"1px solid var(--bdr)",display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,flexWrap:"wrap"}}>
        <div><div style={{fontSize:12,fontWeight:700,color:"var(--t0)"}}>{current&&current.name}</div><div style={{fontSize:10,color:"var(--t3)"}}>{isPdf?"PDF preview":"Document preview"}</div></div>
        <a href={url} target="_blank" rel="noreferrer" style={{color:"var(--acc)",fontSize:11,fontWeight:600,textDecoration:"none"}}>Open externally</a>
      </div>
      <div style={{flex:1,minHeight:0,background:"var(--bg2)"}}>
        <object key={url} data={url+"#view=FitH"} type={isPdf?"application/pdf":"text/html"} style={{width:"100%",height:"100%",border:"none",display:"block",background:"#fff"}}><iframe src={url} title={current&&current.name||"Document"} style={{width:"100%",height:"100%",border:"none",display:"block",background:"#fff"}}/></object>
      </div>
    </div>
  </div>;
}

function RealWorldTab({a,onSave}){
  const cc=CC[a.type]||"#64748B", rw=a.rw||{};
  const [fetching,setFetching]=useState(false),[fetchMsg,setFetchMsg]=useState("");
  const [manufacturer,setManufacturer]=useState(rw.mfr||"");
  const [manufacturerFull,setManufacturerFull]=useState(rw.manufacturer_full_name||rw.mfr||"");
  const [model,setModel]=useState(rw.model||"");
  const [category,setCategory]=useState(rw.category||a.sub||"");
  const [icao,setIcao]=useState(rw.icao||"");
  const [latVal,setLatVal]=useState(rw.lat!=null?String(rw.lat):'');
  const [lonVal,setLonVal]=useState(rw.lon!=null?String(rw.lon):'');
  const [shellMode,setShellMode]=useState(null);
  const [mode,setMode]=useState('web');
  const [nativeState,setNativeState]=useState({current_url:'',current_title:'',visible:false});
  const [browserSeed,setBrowserSeed]=useState(0);
  const desktopNative=shellMode==='qt';
  const saved=useMemo(()=>((a.usr&&a.usr.data_resources)||[]).map(ensureArticleCategory),[a.id,a.usr&&a.usr.data_resources]);
  const [airportSites,setAirportSites]=useState(()=>loadSiteEntries('hangar_airport_sites', defaultAirportSiteEntries()));
  const [aircraftSites,setAircraftSites]=useState(()=>loadSiteEntries('hangar_aircraft_sites', defaultAircraftSiteEntries()));
  const aircraftQ=[manufacturerFull||manufacturer,model].filter(Boolean).join(' ').trim();
  const airportCode=(icao||rw.icao||'').trim().toUpperCase();
  const airportName=(rw.name||a.title||'').trim();
  const airportQ=(airportCode?`${airportCode} Airport`:(airportName?`${airportName} airport`:''));
  // Build the browser's default search from the saved add-on data, not from the
  // live editable inputs. Otherwise typing into Manufacturer/Model changes the
  // derived URL, which retriggers the reset effect and makes fields feel locked.
  const initialAircraftQ=[rw.manufacturer_full_name||rw.mfr||'', rw.model||a.title||''].filter(Boolean).join(' ').trim();
  const defaultQ=(a.type==='Airport'?airportQ:(initialAircraftQ||a.title||'')).trim();
  const defaultUrl=googleSearchUrl(defaultQ);
  useEffect(()=>{fetch('/api/app/info').then(r=>r.json()).then(d=>setShellMode(d.shell_mode||'browser')).catch(()=>setShellMode('browser'));},[]);
  useEffect(()=>{
    // Reset the editor only when the user changes add-ons (or when the shell
    // mode changes), not when they type into the editable fields.
    setManufacturer(rw.mfr||"");
    setManufacturerFull(rw.manufacturer_full_name||rw.mfr||"");
    setModel(rw.model||"");
    setCategory(rw.category||a.sub||"");
    setIcao(rw.icao||"");
    setLatVal(rw.lat!=null?String(rw.lat):'');
    setLonVal(rw.lon!=null?String(rw.lon):'');
    setFetchMsg("");
    setMode('web');
    setBrowserSeed(s=>s+1);
    if(desktopNative){
      fetch('/api/browser/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:defaultUrl,title:'Web Search',request_id:Date.now()})}).catch(()=>{});
    }
  },[a.id,desktopNative,defaultUrl]);
  useEffect(()=>{ function onMsg(ev){ const d=ev&&ev.data; if(d&&d.type==='hangar-native-browser-state'){ setNativeState({current_url:String(d.url||''), current_title:String(d.title||''), visible:!!d.visible}); } } window.addEventListener('message',onMsg); return ()=>window.removeEventListener('message',onMsg); },[]);
  useEffect(()=>{
    function onOpts(ev){
      const d=(ev&&ev.detail)||{};
      if(d.airport_sites) setAirportSites(d.airport_sites);
      if(d.aircraft_sites) setAircraftSites(d.aircraft_sites);
    }
    window.addEventListener('hangar-data-options-updated',onOpts);
    return ()=>window.removeEventListener('hangar-data-options-updated',onOpts);
  },[]);
  useEffect(()=>{ if(!desktopNative) return; if(mode==='saved' && (!nativeState.current_url || nativeState.current_url==='about:blank')){ fetch('/api/browser/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:googleSearchUrl(''),title:'Web Search',request_id:Date.now()})}).catch(()=>{}); } },[mode,desktopNative,nativeState.current_url]);
  async function openBrowserUrl(url,title){ if(!desktopNative) return; await fetch('/api/browser/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,title:title||url,request_id:Date.now()})}).catch(()=>{}); }
  function runOriginalSearch(){
    setMode('web');
    setBrowserSeed(s=>s+1);
    if(desktopNative){ return openBrowserUrl(defaultUrl,'Web Search'); }
  }
  async function fetchSpecs(){
    try{
      setFetching(true); setFetchMsg("");
      if(a.type==="Aircraft"){
        const data=await fetchJsonSafe('/api/ai/populate-aircraft',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({manufacturer,manufacturer_full_name:manufacturerFull||manufacturer,model})});
        const nextManufacturer=data.manufacturer||manufacturer;
        const nextManufacturerFull=data.manufacturer_full_name||manufacturerFull||manufacturer;
        const nextModel=data.model||model;
        const nextCategory=data.category||category||"";
        setManufacturer(nextManufacturer);
        setManufacturerFull(nextManufacturerFull);
        setModel(nextModel);
        setCategory(nextCategory);
        const nextRw={...rw,mfr:nextManufacturer,manufacturer_full_name:nextManufacturerFull,model:nextModel,category:nextCategory,engine:data.engine||rw.engine,engine_type:data.engine_type||rw.engine_type,max_speed:data.max_speed||rw.max_speed,cruise:data.cruise||rw.cruise,range:rw.range,range_nm:data.range_nm??rw.range_nm,ceiling:data.ceiling||rw.ceiling,seats:data.seats||rw.seats,mtow:data.mtow||rw.mtow,introduced:data.introduced||rw.introduced,fuel_capacity:data.fuel_capacity||rw.fuel_capacity,wingspan:data.wingspan||rw.wingspan,length:data.length||rw.length,height:data.height||rw.height,avionics:data.avionics||rw.avionics,variants:data.variants||rw.variants,in_production:data.in_production||rw.in_production,aircraft_cost:data.aircraft_cost||rw.aircraft_cost,country_of_origin:data.country_of_origin||rw.country_of_origin,source:data.source||'Selected AI Search',wiki_url:data.wiki_url||rw.wiki_url};
        onSave&&onSave(a.id,{manufacturer:nextManufacturer,manufacturer_full_name:nextManufacturerFull,model:nextModel,category:nextCategory,sub:data.subtype||a.sub,rw_override:nextRw});
        const sourceLabel=shortUrlLabel(data.source||'');
        setFetchMsg((data.provider_name?data.provider_name:'Selected AI')+' populated aircraft specifications.'+(sourceLabel?(' Source: '+sourceLabel+'.'):'')+(data.search_candidate?(' Search used: '+data.search_candidate):''));
      } else if(a.type==="Airport"){
        const data=await fetchJsonSafe('/api/airport/fetch-data',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({icao,title:rw.name||a.title||''})});
        const normalizedState=normalizeUSStateAbbr(data.country||rw.country, data.state||rw.state);
        const nextRw={...rw,icao:data.icao||icao,name:data.name||rw.name,city:data.city||rw.city,municipality:data.municipality||data.city||rw.municipality,country:data.country||rw.country,state:normalizedState,province:data.province||rw.province,region:data.region||normalizedState||rw.region,continent:data.continent||rw.continent,elev:data.elev||rw.elev,lat:data.lat??rw.lat,lon:data.lon??rw.lon,scheduled:data.scheduled??(data.airport_type?(data.airport_type.includes('Commercial')?'yes':'no'):rw.scheduled),airport_type:data.airport_type||rw.airport_type,runways:data.runways||rw.runways,source:data.source||'Airport Lookup',wiki_url:data.wiki_url||rw.wiki_url,home_link:data.home_link||rw.home_link,first_opened:data.first_opened||rw.first_opened,passenger_count:data.passenger_count||rw.passenger_count,cargo_count:data.cargo_count||rw.cargo_count,us_rank:data.us_rank||rw.us_rank,world_rank:data.world_rank||rw.world_rank,hub_airlines:data.hub_airlines||rw.hub_airlines};
        setIcao(nextRw.icao||'');
        setLatVal(nextRw.lat!=null?String(nextRw.lat):'');
        setLonVal(nextRw.lon!=null?String(nextRw.lon):'');
        onSave&&onSave(a.id,{sub:data.airport_type||a.sub,rw_override:nextRw});
        setFetchMsg('Fetched airport details.');
      }
    }catch(e){setFetchMsg((e&&e.message)||'Fetch failed.');}
    finally{setFetching(false);}
  }
  function saveCore(){
    if(a.type==='Aircraft'){ onSave&&onSave(a.id,{manufacturer,manufacturer_full_name:manufacturerFull,model,category,rw_override:{mfr:manufacturer,manufacturer_full_name:manufacturerFull,model,category}}); }
    if(a.type==='Airport'){ const parsedLat=latVal!==''?Number(latVal):null; const parsedLon=lonVal!==''?Number(lonVal):null; onSave&&onSave(a.id,{rw_override:{icao:icao||rw.icao||'', lat:Number.isFinite(parsedLat)?parsedLat:rw.lat, lon:Number.isFinite(parsedLon)?parsedLon:rw.lon}}); }
    setFetchMsg('Saved.');
  }
  function persistResources(next){ onSave&&onSave(a.id,{data_resources:next}); }
  function saveCurrentArticle(){ const url=nativeState.current_url||''; const title=(nativeState.current_title||url||'Article').trim(); if(!url || url==='about:blank' || String(url).startsWith('search:')) return; persistResources([...(saved||[]),ensureArticleCategory({id:'r'+Date.now(),type:'link',title,url,saved:new Date().toISOString().slice(0,10)})]); }
  function updateCategory(item,categoryLabel){ persistResources(saved.map(r=>(r.id===item.id?{...r,category:categoryLabel}:r))); }
  function removeSaved(item){ persistResources(saved.filter(r=>r.id!==item.id)); }
  function openSaved(r){ openBrowserUrl(r.url,r.title||r.url); }
  const airportSiteLinks=(airportSites||[]).map(site=>({label:site.name,url:siteSearchUrl(site, airportQ||airportName||a.title||'')})).filter(Boolean);
  const aircraftSiteLinks=(aircraftSites||[]).map(site=>({label:site.name,url:siteSearchUrl(site, aircraftQ||initialAircraftQ||a.title||'')})).filter(Boolean);
  const left = a.type==='Airport' ? <div><div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:10,flexWrap:'wrap'}}><DL label='Airport Information' color='var(--acc)'/><div style={{display:'flex',gap:8,flexWrap:'wrap'}}><Btn label={fetching?'Fetching...':'Fetch Airport Data'} color='var(--acc)' sm onClick={fetchSpecs} disabled={fetching}/><Btn label='Reset Browser' color='var(--acc)' sm onClick={runOriginalSearch} title='Reload the original search for this add-on.'/><Btn label='Save' color='var(--grn)' sm onClick={saveCore} title='Save your manual edits. Airport data fetch already saves returned data automatically.'/></div></div>{fetchMsg&&<div style={{fontSize:11,color:'var(--t2)',marginBottom:10}}>{fetchMsg}</div>}<div style={{display:'grid',gridTemplateColumns:'repeat(3,minmax(0,1fr))',gap:8,marginBottom:12}}><div><div style={{fontSize:10,color:'var(--t2)',marginBottom:4}}>ICAO (reference)</div><input value={icao} readOnly style={{width:'100%',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none',opacity:0.9}}/></div><div><div style={{fontSize:10,color:'var(--t2)',marginBottom:4}}>Latitude (optional)</div><input value={latVal} onChange={e=>setLatVal(e.target.value)} placeholder='37.61981' style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/></div><div><div style={{fontSize:10,color:'var(--t2)',marginBottom:4}}>Longitude (optional)</div><input value={lonVal} onChange={e=>setLonVal(e.target.value)} placeholder='-122.37482' style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/></div></div><div style={{fontSize:10,color:'var(--t3)',marginBottom:10}}>Coordinates are optional here and are used when automatic airport lookups are unavailable.</div><KVG pairs={[['Full Name',rw.name],['Municipality',rw.municipality||rw.city],['Coordinates',(rw.lat!=null&&rw.lon!=null)?`${rw.lat.toFixed?rw.lat.toFixed(4):rw.lat}, ${rw.lon.toFixed?rw.lon.toFixed(4):rw.lon}`:''],['Elevation',rw.elev],['Continent',rw.continent],['Country',rw.country],['Region',rw.region],['State',rw.state],['Province',rw.province],['Airport Type',rw.airport_type],['Scheduled',rw.scheduled],['Date First Opened',rw.first_opened],['US Passenger Rank',rw.us_rank],['World Passenger Rank',rw.world_rank],['Passenger Count',rw.passenger_count],['Cargo Count',rw.cargo_count],['Hub / Key Airlines',rw.hub_airlines],['Web Data Source',shortUrlLabel(rw.source)]]}/>{rw.runways&&rw.runways.length>0&&<div style={{marginTop:14}}><DL label='Runways' color='var(--acc)'/>{rw.runways.map(r=>(<div key={r.id} style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:8,padding:'9px 12px',marginBottom:6,display:'grid',gridTemplateColumns:'90px 1fr auto',gap:10,alignItems:'center'}}><span style={{fontSize:13,color:cc,fontWeight:800,fontFamily:'monospace'}}>{r.id}</span><span style={{fontSize:12,color:'var(--t1)'}}>{r.len}</span><span style={{fontSize:11,color:'var(--t3)'}}>ILS: {r.ils}</span></div>))}</div>}</div> : a.type==='Aircraft' ? <div><div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:10,flexWrap:'wrap'}}><DL label='Aircraft Specifications' color='var(--grn)'/><div style={{display:'flex',gap:8,flexWrap:'wrap'}}><Btn label={fetching?'Populating...':'Populate with selected AI'} color='var(--grn)' sm onClick={fetchSpecs} disabled={fetching} title='Populate aircraft specifications and save the returned data automatically.'/><Btn label='Save' color='var(--grn)' sm onClick={saveCore} title='Save your manual edits. AI populate already saves returned data automatically.'/></div></div>{fetchMsg&&<div style={{fontSize:11,color:'var(--t2)',marginBottom:10}}>{fetchMsg}</div>}<div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:12}}><div><div style={{fontSize:10,color:'var(--t2)',marginBottom:4}}>Manufacturer</div><input value={manufacturer} onChange={e=>setManufacturer(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/></div><div><div style={{fontSize:10,color:'var(--t2)',marginBottom:4}}>Model</div><input value={model} onChange={e=>setModel(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/></div><div><div style={{fontSize:10,color:'var(--t2)',marginBottom:4}}>Manufacturer Full Name</div><input value={manufacturerFull} onChange={e=>setManufacturerFull(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/></div><div><div style={{fontSize:10,color:'var(--t2)',marginBottom:4}}>Category</div><input value={category} onChange={e=>setCategory(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/></div></div><KVG pairs={[['Category',rw.category||category],['Date Introduced',rw.introduced],['Engine',rw.engine],['Engine Type',rw.engine_type],['Max Speed',rw.max_speed],['Cruise Speed',rw.cruise],['Range (NM)',rw.range_nm],['Ceiling',rw.ceiling],['Passenger Capacity',rw.seats],['Fuel Capacity',rw.fuel_capacity],['Wingspan',rw.wingspan],['Length',rw.length],['Height',rw.height],['In Production',rw.in_production],['Aircraft Cost',rw.aircraft_cost],['Country of Origin',rw.country_of_origin],['MTOW',rw.mtow],['Web Data Source',shortUrlLabel(rw.source)]]}/>{rw.avionics&&<div style={{marginTop:12}}><DL label='Avionics' color='var(--vio)'/><div style={{whiteSpace:'pre-wrap',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:8,padding:'9px 11px',fontSize:12,color:'var(--t1)',lineHeight:1.6}}>{rw.avionics}</div></div>}{rw.variants&&<div style={{marginTop:12}}><DL label='Variants' color='var(--acc)'/><div style={{whiteSpace:'pre-wrap',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:8,padding:'9px 11px',fontSize:12,color:'var(--t1)',lineHeight:1.6}}>{rw.variants}</div></div>}</div> : <div style={{fontSize:13,color:'var(--t2)'}}>No real-world data available for this addon type.</div>;
  if(desktopNative){
    const siteLinks=a.type==='Airport'?airportSiteLinks:aircraftSiteLinks;
    return (
      <div style={{display:'flex',flexDirection:'column',gap:12,height:'calc(100vh - 220px)',minHeight:560}}>
        <div style={{overflowY:'auto',paddingRight:4,minWidth:0,display:'flex',flexDirection:'column',gap:12}}>
          {left}
          <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,padding:12,display:'flex',flexDirection:'column',gap:10}}>
            <div style={{display:'flex',gap:6,flexShrink:0}}>
              {[['web','Web Search'],['saved',`Saved (${saved.length})`]].map(([id,l]) => (
                <button
                  key={id}
                  onClick={() => {
                    setMode(id);
                    if(id==='saved' && (!nativeState.current_url || nativeState.current_url==='about:blank')){
                      openBrowserUrl('https://www.bing.com','Web Search');
                    }
                    if(id==='web') runOriginalSearch();
                  }}
                  style={{background:mode===id?'var(--accD)':'transparent',border:'1px solid '+(mode===id?'var(--accB)':'var(--bdr)'),color:mode===id?'var(--acc)':'var(--t2)',borderRadius:7,padding:'6px 12px',cursor:'pointer',fontSize:11,fontWeight:600,fontFamily:'inherit'}}
                >
                  {l}
                </button>
              ))}
            </div>
            <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center'}}>
              <Btn label='Reset Browser' color='var(--acc)' sm onClick={runOriginalSearch} title='Reload the original search for this add-on.'/>
              {nativeState.current_url && nativeState.current_url!=='about:blank' && !String(nativeState.current_url).startsWith('search:') && (
                <Btn label='Save Current Article' color='var(--grn)' sm onClick={saveCurrentArticle}/>
              )}
            </div>
          </div>
          {mode==='web' ? (
            <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,padding:12}}>
              <div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:8}}>
                {a.type==='Airport'?'Recommended Airport Sites':'Recommended Aircraft Sites'}
              </div>
              <div style={{display:'flex',flexDirection:'column',gap:8}}>
                {siteLinks.map((site,i)=>(
                  <Btn key={i} label={site.label} color={a.type==='Airport'?'var(--acc)':'var(--grn)'} sm onClick={()=>openBrowserUrl(site.url,site.label)}/>
                ))}
              </div>
            </div>
          ) : (
            <SavedResourcesPanel
              items={saved}
              onOpen={openSaved}
              onDelete={removeSaved}
              onCategoryChange={updateCategory}
              emptyText='No saved articles yet. Open a page in the browser and click Save Current Article.'
            />
          )}
        </div>
      </div>
    );
  }
  return <div style={{display:'flex',flexDirection:'column',gap:16}}>{left}<EmbeddedBrowserPane key={a.id+'|'+defaultQ+'|'+browserSeed} initialQuery={defaultQ} searchContext='specs' height='calc(100vh - 420px)'/></div>;
}

function FeaturesTab({a,injected,onInjected,onSave}){
  const editorRef=useRef(null);
  const [saved,setSaved]=useState(false);
  useEffect(()=>{if(editorRef.current){applyThemedHtml(editorRef.current,a.usr.features||"");}},[a.id]);
  useEffect(()=>{if(injected&&editorRef.current){applyThemedHtml(editorRef.current,injected);if(onInjected)onInjected();editorRef.current.style.border="2px solid var(--grn)";setTimeout(()=>{if(editorRef.current)editorRef.current.style.border="1px solid var(--bdr)";},1500);}},[injected]);
  function save(){const html=editorRef.current?sanitizeHtmlForTheme(editorRef.current.innerHTML):""; if(onSave) onSave(a.id,{features:html}); else if(a.usr) a.usr.features=html; setSaved(true);setTimeout(()=>setSaved(false),1800);}
  function handlePaste(e){
    e.preventDefault();
    const items=e.clipboardData&&e.clipboardData.items;
    let html="", plain="";
    if(items){
      for(let i=0;i<items.length;i++){
        if(items[i].type==="text/html"){
          html=e.clipboardData.getData("text/html");
          break;
        }
      }
      if(!html) plain=e.clipboardData.getData("text/plain");
    }
    if(html){
      document.execCommand("insertHTML", false, sanitizeHtmlForTheme(html));
    }else if(plain){
      const lines=plain.split(/\r?\n/);
      const html2=lines.map(l=>l.trim()?`<p>${l}</p>`:"").join("");
      document.execCommand("insertHTML", false, html2 || `<p>${plain}</p>`);
    }
  }
  return <div style={{display:"flex",flexDirection:"column",height:"calc(100vh - 220px)",minHeight:400,gap:10}}>
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}><div style={{fontSize:12,color:"var(--t1)"}}>Paste text from any web page — formatting is preserved automatically. You can also type notes directly.</div><div style={{display:"flex",gap:7,flexWrap:'wrap'}}><Btn label='Reformat Features' color='var(--t2)' sm onClick={()=>{if(editorRef.current) applyReformatToEditor(editorRef.current,{stripImages:false});}}/><Btn label='Reading Mode' color='var(--vio)' sm onClick={()=>{if(editorRef.current) applyReformatToEditor(editorRef.current,{stripImages:true});}}/><Btn label="Clear" color="var(--red)" sm onClick={()=>{if(editorRef.current)editorRef.current.innerHTML="";}}/><Btn label={saved?"Saved!":"Save"} color={saved?"var(--grn)":"var(--acc)"} sm onClick={save}/></div></div>
    <div style={{fontSize:10,color:'var(--t3)',marginTop:-2}}>Reformat Features keeps useful structure but normalizes colors and list spacing. Reading Mode strips most images and noisy page elements for cleaner feature text.</div>
    <div ref={editorRef} contentEditable={true} className="theme-html features-editor" suppressContentEditableWarning={true} onPaste={handlePaste} style={{flex:1,background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:10,padding:"14px 16px",color:"var(--t0)",fontSize:13,outline:"none",lineHeight:1.75,overflowY:"auto",cursor:"text",minHeight:0}} data-placeholder="Paste any web page content here or type feature notes..."/>
    <style>{".features-editor:empty:before{content:attr(data-placeholder);color:var(--t3);pointer-events:none;}"}</style>
  </div>;
}

function GalleryTab({a,onSaveMeta}){
  const cc=CC[a.type]||"#64748B";
  const apiImgs=(a.gallery_paths||[]).map((_,i)=>"/gallery/"+a.id+"/"+i);
  const imgs=apiImgs;
  const defaultImageSearch=((a.publisher?a.publisher+' ':'')+a.title+' msfs').trim();
  const defaultImageUrl=googleSearchUrl(defaultImageSearch,{images:true});
  const [sel,setSel]=useState(0),[loaded,setLoaded]=useState({}),[failed,setFailed]=useState({}),[busy,setBusy]=useState(false),[msg,setMsg]=useState("");
  const [browserSeed,setBrowserSeed]=useState(0);
  const [shellMode,setShellMode]=useState(null);
  const desktopNative=shellMode==='qt';
  const fileRef=useRef(null), pasteRef=useRef(null);
  useEffect(()=>{setSel(0);setLoaded({});setFailed({});},[a.id,(a.gallery_paths||[]).join("|")]);
  useEffect(()=>{fetch('/api/app/info').then(r=>r.json()).then(d=>setShellMode(d.shell_mode||'browser')).catch(()=>setShellMode('browser'));},[]);
  useEffect(()=>{
    if(desktopNative){
      fetch('/api/browser/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:defaultImageUrl,title:'Image Search',request_id:Date.now()})}).catch(()=>{});
    }
  },[a.id,desktopNative]);
  async function syncFromResponse(res){
    const data=await res.json();
    if(onSaveMeta) onSaveMeta(a.id,{thumbnail_path:data.thumbnail_path,gallery_paths:data.gallery_paths});
    setMsg("Updated gallery"); setTimeout(()=>setMsg(""),1800);
  }
  async function uploadFiles(files){
    if(!files||!files.length) return;
    setBusy(true);
    try{
      for(const file of files){
        const fd=new FormData(); fd.append("file",file,file.name||"image.png");
        const res=await fetch("/api/addons/"+a.id+"/gallery/upload",{method:"POST",body:fd});
        if(!res.ok) throw new Error("Upload failed");
        await syncFromResponse(res);
      }
    }catch(e){setMsg(e.message||"Upload failed");}finally{setBusy(false); if(fileRef.current) fileRef.current.value="";}
  }
  async function deleteCurrent(){
    if(!imgs.length) return;
    if(!window.confirm("Delete selected image from gallery?")) return;
    setBusy(true);
    try{
      const res=await fetch("/api/addons/"+a.id+"/gallery/"+sel,{method:"DELETE"});
      if(!res.ok) throw new Error("Delete failed");
      await syncFromResponse(res);
      setSel(s=>Math.max(0,s-1));
    }catch(e){setMsg(e.message||"Delete failed");}finally{setBusy(false);}
  }
  async function setDefault(){
    if(!imgs.length) return;
    setBusy(true);
    try{
      const res=await fetch("/api/addons/"+a.id+"/gallery/set-default",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({index:sel})});
      if(!res.ok) throw new Error("Set default failed");
      await syncFromResponse(res);
    }catch(e){setMsg(e.message||"Set default failed");}finally{setBusy(false);}
  }
  async function pasteFromClipboard(){
    try{
      if(navigator.clipboard && navigator.clipboard.read){
        const items=await navigator.clipboard.read();
        const files=[];
        for(const item of items){
          for(const type of item.types){
            if(type.startsWith("image/")){
              const blob=await item.getType(type);
              files.push(new File([blob],"clipboard."+(type.split("/")[1]||"png"),{type}));
            }
          }
        }
        if(files.length){ await uploadFiles(files); return; }
      }
      setMsg("Click the large paste box and press Ctrl+V.");
      pasteRef.current&&pasteRef.current.focus();
    }catch(e){setMsg("Clipboard access was blocked. Click the paste box and press Ctrl+V."); pasteRef.current&&pasteRef.current.focus();}
  }
  function onPaste(e){
    const items=[...(e.clipboardData&&e.clipboardData.items||[])].filter(it=>it.type&&it.type.startsWith("image/"));
    if(!items.length) return;
    e.preventDefault();
    const files=items.map((it,i)=>it.getAsFile()).filter(Boolean);
    uploadFiles(files);
  }
  function resetSearch(){
    if(desktopNative){
      fetch('/api/browser/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:defaultImageUrl,title:'Image Search',request_id:Date.now()})}).catch(()=>{});
    }
    setBrowserSeed(s=>s+1);
  }
  const leftPane=<div onPaste={onPaste}><div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:12,alignItems:"center"}}>
    <Btn label="Add Image From Folder" color="var(--acc)" sm onClick={()=>fileRef.current&&fileRef.current.click()} disabled={busy}/>
    <Btn label="Paste Clipboard Image" color="var(--vio)" sm onClick={pasteFromClipboard} disabled={busy}/>
    <Btn label="Set Selected As Default" color="var(--grn)" sm onClick={setDefault} disabled={busy||!imgs.length}/>
    <Btn label="Delete Selected" color="var(--red)" sm onClick={deleteCurrent} disabled={busy||!imgs.length}/>
    <Btn label="Reset Image Search" color="var(--acc)" sm onClick={resetSearch}/>
    {msg&&<span style={{fontSize:11,color:"var(--t2)"}}>{msg}</span>}
    <input ref={fileRef} type="file" accept="image/*" multiple style={{display:"none"}} onChange={e=>uploadFiles([...e.target.files||[]])}/>
  </div>
  <div ref={pasteRef} tabIndex={0} style={{marginBottom:12,background:'linear-gradient(135deg,var(--vioD),transparent)',border:'1px dashed var(--vio)',borderRadius:12,padding:'14px 16px',fontSize:12,color:'var(--t1)',outline:'none'}}>
    <div style={{fontSize:13,fontWeight:800,color:'var(--t0)',marginBottom:4}}>Paste image from clipboard</div>
    <div>Click here and press <strong>Ctrl+V</strong>, or use the <strong>Paste Clipboard Image</strong> button above.</div>
  </div>
  {!imgs.length ? <div style={{textAlign:"center",padding:"40px 0",color:"var(--t2)",fontSize:13}}>No gallery images found for this addon.</div> : <div><div style={{position:"relative",borderRadius:12,overflow:"hidden",border:"1px solid var(--bdr)",marginBottom:10,background:"var(--bg2)",height:"58vh",minHeight:320}}>{!loaded[sel]&&!failed[sel]&&<div className="shimmer" style={{position:"absolute",inset:0}}/>}{!failed[sel]?<img src={imgs[sel]} crossOrigin="anonymous" onLoad={()=>setLoaded(l=>({...l,[sel]:true}))} onError={()=>setFailed(f=>({...f,[sel]:true}))} alt="" style={{width:"100%",height:"100%",objectFit:"contain",display:"block",opacity:loaded[sel]?1:0,transition:"opacity 0.35s",background:"var(--bg2)"}}/>:<div style={{height:"100%",display:"flex",alignItems:"center",justifyContent:"center",color:"var(--t2)"}}>Image unavailable</div>}<div style={{position:"absolute",bottom:0,left:0,right:0,background:"linear-gradient(transparent,rgba(5,12,24,.88))",padding:"22px 12px 10px",display:"flex",alignItems:"center",justifyContent:"space-between"}}><div style={{display:"flex",gap:8,alignItems:"center"}}><Chip label={(sel+1)+" / "+imgs.length} color={cc} sm/>{a.thumbnail_path===a.gallery_paths[sel]&&<Chip label="Default" color="var(--grn)" sm/>}</div><div style={{display:"flex",gap:6,alignItems:"center"}}><button onClick={()=>setSel(s=>Math.max(0,s-1))} disabled={sel===0} style={{background:"rgba(0,0,0,.6)",border:"1px solid var(--bdr)",color:sel===0?"var(--t3)":"var(--t0)",borderRadius:6,width:30,height:30,fontSize:15,cursor:sel===0?"not-allowed":"pointer"}}>{"<"}</button><button onClick={()=>setSel(s=>Math.min(imgs.length-1,s+1))} disabled={sel===imgs.length-1} style={{background:"rgba(0,0,0,.6)",border:"1px solid var(--bdr)",color:sel===imgs.length-1?"var(--t3)":"var(--t0)",borderRadius:6,width:30,height:30,fontSize:15,cursor:sel===imgs.length-1?"not-allowed":"pointer"}}>{">"}</button></div></div></div><div style={{display:"flex",gap:7,marginBottom:12,overflowX:"auto",paddingBottom:4}}>{imgs.map((src,i)=>(<div key={i} onClick={()=>setSel(i)} style={{width:96,height:68,flexShrink:0,borderRadius:8,overflow:"hidden",border:"2px solid "+(i===sel?cc:"var(--bdr)"),cursor:"pointer",opacity:i===sel?1:0.72,background:"var(--bg2)"}}><img src={src} alt="" style={{width:"100%",height:"100%",objectFit:"cover",display:"block"}}/></div>))}</div></div>}
  </div>;
  if(desktopNative){
    return <div style={{display:'grid',gridTemplateColumns:'1fr',gap:12,minHeight:520}}>{leftPane}<div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,padding:12,fontSize:12,color:'var(--t2)',lineHeight:1.7}}>The native browser on the right is set to image search for this add-on. Use <strong style={{color:'var(--t0)'}}>Reset Image Search</strong> to jump back to the default image search at any time.</div></div>;
  }
  return <div style={{display:'grid',gridTemplateColumns:'minmax(0,1fr) minmax(620px,0.95fr)',gap:12,minHeight:520}}>{leftPane}<div style={{display:'flex',flexDirection:'column',gap:10}}><div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,padding:12,fontSize:12,color:'var(--t2)',lineHeight:1.7}}>Image search results are shown on the right for quick image hunting. Use <strong style={{color:'var(--t0)'}}>Reset Image Search</strong> to jump back to the default search for this add-on.</div><EmbeddedBrowserPane key={a.id+'|images|'+browserSeed} initialUrl={defaultImageUrl} titleHint='Image Search' searchContext='images' height='calc(100vh - 280px)' layout='stack' browserMin='620px'/></div></div>;
}

function EmbeddedBrowserPane({initialQuery,initialUrl,titleHint,onSavePage,saveEnabled,shortcuts=[],height="520px",layout="split",browserMin="760px",searchContext='web'}){
  const [query,setQuery]=useState(initialUrl||initialQuery||"");
  const [results,setResults]=useState([]);
  const [loading,setLoading]=useState(false);
  const [msg,setMsg]=useState("");
  const [iframeUrl,setIframeUrl]=useState(initialUrl?('/api/research/open?url='+encodeURIComponent(initialUrl)):"");
  const [pageUrl,setPageUrl]=useState(initialUrl||"");
  const [pageTitle,setPageTitle]=useState(titleHint||"");
  const [shellMode,setShellMode]=useState(null);
  const [nativeState,setNativeState]=useState({current_url:'',current_title:'',visible:false});
  const [browserSeed,setBrowserSeed]=useState(0);
  const [page,setPage]=useState(1);
  const [totalPages,setTotalPages]=useState(1);
  const [totalResults,setTotalResults]=useState(0);
  const [jumpPage,setJumpPage]=useState('1');
  const desktopNative=shellMode==='qt';

  useEffect(()=>{ fetch('/api/app/info').then(r=>r.json()).then(d=>setShellMode(d.shell_mode||'browser')).catch(()=>{}); },[]);

  useEffect(()=>{
    function onMsg(ev){
      const d=ev&&ev.data;
      if(!d) return;
      if(d.type==='hangar-browser-state'){
        if(d.url) setPageUrl(String(d.url));
        if(d.title) setPageTitle(String(d.title));
        return;
      }
      if(d.type==='hangar-native-browser-state'){
        const next={current_url:String(d.url||''), current_title:String(d.title||''), visible:!!d.visible};
        setNativeState(next);
        setPageUrl(next.current_url||'');
        setPageTitle(next.current_title||'');
      }
    }
    window.addEventListener('message', onMsg);
    return ()=>window.removeEventListener('message', onMsg);
  },[]);

  useEffect(()=>{
    if(!desktopNative) return;
    fetch('/api/browser/close',{method:'POST'}).catch(()=>{});
    return ()=>{ fetch('/api/browser/close',{method:'POST'}).catch(()=>{}); };
  },[desktopNative]);

  useEffect(()=>{
    if(shellMode===null) return;
    setQuery(initialUrl||initialQuery||"");
    setPage(1); setJumpPage('1');
    if(initialUrl){ openUrl(initialUrl, titleHint||initialUrl); }
    else if(initialQuery){ doSearch(initialQuery,1); }
    else { setIframeUrl(''); setPageUrl(''); setPageTitle(''); setResults([]); setTotalPages(1); setTotalResults(0); }
  }, [initialQuery, initialUrl, titleHint, shellMode, searchContext]);

  function normalizeUrl(raw){ const v=(raw||'').trim(); if(!v) return ''; if(/^https?:/i.test(v)) return v; if(/^[\w.-]+\.[a-z]{2,}(\/.*)?$/i.test(v)) return 'https://'+v; return ''; }
  function prettyUrl(u){ try{ const x=new URL(u); const path=(x.pathname||'/').replace(/\/$/,'')||'/'; const s=x.hostname+path; return s.length>90?s.slice(0,90)+'…':s; }catch(e){ return u; } }
  function isYoutubeQuery(v){ const q=String(v||'').toLowerCase(); return q.includes('site:youtube.com') || q.includes('site:youtu.be') || q.startsWith('youtube '); }
  function youtubeSearchUrl(v){ const cleaned=String(v||'').replace(/site:youtube\.com/ig,'').replace(/site:youtu\.be/ig,'').replace(/\byoutube\b/ig,'').trim(); return 'https://www.youtube.com/results?search_query='+encodeURIComponent(cleaned); }
  function googleSearchUrl(v){ return window.googleSearchUrl?window.googleSearchUrl(v):('https://www.bing.com/search?q='+encodeURIComponent(String(v||'').trim())); }

  async function openNative(url,title){
    const clean=normalizeUrl(url)||url.trim();
    if(!clean) return;
    setResults([]); setTotalPages(1); setTotalResults(0);
    setPageUrl(clean); setPageTitle(title||clean);
    try{
      await fetch('/api/browser/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:clean,title:title||clean,request_id:Date.now()})});
      setMsg('Opened in native browser panel.');
    }catch(e){ setMsg('Could not open the native browser panel.'); }
  }

  function openUrl(url,title){
    const clean=normalizeUrl(url)||url.trim(); if(!clean) return;
    setResults([]); setTotalPages(1); setTotalResults(0);
    if(desktopNative){ openNative(clean,title||clean); return; }
    setPageUrl(clean); setPageTitle(title||clean); setIframeUrl('/api/research/open?url='+encodeURIComponent(clean));
  }

  async function doSearch(q,nextPage){
    const term=(q||query||'').trim(); if(!term) return;
    const usePage=Math.max(1, Number(nextPage||page||1));
    setLoading(true); setMsg(''); setQuery(term); setPage(usePage); setJumpPage(String(usePage)); setPageTitle('Search: '+term); setPageUrl('search:'+term);
    if(desktopNative){ try{ await fetch('/api/browser/close',{method:'POST'}); }catch(e){} }
    if(isYoutubeQuery(term)){
      const yt=youtubeSearchUrl(term);
      if(desktopNative){ await openNative(yt,'YouTube Search'); }
      else { setIframeUrl('/api/research/open?url='+encodeURIComponent(yt)); setPageUrl(yt); setPageTitle('YouTube Search'); }
      setResults([]); setTotalPages(1); setTotalResults(0); setMsg('Opened YouTube results in the browser.'); setLoading(false); return;
    }
    if(desktopNative){
      const g=googleSearchUrl(term);
      await openNative(g,'Web Search');
      setResults([]); setTotalPages(1); setTotalResults(0); setMsg('Opened search results in the browser panel.');
      setLoading(false); return;
    }
    setIframeUrl('/api/research/searchpage?q='+encodeURIComponent(term)+'&context='+encodeURIComponent(searchContext)+'&page='+usePage);
    try{
      const res=await fetch('/api/research/search?q='+encodeURIComponent(term)+'&context='+encodeURIComponent(searchContext)+'&page='+usePage);
      const data=await res.json();
      if(data.auto_open_url){
        setIframeUrl('/api/research/open?url='+encodeURIComponent(data.auto_open_url)); setPageUrl(data.auto_open_url); setPageTitle('YouTube Search');
        setResults([]); setTotalPages(1); setTotalResults(0); setMsg('Opened YouTube results in the browser.');
      } else {
        const hits=data.results||[];
        setResults(hits);
        setTotalPages(data.total_pages||1);
        setTotalResults(data.total_results||hits.length||0);
        if(!hits.length) setMsg('No results found.');
      }
    }catch(e){ setResults([]); setTotalPages(1); setTotalResults(0); setMsg('Search failed.'); }
    finally{ setLoading(false); }
  }

  function go(){ const raw=(query||'').trim(); if(!raw) return; const u=normalizeUrl(raw); if(u){ openUrl(u,u); } else { doSearch(raw,1); } }
  function handleSave(){ const saveUrl=desktopNative?(nativeState.current_url||pageUrl):pageUrl; const saveTitle=desktopNative?(nativeState.current_title||pageTitle):pageTitle; if(!saveEnabled || !onSavePage || !saveUrl || String(saveUrl).startsWith('search:') || String(saveUrl).includes('/api/research/searchpage')) return; onSavePage({url:saveUrl, title:saveTitle||saveUrl}); }
  const canSave=desktopNative ? !!(nativeState.current_url && !String(nativeState.current_url).startsWith('search:') && !String(nativeState.current_url).includes('/api/research/searchpage')) : (!!pageUrl && !String(pageUrl).startsWith('search:') && !String(pageUrl).includes('/api/research/searchpage'));

  const resultList=(loading
    ? <div style={{fontSize:12,color:'var(--t2)',padding:12}}>Searching for <span style={{color:'var(--acc)',fontWeight:700}}>{query}</span>…</div>
    : results.length===0
    ? <div style={{fontSize:12,color:'var(--t2)',padding:12}}>{msg|| (desktopNative?'Type a query or URL. Search results will appear here; pages open in the native browser panel.':'Type a query or URL to begin.')}</div>
    : <div style={{padding:10,overflowY:'auto',display:'flex',flexDirection:'column',gap:8}}>{results.map((r,i)=><div key={(r.url||'')+i} style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:10,padding:'10px 12px'}}><a href='#' onClick={e=>{e.preventDefault();openUrl(r.url,r.title);}} style={{display:'block',fontSize:13,fontWeight:700,color:'var(--acc)',textDecoration:'none',marginBottom:4}}>{r.title}</a><div style={{fontSize:10,color:'var(--t3)',marginBottom:6,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.display_url||prettyUrl(r.url)}</div>{r.snippet&&<div style={{fontSize:11,color:'var(--t1)',lineHeight:1.5}}>{r.snippet}</div>}</div>)}</div>
  );

  const pager = <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,padding:'8px 12px',borderTop:'1px solid var(--bdr)',flexWrap:'wrap'}}><div style={{fontSize:11,color:'var(--t2)'}}>{totalResults?`${totalResults} results • Page ${page} of ${totalPages}`:(loading?'Searching…':'')}</div><div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap'}}><Btn label='Prev' color='var(--t2)' sm disabled={loading||page<=1} onClick={()=>doSearch(query,Math.max(1,page-1))}/><Btn label='Next' color='var(--t2)' sm disabled={loading||page>=totalPages} onClick={()=>doSearch(query,Math.min(totalPages,page+1))}/><input value={jumpPage} onChange={e=>setJumpPage(e.target.value.replace(/[^0-9]/g,''))} style={{width:52,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'5px 8px',color:'var(--t0)',fontSize:11}}/><Btn label='Go to Page' color='var(--acc)' sm disabled={loading} onClick={()=>doSearch(query,Math.max(1,Math.min(totalPages,Number(jumpPage||1))))}/></div></div>;

  const leftPane=<div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,overflow:'hidden',display:'flex',flexDirection:'column',minHeight:0}}><div style={{padding:12,borderBottom:'1px solid var(--bdr)',display:'flex',flexDirection:'column',gap:8}}><div style={{display:'flex',gap:8}}><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter') go();}} placeholder='Enter a search query or URL' style={{flex:1,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'10px 12px',color:'var(--t0)',fontSize:13,outline:'none'}}/><Btn label={loading?'Searching…':'Go'} color='var(--acc)' onClick={go} disabled={loading}/><Btn label='Save Article' color='var(--grn)' onClick={handleSave} disabled={!canSave}/></div>{shortcuts.length>0&&<div style={{display:'flex',gap:6,flexWrap:'wrap'}}>{shortcuts.map((s,i)=><Btn key={i} label={s.label} color='var(--t2)' sm onClick={()=>{setQuery(s.value); setPage(1); setJumpPage('1'); const maybeUrl=normalizeUrl(s.value); if(maybeUrl){ openUrl(maybeUrl, s.label||maybeUrl); } else { doSearch(s.value,1); }}}/>)}</div>}{msg&&<div style={{fontSize:11,color:'var(--t2)'}}>{msg}</div>}</div><div style={{flex:1,minHeight:0,overflowY:'auto'}}>{resultList}</div>{pager}</div>;

  if(desktopNative){
    return <div style={{display:'grid',gridTemplateColumns:'1fr',gap:12,height,minHeight:480}}>{leftPane}</div>;
  }

  return <div style={{display:'grid',gridTemplateColumns:layout==='stack'?'1fr':`300px minmax(${browserMin},1fr)`,gap:12,height,minHeight:480}}>{leftPane}<div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,overflow:'hidden',display:'flex',flexDirection:'column',minHeight:0,minWidth:0}}><div style={{padding:'10px 12px',borderBottom:'1px solid var(--bdr)',display:'flex',alignItems:'center',justifyContent:'space-between',gap:8}}><div style={{minWidth:0}}><div style={{fontSize:12,fontWeight:700,color:'var(--t0)',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{pageTitle||'Embedded Browser'}</div><div style={{fontSize:10,color:'var(--t3)',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{pageUrl&&String(pageUrl).startsWith('search:')?String(pageUrl).slice(7):pageUrl||'Use search or open a URL.'}</div></div>{pageUrl&&!String(pageUrl).startsWith('search:')&&<a href={pageUrl} target='_blank' rel='noreferrer' style={{color:'var(--acc)',fontSize:11,fontWeight:600,textDecoration:'none',flexShrink:0}}>Open externally</a>}</div><div style={{flex:1,minHeight:0,background:'#fff'}}>{iframeUrl?<iframe name='research_frame' src={iframeUrl} title='EmbeddedBrowser' referrerPolicy='no-referrer-when-downgrade' allow='clipboard-read; clipboard-write' style={{width:'100%',height:'100%',border:'none',display:'block',background:'#fff'}}/>:<div style={{height:'100%',display:'flex',alignItems:'center',justifyContent:'center',color:'#64748B',fontSize:13}}>Choose a result to view it here.</div>}</div></div></div>;
}

function SavedResourcesPanel({items,onOpen,onDelete,onCategoryChange,extraButtons,emptyText}){
  const groups=useMemo(()=>groupArticleResources(items||[]),[items]);
  const total=(items||[]).length;
  if(!total) return <div style={{textAlign:'center',padding:'40px 0',color:'var(--t2)',fontSize:13}}>{emptyText||'No saved articles yet.'}</div>;
  return <div style={{display:'flex',flexDirection:'column',gap:12}}>{ARTICLE_CATEGORIES.map(cat=>{
    const list=groups[cat]||[];
    if(!list.length) return null;
    return <div key={cat} style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,overflow:'hidden'}}>
      <div style={{padding:'10px 12px',borderBottom:'1px solid var(--bdr)',fontSize:11,fontWeight:700,color:'var(--t1)',textTransform:'uppercase',letterSpacing:'0.06em'}}>{cat} ({list.length})</div>
      <div style={{padding:10,display:'flex',flexDirection:'column',gap:8}}>{list.map((r,i)=><div key={r.id||i} style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:10,padding:12}}><div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:10}}><div style={{flex:1,minWidth:0}}><a href='#' onClick={e=>{e.preventDefault();onOpen&&onOpen(r);}} style={{display:'inline-block',fontSize:13,fontWeight:700,color:'var(--acc)',textDecoration:'none',marginBottom:4}}>{r.title||r.url}</a><div style={{fontSize:10,color:'var(--t3)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.url}</div><div style={{fontSize:10,color:'var(--t3)',marginTop:4}}>Saved {r.saved||''}</div></div><div style={{display:'flex',flexDirection:'column',gap:6,alignItems:'flex-end',flexShrink:0}}><select value={(r.category||cat)} onChange={e=>onCategoryChange&&onCategoryChange(r,e.target.value)} style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'6px 8px',color:'var(--t0)',fontSize:11,fontFamily:'inherit'}}>{ARTICLE_CATEGORIES.map(opt=><option key={opt} value={opt}>{opt}</option>)}</select><div style={{display:'flex',gap:6,flexWrap:'wrap',justifyContent:'flex-end'}}>{extraButtons?extraButtons(r):null}<Btn label='x' color='var(--red)' sm onClick={()=>onDelete&&onDelete(r)}/></div></div></div></div>)}</div>
    </div>;
  })}</div>;
}

function ResearchTab({a,apiKey,onSendToFeatures,onSendToOverview,onSaveResources}){
  const defaultQ=((a.publisher?a.publisher+" ":"")+a.title).trim();
  const defaultUrl=googleSearchUrl(defaultQ);
  function openSpecsSearch(){ setMode('web'); return openBrowserUrl(defaultUrl,'Web Search'); }
  const [mode,setMode]=useState("web");
  const [extracting,setExtracting]=useState(null);
  const [shellMode,setShellMode]=useState(null);
  const [nativeState,setNativeState]=useState({current_url:'',current_title:'',visible:false});
  const [browserSeed,setBrowserSeed]=useState(0);
  const desktopNative=shellMode==='qt';
  const saved=useMemo(()=>((a.usr&&a.usr.research_resources)||(a.usr&&a.usr.resources)||[]).map(ensureArticleCategory),[a.id,a.usr&&a.usr.research_resources,a.usr&&a.usr.resources]);

  useEffect(()=>{
    fetch('/api/app/info').then(r=>r.json()).then(d=>setShellMode(d.shell_mode||'browser')).catch(()=>setShellMode('browser'));
  },[]);

  useEffect(()=>{
    function onMsg(ev){
      const d=ev&&ev.data;
      if(d&&d.type==='hangar-native-browser-state'){
        setNativeState({current_url:String(d.url||''), current_title:String(d.title||''), visible:!!d.visible});
      }
    }
    window.addEventListener('message',onMsg);
    return ()=>window.removeEventListener('message',onMsg);
  },[]);

  useEffect(()=>{
    setMode('web');
    if(desktopNative){
      fetch('/api/browser/open',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url:defaultUrl,title:'Web Search',request_id:Date.now()})
      }).catch(()=>{});
    }
  },[a.id,defaultQ,desktopNative]);

  useEffect(()=>{
    if(!desktopNative) return;
    if(mode==='saved' && (!nativeState.current_url || nativeState.current_url==='about:blank')){
      fetch('/api/browser/open',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url:googleSearchUrl(''),title:'Web Search',request_id:Date.now()})
      }).catch(()=>{});
    }
  },[mode,desktopNative,nativeState.current_url]);

  function persist(next){
    if(onSaveResources) onSaveResources(a.id,{research_resources:next});
  }

  function savePage(info){
    const title=(info.title||info.url||'Article').trim();
    const url=(info.url||'').trim();
    if(!url) return;
    persist([...(saved||[]), ensureArticleCategory({id:'r'+Date.now(),type:'link',title,url,saved:new Date().toISOString().slice(0,10)})]);
  }

  function saveCurrentArticle(){
    const url=nativeState.current_url||'';
    const title=(nativeState.current_title||url||'Article').trim();
    if(!url || url==='about:blank' || String(url).startsWith('search:')) return;
    savePage({title,url});
  }

  function openSaved(r){
    if(desktopNative){
      fetch('/api/browser/open',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url:r.url,title:r.title||r.url,request_id:Date.now()})
      }).catch(()=>{});
    }
  }

  function updateCategory(item,category){
    persist(saved.map(r=>(r.id===item.id?{...r,category}:r)));
  }

  function removeSaved(item){
    persist(saved.filter(r=>r.id!==item.id));
  }

  async function extractToTarget(r,target){
    const send=target==='overview'?onSendToOverview:onSendToFeatures;
    if(!send) return;
    setExtracting((r.id||r.url)+':'+target);
    try{
      const res=await fetch('/api/research/readable?url='+encodeURIComponent(r.url));
      if(!res.ok) throw new Error(await res.text());
      const data=await res.json();
      send(data.html||`<h3>${r.title||r.url}</h3><p><a href="${r.url}" target="_blank">${r.url}</a></p>`);
    }catch(e){
      send(`<h3>${r.title||r.url}</h3><p><a href="${r.url}" target="_blank">${r.url}</a></p>`);
    } finally {
      setExtracting(null);
    }
  }

  const extraButtons = (r) => (
    <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
      <Btn
        label={extracting===(r.id||r.url)+':features'?'Extracting…':'→ Features'}
        color='var(--vio)'
        sm
        disabled={!!extracting}
        onClick={()=>extractToTarget(r,'features')}
      />
      {onSendToOverview ? (
        <Btn
          label={extracting===(r.id||r.url)+':overview'?'Extracting…':'→ Overview'}
          color='var(--acc)'
          sm
          disabled={!!extracting}
          onClick={()=>extractToTarget(r,'overview')}
        />
      ) : null}
    </div>
  );

  if(!desktopNative){
    return (
      <div style={{display:'flex',flexDirection:'column',gap:8,height:'calc(100vh - 220px)',minHeight:520}}>
        <div style={{display:'flex',gap:6,flexShrink:0}}>
          {[['web','Web Search'],['saved','Saved ('+saved.length+')']].map(([id,l])=>(
            <button
              key={id}
              onClick={()=>setMode(id)}
              style={{background:mode===id?'var(--accD)':'transparent',border:'1px solid '+(mode===id?'var(--accB)':'var(--bdr)'),color:mode===id?'var(--acc)':'var(--t2)',borderRadius:7,padding:'6px 12px',cursor:'pointer',fontSize:11,fontWeight:600,fontFamily:'inherit'}}
            >
              {l}
            </button>
          ))}
        </div>
        {mode==='web' ? (
          <>
            <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center',marginBottom:8}}><Btn label='Reset Browser' color='var(--acc)' sm onClick={()=>{ setMode('web'); setBrowserSeed(s=>s+1); }} title='Reload the original search for this add-on.'/></div>
            <EmbeddedBrowserPane
              key={a.id+'|'+mode+'|'+defaultQ+'|'+browserSeed}
              initialQuery={defaultQ}
              saveEnabled
              onSavePage={savePage}
              shortcuts={[]}
              searchContext='research'
              height='calc(100vh - 280px)'
            />
          </>
        ) : (
          <SavedResourcesPanel
            items={saved}
            onOpen={()=>{}}
            onDelete={removeSaved}
            onCategoryChange={updateCategory}
            extraButtons={extraButtons}
            emptyText='No saved resources yet.'
          />
        )}
      </div>
    );
  }

  return (
    <div style={{display:'flex',flexDirection:'column',gap:12,height:'calc(100vh - 220px)',minHeight:560}}>
      <div style={{overflowY:'auto',paddingRight:4,minWidth:0,display:'flex',flexDirection:'column',gap:12}}>
        <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,padding:12,display:'flex',flexDirection:'column',gap:10}}>
          <div style={{display:'flex',gap:6,flexShrink:0}}>
            {[['web',`Web Search`],['saved',`Saved (${saved.length})`]].map(([id,l])=>(
              <button
                key={id}
                onClick={()=>{
                  setMode(id);
                  if(id==='web'){
                    fetch('/api/browser/open',{
                      method:'POST',
                      headers:{'Content-Type':'application/json'},
                      body:JSON.stringify({url:defaultUrl,title:'Web Search',request_id:Date.now()})
                    }).catch(()=>{});
                  }
                  if(id==='saved' && (!nativeState.current_url || nativeState.current_url==='about:blank')){
                    fetch('/api/browser/open',{
                      method:'POST',
                      headers:{'Content-Type':'application/json'},
                      body:JSON.stringify({url:googleSearchUrl(''),title:'Web Search',request_id:Date.now()})
                    }).catch(()=>{});
                  }
                }}
                style={{background:mode===id?'var(--accD)':'transparent',border:'1px solid '+(mode===id?'var(--accB)':'var(--bdr)'),color:mode===id?'var(--acc)':'var(--t2)',borderRadius:7,padding:'6px 12px',cursor:'pointer',fontSize:11,fontWeight:600,fontFamily:'inherit'}}
              >
                {l}
              </button>
            ))}
          </div>
          <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
            <Btn label='Reset Browser' color='var(--acc)' sm onClick={()=>{ fetch('/api/browser/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:defaultUrl,title:'Web Search',request_id:Date.now()})}).catch(()=>{}); setMode('web'); }} title='Reload the original search for this add-on.'/>
            {nativeState.current_url && nativeState.current_url!=='about:blank' && !String(nativeState.current_url).startsWith('search:') ? (
              <Btn label='Save Current Article' color='var(--grn)' sm onClick={saveCurrentArticle}/>
            ) : null}
          </div>
          {nativeState.current_title ? (
            <div style={{fontSize:10,color:'var(--t3)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{nativeState.current_title}</div>
          ) : null}
        </div>
        {mode==='saved' ? (
          <SavedResourcesPanel
            items={saved}
            onOpen={openSaved}
            onDelete={removeSaved}
            onCategoryChange={updateCategory}
            extraButtons={extraButtons}
            emptyText='No saved resources yet. Open a page in the browser and click Save Current Article.'
          />
        ) : (
          <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,padding:14,fontSize:12,color:'var(--t2)',lineHeight:1.7}}>
            Saved articles live on the left. The browser can be reset to the original search for this add-on at any time.
          </div>
        )}
      </div>
    </div>
  );
}


function MapTab({a,allAddons,onOpenAddon,onSave}){
  const cc=CC[a.type]||"#38BDF8";
  const mapRef=useRef(null),leafRef=useRef(null),overlayRef=useRef(null),rangeRef=useRef(null);
  const [layer,setLayer]=useState("satellite"),[zoom,setZoom]=useState("airport");
  const [ready,setReady]=useState(false),[radius,setRadius]=useState(0),[fetchMsg,setFetchMsg]=useState(''),[renderError,setRenderError]=useState('');
  const [inRange,setInRange]=useState([]),[selAc,setSelAc]=useState(null);
  const [searchText,setSearchText]=useState((a.usr&&a.usr.map_search_label)||((a.rw&&a.rw.icao)||a.title||''));
  const [saving,setSaving]=useState(false),[searching,setSearching]=useState(false);
  const [drawMode,setDrawMode]=useState('view');
  const initialPoint=useMemo(()=>{
    const lat=Number((a.usr&&a.usr.map_lat)!=null?(a.usr&&a.usr.map_lat):(addonCoordinates(a)&&addonCoordinates(a).lat));
    const lon=Number((a.usr&&a.usr.map_lon)!=null?(a.usr&&a.usr.map_lon):(addonCoordinates(a)&&addonCoordinates(a).lon));
    return Number.isFinite(lat)&&Number.isFinite(lon)?{lat,lon}:null;
  },[a.id]);
  const [mapPoint,setMapPoint]=useState(initialPoint);
  const [mapPolygon,setMapPolygon]=useState(()=>Array.isArray(a.usr&&a.usr.map_polygon)?(a.usr.map_polygon||[]):[]);
  useEffect(()=>{ setMapPoint(initialPoint); setMapPolygon(Array.isArray(a.usr&&a.usr.map_polygon)?(a.usr.map_polygon||[]):[]); setSearchText((a.usr&&a.usr.map_search_label)||((a.rw&&a.rw.icao)||a.title||'')); setFetchMsg(''); setDrawMode('view'); },[a.id]);
  const LAYERS={satellite:{l:"Satellite",tile:"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",attr:"Esri"},road:{l:"Road",tile:"https://tile.openstreetmap.org/{z}/{x}/{y}.png",attr:"OSM"}};
  const ZOOMS={region:{l:"Region",z:9},airport:{l:"Airport",z:14},runway:{l:"Runway",z:17}};
  function hasValidPoint(pt){ return pt&&Number.isFinite(Number(pt.lat))&&Number.isFinite(Number(pt.lon))&&Number(pt.lat)>=-90&&Number(pt.lat)<=90&&Number(pt.lon)>=-180&&Number(pt.lon)<=180; }
  function centroid(poly){ if(!Array.isArray(poly)||!poly.length) return null; let lat=0,lon=0,count=0; poly.forEach(p=>{ const la=Number(p&&p.lat), lo=Number(p&&p.lon); if(Number.isFinite(la)&&Number.isFinite(lo)){ lat+=la; lon+=lo; count++; }}); return count?{lat:lat/count,lon:lon/count}:null; }
  const activePoint=hasValidPoint(mapPoint)?mapPoint:centroid(mapPolygon);
  const hasRenderableMapData = !!activePoint || (Array.isArray(mapPolygon)&&mapPolygon.length>2);
  useEffect(()=>{
    if(!mapRef.current || typeof L==='undefined') return;
    setRenderError(!hasRenderableMapData ? 'No valid coordinates are saved for this add-on yet. Add optional latitude/longitude on the Airport Data tab or use Search Place / Set Point here.' : '');
    let cancelled=false;
    const tid=setTimeout(()=>{
      try{
        if(leafRef.current){ try{ leafRef.current.off(); leafRef.current.remove(); }catch(e){} leafRef.current=null; }
        const map=L.map(mapRef.current,{zoomControl:true,scrollWheelZoom:true});
        leafRef.current=map;
        setReady(false);
        const cur=LAYERS[layer];
        const tile=L.tileLayer(cur.tile,{attribution:cur.attr,maxZoom:19});
        tile.on('load',()=>!cancelled&&setReady(true));
        tile.on('tileerror',()=>!cancelled&&setFetchMsg('Base map tiles could not be loaded.'));
        tile.addTo(map);
        const group=L.layerGroup().addTo(map);
        overlayRef.current=group;
        if(activePoint){ map.setView([activePoint.lat,activePoint.lon],ZOOMS[zoom].z); }
        else if(Array.isArray(mapPolygon)&&mapPolygon.length>2){ const b=L.latLngBounds(mapPolygon.map(p=>[p.lat,p.lon])); map.fitBounds(b,{padding:[24,24]}); }
        else { map.setView([20,0],2); }
        const bounds=[];
        if(hasValidPoint(mapPoint)){
          const pin=L.divIcon({html:'<div style="width:16px;height:16px;border-radius:50%;background:'+cc+';border:3px solid #fff;box-shadow:0 0 12px '+cc+'88;"></div>',iconSize:[16,16],iconAnchor:[8,8],className:""});
          L.marker([mapPoint.lat,mapPoint.lon],{icon:pin}).addTo(group).bindPopup('<b style="color:'+cc+'">'+escapeHtml((a.rw&&a.rw.icao)||a.title)+'</b><br/>'+escapeHtml(a.title));
          bounds.push([mapPoint.lat,mapPoint.lon]);
        }
        if(Array.isArray(mapPolygon)&&mapPolygon.length>2){
          const poly=L.polygon(mapPolygon.map(p=>[p.lat,p.lon]),{color:cc,fillColor:cc,fillOpacity:0.18,weight:2}).addTo(group);
          poly.bindTooltip('Saved scenery coverage');
          mapPolygon.forEach(p=>bounds.push([p.lat,p.lon]));
        }
        if(a.type==='Airport' && mapPoint && zoom==='runway' && a.rw && a.rw.runways){
          a.rw.runways.forEach(rwy=>{
            const pts=String(rwy.id||'').split('/'),hdg=parseInt(pts[0]||'0',10)*10,rad=hdg*Math.PI/180;
            const al=0.008,aw=0.003,dlat=al*Math.cos(rad),dlon=al*Math.sin(rad)/Math.cos(mapPoint.lat*Math.PI/180);
            L.polygon([[mapPoint.lat-dlat-aw*Math.sin(rad),mapPoint.lon-dlon+aw*Math.cos(rad)],[mapPoint.lat+dlat-aw*Math.sin(rad),mapPoint.lon+dlon+aw*Math.cos(rad)],[mapPoint.lat+dlat+aw*Math.sin(rad),mapPoint.lon+dlon-aw*Math.cos(rad)],[mapPoint.lat-dlat+aw*Math.sin(rad),mapPoint.lon-dlon-aw*Math.cos(rad)]],{color:cc,fillColor:cc,fillOpacity:0.25,weight:1.5}).addTo(group).bindTooltip(rwy.id||'Runway');
          });
        }
        let drag=null;
        map.on('mousedown',e=>{ if(a.type==='Airport' && hasValidPoint(mapPoint)){ drag=e.latlng; } });
        map.on('mousemove',e=>{
          if(!(a.type==='Airport' && hasValidPoint(mapPoint) && drag)) return;
          const R=6371,dLat=(e.latlng.lat-drag.lat)*Math.PI/180,dLon=(e.latlng.lng-drag.lng)*Math.PI/180;
          const aa=Math.sin(dLat/2)**2+Math.cos(drag.lat*Math.PI/180)*Math.cos(e.latlng.lat*Math.PI/180)*Math.sin(dLon/2)**2;
          const nm=R*2*Math.atan2(Math.sqrt(aa),Math.sqrt(1-aa))*0.539957;
          if(rangeRef.current){ try{ rangeRef.current.remove(); }catch(err){} }
          rangeRef.current=L.circle([mapPoint.lat,mapPoint.lon],{radius:nm*1852,color:'#38BDF8',fillColor:'#38BDF8',fillOpacity:0.07,weight:2,dashArray:'6 4'}).addTo(map);
          rangeRef.current.bindTooltip(Math.round(nm)+' nm',{permanent:true,direction:'top'});
          setRadius(Math.round(nm));
          setInRange((allAddons||[]).filter(ac=>addonTypeFor(ac)==='Aircraft'&&ac.rw&&ac.rw.range_nm&&ac.rw.range_nm>=nm));
        });
        map.on('mouseup',()=>{ drag=null; });
        map.on('click',e=>{
          if(drawMode==='set-point'){
            setMapPoint({lat:Number(e.latlng.lat.toFixed(6)),lon:Number(e.latlng.lng.toFixed(6))});
            setFetchMsg('Point updated. Save Map Data to keep it.');
          }else if(drawMode==='draw-polygon'){
            setMapPolygon(cur=>[...(cur||[]),{lat:Number(e.latlng.lat.toFixed(6)),lon:Number(e.latlng.lng.toFixed(6))}]);
            setFetchMsg('Coverage point added. Keep clicking to define the area, then Save Map Data.');
          }
        });
        if(bounds.length>1){ try{ map.fitBounds(bounds,{padding:[24,24],maxZoom:ZOOMS[zoom].z}); }catch(e){} }
        setTimeout(()=>{ try{ map.invalidateSize(true); }catch(e){} },90);
        setTimeout(()=>{ try{ map.invalidateSize(true); }catch(e){} if(!cancelled) setReady(true); },360);
      }catch(e){ console.warn('Map error:',e); if(!cancelled) setFetchMsg('Map failed to render.'); }
    },120);
    return ()=>{ cancelled=true; clearTimeout(tid); if(leafRef.current){ try{ leafRef.current.off(); leafRef.current.remove(); }catch(e){} leafRef.current=null; } };
  },[a.id,layer,zoom,JSON.stringify(mapPoint),JSON.stringify(mapPolygon),drawMode,hasRenderableMapData]);

  async function findPlace(){
    const q=String(searchText||'').trim();
    if(!q) return;
    setSearching(true); setFetchMsg('Searching map locations...');
    try{
      const data=await fetchJsonSafe('/api/map/search-place',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q,limit:5})});
      const first=(data&&data.results&&data.results[0])||null;
      if(first && hasValidPoint(first)){
        setMapPoint({lat:first.lat,lon:first.lon});
        setFetchMsg('Map centered on '+(first.label||q)+'.');
        if(leafRef.current){ try{ leafRef.current.setView([first.lat,first.lon], a.type==='Airport'?ZOOMS.airport.z:11); }catch(e){} }
      }else{
        setFetchMsg('No map search results found.');
      }
    }catch(e){ setFetchMsg((e&&e.message)||'Place search failed.'); }
    finally{ setSearching(false); }
  }
  async function saveMapData(){
    setSaving(true);
    try{
      const zoomLevel=leafRef.current?leafRef.current.getZoom():null;
      onSave&&onSave(a.id,{map_lat:mapPoint&&mapPoint.lat,map_lon:mapPoint&&mapPoint.lon,map_zoom:zoomLevel||undefined,map_search_label:searchText||'',map_polygon:mapPolygon||[]});
      setFetchMsg('Map data saved.');
    }finally{ setSaving(false); }
  }
  const hasMapData=hasValidPoint(mapPoint) || (Array.isArray(mapPolygon)&&mapPolygon.length>2);
  return <div style={{display:"flex",flexDirection:"column",gap:10}}>
    <div style={{display:'grid',gridTemplateColumns:'minmax(280px,.95fr) minmax(280px,1.05fr)',gap:12,alignItems:'start'}}>
      <div style={{background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:10,padding:"10px 13px"}}>
        <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:8}}>Map Tools</div>
        <div style={{display:'grid',gridTemplateColumns:'1fr auto',gap:8,marginBottom:10}}>
          <ClearableInput value={searchText} setValue={setSearchText} placeholder={a.type==='Airport'?'Search airport or city…':'Search city or scenery area…'} inputStyle={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none',minHeight:'auto'}}/>
          <Btn label={searching?'Searching...':'Search Place'} color='var(--acc)' sm onClick={findPlace} disabled={searching}/>
        </div>
        <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:10}}>
          <Btn label={drawMode==='view'?'View Mode':'View Mode'} color={drawMode==='view'?'var(--grn)':'var(--t2)'} sm onClick={()=>setDrawMode('view')}/>
          <Btn label='Set Point' color={drawMode==='set-point'?'var(--grn)':'var(--t2)'} sm onClick={()=>setDrawMode('set-point')}/>
          {a.type==='Scenery'&&<Btn label='Draw Coverage' color={drawMode==='draw-polygon'?'var(--vio)':'var(--t2)'} sm onClick={()=>setDrawMode('draw-polygon')}/>}          
          {a.type==='Scenery'&&<Btn label='Clear Coverage' color='var(--red)' sm onClick={()=>setMapPolygon([])} disabled={!mapPolygon.length}/>}          
          <Btn label={saving?'Saving...':'Save Map Data'} color='var(--acc)' sm onClick={saveMapData} disabled={saving}/>
        </div>
        <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.65}}>{a.type==='Scenery'?'Search for a place, zoom the map, click Set Point to mark the primary location, and use Draw Coverage to add polygon points for the scenery area. Save stores both the point and the polygon for this add-on.':'Search for the airport or city if needed, then click Set Point to save a better airport location. The airport range tool still works by dragging on the map.'}</div>
        {renderError&&<div style={{marginTop:10,background:'rgba(127,29,29,.16)',border:'1px solid rgba(239,68,68,.28)',color:'var(--red)',borderRadius:10,padding:'10px 12px',fontSize:12,lineHeight:1.6}}>{renderError}</div>}
        {fetchMsg&&<div style={{fontSize:11,color:'var(--t1)',marginTop:8}}>{fetchMsg}</div>}
      </div>
      <div style={{background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:10,padding:"10px 13px"}}>
        <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:6}}>Saved Map Data</div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,fontSize:12,color:'var(--t1)'}}>
          <div><b style={{color:'var(--t0)'}}>Point</b><div>{hasValidPoint(mapPoint)?`${mapPoint.lat.toFixed(5)}, ${mapPoint.lon.toFixed(5)}`:'No point saved'}</div></div>
          <div><b style={{color:'var(--t0)'}}>Coverage</b><div>{mapPolygon&&mapPolygon.length>2?`${mapPolygon.length} polygon points saved`:'No coverage polygon saved'}</div></div>
        </div>
      </div>
    </div>
    <div style={{display:"flex",gap:8,flexWrap:'wrap'}}>{Object.entries(LAYERS).map(([id,ly])=><button key={id} onClick={()=>setLayer(id)} style={{background:layer===id?cc+'22':'transparent',border:'1px solid '+(layer===id?cc+'55':'var(--bdr)'),color:layer===id?cc:'var(--t2)',borderRadius:8,padding:'6px 10px',cursor:'pointer',fontSize:11,fontWeight:600,fontFamily:'inherit'}}>{ly.l}</button>)}{Object.entries(ZOOMS).map(([id,z])=><button key={id} onClick={()=>setZoom(id)} style={{background:zoom===id?'var(--accD)':'transparent',border:'1px solid '+(zoom===id?'var(--accB)':'var(--bdr)'),color:zoom===id?'var(--acc)':'var(--t2)',borderRadius:8,padding:'6px 10px',cursor:'pointer',fontSize:11,fontWeight:600,fontFamily:'inherit'}}>{z.l}</button>)}</div>
    <div style={{position:"relative",height:420,background:"var(--bg2)",borderRadius:12,border:"1px solid var(--bdr)",overflow:'hidden'}}>
      <div ref={mapRef} style={{position:'absolute',inset:0}}/>
      {!ready&&<div style={{position:'absolute',inset:0,display:'flex',alignItems:'center',justifyContent:'center',pointerEvents:'none',background:'linear-gradient(180deg,rgba(5,12,24,.18),rgba(5,12,24,.32))',color:'var(--t2)'}}><div style={{textAlign:'center'}}><div style={{fontSize:13,fontWeight:800,color:'var(--t0)',marginBottom:6}}>Rendering map…</div><div style={{fontSize:11}}>The map is being sized and rendered.</div></div></div>}
      {!hasMapData&&ready&&<div style={{position:'absolute',right:12,bottom:12,background:'rgba(5,12,24,.8)',border:'1px solid var(--bdr)',borderRadius:10,padding:'8px 10px',fontSize:11,color:'var(--t2)'}}>Search for a place or click Set Point to start.</div>}
    </div>
    {a.type==='Airport'&&radius>0&&<div style={{fontSize:11,color:"var(--t2)",textAlign:"center",marginTop:4}}>Drag holding right mouse button to draw range circle — release to see aircraft that can fly that distance</div>}
    {a.type==='Airport'&&inRange.length>0&&<div style={{marginTop:6}}><DL label={`Aircraft In Range (${inRange.length})`} color="#38BDF8"/><div style={{display:"flex",overflowX:"auto",gap:10,paddingBottom:4,marginTop:8}}>{inRange.map(ac=><div key={ac.id} onClick={()=>setSelAc(ac)} style={{minWidth:260,background:"var(--bg1)",border:"1px solid var(--bdr)",borderRadius:12,padding:12,cursor:"pointer",display:"flex",gap:10,boxShadow:selAc&&selAc.id===ac.id?`0 0 0 1px ${cc}55`:"none"}}><div style={{width:78,height:56,borderRadius:9,overflow:"hidden",border:"1px solid var(--bdr)",flexShrink:0}}><AddonImg a={ac} h={56}/></div><div style={{flex:1,minWidth:0}}><div style={{display:"flex",gap:6,marginBottom:6,flexWrap:"wrap"}}><Chip label={addonTypeFor(ac)} color={cc} sm/>{ac.sub&&<Chip label={ac.sub} color={cc} sm/>}</div><div style={{fontSize:14,fontWeight:700,color:"var(--t0)",marginBottom:3}}>{ac.title}</div><div style={{fontSize:11,color:"var(--t2)",marginBottom:7}}>{ac.publisher} · {ac.pr&&ac.pr.ver?('v'+ac.pr.ver):'—'}</div><div style={{display:"flex",gap:8,flexWrap:"wrap"}}>{[[ (ac.rw&&ac.rw.mfr)||"—","Manufacturer"],[(ac.rw&&ac.rw.range_nm)?`${ac.rw.range_nm} nm`:((ac.rw&&ac.rw.range)||"—"),"Range"],[(ac.rw&&ac.rw.cruise)||"—","Cruise"],[(ac.rw&&ac.rw.ceiling)||"—","Ceiling"],[(ac.rw&&ac.rw.seats)||"—","Seats"]].map(([v,l])=><div key={l} style={{background:"var(--bg2)",borderRadius:6,padding:"4px 9px"}}><div style={{fontSize:9,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.06em"}}>{l}</div><div style={{fontSize:12,color:"var(--t0)",fontWeight:600}}>{v}</div></div>)}</div></div><div style={{flexShrink:0,display:'flex',flexDirection:'column',alignItems:'flex-end',gap:6}}><div style={{fontSize:13,color:ac.pr&&ac.pr.price===0?"var(--grn)":"var(--t1)",fontWeight:700}}>{ac.pr&&ac.pr.price===0?"Free":formatCurrencyValue(ac.pr&&ac.pr.price||0)}</div><Btn label='Open Detail' color='var(--acc)' sm onClick={(e)=>{e.stopPropagation();onOpenAddon&&onOpenAddon(ac);}}/></div></div>)}</div></div>}
  </div>;
}

function UserDataTab({a,onSave}){
  const pr=a.pr||{};
  const [rating,setRating]=useState(a.usr.rating||0),[notes,setNotes]=useState(a.usr.notes||"");
  const [paid,setPaid]=useState(a.usr.paid||""),[tags,setTags]=useState(a.usr.tags||[]);
  const [tagInput,setTagInput]=useState(""),[store,setStore]=useState(a.usr.source_store||""),[avionics,setAvionics]=useState((a.usr&&a.usr.avionics)||(a.rw&&a.rw.avionics)||"");
  const [saved,setSaved]=useState(false);
  const TYPE_OPTIONS=ADDON_TYPE_OPTIONS;
  const DEFAULT_SUBTYPES=DEFAULT_SUBTYPE_OPTIONS;
  const DEFAULT_SOURCES=["Aerosoft Shop","flightsim.to","Flightbeam Store","FlyTampa Store","GitHub","iniBuilds Store","Just Flight","MSFS Marketplace","Orbx Direct","PMDG Store","Simmarket","Other"].sort((a,b)=>a.localeCompare(b));
  const DEFAULT_AVIONICS=["Analog","G1000","G3000","G430","G530","G550","G750","GTN 750","Unsure"].sort((a,b)=>a.localeCompare(b));
  const sourceLibrary=useMemo(()=>{ try{ const raw=JSON.parse(localStorage.getItem('hangar_sources')||'null'); return Array.isArray(raw)&&raw.length?raw.sort((a,b)=>a.localeCompare(b)):DEFAULT_SOURCES; }catch(e){ return DEFAULT_SOURCES; } },[]);
  const avionicsLibrary=useMemo(()=>{ try{ const raw=JSON.parse(localStorage.getItem('hangar_avionics')||'null'); return Array.isArray(raw)&&raw.length?raw.sort((a,b)=>a.localeCompare(b)):DEFAULT_AVIONICS; }catch(e){ return DEFAULT_AVIONICS; } },[]);
  const subtypeLibrary=useMemo(()=>{ try{ const raw=JSON.parse(localStorage.getItem('hangar_subtypes')||'null'); return raw&&typeof raw==='object'?raw:DEFAULT_SUBTYPES; }catch(e){ return DEFAULT_SUBTYPES; } },[]);
  const [addonType,setAddonType]=useState(a.type||"Mod"),[subtype,setSubtype]=useState(a.sub||"");
  const subtypeOptions=subtypeLibrary[addonType]||[];
  const settingsTags=useMemo(()=>{ try{ const raw=localStorage.getItem('hangar_tags')||'IFR, VFR, Study Level, Freeware, Payware, Major Hub, Training, Scenic, GA, Helicopter, Military, Business Jet'; return raw.split(',').map(t=>t.trim()).filter(Boolean);}catch(e){return [];} },[]);
  useEffect(()=>{setRating(a.usr.rating||0);setNotes(a.usr.notes||"");setPaid(a.usr.paid||"");setTags(a.usr.tags||[]);setStore(a.usr.source_store||"");setAvionics((a.usr&&a.usr.avionics)||(a.rw&&a.rw.avionics)||"");setAddonType(a.type||'Mod');setSubtype(a.sub||'');},[a.id]);
  useEffect(()=>{ if(subtype && !subtypeOptions.includes(subtype) && subtypeOptions.length){ setSubtype(subtypeOptions[0]); } },[addonType]);
  function save(){ onSave(a.id,{rating,notes,paid:parseFloat(paid)||0,tags,source_store:store,avionics,type:addonType,sub:subtype,rw_override:{avionics}}); setSaved(true);setTimeout(()=>setSaved(false),2000); }
  function addTag(){ const t=tagInput.trim(); if(!t) return; if(!tags.includes(t)) setTags(ts=>[...ts,t]); if(!settingsTags.includes(t)){ const updated=[...settingsTags,t].join(', '); localStorage.setItem('hangar_tags',updated); } setTagInput(''); }
  return <div style={{display:'flex',flexDirection:'column',gap:16}}>
    <div><DL label='Your Rating' color='var(--amb)'/><div style={{display:'flex',alignItems:'center',gap:10}}><Stars v={rating} sz={24} edit onChange={setRating}/><span style={{fontSize:13,color:'var(--t1)'}}>{rating>0?rating+' / 5':'Tap to rate'}</span></div></div>
    <div><DL label='Price Paid' color='var(--grn)'/><div style={{display:'flex',gap:9,alignItems:'center'}}><span style={{fontSize:14,color:'var(--t2)'}}>{currentCurrency()}</span><input value={paid} onChange={e=>setPaid(e.target.value)} placeholder='0.00' style={{width:110,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:13,outline:'none'}}/>{pr.price>0&&<span style={{fontSize:11,color:'var(--t2)'}}>List: {formatCurrencyValue(pr.price)}</span>}</div></div>
    <div><DL label='Addon Classification' color='var(--vio)'/><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:12}}><select value={addonType} onChange={e=>setAddonType(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',color:'var(--t1)',borderRadius:7,padding:'7px 10px',fontSize:12}}>{TYPE_OPTIONS.map(s=><option key={s}>{s}</option>)}</select><ClearableDatalistInput value={subtype} setValue={setSubtype} list='subtype-opts' placeholder='Subtype' inputStyle={{width:'100%',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:7,color:'var(--t0)',fontSize:12,outline:'none'}}/><datalist id='subtype-opts'>{subtypeOptions.map(s=><option key={s} value={s}/>)}</datalist></div></div>
    <div><DL label='Obtained From' color='var(--acc)'/><ClearableDatalistInput value={store} setValue={setStore} placeholder='Where you obtained this add-on' list='store-opts' inputStyle={{width:'100%',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:7,color:'var(--t0)',fontSize:12,outline:'none'}}/><datalist id='store-opts'>{sourceLibrary.map(s=><option key={s} value={s}/>)}</datalist></div>
    <div><DL label='Tags' color='var(--acc)'/><div style={{display:'flex',flexWrap:'wrap',gap:6,marginBottom:8}}>{tags.map(t=><div key={t} style={{background:'var(--accD)',border:'1px solid var(--accB)',borderRadius:20,padding:'3px 10px',display:'flex',alignItems:'center',gap:5}}><span style={{fontSize:11,color:'var(--acc)'}}>{t}</span><span onClick={()=>setTags(ts=>ts.filter(x=>x!==t))} style={{fontSize:14,color:'var(--acc)',cursor:'pointer',lineHeight:1}}>x</span></div>)}</div>{settingsTags.filter(t=>!tags.includes(t)).length>0&&<div style={{marginBottom:8}}><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.07em',marginBottom:5}}>Add from library:</div><div style={{display:'flex',flexWrap:'wrap',gap:5}}>{settingsTags.filter(t=>!tags.includes(t)).map(t=><span key={t} onClick={()=>setTags(ts=>[...ts,t])} style={{background:'var(--bg3)',border:'1px solid var(--bdr)',borderRadius:20,padding:'2px 9px',fontSize:11,color:'var(--t2)',cursor:'pointer'}}>+ {t}</span>)}</div></div>}<div style={{display:'flex',gap:7}}><input value={tagInput} onChange={e=>setTagInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addTag()} placeholder='New tag (adds to library)...' style={{flex:1,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/><Btn label='Add' color='var(--acc)' sm onClick={addTag}/></div></div>
    <div><DL label='Notes' color='var(--amb)'/><textarea value={notes} onChange={e=>setNotes(e.target.value)} placeholder='Tips, impressions, settings, known issues...' style={{width:'100%',height:130,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:8,padding:'10px 12px',color:'var(--t0)',fontSize:12,resize:'vertical',outline:'none',lineHeight:1.65}}/></div>
    <Btn label={saved?'Saved!':'Save Changes'} color={saved?'var(--grn)':'var(--amb)'} onClick={save} full style={{justifyContent:'center',fontWeight:700,padding:'11px'}}/>
  </div>;
}

function AITab({a,availableProviders,selectedProvider,onSendToOverview,onSendToFeatures}){
  const providerChoices=(availableProviders&&availableProviders.length?availableProviders:['gemini']);
  const [provider,setProvider]=useState(selectedProvider||providerChoices[0]||'gemini');
  const [prompt,setPrompt]=useState('');
  const [busy,setBusy]=useState(false);
  const [result,setResult]=useState(null);
  const [msg,setMsg]=useState('');
  useEffect(()=>{ setProvider(selectedProvider||providerChoices[0]||'gemini'); setResult(null); setMsg(''); setPrompt(''); },[a.id,selectedProvider,providerChoices.join('|')]);
  async function run(mode){
    try{
      setBusy(true); setMsg('');
      const data=await fetchJsonSafe('/api/ai/enrich',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,mode:mode||'prompt',prompt,addon_id:a.id})});
      setResult(data);
      setMsg(mode==='prompt'?'Prompt executed.':'Generated AI addon brief.');
    }catch(e){
      setMsg((e&&e.message)||'AI request failed.');
    }finally{ setBusy(false); }
  }
  const answerHtml=(result&&((result.answer_html||'')||(result.bodyHtml||'')))||'';
  const featuresHtml=(result&&((result.featuresHtml||'')||(result.answer_html||'')))||'';
  const answerText=(result&&((result.answer_text||'')||(result.description||'')||(result.realWorldInfo||'')))||'';
  const bullets=(result&&Array.isArray(result.bullets)?result.bullets:(result&&Array.isArray(result.highlights)?result.highlights:[]))||[];
  return <div style={{display:'grid',gridTemplateColumns:'minmax(320px,430px) 1fr',gap:18,alignItems:'start'}}>
    <div style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:14}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:10}}><DL label='AI Workspace' color='var(--vio)'/><div style={{minWidth:150}}><select value={provider} onChange={e=>setProvider(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}>{providerChoices.map(p=><option key={p} value={p}>{providerLabel(p)}</option>)}</select></div></div>
      <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:10}}>Use a custom prompt for this add-on, or generate a structured AI brief you can send to Overview or Features.</div>
      <div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:5}}>Prompt</div>
      <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder='Example: How many of these aircraft are still flying? Or ask for a better features summary from the publisher details.' style={{width:'100%',height:128,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:10,padding:'10px 12px',color:'var(--t0)',fontSize:12,resize:'vertical',outline:'none',lineHeight:1.6,marginBottom:10}}/>
      <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:10}}>
        <Btn label={busy?'Working...':'Execute Prompt'} color='var(--vio)' sm onClick={()=>run('prompt')} disabled={busy || !prompt.trim()}/>
        <Btn label={busy?'Working...':'Generate AI Brief'} color='var(--acc)' sm onClick={()=>run('enrich')} disabled={busy}/>
      </div>
      {msg&&<div style={{fontSize:11,color:busy?'var(--acc)':(msg.toLowerCase().includes('failed')?'var(--red)':'var(--t2)')}}>{msg}</div>}
      {bullets.length>0&&<div style={{marginTop:12}}><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:6}}>Highlights</div><ul style={{margin:'0 0 0 18px',padding:0,color:'var(--t1)',fontSize:12,lineHeight:1.65}}>{bullets.map((b,i)=><li key={i}>{b}</li>)}</ul></div>}
      {result&&<div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:12}}>
        <Btn label='Send to Overview' color='var(--grn)' sm onClick={()=>onSendToOverview&&onSendToOverview(answerHtml||('<p>'+escapeHtml(answerText||'')+'</p>'))} disabled={!(answerHtml||answerText)}/>
        <Btn label='Send to Features' color='var(--grn)' sm onClick={()=>onSendToFeatures&&onSendToFeatures(featuresHtml||answerHtml||('<p>'+escapeHtml(answerText||'')+'</p>'))} disabled={!(featuresHtml||answerHtml||answerText)}/>
      </div>}
    </div>
    <div style={{display:'grid',gap:12}}>
      <div style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:14}}>
        <DL label='AI Response' color='var(--acc)'/>
        {result?<>
          {(result.answer_title||result.headline)&&<div style={{fontSize:16,fontWeight:800,color:'var(--t0)',marginBottom:6}}>{result.answer_title||result.headline}</div>}
          {(answerHtml||answerText)?<div style={{fontSize:12,color:'var(--t1)',lineHeight:1.7}} dangerouslySetInnerHTML={{__html:answerHtml||('<p>'+escapeHtml(answerText||'').replace(/\n/g,'<br/>')+'</p>')}}/>:<div style={{fontSize:12,color:'var(--t2)'}}>No AI response yet.</div>}
        </>:<div style={{fontSize:12,color:'var(--t2)',lineHeight:1.7}}>Run a custom prompt or generate a structured AI brief. Then send the parts you want into Overview or Features.</div>}
      </div>
      {featuresHtml&&<div style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:14}}><DL label='Feature Draft' color='var(--grn)'/><div style={{fontSize:12,color:'var(--t1)',lineHeight:1.7}} dangerouslySetInnerHTML={{__html:featuresHtml}}/></div>}
    </div>
  </div>;
}

function DetailPage({a,onBack,onFav,onSaveUser,availableAIProviders,selectedAIProvider,allAddons,initialTab='overview',onOpenMapAddon,backLabel='Back to Library'}){
  const [tab,setTab]=useState(initialTab||"overview"),cc=CC[a.type]||"#64748B";
  const [injectedFeatures,setInjectedFeatures]=useState(null);
  const [injectedOverview,setInjectedOverview]=useState(null);
  function sendToFeatures(html){setInjectedFeatures(html);setTab("features");}
  function sendToOverview(html){setInjectedOverview(html);setTab("overview");}
  const isGeo=a.type==="Airport"||a.type==="Scenery";
  useEffect(()=>{setTab(initialTab||'overview');},[a.id,initialTab]);
  useEffect(()=>{if(tab==="map"&&!isGeo)setTab("overview");},[a.id,tab,isGeo]);
  useEffect(()=>{
    fetch('/api/browser/close',{method:'POST'}).catch(()=>{});
  },[tab,a.id]);
  useEffect(()=>()=>{ fetch('/api/browser/close',{method:'POST'}).catch(()=>{}); },[]);
  const imgs=(IMGS&&IMGS[a.imgKey])||[];
  const dataTabLabel=(a.entry_kind==='tool')?null:(a.type==="Aircraft"?"Aircraft Data":(a.type==="Airport"?"Airport Data":null));
  const galleryCount=(a.gallery_paths&&a.gallery_paths.length)||imgs.length||0;
  const TABS=[
    {id:"overview",l:"Overview"},
    {id:"features",l:"Features"},
    {id:"userdata",l:"Your Data"},
    {id:"research",l:"Research"},
    {id:"docs",l:"Docs"+(a.docs&&a.docs.length>0?" ("+a.docs.length+")":"")},
    {id:"gallery",l:"Gallery"+(galleryCount>0?" ("+galleryCount+")":"")},
    ...(isGeo?[{id:"map",l:"Map"}]:[]),
    ...(dataTabLabel?[{id:"realworld",l:dataTabLabel}]:[]),
    {id:"ai",l:"AI"},
  ];
  return <div style={{display:"flex",flexDirection:"column",height:"100%",overflow:"hidden",background:"var(--bg0)"}}>
    <div style={{background:"var(--bg1)",borderBottom:"1px solid var(--bdr)",flexShrink:0}}>
      <div style={{padding:"10px 20px 0",maxWidth:1100,margin:"0 auto"}}>
        <button onClick={onBack} style={{background:"none",border:"none",color:"var(--acc)",cursor:"pointer",fontSize:12,fontWeight:600,fontFamily:"inherit",padding:"0 0 8px"}}>{backLabel}</button>
        <div style={{display:"flex",gap:14,alignItems:"flex-start",marginBottom:12,flexWrap:"wrap"}}>
          <div style={{width:96,height:66,borderRadius:10,overflow:"hidden",flexShrink:0,border:"1px solid var(--bdr)"}}>
            <AddonImg a={a} h={66}/>
          </div>
          <div style={{flex:1,minWidth:180}}>
            <div style={{display:"flex",gap:5,marginBottom:5,flexWrap:"wrap"}}><Chip label={addonTypeFor(a)} color={cc} sm/>{a.sub&&<Chip label={a.sub} color={cc} sm/>}{a.hasUpdate&&<Chip label="Update" color="var(--amb)" sm/>}</div>
            <div style={{fontSize:19,fontWeight:800,color:"var(--t0)",lineHeight:1.2,marginBottom:4}}>{a.title}</div>
            <div style={{display:"flex",alignItems:"center",gap:8,fontSize:12,color:"var(--t2)",flexWrap:"wrap"}}>
              <span>{a.publisher}</span>
              {a.pr&&a.pr.ver&&<><span>·</span><span>v{a.pr.ver}</span></>}
              {a.pr&&a.pr.price===0?<><span>·</span><span style={{color:"var(--grn)",fontWeight:600}}>Free</span></>:a.pr&&a.pr.price>0?<><span>·</span><span>${a.pr.price}</span></>:null}
            </div>
          </div>
          <div onClick={e=>e.stopPropagation()} style={{flexShrink:0,marginTop:4}}><FavBtn on={a.usr.fav} onChange={v=>onFav(a.id,v)} sz={22}/></div>
          {a.usr.rating>0&&<div style={{flexShrink:0,marginTop:4}}><Stars v={a.usr.rating} sz={13}/></div>}
          <div style={{flexShrink:0,marginTop:2}}><HelpIcon onClick={()=>window.dispatchEvent(new CustomEvent('hangar-open-guide',{detail:{tab}}))} title='How to use the current detail tab.'/></div>
        </div>
        <div style={{display:"flex",gap:0,overflowX:"auto"}}>
          {TABS.map(t=><button key={t.id} onClick={()=>setTab(t.id)} style={{background:"none",border:"none",borderBottom:tab===t.id?"2px solid "+cc:"2px solid transparent",color:tab===t.id?"var(--t0)":"var(--t2)",padding:"7px 14px",cursor:"pointer",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:"0.05em",whiteSpace:"nowrap",fontFamily:"inherit"}}>{t.l}</button>)}
        </div>
      </div>
    </div>
    <div style={{flex:1,overflowY:"auto"}}>
      <div style={{maxWidth:(tab==="docs"||tab==="research"||tab==="map"||tab==="realworld")?"100%":(tab==="overview"||tab==="features"||tab==="userdata"?"min(1500px, calc(100vw - 48px))":"1120px"),width:"100%",margin:"0 auto",padding:"20px",height:tab==="docs"?"calc(100% - 40px)":"auto",display:tab==="docs"?"flex":undefined,flexDirection:tab==="docs"?"column":undefined}}>
        {tab==="overview"&&<OverviewTab a={a} onSave={onSaveUser} injected={injectedOverview} onInjected={()=>setInjectedOverview(null)}/>}
        {tab==="features"&&<FeaturesTab a={a} injected={injectedFeatures} onInjected={()=>setInjectedFeatures(null)} onSave={onSaveUser}/>}
        {tab==="docs"&&<DocsTab a={a}/>}
        {tab==="gallery"&&<GalleryTab a={a} onSaveMeta={onSaveUser}/>}
        {tab==="research"&&<ResearchTab a={a} onSendToFeatures={sendToFeatures} onSendToOverview={sendToOverview} onSaveResources={onSaveUser}/>}
        {tab==="map"&&isGeo&&<MapTab a={a} allAddons={allAddons} onOpenAddon={onOpenMapAddon} onSave={onSaveUser}/>}
        {tab==="realworld"&&dataTabLabel&&<RealWorldTab a={a} onSave={onSaveUser}/>}
        {tab==="userdata"&&<UserDataTab a={a} onSave={onSaveUser}/>}
        {tab==="ai"&&<AITab a={a} availableProviders={availableAIProviders} selectedProvider={selectedAIProvider} onSendToOverview={sendToOverview} onSendToFeatures={sendToFeatures}/> }
      </div>
    </div>
  </div>;
}

function GeoFilter({addons,filterType,countries,setCountries,regions,setRegions}){
  const [countrySearch,setCountrySearch]=useState('');
  const [regionSearch,setRegionSearch]=useState('');
  const avail=useMemo(()=>[...new Set(addons.filter(a=>a.type===filterType&&a.rw&&a.rw.country).map(a=>a.rw.country))].sort(),[addons,filterType]);
  const avReg=useMemo(()=>{
    if(!countries.length) return [];
    const out=[];
    countries.forEach(c=>{
      addons.filter(a=>a.type===filterType&&a.rw&&a.rw.country===c).forEach(a=>{
        const raw=c==='United States'?(a.rw&&a.rw.state):c==='Canada'?(a.rw&&a.rw.province):(a.rw&&a.rw.region);
        const label=regionDisplayFor(c,raw);
        if(label&&!out.includes(label)) out.push(label);
      });
    });
    return out.sort((a,b)=>a.localeCompare(b));
  },[addons,filterType,countries]);
  const visibleCountries=useMemo(()=>{ const q=String(countrySearch||'').trim().toLowerCase(); return !q?avail:avail.filter(c=>`${c} ${abbr(c)}`.toLowerCase().includes(q)); },[avail,countrySearch]);
  const visibleRegions=useMemo(()=>{ const q=String(regionSearch||'').trim().toLowerCase(); return !q?avReg:avReg.filter(r=>String(r||'').toLowerCase().includes(q)); },[avReg,regionSearch]);
  function togC(c){setCountries(cs=>cs.includes(c)?cs.filter(x=>x!==c):[...cs,c]);setRegions([]);}
  function togR(r){setRegions(rs=>rs.includes(r)?rs.filter(x=>x!==r):[...rs,r]);}
  return <div style={{background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:9,padding:"10px 12px",marginBottom:8}}>
    <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.09em",marginBottom:7}}>Filter by Country</div>
    <ClearableInput value={countrySearch} setValue={setCountrySearch} placeholder='Search country...' inputStyle={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'7px 10px',paddingRight:(countrySearch?34:10),fontSize:11,minHeight:'auto',fontWeight:500}} style={{marginBottom:8}}/>
    <div style={{display:"flex",flexDirection:"column",gap:2,maxHeight:140,overflowY:"auto",marginBottom:avReg.length?8:0}}>
      {visibleCountries.map(c=>(<label key={c} className="cb-item"><input type="checkbox" checked={countries.includes(c)} onChange={()=>togC(c)}/>{abbr(c)}<span style={{fontSize:10,color:"var(--t3)",marginLeft:"auto"}}>{addons.filter(a=>a.type===filterType&&a.rw&&a.rw.country===c).length}</span></label>))}
      {!visibleCountries.length&&<div style={{fontSize:11,color:'var(--t3)',padding:'4px 0'}}>No countries match your search.</div>}
    </div>
    {avReg.length>0&&<>
      <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.09em",marginBottom:6,borderTop:"1px solid var(--bdr)",paddingTop:7}}>State / Province / Region</div>
      <ClearableInput value={regionSearch} setValue={setRegionSearch} placeholder='Search state / province / region...' inputStyle={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'7px 10px',paddingRight:(regionSearch?34:10),fontSize:11,minHeight:'auto',fontWeight:500}} style={{marginBottom:8}}/>
      <div style={{display:"flex",flexDirection:"column",gap:2,maxHeight:120,overflowY:"auto"}}>
        {visibleRegions.map(r=><label key={r} className="cb-item"><input type="checkbox" checked={regions.includes(r)} onChange={()=>togR(r)}/>{r}</label>)}
        {!visibleRegions.length&&<div style={{fontSize:11,color:'var(--t3)',padding:'4px 0'}}>No regions match your search.</div>}
      </div>
    </>}
    {(countries.length>0||regions.length>0)&&<button onClick={()=>{setCountries([]);setRegions([]);setCountrySearch('');setRegionSearch('');}} style={{marginTop:8,background:"none",border:"none",color:"var(--acc)",fontSize:11,cursor:"pointer",fontFamily:"inherit",padding:0}}>Clear filter</button>}
  </div>;
}

function AircraftFinder({addons,onFilterGrid,onOpenDetail,initialState,onStateChange}){
  const aircraft=addons.filter(a=>a.type==="Aircraft");
  const subtypes=["All",...new Set(aircraft.map(a=>a.sub).filter(Boolean))];
  const [sub,setSub]=useState(initialState&&initialState.sub||"All"),[minR,setMinR]=useState(initialState&&initialState.minR||""),[maxR,setMaxR]=useState(initialState&&initialState.maxR||"");
  const [minS,setMinS]=useState(initialState&&initialState.minS||""),[maxS,setMaxS]=useState(initialState&&initialState.maxS||""),[results,setResults]=useState(null);
  useEffect(()=>{ if(initialState&&Array.isArray(initialState.resultIds)){ setResults(initialState.resultIds.map(id=>aircraft.find(a=>a.id===id)).filter(Boolean)); } },[aircraft.length]);
  useEffect(()=>{ onStateChange&&onStateChange({sub,minR,maxR,minS,maxS,resultIds:Array.isArray(results)?results.map(r=>r.id):null}); },[sub,minR,maxR,minS,maxS,results]);
  function search(){
    setResults(aircraft.filter(a=>{
      if(sub!=="All"&&a.sub!==sub) return false;
      const range=(a.rw&&a.rw.range_nm)||0;
      const sm=a.rw&&a.rw.cruise&&a.rw.cruise.match(/([0-9]+)\s*kts?/i);
      const speed=sm?parseInt(sm[1]):0;
      if(minR&&range<parseInt(minR)) return false;
      if(maxR&&range>parseInt(maxR)) return false;
      if(minS&&speed<parseInt(minS)) return false;
      if(maxS&&speed>parseInt(maxS)) return false;
      return true;
    }));
  }
  function NumInput({label,val,set,unit}){
    return <div>
      <div style={{fontSize:10,color:"var(--t2)",textTransform:"uppercase",letterSpacing:"0.07em",marginBottom:5}}>{label}{unit&&<span style={{color:"var(--t3)"}}> ({unit})</span>}</div>
      <input type="number" value={val} onChange={e=>set(e.target.value)} placeholder="Any"
        style={{width:"100%",background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:10,padding:"9px 12px",color:"var(--t0)",fontSize:13,outline:"none"}}/>
    </div>;
  }
  return <div style={{padding:24,maxWidth:980}}>
    <div style={{fontSize:17,fontWeight:800,color:"var(--t0)",marginBottom:4}}>Aircraft Finder</div>
    <div style={{fontSize:12,color:"var(--t2)",marginBottom:20}}>Filter your aircraft by performance specs to find the right plane for your mission.</div>
    <div style={{background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:14,padding:20,marginBottom:18}}>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(150px,1fr))",gap:14,marginBottom:14}}>
        <div>
          <div style={{fontSize:10,color:"var(--t2)",textTransform:"uppercase",letterSpacing:"0.07em",marginBottom:5}}>Subtype</div>
          <select value={sub} onChange={e=>setSub(e.target.value)} style={{width:"100%",background:"var(--bg0)",border:"1px solid var(--bdr)",color:"var(--t1)",borderRadius:10,padding:"9px 12px",fontSize:13,cursor:"pointer"}}>
            {subtypes.map(t=><option key={t}>{t}</option>)}
          </select>
        </div>
        <NumInput label="Min Range" val={minR} set={setMinR} unit="nm"/>
        <NumInput label="Max Range" val={maxR} set={setMaxR} unit="nm"/>
        <NumInput label="Min Cruise" val={minS} set={setMinS} unit="kts"/>
        <NumInput label="Max Cruise" val={maxS} set={setMaxS} unit="kts"/>
      </div>
      <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
        <Btn label="Find Aircraft" color="var(--acc)" onClick={search}/>
        {results!==null&&results.length>0&&<Btn label={"Show "+results.length+" in Grid"} color="var(--grn)" onClick={()=>onFilterGrid&&onFilterGrid(results.map(a=>a.id))}/>}
        {results!==null&&<span style={{fontSize:12,color:"var(--t2)"}}>{results.length} matched</span>}
      </div>
    </div>
    {results!==null&&(results.length===0
      ?<div style={{textAlign:"center",padding:"40px 0",color:"var(--t2)",fontSize:13}}>No aircraft match. Try wider ranges.</div>
      :<div style={{display:"flex",flexDirection:"column",gap:10}}>
        {results.map(ac=>(
          <div key={ac.id} onClick={()=>onOpenDetail&&onOpenDetail(ac)} style={{background:"var(--card)",border:"1px solid var(--bdr)",borderRadius:14,padding:16,display:"flex",gap:14,alignItems:"center",cursor:'pointer'}}>
            <div style={{width:80,height:56,borderRadius:8,overflow:"hidden",flexShrink:0}}><AddonImg a={ac} h={56}/></div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontSize:14,fontWeight:700,color:"var(--t0)",marginBottom:3}}>{ac.title}</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:7}}>{ac.publisher} · {ac.sub}</div>
              <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                {[[(ac.rw&&ac.rw.mfr)||"—","Manufacturer"],[(ac.rw&&ac.rw.range_nm)?`${ac.rw.range_nm} nm`:((ac.rw&&ac.rw.range)||"—"),"Range"],[(ac.rw&&ac.rw.cruise)||"—","Cruise"],[(ac.rw&&ac.rw.ceiling)||"—","Ceiling"],[(ac.rw&&ac.rw.seats)||"—","Seats"]].map(([v,l])=>(
                  <div key={l} style={{background:"var(--bg2)",borderRadius:6,padding:"4px 9px"}}>
                    <div style={{fontSize:9,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.06em"}}>{l}</div>
                    <div style={{fontSize:12,color:"var(--t0)",fontWeight:600}}>{v}</div>
                  </div>
                ))}
              </div>
            </div>
            <div style={{flexShrink:0,display:'flex',flexDirection:'column',alignItems:'flex-end',gap:6}}>
              <div style={{fontSize:13,color:ac.pr&&ac.pr.price===0?"var(--grn)":"var(--t1)",fontWeight:700}}>{ac.pr&&ac.pr.price===0?"Free":formatCurrencyValue(ac.pr&&ac.pr.price||0)}</div>
              <Btn label='Open Detail' color='var(--acc)' sm onClick={(e)=>{e.stopPropagation(); onOpenDetail&&onOpenDetail(ac);}}/>
            </div>
          </div>
        ))}
      </div>)}
  </div>;
}

function ChoiceListManager({label,items,onChange,placeholder="Add item..."}){
  const [draft,setDraft]=useState("");
  const [selected,setSelected]=useState([]);
  function addItem(){
    const v=(draft||"").trim(); if(!v) return;
    if((items||[]).some(x=>String(x).toLowerCase()===v.toLowerCase())){ setDraft(""); return; }
    onChange([...(items||[]), v].sort((a,b)=>String(a).localeCompare(String(b))));
    setDraft("");
  }
  function toggle(val){ setSelected(cur=>cur.includes(val)?cur.filter(x=>x!==val):[...cur,val]); }
  function delSelected(){ onChange((items||[]).filter(x=>!selected.includes(x))); setSelected([]); }
  function editAt(idx,val){ const next=[...(items||[])]; next[idx]=val; onChange(next); }
  return <div style={{marginBottom:12}}>
    <div style={{fontSize:11,color:'var(--t1)',fontWeight:600,marginBottom:6}}>{label}</div>
    <div style={{maxHeight:180,overflowY:'auto',border:'1px solid var(--bdr)',borderRadius:8,background:'var(--bg0)',padding:8}}>
      {(items||[]).length===0&&<div style={{fontSize:11,color:'var(--t3)',padding:6}}>No items yet.</div>}
      {(items||[]).map((item,idx)=><div key={label+idx} style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}><input type='checkbox' checked={selected.includes(item)} onChange={()=>toggle(item)}/><input value={item} onChange={e=>editAt(idx,e.target.value)} style={{flex:1,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:6,padding:'6px 8px',color:'var(--t0)',fontSize:11,outline:'none'}}/></div>)}
    </div>
    <div style={{display:'flex',gap:8,marginTop:8,alignItems:'center'}}>
      <input value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addItem()} placeholder={placeholder} style={{flex:1,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'7px 9px',color:'var(--t0)',fontSize:11,outline:'none'}}/>
      <Btn label='Add' color='var(--acc)' sm onClick={addItem}/>
      <Btn label='Delete Checked' color='var(--red)' sm onClick={delSelected} disabled={selected.length===0}/>
    </div>
  </div>;
}

function SiteListManager({label,items,onChange}){
  const [draftName,setDraftName]=useState('');
  const [draftUrl,setDraftUrl]=useState('');
  const [selected,setSelected]=useState([]);
  function addItem(){
    const name=String(draftName||'').trim();
    const url=String(draftUrl||'').trim();
    if(!name || !url) return;
    const entry={name,url};
    onChange([...(items||[]),entry].filter(x=>x&&x.name&&x.url));
    setDraftName(''); setDraftUrl('');
  }
  function toggle(idx){ setSelected(cur=>cur.includes(idx)?cur.filter(x=>x!==idx):[...cur,idx]); }
  function delSelected(){ onChange((items||[]).filter((_,idx)=>!selected.includes(idx))); setSelected([]); }
  function editAt(idx,key,val){ const next=[...(items||[])]; next[idx]={...(next[idx]||{}),[key]:val}; onChange(next); }
  return <div style={{marginBottom:12}}>
    <div style={{fontSize:11,color:'var(--t1)',fontWeight:600,marginBottom:6}}>{label}</div>
    <div style={{maxHeight:220,overflowY:'auto',border:'1px solid var(--bdr)',borderRadius:8,background:'var(--bg0)',padding:8}}>
      {(items||[]).length===0&&<div style={{fontSize:11,color:'var(--t3)',padding:6}}>No sites yet.</div>}
      {(items||[]).map((item,idx)=><div key={label+idx} style={{display:'grid',gridTemplateColumns:'20px minmax(120px,.7fr) minmax(220px,1fr)',alignItems:'center',gap:8,marginBottom:6}}><input type='checkbox' checked={selected.includes(idx)} onChange={()=>toggle(idx)}/><input value={item.name||''} onChange={e=>editAt(idx,'name',e.target.value)} style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:6,padding:'6px 8px',color:'var(--t0)',fontSize:11,outline:'none'}}/><input value={item.url||''} onChange={e=>editAt(idx,'url',e.target.value)} style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:6,padding:'6px 8px',color:'var(--t0)',fontSize:11,outline:'none'}}/></div>)}
    </div>
    <div style={{display:'grid',gridTemplateColumns:'minmax(120px,.7fr) minmax(220px,1fr) auto auto',gap:8,marginTop:8,alignItems:'center'}}>
      <input value={draftName} onChange={e=>setDraftName(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addItem()} placeholder='Site name' style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'7px 9px',color:'var(--t0)',fontSize:11,outline:'none'}}/>
      <input value={draftUrl} onChange={e=>setDraftUrl(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addItem()} placeholder='https://example.com' style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'7px 9px',color:'var(--t0)',fontSize:11,outline:'none'}}/>
      <Btn label='Add' color='var(--acc)' sm onClick={addItem}/>
      <Btn label='Delete Checked' color='var(--red)' sm onClick={delSelected} disabled={selected.length===0}/>
    </div>
  </div>;
}

function DataOptionsManager(){
  const defaultSubtypes=DEFAULT_SUBTYPE_OPTIONS;
  const [sources,setSources]=useState(()=>{try{const raw=JSON.parse(localStorage.getItem('hangar_sources')||'null');return Array.isArray(raw)&&raw.length?raw:["Aerosoft Shop","flightsim.to","Flightbeam Store","FlyTampa Store","GitHub","iniBuilds Store","Just Flight","MSFS Marketplace","Orbx Direct","PMDG Store","Simmarket","Other"]}catch(e){return ["Aerosoft Shop","flightsim.to","Flightbeam Store","FlyTampa Store","GitHub","iniBuilds Store","Just Flight","MSFS Marketplace","Orbx Direct","PMDG Store","Simmarket","Other"]}});
  const [airportSites,setAirportSites]=useState(()=>loadSiteEntries('hangar_airport_sites', defaultAirportSiteEntries()));
  const [aircraftSites,setAircraftSites]=useState(()=>loadSiteEntries('hangar_aircraft_sites', defaultAircraftSiteEntries()));
  const [avionics,setAvionics]=useState(()=>{try{const raw=JSON.parse(localStorage.getItem('hangar_avionics')||'null');return Array.isArray(raw)&&raw.length?raw:["Analog","G1000","G3000","G430","G530","G550","G750","GTN 750","Unsure"]}catch(e){return ["Analog","G1000","G3000","G430","G530","G550","G750","GTN 750","Unsure"]}});
  const [tags,setTags]=useState(()=>{try{const raw=localStorage.getItem('hangar_tags');return raw?raw.split(',').map(x=>x.trim()).filter(Boolean):["IFR","VFR","Study Level","Freeware","Payware"]}catch(e){return ["IFR","VFR","Study Level","Freeware","Payware"]}});
  const [subtypes,setSubtypes]=useState(()=>{try{const raw=JSON.parse(localStorage.getItem('hangar_subtypes')||'null');return raw&&typeof raw==='object'?raw:defaultSubtypes}catch(e){return defaultSubtypes}});
  const [activeType,setActiveType]=useState('Aircraft');
  const [ok,setOk]=useState(false);
  async function save(){
    const cleanSources=(sources||[]).map(x=>String(x).trim()).filter(Boolean).sort((a,b)=>a.localeCompare(b));
    const cleanAirportSites=(airportSites||[]).map(x=>({name:String((x&&x.name)||'').trim(),url:String((x&&x.url)||'').trim()})).filter(x=>x.name&&x.url);
    const cleanAircraftSites=(aircraftSites||[]).map(x=>({name:String((x&&x.name)||'').trim(),url:String((x&&x.url)||'').trim()})).filter(x=>x.name&&x.url);
    const cleanAvionics=(avionics||[]).map(x=>String(x).trim()).filter(Boolean).sort((a,b)=>a.localeCompare(b));
    const cleanTags=(tags||[]).map(x=>String(x).trim()).filter(Boolean);
    const cleanSubtypes=Object.fromEntries(Object.entries(subtypes||{}).map(([k,v])=>[k,(v||[]).map(x=>String(x).trim()).filter(Boolean)]));
    localStorage.setItem('hangar_sources', JSON.stringify(cleanSources));
    localStorage.setItem('hangar_airport_sites', JSON.stringify(cleanAirportSites));
    localStorage.setItem('hangar_aircraft_sites', JSON.stringify(cleanAircraftSites));
    localStorage.setItem('hangar_avionics', JSON.stringify(cleanAvionics));
    localStorage.setItem('hangar_tags', cleanTags.join(', '));
    localStorage.setItem('hangar_subtypes', JSON.stringify(cleanSubtypes));
    try{ await fetch('/api/data-options',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({options:{sources:cleanSources, airport_sites:cleanAirportSites, aircraft_sites:cleanAircraftSites, avionics:cleanAvionics, tags:cleanTags, subtypes:cleanSubtypes}})});}catch(e){}
    try{ window.dispatchEvent(new CustomEvent('hangar-data-options-updated',{detail:{sources:cleanSources, subtypes:cleanSubtypes, airport_sites:cleanAirportSites, aircraft_sites:cleanAircraftSites}})); }catch(e){}
    setOk(true); setTimeout(()=>setOk(false),1800);
  }
  return <div>
    <div style={{fontSize:11,color:'var(--t2)',marginBottom:12}}>Manage drop-down choices and browser site shortcuts here. Use the site lists to control which quick-search buttons appear in Aircraft Data and Airport Data.</div>
    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(340px,1fr))',gap:16,alignItems:'start'}}>
      <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:12}}>
        <ChoiceListManager label='Obtained From Options' items={sources} onChange={setSources} placeholder='Add source...'/>
        <ChoiceListManager label='Avionics Choices' items={avionics} onChange={setAvionics} placeholder='Add avionics option...'/>
      </div>
      <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:12}}>
        <ChoiceListManager label='Tag Library' items={tags} onChange={setTags} placeholder='Add tag...'/>
        <div style={{marginBottom:0}}>
          <div style={{fontSize:11,color:'var(--t1)',fontWeight:600,marginBottom:6}}>Subtype Choices</div>
          <div style={{display:'flex',gap:8,marginBottom:8,flexWrap:'wrap'}}>{ADDON_TYPE_OPTIONS.map(t=><button key={t} onClick={()=>setActiveType(t)} style={{background:activeType===t?'var(--accD)':'var(--bg0)',border:'1px solid '+(activeType===t?'var(--accB)':'var(--bdr)'),color:activeType===t?'var(--acc)':'var(--t1)',borderRadius:7,padding:'6px 10px',cursor:'pointer',fontSize:11,fontWeight:600}}>{t}</button>)}</div>
          <ChoiceListManager label={activeType+' Subtypes'} items={(subtypes[activeType])||[]} onChange={(vals)=>setSubtypes(cur=>({...cur,[activeType]:vals}))} placeholder={'Add '+activeType.toLowerCase()+' subtype...'}/>
        </div>
      </div>
      <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:12,gridColumn:'1 / -1'}}>
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(420px,1fr))',gap:16,alignItems:'start'}}>
          <SiteListManager label='Airport Data Recommended Sites' items={airportSites} onChange={setAirportSites}/>
          <SiteListManager label='Aircraft Data Recommended Sites' items={aircraftSites} onChange={setAircraftSites}/>
        </div>
      </div>
    </div>
    <div style={{display:'flex',gap:8,alignItems:'center',marginTop:12}}><Btn label={ok?'Saved!':'Save Data Options'} color={ok?'var(--grn)':'var(--acc)'} sm onClick={save}/><span style={{fontSize:10,color:'var(--t3)'}}>These lists drive Your Data dropdowns and data-tab recommended-site buttons.</span></div>
  </div>;
}

function TopFolderSelector({folders,selected,onToggle,onSave,onReload,onReset,apiMode}){
  return <div style={{background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginTop:14}}><div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,flexWrap:"wrap"}}><div><div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Addon Folder Selection</div><div style={{fontSize:11,color:"var(--t2)"}}>Only top folders in your Addons Root are shown here. Checked folders are scanned.</div></div><div style={{display:"flex",gap:8,flexWrap:"wrap"}}><Btn label="Save Selection" color="var(--acc)" sm onClick={onSave}/><Btn label="Reload" color="var(--t2)" sm onClick={onReload}/><Btn label="Reset Library" color="var(--red)" sm onClick={onReset}/></div></div>{!apiMode&&<div style={{fontSize:11,color:"var(--amb)",marginTop:10}}>Start the backend to load folder choices.</div>}{apiMode&&folders.length===0&&<div style={{fontSize:11,color:"var(--t2)",marginTop:10}}>Set and save Addons Root first, then reload this list.</div>}{folders.length>0&&<div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:8,marginTop:12}}>{folders.map(f=><label key={f.path} className="cb-item" style={{background:"var(--bg0)",border:"1px solid var(--bdr)",borderRadius:8,padding:"9px 10px"}}><input type="checkbox" checked={selected.includes(f.path)} onChange={()=>onToggle(f.path)}/><span style={{color:"var(--t0)",fontSize:12,fontWeight:600}}>{f.name}</span><span style={{marginLeft:"auto",fontSize:10,color:"var(--t3)"}}>{f.name}</span></label>)}</div>}</div>;
}


function PathInput({id,label,hint,placeholder}){
  const storageKey='hangar_'+id;
  const [value,setValue]=useState(()=>{try{return localStorage.getItem(storageKey)||''}catch(e){return ''}});
  const [saved,setSaved]=useState(false);
  useEffect(()=>{
    try{ setValue(localStorage.getItem(storageKey)||''); }catch(e){}
  },[storageKey]);
  useEffect(()=>{
    function onPicked(ev){
      if(!ev.detail) return;
      if(id==='addons_root' && ev.detail.id==='addons_root_library') return;
      if(![''+id].includes(ev.detail.id)) return;
      setValue(ev.detail.value||'');
    }
    window.addEventListener('hangar-path-picked', onPicked);
    return ()=>window.removeEventListener('hangar-path-picked', onPicked);
  },[id]);
  async function save(){
    try{localStorage.setItem(storageKey,value||'');}catch(e){}
    try{await fetch('/api/settings/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:value||''})});}catch(e){}
    setSaved(true); setTimeout(()=>setSaved(false),1500);
  }
  function browse(){
    window.dispatchEvent(new CustomEvent('hangar-browse-path',{detail:{id,label,current:value||''}}));
  }
  return <div style={{marginBottom:12}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4,gap:8}}>
      <div style={{fontSize:11,color:'var(--t1)',fontWeight:600}}>{label}</div>
      {saved&&<span style={{fontSize:10,color:'var(--grn)'}}>Saved</span>}
    </div>
    {hint&&<div style={{fontSize:10,color:'var(--t3)',marginBottom:6}}>{hint}</div>}
    <div style={{display:'flex',gap:8,alignItems:'center'}}>
      <ClearableInput value={value} setValue={setValue} placeholder={placeholder||''} style={{flex:1}} inputStyle={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,color:'var(--t0)',fontSize:12,outline:'none',minHeight:'auto',padding:'8px 11px'}}/>
      <Btn label='Browse…' color='var(--t2)' sm onClick={browse}/>
      <Btn label='Save' color='var(--acc)' sm onClick={save}/>
    </div>
  </div>;
}

function FolderBrowserModal({picker,onClose,onChoose}){
  if(!picker) return null;
  const fileMode=picker.mode==='file';
  return <div style={{position:'fixed',inset:0,zIndex:100001,background:'rgba(2,6,23,.55)',display:'flex',alignItems:'center',justifyContent:'center',padding:18}}>
    <div style={{width:'min(920px, 100%)',maxHeight:'min(84vh, 940px)',display:'grid',gridTemplateColumns:'160px 1fr',gap:14,background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:18,boxShadow:'0 28px 80px rgba(0,0,0,.55)',padding:16}}>
      <div style={{display:'flex',flexDirection:'column',gap:10,minHeight:0}}>
        <div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>Drives</div>
        <div style={{display:'grid',gap:8,overflow:'auto'}}>{(picker.drives||[]).map(d=><button key={d.path} onClick={()=>picker.onNavigate&&picker.onNavigate(d.path)} style={{textAlign:'left',background:picker.current===d.path?'var(--accD)':'var(--bg0)',border:'1px solid '+(picker.current===d.path?'var(--accB)':'var(--bdr)'),borderRadius:10,padding:'10px 11px',color:picker.current===d.path?'var(--acc)':'var(--t1)',cursor:'pointer',fontFamily:'inherit'}}>{d.name}</button>)}</div>
      </div>
      <div style={{display:'flex',flexDirection:'column',gap:10,minHeight:0}}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,flexWrap:'wrap'}}>
          <div>
            <div style={{fontSize:18,fontWeight:800,color:'var(--t0)'}}>{fileMode?'Choose File':'Choose Folder'}</div>
            <div style={{fontSize:12,color:'var(--t2)'}}>{picker.label||(fileMode?'Select a file path':'Select a folder path')}</div>
          </div>
          <div style={{display:'flex',gap:8,flexWrap:'wrap'}}><Btn label='Up One Level' color='var(--t2)' sm onClick={()=>picker.parent && picker.onNavigate&&picker.onNavigate(picker.parent)} disabled={!picker.parent}/>{!fileMode&&<Btn label='Use Current Folder' color='var(--acc)' sm onClick={()=>onChoose&&onChoose(picker.id,picker.current)}/>}<Btn label='Cancel' color='var(--t2)' sm onClick={onClose}/></div>
        </div>
        <div style={{fontSize:11,color:'var(--t1)',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:10,padding:'9px 12px',fontFamily:'monospace',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={picker.current}>{picker.current||'No folder selected'}</div>
        <div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>Subfolders</div>
        <div style={{minHeight:fileMode?150:0,overflow:'auto',display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(220px,1fr))',gap:10}}>
          {picker.loading&&<div style={{fontSize:12,color:'var(--t2)'}}>Loading folders…</div>}
          {!picker.loading && (picker.folders||[]).length===0 && <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'14px 12px',fontSize:12,color:'var(--t2)'}}>No child folders found here.</div>}
          {(picker.folders||[]).map(folder=><button key={folder.path} onClick={()=>picker.onNavigate&&picker.onNavigate(folder.path)} style={{textAlign:'left',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'10px 12px',cursor:'pointer',fontFamily:'inherit'}}><div style={{fontSize:12,fontWeight:700,color:'var(--t0)'}}>{folder.name}</div><div style={{fontSize:11,color:'var(--t2)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{folder.path}</div></button>)}
        </div>
        {fileMode&&<><div style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>Matching Files</div><div style={{minHeight:0,overflow:'auto',display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(260px,1fr))',gap:10}}>{picker.loading&&<div style={{fontSize:12,color:'var(--t2)'}}>Loading files…</div>}{!picker.loading && (picker.files||[]).length===0 && <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'14px 12px',fontSize:12,color:'var(--t2)'}}>No matching files found here.</div>}{(picker.files||[]).map(file=><button key={file.path} onClick={()=>onChoose&&onChoose(picker.id,file.path)} style={{textAlign:'left',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'10px 12px',cursor:'pointer',fontFamily:'inherit'}}><div style={{fontSize:12,fontWeight:700,color:'var(--t0)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{file.name}</div><div style={{fontSize:11,color:'var(--t2)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{file.path}</div></button>)}</div></>}
      </div>
    </div>
  </div>;
}

function TagsEditor(){
  const [tags,setTags]=useState(()=>{try{const raw=localStorage.getItem('hangar_tags');return raw?raw.split(',').map(x=>x.trim()).filter(Boolean):[]}catch(e){return []}});
  const [draft,setDraft]=useState('');
  const [saved,setSaved]=useState(false);
  function addTag(){
    const t=String(draft||'').trim();
    if(!t) return;
    if(tags.some(x=>x.toLowerCase()===t.toLowerCase())){ setDraft(''); return; }
    setTags(prev=>[...prev,t]);
    setDraft('');
  }
  function removeTag(tag){ setTags(prev=>prev.filter(t=>t!==tag)); }
  async function save(){
    const clean=(tags||[]).map(x=>String(x).trim()).filter(Boolean);
    try{ localStorage.setItem('hangar_tags', clean.join(', ')); }catch(e){}
    try{ await fetch('/api/data-options',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({options:{tags:clean}})}); }catch(e){}
    setSaved(true); setTimeout(()=>setSaved(false),1500);
  }
  return <div>
    <div style={{display:'flex',flexWrap:'wrap',gap:8,marginBottom:10}}>
      {(tags||[]).length===0&&<div style={{fontSize:11,color:'var(--t3)'}}>No tags saved yet.</div>}
      {(tags||[]).map(tag=><div key={tag} style={{display:'inline-flex',alignItems:'center',gap:6,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:18,padding:'4px 10px'}}><span style={{fontSize:11,color:'var(--t1)'}}>{tag}</span><button onClick={()=>removeTag(tag)} style={{background:'none',border:'none',padding:0,cursor:'pointer',color:'var(--red)',fontSize:13,lineHeight:1}}>×</button></div>)}
    </div>
    <div style={{display:'flex',gap:8,alignItems:'center',marginBottom:8}}>
      <input value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addTag()} placeholder='Add tag...' style={{flex:1,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/>
      <Btn label='Add' color='var(--acc)' sm onClick={addTag}/>
      <Btn label='Save Tags' color='var(--vio)' sm onClick={save}/>
    </div>
    {saved&&<div style={{fontSize:11,color:'var(--grn)'}}>Tag library saved.</div>}
  </div>;
}






function GlobalLibraryMap({items,selectedItems,onOpenAddon,onClose,accent='var(--acc)'}){
  const mapRef=useRef(null), leafRef=useRef(null), tileRef=useRef(null), polygonsRef=useRef(null), autoFitRef=useRef(false);
  const [layer,setLayer]=useState('satellite');
  const [scope,setScope]=useState('filtered');
  const [regionKey,setRegionKey]=useState('world');
  const [resolvedItems,setResolvedItems]=useState([]);
  const [projectedPoints,setProjectedPoints]=useState([]);
  const [selectedAddonId,setSelectedAddonId]=useState('');
  const [hoveredAddonId,setHoveredAddonId]=useState('');
  const [showList,setShowList]=useState(true);
  const [listSearch,setListSearch]=useState('');
  const [mapReady,setMapReady]=useState(false);
  const [progress,setProgress]=useState({phase:'idle',done:0,total:0,message:''});
  const [renderError,setRenderError]=useState('');
  const [mapBounds,setMapBounds]=useState(null);

  const selectedGeoCount=useMemo(()=>((selectedItems||[]).filter(a=>['Airport','Scenery'].includes(addonTypeFor(a)))).length,[selectedItems]);
  const sourceItems=useMemo(()=>{
    let src=(scope==='selected' && selectedGeoCount>0)?(selectedItems||[]):(items||[]);
    return src.filter(a=>['Airport','Scenery'].includes(addonTypeFor(a)));
  },[scope,selectedGeoCount,selectedItems,items]);

  const LAYERS={
    satellite:{l:'Satellite',tile:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',attr:'Esri'},
    road:{l:'Road',tile:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',attr:'OSM'}
  };
  const REGIONS={
    world:{label:'World', bounds:[[-58,-170],[84,190]]},
    north_america:{label:'North America', bounds:[[7,-168],[83,-52]]},
    south_america:{label:'South America', bounds:[[-58,-93],[15,-30]]},
    europe:{label:'Europe', bounds:[[34,-12],[72,35]]},
    africa:{label:'Africa', bounds:[[-36,-20],[38,55]]},
    asia:{label:'Asia', bounds:[[2,25],[76,180]]},
    oceania:{label:'Oceania', bounds:[[-50,110],[10,180]]},
    caribbean:{label:'Caribbean', bounds:[[8,-90],[30,-58]]}
  };

  function valid(lat,lon){
    const la=Number(lat), lo=Number(lon);
    if(!Number.isFinite(la) || !Number.isFinite(lo)) return false;
    if(la===0 && lo===0) return false;
    return la>=-90 && la<=90 && lo>=-180 && lo<=180;
  }
  function airportSubtypeKey(addon){ return String(addon&&addon.sub||'Other').trim() || 'Other'; }
  function subtypeColor(addon){
    const sub=String(addon&&addon.sub||'').toLowerCase();
    if(addonTypeFor(addon)==='Airport'){
      if(sub.includes('international')) return '#38BDF8';
      if(sub.includes('regional')) return '#22C55E';
      if(sub.includes('municipal')) return '#FBBF24';
      if(sub.includes('military')) return '#F97316';
      if(sub.includes('heli')) return '#A78BFA';
      if(sub.includes('bush') || sub.includes('strip')) return '#FB7185';
      if(sub.includes('commercial')) return '#38BDF8';
      return '#38BDF8';
    }
    return '#F59E0B';
  }
  const airportLegend=useMemo(()=>{
    const map=new Map();
    (resolvedItems||[]).forEach(item=>{
      if(addonTypeFor(item&&item.addon)!=='Airport' || !item.point) return;
      const key=airportSubtypeKey(item.addon);
      if(!map.has(key)) map.set(key, subtypeColor(item.addon));
    });
    return Array.from(map.entries()).map(([label,color])=>({label,color}));
  },[resolvedItems]);
  function markerColor(addon){
    if(addonTypeFor(addon)==='Airport' && airportLegend.length<=1) return '#38BDF8';
    return subtypeColor(addon);
  }

  function inBounds(item,bounds){
    if(!bounds) return true;
    try{
      if(item && item.point && valid(item.point.lat,item.point.lon)){
        return bounds.contains([Number(item.point.lat), Number(item.point.lon)]);
      }
      if(item && Array.isArray(item.polygon) && item.polygon.length>2){
        return item.polygon.some(p=>valid(p&&p.lat,p&&p.lon) && bounds.contains([Number(p.lat), Number(p.lon)]));
      }
    }catch(e){}
    return false;
  }

  const displayItems=useMemo(()=>{
    const scoped=(scope==='view' && mapBounds)?(resolvedItems||[]).filter(item=>inBounds(item, mapBounds)):(resolvedItems||[]);
    return scoped;
  },[resolvedItems, scope, mapBounds]);

  const filteredListItems=useMemo(()=>{
    const q=String(listSearch||'').trim().toLowerCase();
    const src=displayItems.filter(item=>item && (item.point || (Array.isArray(item.polygon)&&item.polygon.length>2)));
    if(!q) return src;
    return src.filter(item=>{
      const a=item.addon||{};
      const hay=[a.title,a.sub,item.icao,a.publisher,(a.rw&&a.rw.country),(a.rw&&a.rw.state),(a.rw&&a.rw.region)].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(q);
    });
  },[displayItems,listSearch]);

  const selectedItem=useMemo(()=>displayItems.find(item=>String(item.addon&&item.addon.id)===String(selectedAddonId))||null,[displayItems,selectedAddonId]);
  const hoveredPoint=useMemo(()=>projectedPoints.find(pt=>String(pt.key)===String(hoveredAddonId))||null,[projectedPoints,hoveredAddonId]);

  function syncProjected(){
    const map=leafRef.current;
    if(!map){ setProjectedPoints([]); return; }
    const pts=(displayItems||[]).filter(item=>item&&item.point&&valid(item.point.lat,item.point.lon)).map(item=>{
      const pt=map.latLngToContainerPoint([Number(item.point.lat), Number(item.point.lon)]);
      return {key:String(item.addon&&item.addon.id), addon:item.addon, item, x:Math.round(pt.x), y:Math.round(pt.y), lat:Number(item.point.lat), lon:Number(item.point.lon), source:item.source||'', icao:item.icao||'', visible:Number.isFinite(pt.x)&&Number.isFinite(pt.y)};
    });
    setProjectedPoints(pts);
    if(pts.length) setRenderError('');
  }

  function refreshPolygonLayers(){
    const layerGroup=polygonsRef.current;
    if(!layerGroup) return;
    try{ layerGroup.clearLayers(); }catch(e){}
    (displayItems||[]).forEach(item=>{
      if(!Array.isArray(item.polygon) || item.polygon.length<3) return;
      const latlngs=item.polygon.map(p=>[Number(p.lat),Number(p.lon)]).filter(([la,lo])=>valid(la,lo));
      if(latlngs.length<3) return;
      const poly=L.polygon(latlngs,{color:markerColor(item.addon),fillColor:markerColor(item.addon),fillOpacity:0.16,weight:2});
      poly.on('click',()=>setSelectedAddonId(String(item.addon&&item.addon.id||'')));
      layerGroup.addLayer(poly);
    });
  }

  function fitItemsToMap(list){
    const map=leafRef.current;
    if(!map) return;
    const latlngs=[];
    (list||[]).forEach(item=>{
      if(item.point && valid(item.point.lat,item.point.lon)) latlngs.push([Number(item.point.lat), Number(item.point.lon)]);
      if(Array.isArray(item.polygon)) item.polygon.forEach(p=>{ if(valid(p&&p.lat,p&&p.lon)) latlngs.push([Number(p.lat), Number(p.lon)]); });
    });
    if(!latlngs.length){ map.setView([20,0],2); return; }
    if(latlngs.length===1){ map.setView(latlngs[0], 8); return; }
    try{ map.fitBounds(latlngs,{padding:[40,40],maxZoom:7}); }catch(e){ map.setView([20,0],2); }
  }

  function applyRegion(key){
    const map=leafRef.current;
    setRegionKey(key);
    if(!map) return;
    const preset=REGIONS[key]||REGIONS.world;
    try{ map.fitBounds(preset.bounds,{padding:[20,20],maxZoom:key==='world'?3:6}); }catch(e){}
  }

  function selectItem(item,{zoomInto=false}={}){
    if(!item) return;
    setSelectedAddonId(String(item.addon&&item.addon.id||''));
    const map=leafRef.current;
    if(map && item.point && valid(item.point.lat,item.point.lon) && zoomInto){
      try{ map.setView([Number(item.point.lat), Number(item.point.lon)], Math.max(map.getZoom(), 9), {animate:true}); }catch(e){}
    }
  }

  useEffect(()=>{ if(scope==='selected' && selectedGeoCount===0) setScope('filtered'); },[scope,selectedGeoCount]);

  useEffect(()=>{
    let alive=true;
    async function resolveCoords(){
      setMapReady(false); setRenderError(''); autoFitRef.current=false;
      if(!sourceItems.length){ if(alive){ setResolvedItems([]); setProgress({phase:'done',done:0,total:0,message:'No airport or scenery add-ons are available for the current map scope.'}); } return; }
      setProgress({phase:'loading',done:0,total:sourceItems.length,message:`Resolving ${sourceItems.length} airport/scenery location${sourceItems.length===1?'':'s'}...`});
      try{
        const direct=sourceItems.map(addon=>{
          const coords=addonCoordinates(addon);
          const point=coords&&valid(coords.lat,coords.lon)?{lat:Number(coords.lat),lon:Number(coords.lon)}:null;
          const polygon=Array.isArray(addon&&addon.usr&&addon.usr.map_polygon)?(addon.usr.map_polygon||[]).filter(p=>valid(p&&p.lat,p&&p.lon)).map(p=>({lat:Number(p.lat),lon:Number(p.lon)})):[];
          const icao=String((addon&&addon.rw&&addon.rw.icao)||'').trim().toUpperCase();
          return {addon, point, polygon, source:point?'stored':(polygon.length?'polygon':''), icao};
        });
        let resolved=direct.filter(x=>x.point || x.polygon.length>2);
        const unresolved=direct.filter(x=>!x.point && x.polygon.length<=2).map(x=>x.addon);
        if(unresolved.length){
          const data=await fetchJsonSafe('/api/map/resolve-addons-coords',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({addon_ids:unresolved.map(a=>a.id)})});
          const byId=new Map((unresolved||[]).map(a=>[String(a.id),a]));
          ((data&&data.items)||[]).forEach(it=>{
            const addon=byId.get(String(it.addon_id));
            if(!addon) return;
            const point=it&&it.point&&valid(it.point.lat,it.point.lon)?{lat:Number(it.point.lat),lon:Number(it.point.lon)}:null;
            const polygon=Array.isArray(it&&it.polygon)?it.polygon.filter(p=>valid(p&&p.lat,p&&p.lon)).map(p=>({lat:Number(p.lat),lon:Number(p.lon)})):[];
            if(point || polygon.length>2) resolved.push({addon, point, polygon, source:it.source||'backend', icao:String((addon&&addon.rw&&addon.rw.icao)||'').trim().toUpperCase()});
          });
        }
        if(alive){
          setResolvedItems(resolved);
          const markerCount=resolved.filter(x=>x&&x.point).length;
          const polygonCount=resolved.filter(x=>x&&Array.isArray(x.polygon)&&x.polygon.length>2).length;
          setProgress({phase:'done',done:markerCount,total:sourceItems.length,message:markerCount||polygonCount?`Ready to display ${markerCount} marker${markerCount===1?'':'s'}${polygonCount?` and ${polygonCount} coverage area${polygonCount===1?'':'s'}`:''}.`:'No mapped coordinates were found for the current scope.'});
          setRenderError(markerCount||polygonCount?'':'No airport or scenery markers could be plotted for the current scope.');
        }
      }catch(err){
        console.warn('Global map resolution error',err);
        if(alive){ setResolvedItems([]); setRenderError('Global map failed to resolve airport or scenery locations.'); setProgress({phase:'error',done:0,total:sourceItems.length,message:'Global map failed to resolve airport or scenery locations.'}); }
      }
    }
    resolveCoords();
    return ()=>{ alive=false; };
  },[sourceItems]);

  useEffect(()=>{
    if(!mapRef.current || typeof L==='undefined' || leafRef.current) return;
    try{
      const map=L.map(mapRef.current,{zoomControl:true,scrollWheelZoom:true});
      leafRef.current=map;
      polygonsRef.current=L.featureGroup().addTo(map);
      map.setView([20,0],2);
      const sync=()=>{ try{ setMapBounds(map.getBounds()); syncProjected(); }catch(e){} };
      map.on('move zoom moveend zoomend resize viewreset', sync);
      map.whenReady(()=>{ try{ map.invalidateSize(true); }catch(e){} setMapReady(true); sync(); });
      setTimeout(()=>{ try{ map.invalidateSize(true); sync(); }catch(e){} },250);
    }catch(e){ console.warn('Global map init error',e); setRenderError('Global map failed to render.'); }
    return ()=>{ if(leafRef.current){ try{ leafRef.current.off(); leafRef.current.remove(); }catch(e){} leafRef.current=null; } tileRef.current=null; polygonsRef.current=null; };
  },[]);

  useEffect(()=>{
    const map=leafRef.current;
    if(!map || typeof L==='undefined') return;
    try{
      if(tileRef.current){ try{ map.removeLayer(tileRef.current); }catch(e){} }
      const cur=LAYERS[layer];
      const tile=L.tileLayer(cur.tile,{attribution:cur.attr,maxZoom:19});
      tile.on('load',()=>setMapReady(true));
      tile.on('tileerror',()=>setRenderError('Base map tiles could not be loaded.'));
      tile.addTo(map);
      tileRef.current=tile;
      setTimeout(()=>{ try{ map.invalidateSize(true); syncProjected(); }catch(e){} },150);
    }catch(e){ console.warn('Global map layer error',e); }
  },[layer]);

  useEffect(()=>{
    refreshPolygonLayers();
    syncProjected();
    if(!autoFitRef.current && resolvedItems.length && leafRef.current){
      fitItemsToMap(resolvedItems);
      autoFitRef.current=true;
    }
  },[displayItems, resolvedItems]);

  useEffect(()=>{
    if(!selectedItem && projectedPoints.length){
      setHoveredAddonId('');
    }
  },[selectedItem, projectedPoints]);

  const airportLegendVisible=airportLegend.length>1;
  const airportListLabel=displayItems.some(item=>addonTypeFor(item&&item.addon)==='Scenery')?'Airport / Scenery Listing':'Airport Listing';
  const statusTone=renderError?'var(--red)':progress.phase==='loading'?'var(--acc)':'var(--t2)';
  const markerCount=displayItems.filter(x=>x&&x.point).length;
  const polygonCount=displayItems.filter(x=>x&&Array.isArray(x.polygon)&&x.polygon.length>2).length;

  return <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:14,padding:'12px 12px 10px',display:'flex',flexDirection:'column',gap:10,height:'100%',minHeight:0,resize:'both',overflow:'hidden'}}>
    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,flexWrap:'wrap'}}>
      <div>
        <div style={{fontSize:13,fontWeight:800,color:'var(--t0)'}}>Global Map</div>
        <div style={{fontSize:11,color:'var(--t2)'}}>Explore airport and scenery relationships spatially without opening a full detail view for every item.</div>
      </div>
      <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
        <div style={{display:'flex',gap:8,alignItems:'center',padding:'5px 7px',border:'1px solid var(--bdr)',borderRadius:10,background:'var(--bg0)'}}>
          <span style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>Scope</span>
          <button onClick={()=>setScope('filtered')} style={{background:scope==='filtered'?accent+'22':'transparent',border:'1px solid '+(scope==='filtered'?accent+'55':'var(--bdr)'),color:scope==='filtered'?accent:'var(--t2)',borderRadius:7,padding:'5px 8px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>Filtered Results ({items.filter(a=>['Airport','Scenery'].includes(addonTypeFor(a))).length})</button>
          {!!selectedGeoCount&&<button onClick={()=>setScope('selected')} style={{background:scope==='selected'?accent+'22':'transparent',border:'1px solid '+(scope==='selected'?accent+'55':'var(--bdr)'),color:scope==='selected'?accent:'var(--t2)',borderRadius:7,padding:'5px 8px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>Selected Only ({selectedGeoCount})</button>}
          <button onClick={()=>setScope('view')} style={{background:scope==='view'?accent+'22':'transparent',border:'1px solid '+(scope==='view'?accent+'55':'var(--bdr)'),color:scope==='view'?accent:'var(--t2)',borderRadius:7,padding:'5px 8px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>Visible Region Only</button>
        </div>
        <button onClick={onClose} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'5px 10px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>Close</button>
      </div>
    </div>

    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10,flexWrap:'wrap'}}>
      <div style={{display:'flex',gap:10,flexWrap:'wrap',alignItems:'stretch'}}>
        <div style={{display:'flex',gap:8,alignItems:'center',padding:'6px 8px',border:'1px solid var(--bdr)',borderRadius:10,background:'var(--bg0)'}}>
          <span style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>Map Type</span>
          {Object.entries(LAYERS).map(([k,v])=><button key={k} onClick={()=>setLayer(k)} style={{background:layer===k?accent+'22':'transparent',border:'1px solid '+(layer===k?accent+'55':'var(--bdr)'),color:layer===k?accent:'var(--t2)',borderRadius:7,padding:'5px 10px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>{v.l}</button>)}
        </div>
        <div style={{display:'flex',gap:8,alignItems:'center',padding:'6px 8px',border:'1px solid var(--bdr)',borderRadius:10,background:'var(--bg0)'}}>
          <span style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>View</span>
          <button onClick={()=>{setRegionKey('world'); fitItemsToMap(displayItems.length?displayItems:resolvedItems);}} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'5px 10px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>Global</button>
          <button onClick={()=>fitItemsToMap(displayItems.length?displayItems:resolvedItems)} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'5px 10px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>Fit Results</button>
          <select value={regionKey} onChange={e=>setRegionKey(e.target.value)} style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'6px 10px',color:'var(--t1)',fontSize:11,fontFamily:'inherit'}}>
            {Object.entries(REGIONS).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}
          </select>
          <button onClick={()=>applyRegion(regionKey)} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'5px 10px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>Region</button>
        </div>
        {airportLegendVisible && <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap',padding:'6px 8px',border:'1px solid var(--bdr)',borderRadius:10,background:'var(--bg0)'}}>
          <span style={{fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>Legend</span>
          {airportLegend.map(entry=><div key={entry.label} style={{display:'flex',alignItems:'center',gap:6,fontSize:11,color:'var(--t1)'}}><span style={{width:12,height:12,borderRadius:'999px',display:'inline-block',background:entry.color,border:'2px solid #fff',boxShadow:'0 0 0 1px rgba(15,23,42,.55)'}}/><span>{entry.label}</span></div>)}
        </div>}
      </div>
      <div style={{fontSize:11,color:statusTone,fontWeight:700}}>{progress.phase==='loading'?(progress.message||'Resolving locations…'):(renderError||progress.message||`${markerCount} marker${markerCount===1?'':'s'} ready`)}</div>
    </div>

    <div style={{background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:10,display:'flex',flexDirection:'column',gap:8,flex:1,minHeight:360,overflow:'hidden'}}>
      <div style={{fontSize:11,color:'var(--t2)',display:'flex',justifyContent:'space-between',gap:10,flexWrap:'wrap'}}><span>Markers: {markerCount} / {sourceItems.length} items in scope • Coverage Areas: {polygonCount}</span><span>{mapReady?'Map ready':'Preparing map…'}</span></div>
      <div style={{position:'relative',flex:1,minHeight:320,borderRadius:10,overflow:'hidden',background:'#0b1220'}}>
        <div ref={mapRef} style={{position:'absolute',inset:0,borderRadius:10,overflow:'hidden',background:'#0b1220',zIndex:1}}/>
        <div style={{position:'absolute',inset:0,zIndex:5000,pointerEvents:'none',overflow:'hidden'}}>
          {projectedPoints.map(pt=>{
            const color=markerColor(pt.addon);
            const selected=String(pt.key)===String(selectedAddonId);
            return <button key={pt.key} onClick={()=>selectItem(pt.item)} onMouseEnter={()=>setHoveredAddonId(pt.key)} onMouseLeave={()=>setHoveredAddonId(cur=>cur===pt.key?'':cur)} style={{position:'absolute',left:pt.x,top:pt.y,transform:'translate(-50%,-50%)',pointerEvents:'auto',display:'flex',alignItems:'center',justifyContent:'center',background:'transparent',border:'none',padding:0,cursor:'pointer'}}>
              <span style={{width:selected?22:18,height:selected?22:18,borderRadius:'999px',display:'inline-block',background:color,border:selected?'4px solid #fff':'3px solid #fff',boxShadow:selected?('0 0 0 4px rgba(15,23,42,.86), 0 0 20px '+color+'dd'):('0 0 0 3px rgba(15,23,42,.78), 0 0 10px rgba(0,0,0,.35)')}}/>
            </button>;
          })}
          {hoveredPoint && <div style={{position:'absolute',left:hoveredPoint.x,top:hoveredPoint.y-18,transform:'translate(-50%,-100%)',pointerEvents:'none',padding:'4px 8px',borderRadius:8,background:'rgba(15,23,42,.96)',border:'1px solid rgba(255,255,255,.22)',color:'#fff',fontSize:11,fontWeight:700,whiteSpace:'nowrap',boxShadow:'0 4px 14px rgba(0,0,0,.35)'}}>{hoveredPoint.addon.title}</div>}
        </div>
      </div>
      {renderError&&<div style={{background:'rgba(127,29,29,.16)',border:'1px solid rgba(239,68,68,.28)',color:'var(--red)',borderRadius:10,padding:'10px 12px',fontSize:12,lineHeight:1.6}}>{renderError}</div>}
      {!renderError&&progress.phase==='loading'&&<div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6}}>Please wait while the app resolves airport and scenery coordinates for the current map scope.</div>}

      {selectedItem && <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,flexWrap:'wrap',background:'var(--bg0)',border:'1px solid '+accent+'44',borderRadius:10,padding:'8px 10px'}}>
        <div>
          <div style={{fontSize:11,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em'}}>Selected Airport</div>
          <div style={{fontSize:13,fontWeight:800,color:'var(--t0)'}}>{selectedItem.addon.title}</div>
        </div>
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
          <button onClick={()=>selectItem(selectedItem,{zoomInto:true})} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'6px 10px',fontSize:11,fontWeight:700,fontFamily:'inherit',cursor:'pointer'}}>Zoom to Airport</button>
          <button onClick={()=>onOpenAddon&&onOpenAddon(selectedItem.addon)} style={{background:accent+'22',border:'1px solid '+accent+'55',color:accent,borderRadius:7,padding:'6px 10px',fontSize:11,fontWeight:700,fontFamily:'inherit',cursor:'pointer'}}>Open Airport Detail</button>
        </div>
      </div>}

      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,flexWrap:'wrap'}}>
        <div style={{fontSize:12,fontWeight:800,color:'var(--t1)'}}>{airportListLabel}</div>
        <button onClick={()=>setShowList(v=>!v)} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'5px 10px',fontSize:11,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>{showList?'Hide Airport List':'Show Airport List'}</button>
      </div>
      {showList && <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:10,padding:'8px 10px',display:'flex',flexDirection:'column',gap:8,maxHeight:220,minHeight:120,overflow:'hidden'}}>
        <ClearableInput value={listSearch} setValue={setListSearch} placeholder={`Search ${airportListLabel.toLowerCase()}...`} inputStyle={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'7px 10px',paddingRight:(listSearch?34:10),fontSize:11,minHeight:'auto',fontWeight:500}}/>
        <div style={{display:'grid',gridTemplateColumns:'minmax(220px,2fr) 120px 100px 190px',gap:8,fontSize:10,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.06em',paddingBottom:2,borderBottom:'1px solid var(--bdr)'}}><div>Airport</div><div>Subtype</div><div>ICAO</div><div>Actions</div></div>
        <div style={{display:'grid',gap:6,overflow:'auto'}}>
          {filteredListItems.length===0 && <div style={{fontSize:11,color:'var(--t2)'}}>No airports match the current listing search.</div>}
          {filteredListItems.map(item=>{
            const selected=String(item.addon&&item.addon.id)===String(selectedAddonId);
            return <div key={String(item.addon&&item.addon.id)} style={{display:'grid',gridTemplateColumns:'minmax(220px,2fr) 120px 100px 190px',gap:8,alignItems:'center',padding:'6px 4px',borderRadius:8,background:selected?accent+'12':'transparent',border:selected?('1px solid '+accent+'33'):'1px solid transparent'}}>
              <div style={{color:'var(--t1)',fontSize:11,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={item.addon.title}>{item.addon.title}</div>
              <div style={{color:'var(--t2)',fontSize:11}}>{item.addon.sub||'—'}</div>
              <div style={{color:'var(--t2)',fontSize:11}}>{item.icao||'—'}</div>
              <div style={{display:'flex',gap:6,justifyContent:'flex-end',flexWrap:'wrap'}}>
                <button onClick={()=>selectItem(item)} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'4px 8px',fontSize:10,fontWeight:700,fontFamily:'inherit',cursor:'pointer'}}>Select</button>
                <button onClick={()=>selectItem(item,{zoomInto:true})} style={{background:'transparent',border:'1px solid var(--bdr)',color:'var(--t2)',borderRadius:7,padding:'4px 8px',fontSize:10,fontWeight:700,fontFamily:'inherit',cursor:'pointer'}}>Zoom</button>
                <button onClick={()=>onOpenAddon&&onOpenAddon(item.addon)} style={{background:accent+'22',border:'1px solid '+accent+'55',color:accent,borderRadius:7,padding:'4px 8px',fontSize:10,fontWeight:700,fontFamily:'inherit',cursor:'pointer'}}>Detail</button>
              </div>
            </div>;
          })}
        </div>
      </div>}
    </div>
  </div>;
}



function App(){
  const [addons,setAddons]=useState([]);
  const [apiMode,setApiMode]=useState(false);
  const [initialLoad,setInitialLoad]=useState(true);
  const [section,setSection]=useState("library");
  const [settingsTab,setSettingsTab]=useState('library');
  const [detailContext,setDetailContext]=useState(null);
  const [detailInitialTab,setDetailInitialTab]=useState('overview');
  const [finderState,setFinderState]=useState(null);
  const [selected,setSelected]=useState(null),[detail,setDetail]=useState(null);
  const [pickedIds,setPickedIds]=useState([]);
  const [removeFolders,setRemoveFolders]=useState(false);
  const [ignoreOnRemove,setIgnoreOnRemove]=useState(false);
  const [notice,setNotice]=useState(null);
  const [activityState,setActivityState]=useState(null);
  const [helpPanel,setHelpPanel]=useState(null);
  const [confirmDialog,setConfirmDialog]=useState(null);
  const confirmActionRef=useRef(null);
  const [folderPicker,setFolderPicker]=useState(null);
  // Auto-dismiss transient notifications so the grid does not require constant manual cleanup.
  useEffect(()=>{
    if(!notice) return;
    const t=setTimeout(()=>setNotice(cur=>cur===notice?null:cur),60000);
    return ()=>clearTimeout(t);
  },[notice]);
  const [profiles,setProfiles]=useState([]);
  const [activeCollectionId,setActiveCollectionId]=useState('');
  const [collectionPickedIds,setCollectionPickedIds]=useState([]);
  const [collectionAddPickedIds,setCollectionAddPickedIds]=useState([]);
  const [collectionSearch,setCollectionSearch]=useState('');
  // Store the ids of the collections currently selected at the top of the grid.
  const [libraryCollectionFilterIds,setLibraryCollectionFilterIds]=useState([]);
  const [communityActionScope,setCommunityActionScope]=useState('displayed');
  const [communityActionMode,setCommunityActionMode]=useState('activate');
  const [localeLanguage,setLocaleLanguage]=useState(()=>localStorage.getItem('hangar_language')||'English');
  const [localeCurrency,setLocaleCurrency]=useState(()=>localStorage.getItem('hangar_currency')||'$');
  const [localeCalendar,setLocaleCalendar]=useState(()=>localStorage.getItem('hangar_calendar_format')||localStorage.getItem('hangar_calendar')||'MM/DD/YYYY');
  const [searchProvider,setSearchProvider]=useState(()=>localStorage.getItem('hangar_search_provider')||'bing');
  const [gridScale,setGridScale]=useState(()=>localStorage.getItem('hangar_grid_scale')||'medium');
  const [noteModal,setNoteModal]=useState(null);
  const [search,setSearch]=useState(""),[filterType,setFilterType]=useState("All");
  const [filterSub,setFilterSub]=useState("All");
  const [filterCountries,setFilterCountries]=useState([]),[filterRegions,setFilterRegions]=useState([]);
  // Toggle lightweight view filters that can be combined with search, type,
  // collections, and the aircraft finder result set.
  const [favOnly,setFavOnly]=useState(false),[activeOnly,setActiveOnly]=useState(()=>localStorage.getItem('hangar_filter_active_only')==='1'),[inactiveOnly,setInactiveOnly]=useState(false),[sort,setSort]=useState("title");
  const [sortDir,setSortDir]=useState('asc');
  const [sourceFilter,setSourceFilter]=useState('All');
  const [obtainedFromFilter,setObtainedFromFilter]=useState('All');
  const [obtainedFromChoices,setObtainedFromChoices]=useState(()=>storedObtainedFromOptions());
  const [showGlobalMap,setShowGlobalMap]=useState(false);
  const [aiPopulateStatus,setAiPopulateStatus]=useState(null);
  useEffect(()=>{
    if(!aiPopulateStatus) return;
    const t=setTimeout(()=>setAiPopulateStatus(cur=>cur===aiPopulateStatus?null:cur),60000);
    return ()=>clearTimeout(t);
  },[aiPopulateStatus]);
  const [sidebarOpen,setSidebarOpen]=useState(true);
  const [apiKey,setApiKey]=useState(()=>localStorage.getItem("msfs_oai")||"");
  const [googleKey,setGoogleKey]=useState(()=>localStorage.getItem("msfs_google")||"");
  const [claudeKey,setClaudeKey]=useState(()=>localStorage.getItem("msfs_claude")||"");
  const [simName,setSimName]=useState(()=>localStorage.getItem('hangar_sim_name')||'MSFS');
  const [simVersion,setSimVersion]=useState(()=>localStorage.getItem('hangar_sim_version')||'2024');
  const [selectedAIProvider,setSelectedAIProvider]=useState(()=>localStorage.getItem('hangar_ai_provider')||'gemini');
  const [aiUsage,setAIUsage]=useState(null);
  const [bulkGeminiProgress,setBulkGeminiProgress]=useState(null);
  const [bulkOverrideExisting,setBulkOverrideExisting]=useState(false);
  const [bulkIncludeAircraftData,setBulkIncludeAircraftData]=useState(true);
  const [finderIds,setFinderIds]=useState(null);
  const [scanning,setScanning]=useState(false);
  const [scanProgress,setScanProgress]=useState(null);
  const [scanPopulateNewAI,setScanPopulateNewAI]=useState(()=>localStorage.getItem('hangar_scan_populate_new_ai')==='1');
  const [ignoredItems,setIgnoredItems]=useState([]);
  const [topFolders,setTopFolders]=useState([]);
  const [selectedFolders,setSelectedFolders]=useState([]);
  const [addonsRootPath,setAddonsRootPath]=useState(()=>localStorage.getItem('hangar_addons_root')||'');
  const [savedAddonsRoot,setSavedAddonsRoot]=useState(()=>localStorage.getItem('hangar_addons_root')||'');
  const [toolName,setToolName]=useState('');
  const [toolPublisher,setToolPublisher]=useState('');
  const [toolPath,setToolPath]=useState('');
  const [toolWorkingDir,setToolWorkingDir]=useState('');
  const [toolType,setToolType]=useState('Utility');
  const [toolSubtype,setToolSubtype]=useState('Utility');
  const [toolNotes,setToolNotes]=useState('');
  const [subtypeAIType,setSubtypeAIType]=useState('Aircraft');
  const [subtypeAIAllTypes,setSubtypeAIAllTypes]=useState(false);
  const [subtypeAIProgress,setSubtypeAIProgress]=useState(null);
  const [relocateRepairLinks,setRelocateRepairLinks]=useState(true);
  const [relocatePreview,setRelocatePreview]=useState(null);
  const [relocateBusy,setRelocateBusy]=useState(false);
  const [activatedOnly,setActivatedOnly]=useState(()=>localStorage.getItem("hangar_scan_active_only")==="1");
  const scanWsRef=useRef(null);
  const bulkNoticeRef=useRef('');
  const subtypeNoticeRef=useRef('');
  const gridRef=useRef(null), gridScrollRef=useRef(0), selectedIdRef=useRef(null);
  const collectionsStripRef=useRef(null);
  const isMobile=useIsMobile();

  // Contextual help is structured so the same content can later feed the PDF
  // guide. The overlay explains both screen purpose and common workflows.
  const GUIDE_TEXT={
    library:{title:'Library',purpose:'Library is the main workspace for browsing, filtering, selecting, and batch-managing add-ons.',when:'Use Library whenever you want to search, compare cards, build a collection from the current result set, or activate/deactivate add-ons from the current displayed view or from selected collections.',actions:['Click an add-on card to open the full detail view.','Use the Select checkbox on cards when you want batch actions such as creating a collection, deleting multiple add-ons, or bulk changing type/subtype.','Use Search, Type, Subtype, Favorites, Active, and Collections together. The grid always reflects the combined result.','Use Select Displayed when you want every currently visible grid result added to a new collection without manually checking each card.','Use the Community Folder action bar next to Collections to activate or deactivate either the displayed grid results or the selected collection chips.'],tips:['Collections are saved sets. Grid filters are temporary working sets. Both can drive activation or deactivation through the same action bar.']},
    collections:{title:'Collections',purpose:'Collections are saved sets of add-ons that you can reuse for filtering, activation, and organization.',when:'Use Collections when you need to rename a collection, delete it, inspect when it was created, or curate its membership one item or many items at a time.',actions:['Use the left list to choose which collection you want to manage.','Click a row in either panel to open the add-on detail if you need more context.','Use Select on rows to remove multiple add-ons from the current collection at once.','Use the search box on the Add More Items side to find library add-ons that are not yet in the selected collection.'],tips:['Keep quick filtering on the Library screen. Use this Collections screen for editing and housekeeping so the UI stays streamlined.']},
    finder:{title:'Aircraft Finder',purpose:'Aircraft Finder compares candidate aircraft for a route or mission.',when:'Use it when you know the distance or want to see which aircraft can satisfy a range requirement before opening one in full detail.',actions:['Select finder filters, review the results, then click a result to open full detail.','When you exit the detail screen, the app returns you to Aircraft Finder so you can continue comparing.'],tips:['Finder is ideal for ad-hoc comparison. Collections are better for saved groups you revisit often.']},
    settings:{title:'Settings',purpose:'Settings controls folders, simulator identity, AI providers, localization, browser search provider, and Community-folder management.',when:'Use Settings when you first configure the app or when you need to change system-level behavior rather than edit a single add-on.',actions:['Use Community Folder Management for global activate-all or deactivate-all actions and for choosing the Add-ons Root and Community folders.','Use AI settings to choose which provider Populate actions use and to store the matching API key.','Use User Interface settings to choose search provider, language, currency symbol, calendar format, and visual options.'],tips:['Folder paths are saved per user. After changing a major path, refresh the related screen or rescan if needed.']},
    overview:{title:'Overview',purpose:'Overview stores the polished summary and key product metadata for the selected add-on.',when:'Use Overview when you want the high-level description, release/version fields, pricing, and notes that matter most for browsing the library.',actions:['Use Populate with selected AI to refresh overview text and product metadata such as installed version, current version, release dates, and pricing.','Use Save after manual edits. AI populate already saves returned data automatically.'],tips:['Overview should read like a clean product page summary. Features is where the longer detailed breakdown belongs.']},
    features:{title:'Features',purpose:'Features is the detailed product-style writeup for the add-on.',when:'Use it when the Overview is too short to capture included content, systems depth, compatibility, or other vendor-style detail.',actions:['Populate with selected AI when you want a richer, formatted feature list.','Send cleaned article content here from Research when you want to preserve details from a product page.']},
    research:{title:'Research',purpose:'Research combines a browser and saved article list for web investigation.',when:'Use it when you need product pages, release posts, reviews, or manual web browsing tied to the selected add-on.',actions:['Reset Browser reloads the original search for the add-on as if you opened the tab for the first time.','Save useful pages to the article list, then send content to Overview or Features when it belongs in the library record.']},
    realworld:{title:'Aircraft or Airport Data',purpose:'This tab stores structured real-world specs and reference data.',when:'Use it when you want aircraft performance data, airport facts, web sources, and manual corrections.',actions:['Populate with selected AI fills the structured data fields and saves them automatically.','Use Save when you manually adjust editable fields such as manufacturer, model, or category.','Web Data Source is the public page or domain that most likely backed the retrieved facts when the app could identify one.']},
    userdata:{title:'Your Data',purpose:'Your Data is for personal workflow fields such as tags, notes, paid price, and rating.',when:'Use it when you want to customize the library for your own purchasing and curation workflow rather than the public product description.',actions:['Use tags and rating to make filtering and sorting more useful later.','Use notes for anything that matters to you but does not belong in the public-style Overview or Features fields.']},
    gallery:{title:'Gallery',purpose:'Gallery stores screenshots and reference images for each add-on.',when:'Use it when you want a better thumbnail, visual references, or quick pasted screenshots tied to the add-on.',actions:['Paste clipboard images or add saved files to build a useful gallery.','Set a preferred default image so the grid stays visually informative.']},
    docs:{title:'Docs',purpose:'Docs keeps manuals, checklists, and PDF references attached to the add-on.',when:'Use it when you want operational documentation available directly from the library entry.',actions:['Open documents inline when possible.','Use Docs instead of stuffing long manual information into Overview or Notes.']},
    ai:{title:'AI Workspace',purpose:'AI Workspace is the flexible prompt area for one-off questions.',when:'Use it when the structured Populate buttons are not enough and you want a custom answer or analysis.',actions:['Enter a custom prompt and execute it when you want something more targeted than the standard populate flows.','Use the structured Populate buttons on Overview or Data screens for normal library population work.']},
    map:{title:'Map',purpose:'Map helps you visualize airports and compare aircraft within range.',when:'Use it when you want a geographic view, range-based comparison, or to drill into a candidate without losing the current airport context.',actions:['Click a candidate aircraft to open its overview or full detail.','When you back out of detail, the app returns you to the map context so you can continue the workflow.']},
  };
  const openGuide=(key)=>{ const g=GUIDE_TEXT[key]; if(g) setHelpPanel(g); };
  function openConfirmDialog(dialog, onConfirm){
    // Desktop shells can suppress native window.confirm dialogs or show them
    // behind the app window. Use an in-app confirmation overlay instead so
    // activation/deactivation previews are always visible and reliable.
    confirmActionRef.current=onConfirm||null;
    setConfirmDialog(dialog||null);
  }
  function closeConfirmDialog(){
    confirmActionRef.current=null;
    setConfirmDialog(null);
  }
  async function confirmDialogProceed(){
    const fn=confirmActionRef.current;
    closeConfirmDialog();
    if(fn) await fn();
  }
  // Load backend settings + addons on startup
  useEffect(()=>{
    setInitialLoad(true);
    fetch("/api/settings").then(r=>r.ok?r.json():{}).then(s=>{
      if(s.addons_root){ localStorage.setItem("hangar_addons_root",s.addons_root); setAddonsRootPath(s.addons_root); setSavedAddonsRoot(s.addons_root); }
      if(s.community_dir) localStorage.setItem("hangar_community_dir",s.community_dir);
      if(s.openai_key) saveKey(s.openai_key);
      if(s.google_api_key) saveGoogleKey(s.google_api_key);
      if(s.claude_api_key) saveClaudeKey(s.claude_api_key);
      if(s.flight_sim_name){ setSimName(s.flight_sim_name); localStorage.setItem('hangar_sim_name', s.flight_sim_name); }
      if(s.flight_sim_version){ setSimVersion(s.flight_sim_version); localStorage.setItem('hangar_sim_version', s.flight_sim_version); }
      if(s.ai_provider){ setSelectedAIProvider(s.ai_provider); localStorage.setItem('hangar_ai_provider', s.ai_provider); }
      if(s.language){ setLocaleLanguage(s.language); localStorage.setItem('hangar_language', s.language); }
      if(s.currency_symbol){ setLocaleCurrency(s.currency_symbol); localStorage.setItem('hangar_currency', s.currency_symbol); }
      if(s.calendar_format){ setLocaleCalendar(s.calendar_format); localStorage.setItem('hangar_calendar_format', s.calendar_format); localStorage.setItem('hangar_calendar', s.calendar_format); }
      if(s.search_provider){ setSearchProvider(String(s.search_provider).toLowerCase()==='google'?'google':'bing'); localStorage.setItem('hangar_search_provider', String(s.search_provider).toLowerCase()==='google'?'google':'bing'); }
    }).catch(()=>{});
    fetch("/api/data-options").then(r=>r.ok?r.json():null).then(opts=>{
      if(!opts) return;
      if(Array.isArray(opts.sources)){ localStorage.setItem('hangar_sources', JSON.stringify(opts.sources)); setObtainedFromChoices(['All',...Array.from(new Set(opts.sources.map(v=>String(v||'').trim()).filter(Boolean))).sort((a,b)=>String(a).localeCompare(String(b)))]); }
      if(Array.isArray(opts.avionics)) localStorage.setItem('hangar_avionics', JSON.stringify(opts.avionics));
      if(Array.isArray(opts.tags)) localStorage.setItem('hangar_tags', opts.tags.join(', '));
      if(opts.subtypes) localStorage.setItem('hangar_subtypes', JSON.stringify(opts.subtypes));
    }).catch(()=>{});
    fetch("/api/addons")
      .then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
      .then(data=>{setAddons(data);setApiMode(true);setInitialLoad(false);})
      .catch(()=>{setApiMode(false);setInitialLoad(false);});
  },[]);

  useEffect(()=>{if(selected)setSelected(addons.find(a=>a.id===selected.id)||null);},[addons]);
  useEffect(()=>{ try{ localStorage.setItem('hangar_grid_scale', gridScale); }catch(e){} },[gridScale]);
  useEffect(()=>{
    function onDataOptionsUpdated(ev){
      const src=ev&&ev.detail&&ev.detail.sources;
      if(Array.isArray(src)&&src.length){
        setObtainedFromChoices(['All',...Array.from(new Set(src.map(v=>String(v||'').trim()).filter(Boolean))).sort((a,b)=>String(a).localeCompare(String(b)))]);
      }else{
        setObtainedFromChoices(storedObtainedFromOptions());
      }
    }
    window.addEventListener('hangar-data-options-updated', onDataOptionsUpdated);
    return ()=>window.removeEventListener('hangar-data-options-updated', onDataOptionsUpdated);
  },[]);
  useEffect(()=>{ try{ localStorage.setItem('hangar_filter_active_only', activeOnly?'1':'0'); }catch(e){} },[activeOnly]);
  useEffect(()=>{if(detail)setDetail(addons.find(a=>a.id===detail.id)||null);},[addons]);

  async function loadFolderPickerPath(pathValue, meta={}){
    const currentPath=pathValue||'';
    const driveData=await fetchJsonSafe('/api/folders/drives').catch(()=>({drives:[]}));
    let children={root:currentPath,parent:'',folders:[]};
    if(currentPath){
      children=await fetchJsonSafe('/api/folders/children?root='+encodeURIComponent(currentPath)).catch(()=>({root:currentPath,parent:'',folders:[]}));
    } else if(driveData.drives&&driveData.drives.length){
      const fallback=driveData.drives[0].path;
      children=await fetchJsonSafe('/api/folders/children?root='+encodeURIComponent(fallback)).catch(()=>({root:fallback,parent:'',folders:[]}));
    }
    const root=children.root || currentPath || ((driveData.drives&&driveData.drives[0]&&driveData.drives[0].path)||'');
    let files=[];
    if(meta.mode==='file'){
      const pattern=encodeURIComponent(meta.pattern||'*.exe');
      const fileData=await fetchJsonSafe('/api/folders/files?root='+encodeURIComponent(root)+'&pattern='+pattern).catch(()=>({files:[]}));
      files=Array.isArray(fileData.files)?fileData.files:[];
    }
    setFolderPicker(cur=>({...(cur||{}),...meta,id:meta.id||cur&&cur.id,label:meta.label||cur&&cur.label,current:root,parent:children.parent||'',folders:children.folders||[],files,drives:driveData.drives||[],loading:false,onNavigate:(nextPath)=>{setFolderPicker(prev=>prev?{...prev,loading:true}:prev); loadFolderPickerPath(nextPath, meta);}}));
  }


  useEffect(()=>{
    function onOpenGuide(ev){
      const tab=ev&&ev.detail&&ev.detail.tab;
      if(tab) openGuide(tab);
    }
    function onOpenDetail(ev){
      const addonId=ev&&ev.detail&&ev.detail.addonId;
      if(!addonId) return;
      const addon=addons.find(a=>a.id===addonId);
      if(addon){ setDetail(addon); setDetailInitialTab('overview'); }
    }
    async function onBrowsePath(ev){
      const detail=ev&&ev.detail||{};
      const nativePicked=await openNativePathPicker(detail);
      if(typeof nativePicked==='string' && nativePicked){
        window.dispatchEvent(new CustomEvent('hangar-path-picked',{detail:{id:detail.id||'',value:nativePicked}}));
        return;
      }
      setFolderPicker({id:detail.id||'',label:detail.label||'Choose Folder',current:detail.current||'',parent:'',folders:[],files:[],drives:[],loading:true,onNavigate:null,mode:detail.mode||'folder',pattern:detail.pattern||''});
      loadFolderPickerPath(detail.current||'', {id:detail.id||'',label:detail.label||'Choose Folder',mode:detail.mode||'folder',pattern:detail.pattern||''});
    }
    window.addEventListener('hangar-open-detail', onOpenDetail);
    window.addEventListener('hangar-open-guide', onOpenGuide);
    window.addEventListener('hangar-browse-path', onBrowsePath);
    return ()=>{
      window.removeEventListener('hangar-open-detail', onOpenDetail);
      window.removeEventListener('hangar-open-guide', onOpenGuide);
      window.removeEventListener('hangar-browse-path', onBrowsePath);
    };
  },[addons]);
  useEffect(()=>{ setAiPopulateStatus(null); },[selected&&selected.id,pickedIds.join('|')]);
  useEffect(()=>{ if(filterType!=='Airport' && filterType!=='Scenery') setShowGlobalMap(false); },[filterType]);
  useEffect(()=>{ setSelected(null); },[search,filterType,filterSub,sourceFilter,obtainedFromFilter,filterCountries.join('|'),filterRegions.join('|'),favOnly,activeOnly,inactiveOnly,libraryCollectionFilterIds.join('|'),finderIds&&finderIds.join('|')]);

  useEffect(()=>{
    localStorage.setItem('hangar_language', localeLanguage || 'English');
    localStorage.setItem('hangar_currency', localeCurrency || '$');
    localStorage.setItem('hangar_calendar_format', localeCalendar || 'MM/DD/YYYY');
    localStorage.setItem('hangar_calendar', localeCalendar || 'MM/DD/YYYY');
    localStorage.setItem('hangar_search_provider', searchProvider || 'bing');
  },[localeLanguage,localeCurrency,localeCalendar,searchProvider]);

  useEffect(()=>{
    setPickedIds(cur=>cur.filter(id=>addons.some(a=>a.id===id)));
  },[addons]);

  const configuredAIProviders=useMemo(()=>[
    ...(googleKey?['gemini']:[]),
    ...(apiKey?['openai']:[]),
    ...(claudeKey?['claude']:[]),
  ],[googleKey,apiKey,claudeKey]);

  const hasSelectedProviderKey=(selectedAIProvider==='gemini'&&!!googleKey)||(selectedAIProvider==='openai'&&!!apiKey)||(selectedAIProvider==='claude'&&!!claudeKey);

  async function loadAIUsage(){
    if(!apiMode) return;
    try{
      const data=await fetch('/api/ai/usage-status').then(r=>r.ok?r.json():null);
      if(data) setAIUsage(data);
    }catch(e){}
  }

  async function loadProfiles(){
    if(!apiMode) return;
    try{
      const data=await fetch('/api/profiles').then(r=>r.ok?r.json():{profiles:[]});
      setProfiles(Array.isArray(data&&data.profiles)?data.profiles:[]);
    }catch(e){ setProfiles([]); }
  }

  useEffect(()=>{ if(apiMode) loadProfiles(); },[apiMode]);
  useEffect(()=>{
    if(!profiles.length){
      setActiveCollectionId('');
      return;
    }
    if(!profiles.some(p=>p.id===activeCollectionId)) setActiveCollectionId(profiles[0].id);
  },[profiles,activeCollectionId]);
  useEffect(()=>{
    // Keep collection-derived UI state valid if collections are renamed or deleted.
    setLibraryCollectionFilterIds(cur=>cur.filter(id=>profiles.some(p=>p.id===id)));
      },[profiles]);
  useEffect(()=>{ if(apiMode && section==='settings') loadAIUsage(); },[apiMode,section]);

  function togglePicked(id){
    setPickedIds(cur=>cur.includes(id)?cur.filter(x=>x!==id):[...cur,id]);
  }

  async function removeSelectedAddons(){
    if(pickedIds.length===0) return;
    if(!window.confirm(`Remove ${pickedIds.length} selected add-on${pickedIds.length===1?'':'s'} from the library${removeFolders?' and from disk':''}${(!removeFolders&&ignoreOnRemove)?' and exclude them from future scans':''}?`)) return;
    try{
      const data=await fetchJsonSafe('/api/library/remove-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({addon_ids:pickedIds,remove_folders:removeFolders,ignore_future:!removeFolders&&ignoreOnRemove})});
      setPickedIds([]);
      setSelected(null);
      await refreshLibrary();
      if(!removeFolders&&ignoreOnRemove) await loadIgnoredItems();
      setNotice({title:'Selected add-ons removed',message:`Removed ${data.removed_ids?data.removed_ids.length:pickedIds.length} add-on${(data.removed_ids?data.removed_ids.length:pickedIds.length)===1?'':'s'} from the library.${removeFolders?' Local folders were also removed when possible.':''}${(!removeFolders&&ignoreOnRemove)?` ${data.ignored_count||0} add-on(s) were added to the ignored list for future scans.`:''}`});
    }catch(e){ alert(e.message||'Failed to remove selected add-ons'); }
  }

  async function createProfileFromSelection(name){
    if(!name || pickedIds.length===0) return;
    try{
      await fetchJsonSafe('/api/profiles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,addon_ids:pickedIds})});
      await loadProfiles();
      setNotice({title:'Collection created',message:`Saved collection “${name}” with ${pickedIds.length} selected add-ons.`});
    }catch(e){ alert(e.message||'Failed to create collection'); }
  }

  async function bulkUpdateSelected(type,subtype){
    if(!pickedIds.length || !type) return;
    try{
      await Promise.all(pickedIds.map(id=>fetch('/api/addons/'+id+'/meta',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({type,sub:subtype||''})}).catch(()=>null)));
      setAddons(ads=>ads.map(a=>pickedIds.includes(a.id)?{...a,type,sub:subtype||''}:a));
      setNotice({title:'Selected add-ons updated',message:`Applied ${type}${subtype?` / ${subtype}`:''} to ${pickedIds.length} selected add-on${pickedIds.length===1?'':'s'}.`});
    }catch(e){ alert(e.message||'Failed to update selected add-ons'); }
  }

  async function applyProfile(profile){
    if(!profile) return;
    try{
      const data=await fetchJsonSafe('/api/profiles/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:profile.id})});
      setNotice({title:'Collection applied',message:data.message||`Applied collection “${profile.name}”.`});
    }catch(e){ alert(e.message||'Failed to apply profile'); }
  }

  async function deleteProfile(profile){
    if(!profile) return;
    if(!window.confirm(`Delete collection "${profile.name}"?`)) return;
    try{
      await fetchJsonSafe('/api/profiles/'+profile.id,{method:'DELETE'});
      if(activeCollectionId===profile.id) setActiveCollectionId('');
      setCollectionPickedIds([]);
      setCollectionAddPickedIds([]);
      await loadProfiles();
      setNotice({title:'Collection deleted',message:`Deleted collection “${profile.name}”.`});
    }catch(e){ alert(e.message||'Failed to delete collection'); }
  }

  async function updateCollection(profile, nextAddonIds, nameOverride){
    if(!profile) return;
    const deduped=[...new Set((nextAddonIds||[]).filter(Boolean))];
    try{
      await fetchJsonSafe('/api/profiles/'+profile.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:nameOverride||profile.name,addon_ids:deduped})});
      await loadProfiles();
      return true;
    }catch(e){ alert(e.message||'Failed to update collection'); return false; }
  }

  async function addSelectionToCollection(profile){
    if(!profile || !pickedIds.length) return;
    const existing=new Set(profile.addon_ids||[]);
    const next=[...(profile.addon_ids||[]), ...pickedIds.filter(id=>!existing.has(id))];
    const ok=await updateCollection(profile, next);
    if(ok) setNotice({title:'Collection updated',message:`Added ${pickedIds.length} selected add-on${pickedIds.length===1?'':'s'} to “${profile.name}”.`});
  }

  async function removeFromCollection(profile, ids){
    if(!profile || !(ids||[]).length) return;
    const next=(profile.addon_ids||[]).filter(id=>!ids.includes(id));
    const ok=await updateCollection(profile, next);
    if(ok){
      setCollectionPickedIds([]);
      setNotice({title:'Collection updated',message:`Removed ${ids.length} add-on${ids.length===1?'':'s'} from “${profile.name}”.`});
    }
  }

  async function addToCollectionFromManager(profile, ids){
    if(!profile || !(ids||[]).length) return;
    const existing=new Set(profile.addon_ids||[]);
    const next=[...(profile.addon_ids||[]), ...ids.filter(id=>!existing.has(id))];
    const ok=await updateCollection(profile, next);
    if(ok){
      setCollectionAddPickedIds([]);
      setNotice({title:'Collection updated',message:`Added ${ids.length} add-on${ids.length===1?'':'s'} to “${profile.name}”.`});
    }
  }

  async function removeSelectedFromActiveCollection(profile){
    if(!profile || !pickedIds.length) return;
    const ok=await updateCollection(profile, (profile.addon_ids||[]).filter(id=>!pickedIds.includes(id)));
    if(ok){
      setNotice({title:'Collection updated',message:`Removed ${pickedIds.length} selected add-on${pickedIds.length===1?'':'s'} from “${profile.name}”.`});
      setPickedIds([]);
      await loadProfiles();
    }
  }

  async function removeAddonFromCollection(profile, addonId){
    if(!profile || !addonId) return;
    const ok=await updateCollection(profile, (profile.addon_ids||[]).filter(id=>id!==addonId));
    if(ok){
      setNotice({title:'Collection updated',message:`Removed add-on from “${profile.name}”.`});
      await loadProfiles();
    }
  }

  function viewCollectionInLibrary(profile){
    if(!profile) return;
    // Opening a collection from any legacy management path now simply toggles that
    // collection on at the top-of-grid filter strip and returns the user to Library.
    setLibraryCollectionFilterIds([profile.id]);
    setSection('library');
  }

  function selectDisplayedAddons(){
    // Selecting the currently displayed grid is the fastest way to build a new
    // collection from the exact result set created by search, filters, and
    // collection chips at the top of the Library screen.
    setPickedIds(filtered.map(a=>a.id));
  }

  async function renameCollection(profile, nextName){
    if(!profile || !nextName) return;
    const ok=await updateCollection(profile, profile.addon_ids||[], nextName);
    if(ok) setNotice({title:'Collection renamed',message:`Renamed collection to “${nextName}”.`});
  }

  function buildCollectionActivationPreview(profileIds){
    const chosen=(profiles||[]).filter(p=>(profileIds||[]).includes(p.id));
    const desiredIds=[...new Set(chosen.flatMap(p=>p.addon_ids||[]))];
    const desiredSet=new Set(desiredIds);
    const managedAddons=addons.filter(a=>a.managed!==false && a.entry_kind==='addon');
    const managedIds=new Set(managedAddons.map(a=>a.id));
    const scopedDesiredIds=desiredIds.filter(id=>managedIds.has(id));
    const scopedDesiredSet=new Set(scopedDesiredIds);
    const toCreate=managedAddons.filter(a=>scopedDesiredSet.has(a.id) && !a.enabled);
    const toRemove=managedAddons.filter(a=>!scopedDesiredSet.has(a.id) && a.enabled);
    return {collections:chosen, desiredIds:scopedDesiredIds, toCreate, toRemove};
  }

  async function applyCollectionsWithPreview(profileIds, opts={}){
    const preview=buildCollectionActivationPreview(profileIds);
    if(!preview.collections.length){
      setNotice({title:'No collections selected',message:'Select one or more collections in the Collections screen first.',kind:'error'});
      return;
    }
    const names=preview.collections.map(p=>`• ${p.name}`).join('\n');
    const createdPreview=preview.toCreate.slice(0,6).map(a=>`+ ${a.title}`).join('\n');
    const removedPreview=preview.toRemove.slice(0,6).map(a=>`- ${a.title}`).join('\n');
    const message=`Collections in this activation set:
${names}

Symbolic links to create or enable: ${preview.toCreate.length}
Symbolic links to remove or disable: ${preview.toRemove.length}

${createdPreview?`Create / enable examples:
${createdPreview}

`:''}${removedPreview?`Remove / disable examples:
${removedPreview}

`:''}Continue?`;
    if(opts.previewOnly){
      setNotice({title:'Collection activation preview',message});
      return;
    }
    openConfirmDialog({
      eyebrow:'Collection activation preview',
      title:`Apply ${preview.collections.length} collection${preview.collections.length===1?'':'s'} to the Community folder?`,
      message,
      confirmLabel:'Execute Activation',
      confirmColor:'var(--grn)'
    }, async ()=>{
      try{
        setActivityState({eyebrow:'Collection activation',title:'Activation in progress',message:`Applying ${preview.collections.length} collection${preview.collections.length===1?'':'s'} and updating Community links...`,current:'Applying collection selection…',pct:24,done:false,kind:'running'});
        const data=await fetchJsonSafe('/api/library/apply-visible',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({addon_ids:preview.desiredIds})});
        setActivityState({eyebrow:'Collection activation',title:'Activation complete',message:'Refreshing the library grid in the background so active status stays in sync.',current:'Refreshing library…',pct:82,done:false,kind:'running'});
        await refreshLibrary();
        setActivityState({eyebrow:'Collection activation',title:'Collections applied',message:`Applied ${preview.collections.length} collection${preview.collections.length===1?'':'s'}. Enabled ${data.enabled||0} add-ons and disabled ${data.disabled||0}.`,current:'Completed',pct:100,done:true,kind:'success'});
        setNotice({title:'Collections applied',message:`Applied ${preview.collections.length} collection${preview.collections.length===1?'':'s'}. Enabled ${data.enabled||0} add-ons and disabled ${data.disabled||0}.`});
      }catch(e){
        setActivityState({eyebrow:'Collection activation',title:'Collection activation failed',message:e.message||'Failed to apply the selected collections.',current:'Stopped',pct:100,done:true,kind:'error'});
        setNotice({title:'Collection activation failed',message:e.message||'Failed to apply the selected collections.',kind:'error'});
      }
    });
  }

  async function runCommunityAction(scope, action, opts={}){
    if(scope==='displayed' && !filtered.length){
      setNotice({title:'Nothing to process',message:'The current grid view is empty, so there are no displayed add-ons to activate or deactivate.',kind:'error'});
      return;
    }
    if(scope==='collections' && !libraryCollectionFilterIds.length){
      setNotice({title:'No collections selected',message:'Select one or more collection chips first, or change the scope to Displayed Add-ons.',kind:'error'});
      return;
    }
    if(scope==='all' && !addons.length){
      setNotice({title:'Library is empty',message:'There are no add-ons in the library yet.',kind:'error'});
      return;
    }
    const payload={
      scope,
      action,
      addon_ids: scope==='displayed' ? filtered.filter(a=>a.managed!==false && a.entry_kind==='addon').map(a=>a.id) : [],
      collection_ids: scope==='collections' ? libraryCollectionFilterIds : [],
    };
    try{
      const preview=await fetchJsonSafe('/api/community/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const labelScope=scope==='displayed'?'displayed add-ons':scope==='collections'?'selected collections':'entire library';
      const sampleLines=(action==='activate'?(preview.sample_create||[]):(preview.sample_remove||[])).slice(0,6).map(title=>`• ${title}`).join('\n');
      const dangerNote=scope==='all'&&action==='deactivate' ? `

Warning:
This will remove every managed add-on link from the Community folder.
Your original add-on folders are not deleted, but MSFS may load nothing until you reactivate a set.` : '';
      const message=`Action: ${action.charAt(0).toUpperCase()+action.slice(1)}
Scope: ${labelScope}

Target add-ons: ${preview.target_count}
${action==='activate'?'Links to create or enable':'Links to remove or disable'}: ${action==='activate'?preview.create_count:preview.remove_count}
Already matching this action: ${preview.already_matching}${preview.collection_names&&preview.collection_names.length?`

Collections:
${preview.collection_names.map(name=>`• ${name}`).join('\n')}`:''}${sampleLines?`

Examples:
${sampleLines}`:''}${dangerNote}

Continue?`;
      if(opts.previewOnly){ setNotice({title:'Community action preview',message}); return; }
      openConfirmDialog({
        eyebrow:'Community folder preview',
        title:`${action.charAt(0).toUpperCase()+action.slice(1)} ${labelScope}`,
        message,
        confirmLabel: action==='activate' ? 'Confirm Activate' : 'Confirm Deactivate',
        confirmColor: action==='activate' ? 'var(--grn)' : 'var(--red)'
      }, async ()=>{
        try{
          setActivityState({eyebrow:'Community folder action',title:`${action.charAt(0).toUpperCase()+action.slice(1)} in progress`,message:`Updating the Community folder for ${labelScope}...`,current:'Applying symbolic-link changes…',pct:22,done:false,kind:'running'});
          const result=await fetchJsonSafe('/api/community/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
          setActivityState({eyebrow:'Community folder action',title:`${action.charAt(0).toUpperCase()+action.slice(1)} complete`,message:`Refreshing the library grid so the activation state reflects the finished action.`,current:'Refreshing library…',pct:84,done:false,kind:'running'});
          await refreshLibrary();
          setActivityState({eyebrow:'Community folder action',title:'Community folder updated',message:`${action==='activate'?'Enabled':'Disabled'} ${action==='activate'?(result.enabled||0):(result.disabled||0)} add-on link${(action==='activate'?(result.enabled||0):(result.disabled||0))===1?'':'s'} for ${labelScope}.${result.failures&&result.failures.length?`

Failures: ${result.failures.length}`:''}`,current:'Completed',pct:100,done:true,kind:'success'});
          setNotice({title:'Community folder updated',message:`${action==='activate'?'Enabled':'Disabled'} ${action==='activate'?(result.enabled||0):(result.disabled||0)} add-on link${(action==='activate'?(result.enabled||0):(result.disabled||0))===1?'':'s'} for ${labelScope}.${result.failures&&result.failures.length?`

Failures: ${result.failures.length}`:''}`});
        }catch(e){
          setActivityState({eyebrow:'Community folder action',title:'Community action failed',message:e.message||'Failed to update the Community folder.',current:'Stopped',pct:100,done:true,kind:'error'});
          setNotice({title:'Community action failed',message:e.message||'Failed to update the Community folder.',kind:'error'});
        }
      });
    }catch(e){
      setNotice({title:'Community action failed',message:e.message||'Failed to update the Community folder.',kind:'error'});
    }
  }

  async function saveSearchProvider(){
    const value=(searchProvider||'bing').toLowerCase()==='google'?'google':'bing';
    try{
      localStorage.setItem('hangar_search_provider', value);
      await fetch('/api/settings/search_provider',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value})});
      setNotice({title:'Browser search provider saved',message:`The built-in browser will now use ${searchProviderLabel(value)} for web and image searches.`});
    }catch(e){ alert('Failed to save search provider'); }
  }

  async function runLitePopulate(addon){
    if(!addon) return;
    let pct=12;
    setAiPopulateStatus({addonId:addon.id,pct:12,message:'Preparing selected AI populate...',kind:'running'});
    const timer=setInterval(()=>{
      pct=Math.min(88,pct+Math.floor(Math.random()*8)+4);
      setAiPopulateStatus(cur=>cur&&cur.addonId===addon.id&&cur.kind!=='error'&&cur.kind!=='done'?{...cur,pct,message:addon.type==='Aircraft'?'Populating add-on and aircraft data...':'Populating add-on data...'}:cur);
    },500);
    try{
      const data=await fetchJsonSafe('/api/ai/populate-lite/'+addon.id,{method:'POST'});
      clearInterval(timer);

      // Merge the returned low-cost populate result directly into the in-memory
      // add-on list so the sidebar and detail tabs reflect product + aircraft
      // updates immediately instead of waiting for a later manual refresh.
      const nextAddonFields={};
      if(data.subtype!==undefined) nextAddonFields.sub=data.subtype||addon.sub;
      if(data.latest_version!==undefined || data.latest_version_date!==undefined || data.released!==undefined || data.price!==undefined || data.store_name!==undefined){
        nextAddonFields.pr={
          ...(addon.pr||{}),
          ...(data.latest_version!==undefined?{latest_ver:data.latest_version}:{}),
          ...(data.latest_version_date!==undefined?{latest_ver_date:data.latest_version_date}:{}),
          ...(data.released!==undefined?{released:data.released}:{}),
          ...(data.price!==undefined?{price:data.price}:{}),
          ...(data.store_name!==undefined?{source_store:data.store_name}:{}),
        };
      }
      if(data.summary_html!==undefined) nextAddonFields.summary=data.summary_html||addon.summary;
      if(data.features_html!==undefined) nextAddonFields.usr={...(addon.usr||{}), features:data.features_html||((addon.usr&&addon.usr.features)||'')};
      if(addon.type==='Aircraft'){
        nextAddonFields.rw={
          ...(addon.rw||{}),
          ...(data.manufacturer!==undefined?{mfr:data.manufacturer}:{}),
          ...(data.manufacturer_full_name!==undefined?{manufacturer_full_name:data.manufacturer_full_name}:{}),
          ...(data.model!==undefined?{model:data.model}:{}),
          ...(data.category!==undefined?{category:data.category}:{}),
          ...(data.engine!==undefined?{engine:data.engine}:{}),
          ...(data.engine_type!==undefined?{engine_type:data.engine_type}:{}),
          ...(data.max_speed!==undefined?{max_speed:data.max_speed}:{}),
          ...(data.cruise!==undefined?{cruise:data.cruise}:{}),
          ...(data.range_nm!==undefined?{range_nm:data.range_nm}:{}),
          ...(data.ceiling!==undefined?{ceiling:data.ceiling}:{}),
          ...(data.seats!==undefined?{seats:data.seats}:{}),
          ...(data.mtow!==undefined?{mtow:data.mtow}:{}),
          ...(data.fuel_capacity!==undefined?{fuel_capacity:data.fuel_capacity}:{}),
          ...(data.wingspan!==undefined?{wingspan:data.wingspan}:{}),
          ...(data.length!==undefined?{length:data.length}:{}),
          ...(data.height!==undefined?{height:data.height}:{}),
          ...(data.avionics!==undefined?{avionics:data.avionics}:{}),
          ...(data.variants!==undefined?{variants:data.variants}:{}),
          ...(data.in_production!==undefined?{in_production:data.in_production}:{}),
          ...(data.aircraft_cost!==undefined?{aircraft_cost:data.aircraft_cost}:{}),
          ...(data.country_of_origin!==undefined?{country_of_origin:data.country_of_origin}:{}),
          ...(data.introduced!==undefined?{introduced:data.introduced}:{}),
          ...(data.aircraft_source!==undefined?{source:data.aircraft_source||data.source}:{}),
          ...(data.aircraft_source===undefined && data.source!==undefined?{source:data.source}:{}),
        };
      }
      if(Object.keys(nextAddonFields).length){
        setAddons(cur=>cur.map(x=>x.id===addon.id?{...x,...nextAddonFields, pr:nextAddonFields.pr||x.pr, usr:nextAddonFields.usr||x.usr, rw:nextAddonFields.rw||x.rw}:x));
      }
      setAiPopulateStatus({addonId:addon.id,pct:100,message:'Populate complete',kind:'done'});
      await new Promise(r=>setTimeout(r,900));
      refreshLibrary();
      await loadAIUsage();
      const productSourceLabel=shortUrlLabel(data.product_source || ((data.product_sources&&data.product_sources[0])||''));
      const aircraftSourceLabel=shortUrlLabel(data.aircraft_source || ((data.aircraft_sources&&data.aircraft_sources[0])||''));
      const sourceParts=[];
      if(productSourceLabel) sourceParts.push(`Product source: ${productSourceLabel}.`);
      if(addon.type==='Aircraft' && aircraftSourceLabel) sourceParts.push(`Aircraft source: ${aircraftSourceLabel}.`);
      setNotice({title:'AI populate finished',message:`${addon.title} populated using ${data.provider_name||'the selected AI'}.${data.search_candidate?` Search used: ${data.search_candidate}.`:''}${sourceParts.length?`\n\n${sourceParts.join(' ')}`:''}`});
      setTimeout(()=>setAiPopulateStatus(cur=>cur&&cur.addonId===addon.id&&cur.kind==='done'?null:cur),3500);
    }catch(e){
      clearInterval(timer);
      setAiPopulateStatus({addonId:addon.id,pct:100,message:e.message||'Populate failed',kind:'error'});
      await loadAIUsage();
      setNotice({title:'AI populate failed',message:e.message||'Selected AI populate failed.',kind:'error'});
    }
  }

    async function applyVisibleGridActivation(){
    // Use the currently displayed grid rows as the exact activation plan.
    if(!filtered.length){
      setNotice({title:'Nothing to activate',message:'The current grid has no displayed add-ons to apply to the Community folder.',kind:'error'});
      return;
    }
    const confirmed=window.confirm(`Activate the ${filtered.length} add-ons currently displayed on the grid?\n\nAny add-on not displayed will be deactivated from the Community folder.`);
    if(!confirmed) return;
    try{
      const data=await fetchJsonSafe('/api/library/apply-visible',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({addon_ids:filtered.filter(a=>a.managed!==false && a.entry_kind==='addon').map(a=>a.id)})});
      refreshLibrary();
      setNotice({title:'Grid activation complete',message:`Enabled ${data.enabled||0} add-ons and disabled ${data.disabled||0} add-ons based on the current grid view.${data.failures&&data.failures.length?`\n\nFailures: ${data.failures.length}`:''}`});
    }catch(e){
      setNotice({title:'Grid activation failed',message:e.message||'Failed to apply the current grid to the Community folder.',kind:'error'});
    }
  }

  function toggleCollectionFilter(profile){
    // Toggle one collection chip on/off while keeping the rest of the combined
    // filter intact. The filtered grid uses the union of all active collection ids.
    setLibraryCollectionFilterIds(cur=>cur.includes(profile.id)?cur.filter(id=>id!==profile.id):[...cur,profile.id]);
  }

async function removeSingleAddon(addon){
    if(!addon) return;
    if(!window.confirm(`Remove ${addon.title} from the library${removeFolders?' and from disk':''}?`)) return;
    try{
      const data=await fetchJsonSafe('/api/library/remove-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({addon_ids:[addon.id],remove_folders:removeFolders})});
      setSelected(null);
      refreshLibrary();
      setNotice({title:'Add-on removed',message:`Removed ${addon.title} from the library.${removeFolders?' Local folder was also removed when possible.':''}`});
    }catch(e){ alert(e.message||'Failed to remove add-on'); }
  }

  async function restoreIgnoredSelection(ignoreIds){
    if(!ignoreIds || !ignoreIds.length) return;
    try{
      await fetchJsonSafe('/api/library/ignored/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ignore_ids:ignoreIds})});
      await loadIgnoredItems();
      setNotice({title:'Ignored add-ons updated',message:`Removed ${ignoreIds.length} item(s) from the ignored-scan list.`});
    }catch(e){ setNotice({title:'Ignored list update failed',message:e.message||'Failed to update ignored add-ons.',kind:'error'}); }
  }

  async function saveAISelection(){
    try{
      await fetch('/api/settings/ai_provider',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:selectedAIProvider})});
      localStorage.setItem('hangar_ai_provider', selectedAIProvider);
      await loadAIUsage();
      setNotice({title:'AI provider saved',message:`Populate actions now use ${providerLabel(selectedAIProvider)} with the app's lower-cost populate model.`});
    }catch(e){ alert('Failed to save AI settings'); }
  }

  async function saveLocalization(){
    try{
      localStorage.setItem('hangar_language', localeLanguage || 'English');
      localStorage.setItem('hangar_currency', localeCurrency || '$');
      localStorage.setItem('hangar_calendar_format', localeCalendar || 'MM/DD/YYYY');
      localStorage.setItem('hangar_calendar', localeCalendar || 'MM/DD/YYYY');
      await Promise.all([
        fetch('/api/settings/language',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:localeLanguage})}).catch(()=>{}),
        fetch('/api/settings/currency_symbol',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:localeCurrency})}).catch(()=>{}),
        fetch('/api/settings/calendar_format',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:localeCalendar})}).catch(()=>{}),
      ]);
      setNotice({title:'Localization saved',message:'Currency, date format, and language preferences were saved.'});
    }catch(e){ alert('Failed to save localization'); }
  }

  const setFav=(id,v)=>{
    setAddons(ads=>ads.map(a=>a.id===id?{...a,usr:{...a.usr,fav:v}}:a));
    fetch("/api/addons/"+id+"/user",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({fav:v})}).catch(()=>{});
  };
  const saveNotes=(id,notes)=>{
    setAddons(ads=>ads.map(a=>a.id===id?{...a,usr:{...a.usr,notes}}:a));
    fetch("/api/addons/"+id+"/user",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({notes})}).catch(()=>{});
    setNoteModal(null);
  };
  const saveUser=(id,data)=>{
    setAddons(ads=>ads.map(a=>a.id===id?{...a,
      ...(data.summary!==undefined?{summary:data.summary}:{}),
      ...(data.type!==undefined?{type:data.type}:{}),
      ...(data.sub!==undefined?{sub:data.sub}:{}),
      ...(data.title!==undefined?{title:data.title}:{}),
      ...(data.publisher!==undefined?{publisher:data.publisher}:{}),
      ...(data.thumbnail_path!==undefined?{thumbnail_path:data.thumbnail_path}:{}),
      ...(data.gallery_paths!==undefined?{gallery_paths:data.gallery_paths}:{}),
      ...(data.package_name!==undefined?{package_name:data.package_name}:{}),
      pr:{...a.pr,
        ...(data.manufacturer!==undefined?{manufacturer:data.manufacturer}:{}),
        ...(data.version!==undefined?{ver:data.version}:{}),
        ...(data.latest_version!==undefined?{latest_ver:data.latest_version}:{}),
        ...(data.latest_version_date!==undefined?{latest_ver_date:data.latest_version_date}:{}),
        ...(data.released!==undefined?{released:data.released}:{}),
        ...(data.price!==undefined?{price:data.price}:{}),
        ...(data.package_name!==undefined?{package_name:data.package_name}:{}),
        ...(data.product_source_store!==undefined?{source_store:data.product_source_store}:{}),
      },
      rw:{...(a.rw||{}), ...(data.rw_override||{}),
        ...(data.manufacturer!==undefined?{mfr:data.manufacturer}:{}),
        ...(data.manufacturer_full_name!==undefined?{manufacturer_full_name:data.manufacturer_full_name}:{}),
        ...(data.model!==undefined?{model:data.model}:{}),
        ...(data.category!==undefined?{category:data.category}:{}),
        ...(data.avionics!==undefined?{avionics:data.avionics}:{}),
      },
      usr:{...a.usr,...Object.fromEntries(Object.entries(data).filter(([k])=>["fav","rating","notes","tags","paid","source_store","avionics","features","resources","research_resources","data_resources","map_lat","map_lon","map_zoom","map_search_label","map_polygon"].includes(k)))}
    }:a));
    const userData=Object.fromEntries(Object.entries(data).filter(([k])=>["fav","rating","notes","tags","paid","source_store","avionics","features","resources","research_resources","data_resources","map_lat","map_lon","map_zoom","map_search_label","map_polygon"].includes(k)));
    const metaData=Object.fromEntries(Object.entries(data).filter(([k])=>["summary","type","sub","title","publisher","thumbnail_path","gallery_paths","manufacturer","manufacturer_full_name","model","category","icao","version","latest_version","latest_version_date","released","price","package_name","product_source_store","rw_override"].includes(k)));
    if(Object.keys(userData).length) fetch("/api/addons/"+id+"/user",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(userData)}).catch(()=>{});
    if(Object.keys(metaData).length) fetch("/api/addons/"+id+"/meta",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(metaData)}).catch(()=>{});
  };
  const saveKey=(k)=>{setApiKey(k);localStorage.setItem("msfs_oai",k);};
  const saveGoogleKey=(k)=>{setGoogleKey(k);localStorage.setItem("msfs_google",k);};
  const saveClaudeKey=(k)=>{setClaudeKey(k);localStorage.setItem("msfs_claude",k);};
  useEffect(()=>{ 
    let t=null; 
    if(apiMode){ 
      const poll=()=>fetch('/api/gemini/populate-library/status')
        .then(r=>r.ok?r.json():null)
        .then(d=>{
          if(!d) return;
          if(d.running || d.type==='running'){
            bulkNoticeRef.current='';
            setBulkGeminiProgress(d);
            return;
          }
          setBulkGeminiProgress(null);
          if(!d.type || d.type==='idle') return;
          const sig=`${d.type||''}:${d.message||''}`;
          if(sig && bulkNoticeRef.current!==sig){
            bulkNoticeRef.current=sig;
            if(d.type==='done') refreshLibrary();
            loadAIUsage();
            setNotice({title:d.type==='done'?'AI library populate finished':'AI library populate stopped',message:d.message||'Library populate finished.'});
          }
        }).catch(()=>{}); 
      poll(); 
      t=setInterval(poll,1800);
    } 
    return ()=>{if(t) clearInterval(t);}; 
  },[apiMode]);

  useEffect(()=>{
    let t=null;
    if(apiMode){
      const poll=()=>fetch('/api/ai/populate-subtypes/status')
        .then(r=>r.ok?r.json():null)
        .then(async d=>{
          if(!d) return;
          if(d.running || d.type==='running'){
            setSubtypeAIProgress(d);
            return;
          }
          setSubtypeAIProgress(null);
          if(!d.type || d.type==='idle') return;
          const sig=`${d.type||''}:${d.message||''}`;
          if(sig && subtypeNoticeRef.current===sig) return;
          subtypeNoticeRef.current=sig;
          if(d.type==='done'){
            try{
              const opts=await fetch('/api/data-options').then(r=>r.ok?r.json():null);
              if(opts&&opts.subtypes) localStorage.setItem('hangar_subtypes', JSON.stringify(opts.subtypes));
            }catch(e){}
            refreshLibrary();
            setNotice({title:'AI subtype populate finished',message:d.message||'Subtype populate finished.'});
          }
        }).catch(()=>{});
      poll();
      t=setInterval(poll,1800);
    }
    return ()=>{if(t) clearInterval(t);};
  },[apiMode]);

  async function loadTopFolders(){
    if(!apiMode) return;
    try{
      const [foldersRes,selRes]=await Promise.all([
        fetch("/api/folders/top").then(r=>r.ok?r.json():{folders:[]}),
        fetch("/api/selection").then(r=>r.ok?r.json():{paths:[]})
      ]);
      setTopFolders(foldersRes.folders||[]);
      setSelectedFolders(selRes.paths||[]);
    }catch(e){setTopFolders([]);}
  }
  async function loadIgnoredItems(){
    if(!apiMode) return;
    try{
      const data=await fetch('/api/library/ignored').then(r=>r.ok?r.json():{items:[]});
      setIgnoredItems(Array.isArray(data.items)?data.items:[]);
    }catch(e){ setIgnoredItems([]); }
  }
  async function importCommunityOnly(){
    try{
      const res=await fetch('/api/library/import-community-only',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({community_dir:localStorage.getItem('hangar_community_dir')||'', addons_root:addonsRootPath||savedAddonsRoot||''})});
      const data=await res.json().catch(()=>({}));
      if(!res.ok) throw new Error(data.detail||data.message||'Community-only import failed');
      await refreshLibrary();
      setNotice({title:'Community-only import complete',message:`Added ${data.added||0} Community-only item(s). Skipped ${data.skipped||0}.`});
    }catch(e){ setNotice({title:'Community-only import failed',message:e.message||'Import failed.',kind:'error'}); }
  }
  async function importOfficialLibrary(){
    try{
      const root=localStorage.getItem('hangar_official_root')||'';
      setActivityState({eyebrow:'Marketplace import',title:'Importing Official / Marketplace items',message:'Scanning the selected Official / Marketplace folder for manifest-based packages…',current:'Searching package manifests…',pct:22,done:false,kind:'running'});
      const res=await fetch('/api/library/import-official',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({official_root:root})});
      const data=await res.json().catch(()=>({}));
      if(!res.ok) throw new Error(data.detail||data.message||'Official import failed');
      setActivityState({eyebrow:'Marketplace import',title:'Refreshing library',message:`Found ${data.found||0} package folder(s). Added ${data.added||0} and skipped ${data.skipped||0}.`,current:'Refreshing library…',pct:82,done:false,kind:'running'});
      await refreshLibrary();
      setActivityState({eyebrow:'Marketplace import',title:'Official / Marketplace import complete',message:`Found ${data.found||0} package folder(s). Added ${data.added||0} inventory item(s) and skipped ${data.skipped||0}.`,current:'Completed',pct:100,done:true,kind:'success'});
      setNotice({title:'Official / Marketplace import complete',message:`Found ${data.found||0} package folder(s). Added ${data.added||0} inventory item(s) and skipped ${data.skipped||0}.`});
    }catch(e){ setActivityState({eyebrow:'Marketplace import',title:'Official import failed',message:e.message||'Import failed.',current:'Stopped',pct:100,done:true,kind:'error'}); setNotice({title:'Official import failed',message:e.message||'Import failed.',kind:'error'}); }
  }
  async function addExternalTool(){
    try{
      if(!toolName.trim() || !toolPath.trim()) throw new Error('Enter both a display name and an executable path.');
      const res=await fetch('/api/tools/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:toolName.trim(), publisher:toolPublisher.trim(), launch_path:toolPath.trim(), working_dir:toolWorkingDir.trim(), type:toolType, subtype:toolSubtype, notes:toolNotes})});
      const data=await res.json().catch(()=>({}));
      if(!res.ok) throw new Error(data.detail||data.message||'Tool add failed');
      setToolName(''); setToolPublisher(''); setToolPath(''); setToolWorkingDir(''); setToolType('Utility'); setToolSubtype('Utility'); setToolNotes('');
      await refreshLibrary();
      setNotice({title:'External tool added',message:`${toolName.trim()} is now available in the library as a local app item.`});
    }catch(e){ setNotice({title:'Tool add failed',message:e.message||'Could not add the external tool.',kind:'error'}); }
  }
  async function launchTool(addon){
    try{
      const res=await fetch('/api/tools/'+addon.id+'/launch',{method:'POST'});
      const data=await res.json().catch(()=>({}));
      if(!res.ok) throw new Error(data.detail||data.message||'Launch failed');
      setNotice({title:'Tool launched',message:`Started ${addon.title}.`});
    }catch(e){ setNotice({title:'Tool launch failed',message:e.message||`Could not launch ${addon&&addon.title?addon.title:'the tool'}.`,kind:'error'}); }
  }
  useEffect(()=>{if(section==="settings"&&apiMode){ loadTopFolders(); loadIgnoredItems(); }},[section,apiMode,settingsTab]);
  useEffect(()=>{
    function onPicked(ev){
      const detail=ev&&ev.detail||{};
      if(!detail.id) return;
      if(detail.id==='addons_root_library'){ setAddonsRootPath(detail.value||''); return; }
      if(detail.id==='tool_executable'){
        setToolPath(detail.value||'');
        if(!toolWorkingDir && detail.value){
          const lastSlash=Math.max(String(detail.value).lastIndexOf('\\'), String(detail.value).lastIndexOf('/'));
          if(lastSlash>0) setToolWorkingDir(String(detail.value).slice(0,lastSlash));
        }
        return;
      }
      if(detail.id==='tool_working_dir'){ setToolWorkingDir(detail.value||''); return; }
    }
    window.addEventListener('hangar-path-picked', onPicked);
    return ()=>window.removeEventListener('hangar-path-picked', onPicked);
  },[toolWorkingDir]);
  function toggleFolder(path){setSelectedFolders(cur=>cur.includes(path)?cur.filter(p=>p!==path):[...cur,path]);}
  async function saveFolderSelection(){await fetch("/api/selection",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({paths:selectedFolders})}).catch(()=>{});}
  async function resetLibrary(){if(!window.confirm("Reset library database? This does not change Community folder links.")) return; await fetch("/api/library/reset",{method:"POST"}).catch(()=>{}); setAddons([]);setSelected(null);setDetail(null);setFinderIds(null);}


  async function startBulkGemini(addonIds=null){
    if(!apiMode) return;
    const res=await fetch('/api/gemini/populate-library/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({include_overview:true,include_features:true,include_aircraft_data:bulkIncludeAircraftData,override_existing:bulkOverrideExisting,provider:selectedAIProvider,addon_ids:addonIds&&addonIds.length?addonIds:null})}).catch(()=>null);
    if(!res) return;
    const data=await res.json().catch(()=>({}));
    if(!res.ok){ alert(data.detail||'Library populate failed'); await loadAIUsage(); return; }
    await loadAIUsage();
    setBulkGeminiProgress({running:true,pct:0,current:'Preparing...',done:0,total:addonIds&&addonIds.length?addonIds.length:addons.length,message:'',type:'running'});
  }

  // Scan functions
  async function startScan(){
    if(scanning) return;
    await saveFolderSelection();
    localStorage.setItem("hangar_scan_active_only", activatedOnly?"1":"0");
    localStorage.setItem('hangar_scan_populate_new_ai', scanPopulateNewAI?"1":"0");
    await fetch("/api/settings/scan_activated_only",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:activatedOnly?"1":"0"})}).catch(()=>{});
    setScanning(true);setScanProgress({type:"start",pct:0,current:"Starting scan..."});
    const proto=window.location.protocol==="https:"?"wss":"ws";
    const ws=new WebSocket(proto+"://"+window.location.host+"/ws/scan");
    scanWsRef.current=ws;
    ws.onopen=()=>ws.send(JSON.stringify({action:"start",selected_paths:selectedFolders,populate_new_ai:scanPopulateNewAI}));
    ws.onmessage=e=>{
      const msg=JSON.parse(e.data);
      if(msg.type==='ai-progress'){
        setScanProgress({type:'ai-progress',pct:msg.pct||0,current:msg.current||'Populating new add-ons with selected AI...',message:msg.message||'',done:msg.done||0,total:msg.total||0});
        return;
      }
      setScanProgress(msg);
      if(msg.addon){
        setAddons(ads=>{
          const ex=ads.find(a=>a.id===msg.addon.id);
          if(ex) return ads.map(a=>a.id===msg.addon.id?msg.addon:a);
          return [...ads,msg.addon];
        });
      }
      if(msg.type==="done"||msg.type==="cancelled"||msg.type==="error"){
        setScanning(false);
        if(msg.type==="done"){
          refreshLibrary().then(()=>loadIgnoredItems()).catch(()=>{});
          setNotice({title:'Scan finished',message:`Added ${msg.added||0} new, updated ${msg.updated||0}, removed ${msg.removed||0}, ignored ${msg.ignored||0}.${scanPopulateNewAI?` AI-populated ${msg.ai_populated||0} new add-on(s).`:''}`});
        }
        if(msg.type==="error") setNotice({title:'Scan error',message:msg.message||'Scan failed.'});
        if(msg.type==="cancelled") setNotice({title:'Scan stopped',message:'The library scan was cancelled.'});
        setTimeout(()=>setScanProgress(null), 1500);
      } 
    };
    ws.onerror=()=>setScanning(false);
    ws.onclose=()=>setScanning(false);
  }
  function stopScan(){
    if(scanWsRef.current){scanWsRef.current.send(JSON.stringify({action:"stop"}));}
  }
  function refreshLibrary(){
    return fetch("/api/addons").then(r=>r.json()).then(data=>{
      setAddons(data);
      if(selected){
        const updated=data.find(x=>x.id===selected.id);
        if(updated) setSelected(updated);
      }
      return data;
    }).catch(()=>[]);
  }

  function handleAddonToggleEnabled(addonId, enabled, result){
    // Update the visible Library state immediately so a successful single-card
    // toggle feels responsive. We then do a delayed library refresh so the rest
    // of the UI re-syncs with the actual Community folder without hammering the
    // backend on every repaint.
    setAddons(cur=>cur.map(a=>a.id===addonId?{...a, enabled}:a));
    if(selected && selected.id===addonId){
      setSelected(cur=>cur&&cur.id===addonId?{...cur, enabled}:cur);
    }
    setNotice({title:'Addon activation updated',message:result&&result.message?result.message:(enabled?'Addon activated in Community.':'Addon deactivated from Community.')});
    setTimeout(()=>refreshLibrary(), 250);
  }

  function handleAddonToggleError(err, addon){
    setNotice({title:'Addon activation failed',message:(err&&err.message)||`Failed to update ${addon&&addon.title?addon.title:'the add-on'} activation state.`,kind:'error'});
  }

  const isGeoFilter=filterType==="Airport"||filterType==="Scenery";
  const subtypes=useMemo(()=>{
    let library={};
    try{ const raw=JSON.parse(localStorage.getItem('hangar_subtypes')||'null'); library=raw&&typeof raw==='object'?raw:{}; }catch(e){ library={}; }
    const fromData = filterType!=="All" ? ((library[filterType]||DEFAULT_SUBTYPE_OPTIONS[filterType]||[])) : [];
    const fromAddons = addons.filter(a=>filterType==="All"||addonTypeFor(a)===filterType).map(a=>a.sub).filter(Boolean);
    return ["All",...Array.from(new Set([...(fromData||[]), ...(fromAddons||[])])).sort((a,b)=>String(a).localeCompare(String(b)))];
  },[addons,filterType]);

  const selectedItems=useMemo(()=>pickedIds.map(id=>addons.find(a=>a.id===id)).filter(Boolean),[pickedIds,addons]);

  const profileMap=useMemo(()=>Object.fromEntries((profiles||[]).map(p=>[p.id,p])),[profiles]);
  const activeCollection=activeCollectionId?profileMap[activeCollectionId]||null:null;
  const activeCollectionItems=useMemo(()=>activeCollection?((activeCollection.addon_ids||[]).map(id=>addons.find(a=>a.id===id)).filter(Boolean)):[],[activeCollection,addons]);
  const activeCollectionIdsSet=useMemo(()=>new Set(activeCollection?activeCollection.addon_ids||[]:[]),[activeCollection]);
  const collectionAvailableItems=useMemo(()=>addons.filter(a=>!activeCollectionIdsSet.has(a.id)).filter(a=>{ const q=String(collectionSearch||'').trim().toLowerCase(); if(!q) return true; return [a.title,a.publisher,a.type,a.sub,(a.rw&&a.rw.icao)||'',(a.rw&&a.rw.mfr)||''].join(' ').toLowerCase().includes(q); }),[addons,activeCollectionIdsSet,collectionSearch]);
  const collectionStatsById=useMemo(()=>Object.fromEntries((profiles||[]).map(p=>[p.id,{count:(p.addon_ids||[]).length,diskMb:(p.addon_ids||[]).reduce((sum,id)=>{ const a=addons.find(x=>x.id===id); return sum+((a&&a.pr&&Number(a.pr.size_mb))||0); },0)}])),[profiles,addons]);

  // Build the active collection filter before computing the filtered grid so the
  // grid can reliably use one or more selected collections as a combined set.
  const libraryCollectionProfiles=useMemo(()=>libraryCollectionFilterIds.map(id=>profileMap[id]).filter(Boolean),[libraryCollectionFilterIds,profileMap]);
  const libraryCollectionProfile=libraryCollectionProfiles.length===1?libraryCollectionProfiles[0]:null;
  const libraryCollectionFilter=useMemo(()=>{
    if(!libraryCollectionProfiles.length) return null;
    const unionIds=[...new Set(libraryCollectionProfiles.flatMap(p=>p.addon_ids||[]))];
    return {id:libraryCollectionProfiles.length===1?libraryCollectionProfiles[0].id:'multi', name:libraryCollectionProfiles.map(p=>p.name).join(', '), ids:unionIds};
  },[libraryCollectionProfiles]);

  const sourceOptions=useMemo(()=>sourceOptionsFor(addons),[addons]);
  const obtainedFromOptions=obtainedFromChoices;
  const filtered=useMemo(()=>addons.filter(a=>{
    if(filterType!=="All"&&addonTypeFor(a)!==filterType) return false;
    if(sourceFilter!=="All" && sourceCategoryFor(a)!==sourceFilter) return false;
    if(obtainedFromFilter!=="All" && (((a.usr&&a.usr.source_store)||'').trim()!==obtainedFromFilter)) return false;
    if(filterSub!=="All"&&a.sub!==filterSub) return false;
    if(finderIds!==null&&!finderIds.includes(a.id)) return false;
    if(libraryCollectionFilter && Array.isArray(libraryCollectionFilter.ids) && !libraryCollectionFilter.ids.includes(a.id)) return false;
    if(filterCountries.length>0&&!(a.rw&&filterCountries.includes(a.rw.country))) return false;
    if(filterRegions.length>0){
      const c=a.rw&&a.rw.country;
      const label=regionDisplayFor(c, c==="United States"?(a.rw&&a.rw.state):c==="Canada"?(a.rw&&a.rw.province):(a.rw&&a.rw.region));
      if(!filterRegions.includes(label)) return false;
    }
    if(favOnly&&!a.usr.fav) return false;
    if(activeOnly&&!a.enabled) return false;
    if(inactiveOnly&&a.enabled) return false;
    if(search){const q=search.toLowerCase(),hay=[a.title,a.publisher,a.rw&&a.rw.icao,a.rw&&a.rw.mfr,locDisplay(a),...(a.usr.tags||[])].join(" ").toLowerCase();if(!hay.includes(q))return false;}
    return true;
  }).sort((a,b)=>{
    let cmp=0;
    if(sort==="title") cmp=a.title.localeCompare(b.title);
    else if(sort==="type") cmp=a.type.localeCompare(b.type)||a.title.localeCompare(b.title);
    else if(sort==="icao") cmp=((a.rw&&a.rw.icao)||"").localeCompare((b.rw&&b.rw.icao)||"");
    else if(sort==="fav") cmp=(b.usr.fav?1:0)-(a.usr.fav?1:0)||a.title.localeCompare(b.title);
    else if(sort==="price") cmp=(((a.pr&&a.pr.price)||0)-((b.pr&&b.pr.price)||0))||a.title.localeCompare(b.title);
    return sortDir==='desc'?-cmp:cmp;
  }),[addons,filterType,filterSub,sourceFilter,obtainedFromFilter,finderIds,libraryCollectionFilter,filterCountries,filterRegions,favOnly,activeOnly,inactiveOnly,search,sort,sortDir]);

  const stats={total:addons.length,favorites:addons.filter(a=>a.usr.fav).length,active:addons.filter(a=>a.enabled).length,byType:ADDON_TYPE_OPTIONS.reduce((acc,t)=>({...acc,[t]:addons.filter(a=>addonTypeFor(a)===t).length}),{})};
  const filteredTotals=useMemo(()=>({count:filtered.length,active:filtered.filter(a=>a.enabled).length,favorites:filtered.filter(a=>a.usr.fav).length,diskMb:filtered.reduce((sum,a)=>sum+((a.pr&&Number(a.pr.size_mb))||0),0),listPrice:filtered.reduce((sum,a)=>sum+((a.pr&&Number(a.pr.price))||0),0),pricePaid:filtered.reduce((sum,a)=>sum+((a.usr&&Number(a.usr.paid))||0),0)}),[filtered]);
  const collectionMembershipsForSelected=useMemo(()=>selected?(profiles||[]).filter(p=>(p.addon_ids||[]).includes(selected.id)):[],[profiles,selected]);
  const gridCardMin=gridScale==='small'?220:(gridScale==='large'?330:270);
  const NAV=[{id:"library",ic:"L",l:"Library"},{id:"collections",ic:"C",l:"Collections"},{id:"finder",ic:"F",l:"Aircraft Finder"},{id:"settings",ic:"S",l:"Settings"}];
  const TYPES=["All",...ADDON_TYPE_OPTIONS];

  const detailBackLabel = detailContext&&detailContext.type==='global-map' ? 'Return to Global Map' : 'Back to Library';

  if(detail) return <div style={{height:"100%",width:"100%",overflow:"hidden",display:"flex",flexDirection:"column"}}>
    <DetailPage a={detail} backLabel={detailBackLabel} initialTab={detailInitialTab} onBack={()=>{
      if(detailContext&&detailContext.type==='map-parent'){
        const parent=addons.find(a=>a.id===detailContext.parentId);
        setDetail(parent||null);
        setDetailInitialTab('map');
        setDetailContext(null);
        return;
      }
      if(detailContext&&detailContext.type==='finder'){
        setDetail(null);
        setDetailInitialTab('overview');
        setSection('finder');
        setDetailContext(null);
        return;
      }
      if(detailContext&&detailContext.type==='global-map'){
        setDetail(null);
        setDetailInitialTab('overview');
        setDetailContext(null);
        return;
      }
      setDetail(null);
      setDetailInitialTab('overview');
      setDetailContext(null);
      requestAnimationFrame(()=>{const el=gridRef.current;if(el) el.scrollTop=gridScrollRef.current||0;const card=selectedIdRef.current&&document.getElementById("addon-card-"+selectedIdRef.current);if(card) card.scrollIntoView({block:"nearest"});});
    }} onFav={setFav} onSaveUser={saveUser} availableAIProviders={configuredAIProviders} selectedAIProvider={selectedAIProvider} allAddons={addons} onOpenMapAddon={(addon)=>{setDetailContext({type:'map-parent',parentId:detail.id}); setDetailInitialTab('overview'); setDetail(addon);}}/>
    {notice&&<NotificationOverlay notice={notice} onDismiss={()=>setNotice(null)}/>}
    {helpPanel&&<HelpOverlay help={helpPanel} onDismiss={()=>setHelpPanel(null)}/>}
    {confirmDialog&&<ConfirmOverlay dialog={confirmDialog} onCancel={closeConfirmDialog} onConfirm={confirmDialogProceed}/>}
    {activityState&&<ActivityOverlay state={activityState} onDismiss={()=>setActivityState(null)}/>}    {folderPicker&&<FolderBrowserModal picker={folderPicker} onClose={()=>setFolderPicker(null)} onChoose={(id,value)=>{window.dispatchEvent(new CustomEvent('hangar-path-picked',{detail:{id,value}})); setFolderPicker(null);}}/>}
  </div>;

  return <div style={{display:"flex",height:"100%",width:"100%",overflow:"hidden",background:"var(--bg0)"}}>
    <div style={{width:sidebarOpen?188:50,flexShrink:0,background:"var(--bg1)",borderRight:"1px solid var(--bdr)",display:"flex",flexDirection:"column",transition:"width 0.22s",overflow:"hidden"}}>
      <div style={{padding:sidebarOpen?"14px 13px":"14px 0",borderBottom:"1px solid var(--bdr)",display:"flex",alignItems:"center",gap:9,justifyContent:sidebarOpen?"flex-start":"center",flexShrink:0}}>
        <div style={{width:32,height:32,flexShrink:0,background:"linear-gradient(135deg,#0EA5E9,#6366F1)",borderRadius:9,display:"flex",alignItems:"center",justifyContent:"center",fontSize:14,color:"#fff",fontWeight:800,boxShadow:"0 4px 12px rgba(14,165,233,.3)"}}>H</div>
        {sidebarOpen&&<div><div style={{fontFamily:"'Orbitron',monospace",fontSize:11,fontWeight:800,color:"var(--t0)",letterSpacing:"0.06em"}}>MSFS</div><div style={{fontFamily:"'Orbitron',monospace",fontSize:8,color:"var(--acc)",letterSpacing:"0.13em"}}>HANGAR v9</div></div>}
      </div>
      <nav style={{flex:1,padding:"9px 6px",display:"flex",flexDirection:"column",gap:2,overflowY:"auto",minHeight:0}}>
        {NAV.map(n=>(
          <button key={n.id} onClick={()=>{ if(n.id==='settings'){ setSection('settings'); return; } setSection(n.id); }}
            style={{background:(section===n.id)?"var(--accD)":"transparent",border:"1px solid "+((section===n.id)?"var(--accB)":"transparent"),color:(section===n.id)?"var(--acc)":"var(--t2)",borderRadius:8,padding:sidebarOpen?"8px 11px":"8px 0",cursor:"pointer",display:"flex",alignItems:"center",gap:8,fontSize:12,fontWeight:(section===n.id)?600:400,transition:"all 0.14s",width:"100%",justifyContent:sidebarOpen?"flex-start":"center",fontFamily:"inherit"}}>
            <span style={{fontSize:14,flexShrink:0,fontWeight:700}}>{n.ic}</span>
            {sidebarOpen&&<><span>{n.l}</span></>}
          </button>
        ))}
        {sidebarOpen&&section==="library"&&isGeoFilter&&<div style={{marginTop:8}}>
          <GeoFilter addons={addons} filterType={filterType} countries={filterCountries} setCountries={setFilterCountries} regions={filterRegions} setRegions={setFilterRegions}/>
        </div>}
      </nav>
      {sidebarOpen&&<div style={{padding:"9px 13px",borderTop:"1px solid var(--bdr)",flexShrink:0}}>
        <div style={{fontSize:9,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.1em",marginBottom:7}}>Library</div>
        {[['Total',stats.total,'var(--t1)'],...ADDON_TYPE_OPTIONS.map(t=>[t,stats.byType[t]||0,CC[t]||'var(--t1)']),['__spacer__','',null],['Favorites',stats.favorites,'#FBBF24'],['Active',stats.active,'var(--vio)']].map(([l,v,c])=>(
          l==='__spacer__'?<div key={l} style={{height:10}}/>:<div key={l} style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
            <span style={{fontSize:11,color:"var(--t2)"}}>{l}</span>
            <span style={{fontSize:11,fontWeight:700,color:c}}>{v}</span>
          </div>
        ))}
      </div>}
      <button onClick={()=>setSidebarOpen(!sidebarOpen)} style={{background:"none",border:"none",color:"var(--t3)",padding:"9px",cursor:"pointer",fontSize:13,borderTop:"1px solid var(--bdr)",fontFamily:"inherit",flexShrink:0}}>{sidebarOpen?"<":">"}</button>
    </div>
    <div style={{flex:1,display:"flex",flexDirection:"column",minWidth:0,overflow:"hidden"}}>
      <div style={{minHeight:52,display:"flex",alignItems:"center",gap:6,padding:"8px 14px",borderBottom:"1px solid var(--bdr)",background:"var(--bg1)",flexShrink:0,overflowX:"auto",overflowY:"hidden",flexWrap:"wrap",rowGap:6}}>
        {section==="library"&&<>
          <ClearableInput value={search} setValue={setSearch} placeholder="Search name, ICAO, publisher..." style={{flexShrink:0,width:isMobile?240:390}} />
          <div style={{display:'inline-flex',alignItems:'center',gap:8,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'6px 10px',minHeight:48,flexShrink:0}}>
            <span style={{fontSize:11,color:'var(--t2)',fontWeight:800}}>Type:</span>
            <ClearableSelect value={filterType} setValue={value=>{setFilterType(value);setFilterSub('All');setFilterCountries([]);setFilterRegions([]);setSearch('');}} defaultValue='All'
              selectStyle={{background:"transparent",border:"none",color:"var(--t1)",padding:"4px 2px",fontSize:13,cursor:"pointer",fontWeight:700,minWidth:120,outline:'none'}}>
              {TYPES.map(t=><option key={t}>{t}</option>)}
            </ClearableSelect>
          </div>
          <div style={{display:'inline-flex',alignItems:'center',gap:8,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'6px 10px',minHeight:48,flexShrink:0}}>
            <span style={{fontSize:11,color:'var(--t2)',fontWeight:800}}>SubType:</span>
            <ClearableSelect value={filterSub} setValue={setFilterSub} defaultValue='All'
              selectStyle={{background:"transparent",border:"none",color:"var(--t1)",padding:"4px 2px",fontSize:13,cursor:"pointer",fontWeight:700,minWidth:140,outline:'none'}}>
              {subtypes.map(t=><option key={t}>{t}</option>)}
            </ClearableSelect>
          </div>
          <div style={{display:'inline-flex',alignItems:'center',gap:8,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'6px 10px',minHeight:48,flexShrink:0}} title='Filter by library source such as Community, Marketplace, or Local'>
            <span style={{fontSize:11,color:'var(--t2)',fontWeight:800}}>Library Source:</span>
            <ClearableSelect value={sourceFilter} setValue={setSourceFilter} defaultValue='All'
              selectStyle={{background:"transparent",border:"none",color:"var(--t1)",padding:"4px 2px",fontSize:13,cursor:"pointer",fontWeight:700,minWidth:120,outline:'none'}}>
              {sourceOptions.map(t=><option key={t}>{t}</option>)}
            </ClearableSelect>
          </div>
          <div style={{display:'inline-flex',alignItems:'center',gap:8,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'6px 10px',minHeight:48,flexShrink:0}} title='Filter by where the add-on was obtained such as Flightsim.to, Orbx, or direct vendor'>
            <span style={{fontSize:11,color:'var(--t2)',fontWeight:800}}>From:</span>
            <ClearableSelect value={obtainedFromFilter} setValue={setObtainedFromFilter} defaultValue='All'
              selectStyle={{background:"transparent",border:"none",color:"var(--t1)",padding:"4px 2px",fontSize:13,cursor:"pointer",fontWeight:700,minWidth:120,outline:'none'}}>
              {obtainedFromOptions.map(t=><option key={t}>{t}</option>)}
            </ClearableSelect>
          </div>
          {isGeoFilter&&filterCountries.length>0&&<div style={{background:"var(--accD)",border:"1px solid var(--accB)",borderRadius:7,padding:"4px 9px",fontSize:11,color:"var(--acc)",fontWeight:600,flexShrink:0,whiteSpace:"nowrap"}}>
            {filterCountries.map(c=>abbr(c)).join(", ")}{filterRegions.length>0?" / "+filterRegions.join(", "):""}
          </div>}
          {finderIds!==null&&<div style={{display:"flex",alignItems:"center",gap:6,background:"var(--grnD)",border:"1px solid var(--grn)",borderRadius:7,padding:"4px 9px",fontSize:11,color:"var(--grn)",flexShrink:0,whiteSpace:"nowrap"}}>
            Finder: {finderIds.length}
            <span onClick={()=>setFinderIds(null)} style={{cursor:"pointer",fontWeight:700}}>x</span>
          </div>}
          <div style={{display:'inline-flex',alignItems:'center',gap:8,background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'6px 10px',minHeight:48,flexShrink:0,flexWrap:'wrap'}}>
            <span style={{fontSize:11,color:'var(--t2)',fontWeight:800}}>Filter Shortcuts:</span>
            <button title="Filter the grid to favorites only" onClick={()=>setFavOnly(!favOnly)} style={{background:favOnly?"var(--ambD)":"transparent",border:"1px solid "+(favOnly?"rgba(251,191,36,.3)":"var(--bdr)"),color:favOnly?"var(--amb)":"var(--t2)",borderRadius:7,padding:"6px 10px",fontSize:11,fontWeight:600,fontFamily:"inherit",flexShrink:0,cursor:"pointer"}}>{favOnly?"Favs On":"Favs"}</button>
            <button title="Filter the grid to currently activated add-ons only" onClick={()=>{setActiveOnly(!activeOnly); if(!activeOnly) setInactiveOnly(false);}} style={{background:activeOnly?"var(--vioD)":"transparent",border:"1px solid "+(activeOnly?"rgba(167,139,250,.3)":"var(--bdr)"),color:activeOnly?"var(--vio)":"var(--t2)",borderRadius:7,padding:"6px 10px",fontSize:11,fontWeight:600,fontFamily:"inherit",flexShrink:0,cursor:"pointer"}}>{activeOnly?"Active On":"Active"}</button>
            <button title="Filter the grid to inactive add-ons only" onClick={()=>{setInactiveOnly(!inactiveOnly); if(!inactiveOnly) setActiveOnly(false);}} style={{background:inactiveOnly?"rgba(248,113,113,0.12)":"transparent",border:"1px solid "+(inactiveOnly?"rgba(248,113,113,.28)":"var(--bdr)"),color:inactiveOnly?"var(--red)":"var(--t2)",borderRadius:7,padding:"6px 10px",fontSize:11,fontWeight:600,fontFamily:"inherit",flexShrink:0,cursor:"pointer"}}>{inactiveOnly?"Inactive On":"Inactive"}</button>
            {isGeoFilter&&<button title="Open a map for the current filtered airport or scenery results" onClick={()=>setShowGlobalMap(true)} style={{background:"transparent",border:"1px solid var(--bdr)",color:"var(--t2)",borderRadius:7,padding:"6px 10px",fontSize:11,fontWeight:600,fontFamily:"inherit",flexShrink:0,cursor:"pointer"}}>Open Global Map</button>}
          </div>
          <select value={sort} onChange={e=>setSort(e.target.value)}
            style={{marginLeft:"auto",background:"linear-gradient(180deg,var(--bg2),var(--bg1))",border:"1px solid var(--bdr)",color:"var(--t1)",borderRadius:12,padding:"10px 14px",fontSize:13,cursor:"pointer",flexShrink:0,fontWeight:700,minHeight:48}}>
            <option value="title">Name</option><option value="type">Type</option>{filterType==="Airport"&&<option value="icao">ICAO</option>}<option value="fav">Favorites</option><option value="price">Price</option>
          </select>
          <button onClick={()=>setSortDir(d=>d==='asc'?'desc':'asc')} title={sortDir==='asc'?'Ascending':'Descending'} style={{background:"linear-gradient(180deg,var(--bg2),var(--bg1))",border:"1px solid var(--bdr)",color:"var(--t1)",borderRadius:12,padding:"10px 14px",fontSize:14,cursor:"pointer",flexShrink:0,fontWeight:800,minHeight:48}}>{sortDir==='asc'?'↑':'↓'}</button>
          <div style={{display:'flex',alignItems:'center',gap:6,flexShrink:0}}><div style={{display:'flex',gap:4,alignItems:'center',background:'var(--bg2)',border:'1px solid var(--bdr)',borderRadius:12,padding:'4px 6px'}}>{['small','medium','large'].map(size=><button key={size} title={`Set grid card size to ${size}`} onClick={()=>setGridScale(size)} style={{background:gridScale===size?'var(--accD)':'transparent',border:'1px solid '+(gridScale===size?'var(--accB)':'transparent'),color:gridScale===size?'var(--acc)':'var(--t2)',borderRadius:8,padding:'5px 8px',cursor:'pointer',fontSize:10,fontWeight:700,textTransform:'uppercase'}}>{size[0]}</button>)}</div><Btn label='Select Displayed' color='var(--acc)' sm onClick={selectDisplayedAddons} title='Select every add-on currently displayed on the grid so you can create a collection from the current result set.'/><HelpIcon onClick={()=>openGuide('library')} title='Library help'/></div>{pickedIds.length>0&&<div style={{background:'var(--vioD)',border:'1px solid var(--vio)',borderRadius:7,padding:'4px 9px',fontSize:11,color:'var(--vio)',fontWeight:600,flexShrink:0,whiteSpace:'nowrap'}}>Selected: {pickedIds.length} <span onClick={()=>setPickedIds([])} style={{cursor:'pointer',marginLeft:6}}>x</span></div>}
        </>}
        {section!=="library"&&<div style={{display:'flex',alignItems:'center',gap:8}}><div style={{fontSize:14,fontWeight:700,color:"var(--t0)"}}>{(NAV.find(n=>n.id===section)||{}).l||""}</div><HelpIcon onClick={()=>openGuide(section)} title='Screen help'/></div>}
      </div>
      <div style={{flex:1,display:"flex",overflow:"hidden"}}>
        <div style={{flex:selected&&section==="library"&&!isMobile?"0 0 70%":"1",overflowY:"auto",minWidth:0,transition:"flex 0.2s"}}>
          {section==="library"&&<div style={{padding:"12px 14px"}}>
            {/* Keep the collection filter row and totals visible while the user scrolls the grid. */}
            <div style={{position:'sticky',top:0,zIndex:7,background:'linear-gradient(180deg,var(--bg0) 0%, rgba(5,12,24,0.96) 78%, rgba(5,12,24,0.84) 100%)',backdropFilter:'blur(6px)',paddingBottom:10,marginBottom:12}}>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:8,marginBottom:10}}>
                {[['Displayed',filteredTotals.count,'var(--t0)'],['Disk Usage (MB)',formatWholeNumber(filteredTotals.diskMb),'var(--acc)'],['List Price',formatCurrencyWhole(filteredTotals.listPrice),'var(--grn)'],['Price Paid',formatCurrencyWhole(filteredTotals.pricePaid),'var(--amb)'],['Active',filteredTotals.active,'var(--vio)'],['Favorites',filteredTotals.favorites,'#FBBF24']].map(([label,value,color])=><div key={label} style={{background:'rgba(10,22,40,0.92)',border:'1px solid var(--bdr)',borderRadius:12,padding:'8px 10px'}}><div style={{fontSize:9,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:4}}>{label}</div><div style={{fontSize:14,fontWeight:800,color}}>{value}</div></div>)}
              </div>
              {profiles.length>0&&<CollectionStrip profiles={profiles} collectionStatsById={collectionStatsById} activeFilterIds={libraryCollectionFilterIds} onToggle={toggleCollectionFilter} onClear={()=>setLibraryCollectionFilterIds([])} onScrollLeft={()=>{const el=collectionsStripRef.current;if(el) el.scrollBy({left:-260,behavior:'smooth'});}} onScrollRight={()=>{const el=collectionsStripRef.current;if(el) el.scrollBy({left:260,behavior:'smooth'});}} stripRef={collectionsStripRef} actionScope={communityActionScope} setActionScope={setCommunityActionScope} actionMode={communityActionMode} setActionMode={setCommunityActionMode} onExecuteAction={runCommunityAction}/>}
            </div>
            {showGlobalMap&&isGeoFilter&&<div style={{position:'fixed',inset:0,zIndex:100002,background:'rgba(2,6,23,.72)',display:'flex',alignItems:'center',justifyContent:'center',padding:18}}>
              <div style={{width:'min(1320px, 96vw)',height:'min(86vh, 940px)',minWidth:760,minHeight:420,display:'flex',flexDirection:'column',minHeight:0,resize:'both',overflow:'hidden',maxWidth:'96vw',maxHeight:'92vh'}}>
                <GlobalLibraryMap items={filtered} selectedItems={selectedItems} onClose={()=>setShowGlobalMap(false)} onOpenAddon={(addon)=>{ setSelected(addon); setDetailContext({type:'global-map'}); setDetailInitialTab('overview'); setDetail(addon); }} accent='var(--acc)'/>
              </div>
            </div>}
            <div className="card-grid" style={{gridTemplateColumns:`repeat(auto-fill,minmax(min(${gridCardMin}px,100%),1fr))`}}>
              {filtered.map((a,i)=>(
                <div key={a.id} className="fadeUp" style={{animationDelay:(i*0.03)+"s"}}>
                  <AddonCard a={a} scale={gridScale} selected={!isMobile&&selected&&selected.id===a.id} onClick={setSelected} onFav={setFav} onTogglePick={togglePicked} picked={pickedIds.includes(a.id)} onToggleEnabled={handleAddonToggleEnabled} onToggleEnabledError={handleAddonToggleError}/>
                </div>
              ))}
              {initialLoad&&<div style={{gridColumn:"1/-1",textAlign:"center",padding:"60px 0",color:"var(--t2)"}}>
                <div className="spin" style={{width:32,height:32,border:"3px solid var(--acc)",borderTopColor:"transparent",borderRadius:"50%",margin:"0 auto 16px"}}/>
                <div style={{fontSize:13}}>Loading library...</div>
              </div>}
              {!initialLoad&&!apiMode&&addons.length===0&&<div style={{gridColumn:"1/-1",textAlign:"center",padding:"60px 0",color:"var(--t2)"}}>
                <div style={{fontSize:40,marginBottom:16}}>📂</div>
                <div style={{fontSize:16,fontWeight:700,color:"var(--t0)",marginBottom:8}}>No addons in library</div>
                <div style={{fontSize:13,marginBottom:20,maxWidth:400,margin:"0 auto 20px"}}>Go to Settings, set your Addons Root folder, then click Scan Now to populate your library from your installed MSFS addons.</div>
                <Btn label="Go to Settings" color="var(--acc)" onClick={()=>setSection("settings")}/>
              </div>}
              {!initialLoad&&apiMode&&addons.length===0&&<div style={{gridColumn:"1/-1",textAlign:"center",padding:"60px 0",color:"var(--t2)"}}>
                <div style={{fontSize:40,marginBottom:16}}>📂</div>
                <div style={{fontSize:16,fontWeight:700,color:"var(--t0)",marginBottom:8}}>Library is empty</div>
                <div style={{fontSize:13,marginBottom:20}}>Go to Settings and run a Scan to find your installed addons.</div>
                <Btn label="Scan Now" color="var(--acc)" onClick={()=>{setSection("settings");startScan();}}/>
              </div>}
              {!initialLoad&&filtered.length===0&&addons.length>0&&<div style={{gridColumn:"1/-1",textAlign:"center",padding:"60px 0",color:"var(--t2)",fontSize:13}}>No addons match your filters.</div>}
            </div>
          </div>}
          {section==="finder"&&<AircraftFinder addons={addons} onFilterGrid={ids=>{setFinderIds(ids);setSection("library");}} onOpenDetail={(addon)=>{setDetailContext({type:'finder'}); setDetailInitialTab('overview'); setDetail(addon);}} initialState={finderState} onStateChange={setFinderState}/>}
          {section==="collections"&&<CollectionManager profiles={profiles} addons={addons} activeCollectionId={activeCollectionId} setActiveCollectionId={setActiveCollectionId} activeCollection={activeCollection} collectionStatsById={collectionStatsById} collectionPickedIds={collectionPickedIds} setCollectionPickedIds={setCollectionPickedIds} collectionAddPickedIds={collectionAddPickedIds} setCollectionAddPickedIds={setCollectionAddPickedIds} collectionAvailableItems={collectionAvailableItems} activeCollectionItems={activeCollectionItems} collectionSearch={collectionSearch} setCollectionSearch={setCollectionSearch} onRemoveFromCollection={removeFromCollection} onAddToCollection={addToCollectionFromManager} onDeleteCollection={deleteProfile} onRenameCollection={renameCollection} onViewInLibrary={viewCollectionInLibrary}/>}
          {section==="settings"&&<div style={{padding:24,maxWidth:"min(1320px, calc(100vw - 48px))",width:"100%",overflowY:"auto",height:"100%"}}>
            <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:14}}><div style={{fontSize:18,fontWeight:800,color:"var(--t0)"}}>Settings</div><HelpIcon onClick={()=>openGuide('settings')} title='Settings help'/></div>
            <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:18}}>
              {[['library','Library Management'],['community','Community Folder Management'],['ai','AI'],['ui','User Interface'],['data','Data Management']].map(([id,label])=><button key={id} onClick={()=>setSettingsTab(id)} style={{background:settingsTab===id?'var(--accD)':'var(--bg2)',border:'1px solid '+(settingsTab===id?'var(--accB)':'var(--bdr)'),color:settingsTab===id?'var(--acc)':'var(--t1)',borderRadius:10,padding:'9px 12px',fontSize:12,fontWeight:700,cursor:'pointer',fontFamily:'inherit'}}>{label}</button>)}
            </div>


            <div style={{display:settingsTab==='ai'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Populate Data AI Provider</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Choose which AI provider the app uses for Populate actions. Each provider uses its lowest-cost populate model: Gemini Flash-Lite, OpenAI GPT-5.4 Nano, or Claude Haiku. Populate actions can also update the installed version field when newer product metadata is found.</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr",gap:10,marginBottom:10}}>
                <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>Provider</div>
                  <select value={selectedAIProvider} onChange={e=>setSelectedAIProvider(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12}}>
                    <option value='gemini'>Google Gemini</option>
                    <option value='openai'>OpenAI</option>
                    <option value='claude'>Claude</option>
                  </select>
                </div>
                {selectedAIProvider==='openai' && <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>OpenAI API Key</div>
                  <div style={{display:"flex",gap:8}}>
                    <input type="password" id="provider-openai-key" defaultValue={apiKey} placeholder="sk-..." style={{flex:1,background:"var(--bg0)",border:"1px solid var(--bdr)",borderRadius:7,padding:"8px 11px",color:"var(--t0)",fontSize:12,outline:"none",fontFamily:"monospace"}}/>
                    <Btn label="Save" color="var(--acc)" sm onClick={()=>{const v=document.getElementById('provider-openai-key');const k=v&&v.value||'';saveKey(k);fetch('/api/settings/openai_key',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:k})}).catch(()=>{});}}/>
                  </div>
                </div>}
                {selectedAIProvider==='gemini' && <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>Google Gemini API Key</div>
                  <div style={{display:"flex",gap:8}}>
                    <input type="password" id="provider-gemini-key" defaultValue={googleKey} placeholder="AIza..." style={{flex:1,background:"var(--bg0)",border:"1px solid var(--bdr)",borderRadius:7,padding:"8px 11px",color:"var(--t0)",fontSize:12,outline:"none",fontFamily:"monospace"}}/>
                    <Btn label="Save" color="var(--acc)" sm onClick={()=>{const v=document.getElementById('provider-gemini-key');const k=v&&v.value||'';saveGoogleKey(k);fetch('/api/settings/google_api_key',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:k})}).catch(()=>{});}}/>
                  </div>
                </div>}
                {selectedAIProvider==='claude' && <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>Claude API Key</div>
                  <div style={{display:"flex",gap:8}}>
                    <input type="password" id="provider-claude-key" defaultValue={claudeKey} placeholder="sk-ant-..." style={{flex:1,background:"var(--bg0)",border:"1px solid var(--bdr)",borderRadius:7,padding:"8px 11px",color:"var(--t0)",fontSize:12,outline:"none",fontFamily:"monospace"}}/>
                    <Btn label="Save" color="var(--acc)" sm onClick={()=>{const v=document.getElementById('provider-claude-key');const k=v&&v.value||'';saveClaudeKey(k);fetch('/api/settings/claude_api_key',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:k})}).catch(()=>{});}}/>
                  </div>
                </div>}
              </div>
              <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap',marginBottom:8}}>
                <Btn label='Save AI Provider' color='var(--acc)' sm onClick={saveAISelection}/>
                <Btn label='Refresh Usage Info' color='var(--t2)' sm onClick={loadAIUsage}/>
                <span style={{fontSize:11,color:'var(--t2)'}}>Configured: {configuredAIProviders.length?configuredAIProviders.map(providerLabel).join(', '):'none yet'}</span>
              </div>
              {aiUsage&&<div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:10,padding:'10px 12px',fontSize:11,color:'var(--t1)',lineHeight:1.7}}>
                <div style={{fontWeight:700,color:'var(--t0)',marginBottom:4}}>Usage / limits</div>
                <div style={{marginBottom:4}}>Gemini: {aiUsage.gemini_note} {aiUsage.gemini_reset_note}</div>
                {aiUsage.gemini_status&&aiUsage.gemini_status.error&&<div style={{marginBottom:4,color:aiUsage.gemini_status.quota_hit?'var(--amb)':'var(--t2)'}}>Last Gemini status: {aiUsage.gemini_status.error}</div>}
                {aiUsage.openai_rate_limits&&Object.values(aiUsage.openai_rate_limits).some(Boolean)?<div style={{marginBottom:4}}>Last OpenAI rate headers — Remaining requests: {aiUsage.openai_rate_limits.remaining_requests||'—'} · Remaining tokens: {aiUsage.openai_rate_limits.remaining_tokens||'—'} · Request reset: {aiUsage.openai_rate_limits.reset_requests||'—'} · Token reset: {aiUsage.openai_rate_limits.reset_tokens||'—'}</div>:<div style={{marginBottom:4}}>OpenAI remaining usage appears here after the app makes an OpenAI API call.</div>}
                {aiUsage.claude_status&&Object.values(aiUsage.claude_status).some(Boolean)?<div>Last Claude status — Remaining requests: {aiUsage.claude_status.remaining_requests||'—'} · Request reset: {aiUsage.claude_status.reset_requests||'—'} · Retry after: {aiUsage.claude_status.retry_after||'—'}</div>:<div>{aiUsage.claude_note||'Claude remaining usage appears here after the app makes a Claude API call.'}</div>}
              </div>}
            </div>

            <div style={{display:settingsTab==='ai'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Populate Subtypes with AI</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Use the selected AI provider to review your add-ons and choose the most appropriate Subtype from the choices stored in Data Management. If none of the existing choices fit, the AI can add a new subtype to that Type.</div>
              <div style={{display:'grid',gridTemplateColumns:'1fr auto auto',gap:10,alignItems:'end',marginBottom:10}}>
                <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>Type</div>
                  <select value={subtypeAIType} onChange={e=>setSubtypeAIType(e.target.value)} disabled={subtypeAIAllTypes} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12}}>{ADDON_TYPE_OPTIONS.map(opt=><option key={opt} value={opt}>{opt}</option>)}</select>
                </div>
                <label style={{display:'inline-flex',alignItems:'center',gap:6,fontSize:11,color:'var(--t1)',paddingBottom:8}}><input type='checkbox' checked={subtypeAIAllTypes} onChange={e=>setSubtypeAIAllTypes(e.target.checked)}/> Across all Types</label>
                <Btn label={subtypeAIProgress&&subtypeAIProgress.running?'Populating Subtypes...':'Populate with AI for Subtype'} color='var(--vio)' sm disabled={!hasSelectedProviderKey || (subtypeAIProgress&&subtypeAIProgress.running)} onClick={async()=>{ const res=await fetch('/api/ai/populate-subtypes/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({addon_type:subtypeAIType,all_types:subtypeAIAllTypes,provider:selectedAIProvider})}).catch(()=>null); if(!res) return; const data=await res.json().catch(()=>({})); if(!res.ok){ setNotice({title:'Subtype populate failed',message:data.detail||'Could not start subtype populate.',kind:'error'}); return; } setSubtypeAIProgress({running:true,pct:0,current:'Preparing…',done:0,total:data.total||0,message:'Reviewing add-ons and assigning subtypes...',type:'running'}); }}/>
              </div>
              {subtypeAIProgress&&<div>
                <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}><span style={{fontSize:11,color:'var(--t1)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:'70%'}}>{subtypeAIProgress.current||'Reviewing add-ons...'}</span><span style={{fontSize:11,color:subtypeAIProgress.type==='done'?'var(--grn)':'var(--vio)',fontWeight:700}}>{subtypeAIProgress.pct||0}%</span></div>
                <div style={{height:6,background:'var(--bg3)',borderRadius:3,overflow:'hidden'}}><div style={{height:'100%',width:(subtypeAIProgress.pct||0)+'%',background:subtypeAIProgress.type==='done'?'var(--grn)':'var(--vio)',borderRadius:3,transition:'width 0.3s'}}/></div>
                <div style={{fontSize:11,color:'var(--t2)',marginTop:6}}>{subtypeAIProgress.message||'Reviewing add-ons and choosing the best subtype from Data Management.'}</div>
              </div>}
            </div>

            <div style={{display:settingsTab==='library'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Flight Simulator Target</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Used by AI populate actions so release date, list price, and latest version are searched for the correct simulator platform.</div>
              <div style={{display:'grid',gridTemplateColumns:'1.2fr .8fr auto',gap:8,alignItems:'center'}}>
                <input value={simName} onChange={e=>setSimName(e.target.value)} placeholder='MSFS' style={{background:"var(--bg0)",border:"1px solid var(--bdr)",borderRadius:7,padding:"8px 11px",color:"var(--t0)",fontSize:12,outline:"none"}}/>
                <input value={simVersion} onChange={e=>setSimVersion(e.target.value)} placeholder='2024' style={{background:"var(--bg0)",border:"1px solid var(--bdr)",borderRadius:7,padding:"8px 11px",color:"var(--t0)",fontSize:12,outline:"none"}}/>
                <Btn label="Save" color="var(--acc)" sm onClick={()=>{localStorage.setItem('hangar_sim_name',simName); localStorage.setItem('hangar_sim_version',simVersion); fetch('/api/settings/flight_sim_name',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:simName})}).catch(()=>{}); fetch('/api/settings/flight_sim_version',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:simVersion})}).catch(()=>{});}}/>
              </div>
            </div>

            {/* Library scanning */}
            <div style={{display:settingsTab==='library'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Library Import / Update</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:12}}>Choose the Add-ons Root here, preview path relocation when you move your add-on library to a new drive or folder, and then control scanning/import behavior below.</div>
              <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 12px',marginBottom:12}}>
                <div style={{fontSize:11,color:'var(--t1)',fontWeight:700,marginBottom:4}}>Add-ons Root Folder</div>
                <div style={{fontSize:11,color:'var(--t2)',marginBottom:8}}>Where your simulator add-ons are stored. Save this first only when you are setting up a brand-new library. If you already moved the folders in Windows, use the relocation preview below so the existing library paths are updated safely.</div>
                <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
                  <input value={addonsRootPath} onChange={e=>setAddonsRootPath(e.target.value)} placeholder='D:\\MSFS Addons' style={{flex:1,minWidth:260,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 11px',color:'var(--t0)',fontSize:12,outline:'none'}}/>
                  <Btn label='Browse…' color='var(--t2)' sm onClick={()=>window.dispatchEvent(new CustomEvent('hangar-browse-path',{detail:{id:'addons_root_library',label:'Add-ons Root Folder',current:addonsRootPath||savedAddonsRoot||''}}))}/>
                  <Btn label='Save' color='var(--acc)' sm onClick={async()=>{ try{ localStorage.setItem('hangar_addons_root',addonsRootPath||''); }catch(e){}; await fetch('/api/settings/addons_root',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:addonsRootPath||''})}).catch(()=>{}); setSavedAddonsRoot(addonsRootPath||''); setNotice({title:'Add-ons Root saved',message:'The Add-ons Root folder was updated. This changes future scans, but it does not rewrite existing library paths by itself.'}); }}/>
                </div>
              </div>
              <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 12px',marginBottom:12}}>
                <div style={{fontSize:11,color:'var(--t1)',fontWeight:700,marginBottom:4}}>Relocate Add-on Library Root</div>
                <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.65,marginBottom:10}}>Use this after you physically copy or move your add-on folders in Windows. MSFS Hanger will update library records, image/doc paths, and selected scan-folder paths to the new root. It does <strong style={{color:'var(--t0)'}}>not</strong> move files for you.</div>
                <div style={{display:'grid',gridTemplateColumns:'1fr',gap:8,marginBottom:10}}>
                  <div>
                    <div style={{fontSize:10,color:'var(--t2)',marginBottom:4,fontWeight:700}}>Old root detected from current library</div>
                    <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'9px 11px',fontSize:12,color:'var(--t1)',fontFamily:'monospace',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={savedAddonsRoot||'No Add-ons Root saved yet'}>{savedAddonsRoot||'No Add-ons Root saved yet'}</div>
                  </div>
                  <div>
                    <div style={{fontSize:10,color:'var(--t2)',marginBottom:4,fontWeight:700}}>New root from the Add-ons Root field above</div>
                    <div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'9px 11px',fontSize:12,color:'var(--t1)',fontFamily:'monospace',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={addonsRootPath||'Enter the new Add-ons Root above first'}>{addonsRootPath||'Enter the new Add-ons Root above first'}</div>
                  </div>
                </div>
                <label style={{display:'inline-flex',alignItems:'center',gap:8,fontSize:12,color:'var(--t1)',marginBottom:12}}><input type='checkbox' checked={relocateRepairLinks} onChange={e=>setRelocateRepairLinks(e.target.checked)}/> Repair enabled Community symbolic links after the library paths are updated</label>
                <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:10}}>
                  <Btn label={relocateBusy?'Checking...':'Preview Relocation'} color='var(--vio)' sm disabled={relocateBusy||!savedAddonsRoot||!addonsRootPath||savedAddonsRoot===addonsRootPath} onClick={async()=>{ setRelocateBusy(true); try{ const r=await fetch('/api/library/relocate/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_root:savedAddonsRoot||'',new_root:addonsRootPath||'',repair_links:relocateRepairLinks})}); const data=await r.json(); if(!r.ok) throw new Error(data.detail||data.message||'Preview failed'); setRelocatePreview(data); }catch(e){ setRelocatePreview(null); setNotice({title:'Relocation preview failed',message:e.message||'Could not validate the relocation request.',kind:'error'}); } finally{ setRelocateBusy(false); } }}/>
                  <Btn label='Clear Preview' color='var(--t2)' sm onClick={()=>setRelocatePreview(null)} disabled={!relocatePreview}/>
                </div>
                {relocatePreview&&<div style={{background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 13px'}}>
                  <div style={{fontSize:11,fontWeight:800,color:'var(--vio)',marginBottom:6,textTransform:'uppercase',letterSpacing:'0.08em'}}>Preview before execution</div>
                  <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.65,marginBottom:10}}>Confirmed folders exist and are different. Review the summary below, then execute if everything looks right.</div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))',gap:8,marginBottom:10}}>
                    {[['Add-ons to update',relocatePreview.count],['Missing new folders',relocatePreview.missing_count],['Missing manifests',relocatePreview.manifest_missing_count],['Enabled links to repair',relocatePreview.repair_candidates]].map(([k,v])=><div key={k} style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:10,padding:'9px 10px'}}><div style={{fontSize:10,color:'#C8D8EA',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:2,fontWeight:700}}>{k}</div><div style={{fontSize:16,color:'var(--t0)',fontWeight:800}}>{v}</div></div>)}
                  </div>
                  {!!(relocatePreview.sample||[]).length&&<div style={{fontSize:11,color:'var(--t1)',marginBottom:10,maxHeight:140,overflow:'auto'}}>
                    {(relocatePreview.sample||[]).map(item=><div key={item.addon_id} style={{padding:'6px 0',borderTop:'1px solid rgba(255,255,255,.05)'}}><div style={{fontWeight:700,color:'var(--t0)'}}>{item.title}</div><div style={{fontSize:10,color:'var(--t2)',fontFamily:'monospace',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={item.new_addon_path}>{item.new_addon_path}</div></div>)}
                  </div>}
                  <Btn label='Execute Relocation' color='var(--grn)' sm onClick={()=>openConfirmDialog({eyebrow:'Library relocation',title:'Update library paths to the new Add-ons Root?',message:'MSFS Hanger will rewrite stored add-on paths, manifest/image/doc references, selected scan folders, and then optionally repair enabled Community links. It will not move folders on disk. Continue?',confirmLabel:'Execute Relocation',confirmColor:'var(--grn)'}, async()=>{ setRelocateBusy(true); try{ const r=await fetch('/api/library/relocate/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_root:savedAddonsRoot||'',new_root:addonsRootPath||'',repair_links:relocateRepairLinks})}); const data=await r.json(); if(!r.ok) throw new Error(data.detail||data.message||'Relocation failed'); localStorage.setItem('hangar_addons_root', addonsRootPath||''); setSavedAddonsRoot(addonsRootPath||''); setRelocatePreview(null); const refreshed=await fetch('/api/addons').then(rr=>rr.ok?rr.json():[]).catch(()=>[]); if(Array.isArray(refreshed)) setAddons(refreshed); loadTopFolders(); setNotice({title:'Library relocation complete',message:`Updated ${data.updated||0} add-on path record(s). Repaired ${data.repaired_links||0} Community link(s). Missing new folders: ${data.missing_count||0}.`}); }catch(e){ setNotice({title:'Relocation failed',message:e.message||'The library paths could not be updated.',kind:'error'}); } finally{ setRelocateBusy(false); } })}/>
                </div>}
              </div>
              <div style={{borderTop:"1px solid var(--bdr)",paddingTop:12,marginTop:4}}>
                <div style={{fontSize:11,color:"var(--t1)",fontWeight:600,marginBottom:8}}>Scan Library</div>
                {scanProgress&&scanProgress.type!=="done"&&<div style={{marginBottom:10}}>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
                    <span style={{fontSize:11,color:"var(--t1)",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",maxWidth:"70%"}}>{scanProgress.current||"Scanning..."}</span>
                    <span style={{fontSize:11,color:"var(--acc)",fontWeight:700,flexShrink:0}}>{scanProgress.pct||0}%</span>
                  </div>
                  <div style={{height:6,background:"var(--bg3)",borderRadius:3,overflow:"hidden"}}>
                    <div style={{height:"100%",width:(scanProgress.pct||0)+"%",background:"var(--acc)",borderRadius:3,transition:"width 0.3s"}}/>
                  </div>
                  {scanProgress.type==="done"&&<div style={{fontSize:11,color:"var(--grn)",marginTop:6}}>Done — +{scanProgress.added} new, {scanProgress.updated} updated, {scanProgress.removed} removed</div>}
                  {scanProgress.type==="error"&&<div style={{fontSize:11,color:"var(--red)",marginTop:6}}>{scanProgress.message}</div>}
                </div>}
                <div style={{display:"flex",gap:8,alignItems:"center",flexWrap:"wrap"}}>
                  <Btn label={scanning?"Scanning...":"Scan Now"} color="var(--acc)" onClick={scanning?stopScan:startScan}/>
                  {scanning&&<Btn label="Stop" color="var(--red)" sm onClick={stopScan}/>}
                  <label style={{display:"inline-flex",alignItems:"center",gap:6,fontSize:11,color:"var(--t1)"}}><input type="checkbox" checked={activatedOnly} onChange={e=>setActivatedOnly(e.target.checked)}/> Import only activated addons</label>
                  <label style={{display:"inline-flex",alignItems:"center",gap:6,fontSize:11,color:"var(--t1)"}}><input type="checkbox" checked={scanPopulateNewAI} onChange={e=>setScanPopulateNewAI(e.target.checked)}/> Populate new add-ons with selected AI</label>
                </div>
                <div style={{fontSize:10,color:"var(--t3)",marginTop:8}}>When enabled, only newly added add-ons are sent through the same low-cost Populate with AI Data workflow used from the selected add-on panel.</div>
                {!apiMode&&<div style={{fontSize:11,color:"var(--amb)",marginTop:8}}>Not connected to backend. Start via run_hangar.bat to enable scanning.</div>}
              </div>
              <TopFolderSelector folders={topFolders} selected={selectedFolders} onToggle={toggleFolder} onSave={saveFolderSelection} onReload={loadTopFolders} onReset={resetLibrary} apiMode={apiMode}/>
              <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 12px',marginTop:12}}>
                <div style={{fontSize:11,color:'var(--t1)',fontWeight:700,marginBottom:4}}>Ignored from Future Scans</div>
                <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:10}}>Use this list for add-ons you want to keep on disk but not manage in the library. Scan Now will skip them until you remove them from this list.</div>
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:8}}><div style={{fontSize:12,color:'var(--t0)',fontWeight:700}}>{ignoredItems.length} item(s) currently ignored</div>{ignoredItems.length>0&&<Btn label='Refresh' color='var(--t2)' sm onClick={loadIgnoredItems}/>}</div>
                {ignoredItems.length===0?<div style={{fontSize:11,color:'var(--t2)'}}>No ignored add-ons yet.</div>:<div style={{display:'grid',gap:8,maxHeight:200,overflow:'auto'}}>{ignoredItems.slice(0,40).map(item=><div key={item.id} style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:10,padding:'9px 10px'}}><div style={{minWidth:0}}><div style={{fontSize:12,color:'var(--t0)',fontWeight:700,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{item.title||item.package_name||item.addon_path}</div><div style={{fontSize:10,color:'var(--t2)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{item.package_name||item.addon_path}</div></div><Btn label='Allow Scan Again' color='var(--vio)' sm onClick={()=>restoreIgnoredSelection([item.id])}/></div>)}</div>}
              </div>
            </div>

              <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 12px',marginTop:12,display:settingsTab==='library'?'block':'none'}}>
                <div style={{fontSize:11,color:'var(--t1)',fontWeight:700,marginBottom:4}}>Community-only Add-ons</div>
                <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:10}}>Import real folders already installed directly in the Community folder. These items appear in the library as Community Only and are not link-managed.</div>
                <Btn label='Import Community-only Add-ons' color='var(--acc)' sm onClick={importCommunityOnly}/>
              </div>
              <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 12px',marginTop:12,display:settingsTab==='library'?'block':'none'}}>
                <div style={{fontSize:11,color:'var(--t1)',fontWeight:700,marginBottom:4}}>Official / Marketplace Inventory</div>
                <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:10}}>Import Official2024 / OneStore content as inventory you own. These items stay visible in the library but are not link-managed or activatable.</div>
                <PathInput id="official_root" label="Official / Marketplace Folder" hint="Point this to your Official2024, Official, or OneStore folder for Marketplace inventory imports" placeholder="D:\MSFS2024\Official2024"/>
                <Btn label='Import Official / Marketplace Items' color='var(--acc)' sm onClick={importOfficialLibrary}/>
              </div>
              <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 12px',marginTop:12,display:settingsTab==='library'?'block':'none'}}>
                <div style={{fontSize:11,color:'var(--t1)',fontWeight:700,marginBottom:4}}>External Applications / Tools</div>
                <div style={{fontSize:11,color:'var(--t2)',lineHeight:1.6,marginBottom:10}}>Add external flight-sim tools to the library as Local items so they can be launched from MSFS Hanger. Choose one of the normal library Types below, use the tool subtype that fits best, and keep the Source as Local. These items do not use Community activation controls.</div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr 1fr',gap:8,marginBottom:8}}>
                  <input value={toolName} onChange={e=>setToolName(e.target.value)} placeholder='Display name' style={{width:'100%',background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}/>
                  <input value={toolPublisher} onChange={e=>setToolPublisher(e.target.value)} placeholder='Publisher / developer' style={{width:'100%',background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}/>
                  <select value={toolType} onChange={e=>setToolType(e.target.value)} style={{width:'100%',background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}>
                    {ADDON_TYPE_OPTIONS.map(opt=><option key={opt} value={opt}>{opt}</option>)}
                  </select>
                  <select value={toolSubtype} onChange={e=>setToolSubtype(e.target.value)} style={{width:'100%',background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}>
                    {['Air Traffic Control','Mapping','Flight Planning','Navigation','Utility','Sim Platform','Launcher','Other'].map(opt=><option key={opt} value={opt}>{opt}</option>)}
                  </select>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'1fr auto',gap:8,marginBottom:8}}>
                  <input value={toolPath} onChange={e=>setToolPath(e.target.value)} placeholder='Executable path, e.g. C:\Tools\LittleNavmap\Little Navmap.exe' style={{width:'100%',background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}/>
                  <Btn label='Browse EXE…' color='var(--t2)' sm onClick={()=>window.dispatchEvent(new CustomEvent('hangar-browse-path',{detail:{id:'tool_executable',label:'Choose Tool Executable',current:toolWorkingDir||'',mode:'file',pattern:'*.exe,*.bat,*.cmd'}}))}/>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'1fr auto',gap:8,marginBottom:8}}>
                  <input value={toolWorkingDir} onChange={e=>setToolWorkingDir(e.target.value)} placeholder='Working folder (optional)' style={{width:'100%',background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12}}/>
                  <Btn label='Browse Folder…' color='var(--t2)' sm onClick={()=>window.dispatchEvent(new CustomEvent('hangar-browse-path',{detail:{id:'tool_working_dir',label:'Choose Tool Working Folder',current:toolWorkingDir||''}}))}/>
                </div>
                <textarea value={toolNotes} onChange={e=>setToolNotes(e.target.value)} placeholder='Notes (optional)' style={{width:'100%',height:72,background:'var(--bg1)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 10px',color:'var(--t0)',fontSize:12,resize:'vertical',marginBottom:8}}/>
                <Btn label='Add Tool to Library' color='var(--grn)' sm onClick={addExternalTool}/>
              </div>

            {/* Community folder management */}
            <div style={{display:settingsTab==='community'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Community Folder Management</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:12}}>Choose the Community folder here, then use the actions below when you want to activate or deactivate every add-on in the library. The Add-ons Root now lives in the Library Management tab.</div>
              <PathInput id="community_dir" label="Community Folder" hint="The simulator Community folder where directory symbolic links are created" placeholder="C:\\Users\\YourName\\...\\Community"/>
              <div style={{background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:12,padding:'12px 12px',marginTop:12}}>
                <div style={{fontSize:11,color:'var(--t1)',fontWeight:700,marginBottom:8}}>Global symbolic-link actions</div>
                <div style={{fontSize:11,color:'var(--t2)',marginBottom:10}}>These actions change Community-folder links only. They do not delete source addon folders from your Add-ons Root.</div>
                <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
                  <Btn label='Activate All Add-ons' color='var(--grn)' sm onClick={()=>runCommunityAction('all','activate')} title='Create directory symbolic links in Community for every add-on in the library.'/>
                  <Btn label='Deactivate All Add-ons' color='var(--red)' sm onClick={()=>runCommunityAction('all','deactivate')} title='Remove every managed Community-folder link after a confirmation preview. This does not delete your source add-on folders.'/>
                </div>
              </div>
            </div>

            {/* Populate Library with AI */}
            <div style={{display:settingsTab==='ai'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Populate Library with AI</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Populate addon overview summaries, detailed feature writeups, and aircraft data for the whole library using the AI provider selected above. Overview output aims for at least two paragraphs about the addon purpose, while Features is generated as a more in-depth formatted feature breakdown.</div>
              <div style={{display:'flex',gap:12,flexWrap:'wrap',marginBottom:8}}>
                <label style={{display:"inline-flex",alignItems:"center",gap:6,fontSize:11,color:"var(--t1)"}}><input type="checkbox" checked={bulkOverrideExisting} onChange={e=>setBulkOverrideExisting(e.target.checked)}/> Override Existing Overview / Features</label>
                <label style={{display:"inline-flex",alignItems:"center",gap:6,fontSize:11,color:"var(--t1)"}}><input type="checkbox" checked={bulkIncludeAircraftData} onChange={e=>setBulkIncludeAircraftData(e.target.checked)}/> Include Aircraft Data</label>
              </div>
              <div style={{fontSize:10,color:"var(--t3)",marginBottom:10}}>When override is off, existing overview/features are preserved and AI fills blanks or generic placeholder summaries. Turn override on to replace current overview/features with fresh AI output.</div>
              <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap',marginBottom:10}}>
                <Btn label={bulkGeminiProgress&&bulkGeminiProgress.running?"Populating with selected AI...":"Start Library Populate using selected AI"} color="var(--vio)" sm onClick={startBulkGemini} disabled={!hasSelectedProviderKey || (bulkGeminiProgress&&bulkGeminiProgress.running)}/>
                {!hasSelectedProviderKey&&<span style={{fontSize:11,color:'var(--amb)'}}>Save the API key for your selected AI first.</span>}
              </div>
              {bulkGeminiProgress&&bulkGeminiProgress.running&&<div>
                <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}><span style={{fontSize:11,color:"var(--t1)",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",maxWidth:"70%"}}>{bulkGeminiProgress.current||"Populating library..."}</span><span style={{fontSize:11,color:"var(--vio)",fontWeight:700}}>{bulkGeminiProgress.pct||0}%</span></div>
                <div style={{height:6,background:"var(--bg3)",borderRadius:3,overflow:"hidden"}}><div style={{height:"100%",width:(bulkGeminiProgress.pct||0)+"%",background:"var(--vio)",borderRadius:3,transition:"width 0.3s"}}/></div>
                {bulkGeminiProgress.message&&<div style={{fontSize:11,color:bulkGeminiProgress.type==='done'?"var(--grn)":"var(--t2)",marginTop:6}}>{bulkGeminiProgress.message}</div>}
              </div>}
            </div>

            <div style={{display:settingsTab==='ui'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Localization</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Choose the language used for browser and AI research context plus how currency and dates are displayed in the app.</div>
              <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:10,marginBottom:10}}>
                <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>Language</div>
                  <select value={localeLanguage} onChange={e=>setLocaleLanguage(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12}}>
                    {['English','Spanish','French','German','Italian','Portuguese'].map(v=><option key={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>Currency</div>
                  <select value={localeCurrency} onChange={e=>setLocaleCurrency(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12}}>
                    {['$','€','£','¥','CAD$','AUD$'].map(v=><option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <div style={{fontSize:10,color:"var(--t3)",textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>Calendar Format</div>
                  <select value={localeCalendar} onChange={e=>setLocaleCalendar(e.target.value)} style={{width:'100%',background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:7,padding:'8px 11px',color:'var(--t0)',fontSize:12}}>
                    {['MM/DD/YYYY','DD/MM/YYYY','YYYY-MM-DD'].map(v=><option key={v}>{v}</option>)}
                  </select>
                </div>
              </div>
              <Btn label="Save Localization" color="var(--acc)" sm onClick={saveLocalization}/>
            </div>

            <div style={{display:settingsTab==='ui'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Browser Search Provider</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Choose which search engine the built-in browser uses for research, specs, and image searches. Bing remains the default because it is less likely to interrupt with validation.</div>
              <div style={{display:'flex',gap:10,alignItems:'center',flexWrap:'wrap',marginBottom:10}}>
                <select value={searchProvider} onChange={e=>setSearchProvider(e.target.value)} style={{minWidth:180,background:'var(--bg0)',border:'1px solid var(--bdr)',borderRadius:8,padding:'8px 11px',color:'var(--t0)',fontSize:12}}>
                  <option value='bing'>Bing (default)</option>
                  <option value='google'>Google</option>
                </select>
                <Btn label='Save Search Provider' color='var(--acc)' sm onClick={saveSearchProvider}/>
              </div>
              <div style={{fontSize:11,color:'var(--t3)'}}>Google may return stronger result quality for some searches, but it is also more likely to show a human-verification page inside embedded browsing workflows.</div>
            </div>

            {/* Display Mode */}
            <div style={{display:settingsTab==='ui'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:10}}>Display Mode</div>
              <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                {[["system","System Default"],["dark","Dark"],["light","Light"]].map(([mode,label])=>(
                  <button key={mode} onClick={()=>{
                    const r=document.documentElement;
                    if(mode==="light"){r.style.setProperty("--bg0","#F8FAFC");r.style.setProperty("--bg1","#FFFFFF");r.style.setProperty("--bg2","#F1F5F9");r.style.setProperty("--bg3","#E2E8F0");r.style.setProperty("--card","#FFFFFF");r.style.setProperty("--cardH","#F1F5F9");r.style.setProperty("--bdr","rgba(0,0,0,0.1)");r.style.setProperty("--bdrH","rgba(0,0,0,0.2)");r.style.setProperty("--t0","#0F172A");r.style.setProperty("--t1","#334155");r.style.setProperty("--t2","#64748B");r.style.setProperty("--t3","#94A3B8");}
                    else{r.style.setProperty("--bg0","#050C18");r.style.setProperty("--bg1","#0A1628");r.style.setProperty("--bg2","#0F1E35");r.style.setProperty("--bg3","#152540");r.style.setProperty("--card","#192A45");r.style.setProperty("--cardH","#1F3254");r.style.setProperty("--bdr","rgba(255,255,255,0.07)");r.style.setProperty("--bdrH","rgba(255,255,255,0.18)");r.style.setProperty("--t0","#F1F5F9");r.style.setProperty("--t1","#94A3B8");r.style.setProperty("--t2","#64748B");r.style.setProperty("--t3","#475569");}
                    localStorage.setItem("hangar-theme",mode);
                  }} style={{background:"var(--bg0)",border:"2px solid var(--bdr)",color:"var(--t0)",borderRadius:8,padding:"8px 16px",cursor:"pointer",fontSize:12,fontFamily:"inherit",fontWeight:600}}>{label}</button>
                ))}
              </div>
            </div>

            {/* Data Management */}
            <div style={{display:settingsTab==='data'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Data Management</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Manage dropdown choices used in Your Data.</div>
              <DataOptionsManager/>
            </div>

            {/* Tags Management */}
            <div style={{display:settingsTab==='data'?'block':'none',background:"var(--bg2)",border:"1px solid var(--bdr)",borderRadius:12,padding:18,marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:700,color:"var(--t0)",marginBottom:4}}>Tag Library</div>
              <div style={{fontSize:11,color:"var(--t2)",marginBottom:10}}>Tags defined here appear as quick-add options in Your Data tab.</div>
              <TagsEditor/>
            </div>
          </div>}
        </div>
        {(section==="library"&&!isMobile&&(pickedIds.length>0 || selected))&&(
          <div style={{flex:"0 0 30%",minWidth:290,maxWidth:420,flexShrink:0,borderLeft:"1px solid var(--bdr)",overflow:"hidden",height:"100%"}}>
            {pickedIds.length>0 ? (
              <MultiSelectPanel items={selectedItems} removeFolders={removeFolders} setRemoveFolders={setRemoveFolders} ignoreOnRemove={ignoreOnRemove} setIgnoreOnRemove={setIgnoreOnRemove} onRemove={removeSelectedAddons} onCreateProfile={createProfileFromSelection} onAddToExistingCollection={addSelectionToCollection} profiles={profiles} onClearSelection={()=>setPickedIds([])} onBulkUpdate={bulkUpdateSelected} activeCollection={libraryCollectionProfile} onRemoveFromActiveCollection={removeSelectedFromActiveCollection}/>
            ) : selected ? (
              <QuickPanel a={selected} onOpen={(addon)=>{gridScrollRef.current=gridRef.current?gridRef.current.scrollTop:0;selectedIdRef.current=addon.id;setDetail(addon);}} onFav={setFav} onNote={setNoteModal} onLitePopulate={runLitePopulate} onRemoveSingle={removeSingleAddon} onLaunch={launchTool} removeFolders={removeFolders} setRemoveFolders={setRemoveFolders} ignoreOnRemove={ignoreOnRemove} setIgnoreOnRemove={setIgnoreOnRemove} aiPopulateStatus={aiPopulateStatus} collectionMemberships={collectionMembershipsForSelected} onRemoveMembership={removeAddonFromCollection} onToggleEnabled={handleAddonToggleEnabled} onToggleEnabledError={handleAddonToggleError}/>
            ) : null}
          </div>
        )}
      </div>
    </div>
    {selected&&isMobile&&section==="library"&&(
      <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.75)",backdropFilter:"blur(4px)",zIndex:100,display:"flex",alignItems:"flex-end"}} onClick={()=>setSelected(null)}>
        <div onClick={e=>e.stopPropagation()} style={{width:"100%",maxHeight:"88vh",background:"var(--bg1)",borderRadius:"18px 18px 0 0",overflow:"hidden",display:"flex",flexDirection:"column"}}>
          <div style={{textAlign:"center",padding:"10px 0 4px",cursor:"pointer"}} onClick={()=>setSelected(null)}>
            <div style={{width:40,height:4,background:"var(--bdr)",borderRadius:2,margin:"0 auto"}}/>
          </div>
          <div style={{flex:1,overflow:"hidden"}}><QuickPanel a={selected} onOpen={(addon)=>{gridScrollRef.current=gridRef.current?gridRef.current.scrollTop:0;selectedIdRef.current=addon.id;setDetail(addon);}} onFav={setFav} onNote={setNoteModal} onLitePopulate={runLitePopulate} onRemoveSingle={removeSingleAddon} onLaunch={launchTool} removeFolders={removeFolders} setRemoveFolders={setRemoveFolders} ignoreOnRemove={ignoreOnRemove} setIgnoreOnRemove={setIgnoreOnRemove} aiPopulateStatus={aiPopulateStatus} collectionMemberships={collectionMembershipsForSelected} onRemoveMembership={removeAddonFromCollection} onToggleEnabled={handleAddonToggleEnabled} onToggleEnabledError={handleAddonToggleError}/></div>
        </div>
      </div>
    )}
    {notice&&<NotificationOverlay notice={notice} onDismiss={()=>setNotice(null)}/>}
    {helpPanel&&<HelpOverlay help={helpPanel} onDismiss={()=>setHelpPanel(null)}/>}
    {confirmDialog&&<ConfirmOverlay dialog={confirmDialog} onCancel={closeConfirmDialog} onConfirm={confirmDialogProceed}/>}
    {activityState&&<ActivityOverlay state={activityState} onDismiss={()=>setActivityState(null)}/>}    {folderPicker&&<FolderBrowserModal picker={folderPicker} onClose={()=>setFolderPicker(null)} onChoose={(id,value)=>{window.dispatchEvent(new CustomEvent('hangar-path-picked',{detail:{id,value}})); setFolderPicker(null);}}/>}
    {noteModal&&<NotesModal a={noteModal} onSave={saveNotes} onClose={()=>setNoteModal(null)}/>}
  </div>;
}
ReactDOM.createRoot(document.getElementById("root")).render(<App/>);

