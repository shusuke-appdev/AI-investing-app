/* Offline display geometry. No acquisition, scores or financial forecasts. */
const NS='http://www.w3.org/2000/svg',chartObservers=new Set();
function svgNode(tag,attrs={},text){const node=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));if(text!==undefined)node.textContent=String(text);return node;}
const number=(value,digits=2)=>typeof value==='number'&&Number.isFinite(value)?value.toLocaleString('ja-JP',{maximumFractionDigits:digits,minimumFractionDigits:digits}):'未確認';
const pct=value=>Number.isFinite(value)?(value>0?'+':'')+number(value,1)+'%':'未確認';
const dateText=value=>typeof value==='string'&&value?value.slice(0,10).replaceAll('-','/'):'未確認';
function observeChart(holder,draw){let previous=0;const observer=new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(width>0&&Math.abs(width-previous)>.5){previous=width;draw();}});observer.observe(holder);chartObservers.add(observer);}
function lineChart(view){
 const box=el('div','index-plot'),holder=el('div'),tip=el('div','tooltip');tip.setAttribute('role','status');box.append(holder,tip);
 const points=view.points||[],finite=points.flatMap(p=>p.values).filter(Number.isFinite);
 if(points.length<2||!finite.length){holder.append(empty('価格履歴は未取得です。'));return box;}
 function draw(){
  holder.replaceChildren();const W=Math.max(240,Math.round(box.clientWidth||500)),H=232,L=48,R=W-14,B=202;
  const lo=Math.floor((Math.min(...finite)-2)/5)*5,hi=Math.ceil((Math.max(...finite)+2)/5)*5,first=Date.parse(points[0].date),last=Date.parse(points.at(-1).date);
  const x=d=>L+(Date.parse(d)-first)/(last-first||1)*(R-L),y=v=>B-(v-lo)/(hi-lo||1)*178;
  const svg=svgNode('svg',{viewBox:`0 0 ${W} ${H}`,role:'img',tabindex:0,'aria-label':view.singleSeries?'保存された指数推移、期間初日100':'共通観測日でそろえた指数比較、期間初日100'});svg.classList.add('chart');
  for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4,Y=y(v);svg.append(svgNode('line',{x1:L,x2:R,y1:Y,y2:Y,stroke:'var(--line)'}),svgNode('text',{x:L-7,y:Y+4,'text-anchor':'end'},number(v,0)));}
  const ticks=W<380?2:4;for(let i=0;i<=ticks;i++){const d=new Date(first+(last-first)*i/ticks).toISOString().slice(0,7).replace('-','/');svg.append(svgNode('text',{x:L+(R-L)*i/ticks,y:H-6,'text-anchor':i===0?'start':i===ticks?'end':'middle'},d));}
  svg.append(svgNode('line',{x1:L,x2:R,y1:y(100),y2:y(100),stroke:'var(--muted)','stroke-dasharray':'3 4'}));
  view.series.forEach((series,i)=>{let segment=[];const flush=()=>{if(segment.length)svg.append(svgNode('polyline',{points:segment.join(' '),fill:'none',stroke:i?'var(--teal)':'var(--blue)','stroke-width':2.2,'stroke-dasharray':i?'7 3':'none'}));segment=[];};for(const p of points){if(Number.isFinite(p.values[i]))segment.push(`${x(p.date)},${y(p.values[i])}`);else flush();}flush();});
  const cursor=svgNode('line',{y1:24,y2:B,stroke:'var(--muted)',visibility:'hidden'});svg.append(cursor);let index=points.length-1;
  const show=()=>{const p=points[index];tip.textContent=dateText(p.date)+' · '+view.series.map((s,i)=>s.label+' '+number(p.values[i],1)).join(' / ');cursor.setAttribute('x1',x(p.date));cursor.setAttribute('x2',x(p.date));cursor.setAttribute('visibility','visible');};
  svg.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();index=e.key==='Home'?0:e.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,index+(e.key==='ArrowLeft'?-1:1)));show();}};
  svg.onpointermove=e=>{const rect=svg.getBoundingClientRect(),target=first+((e.clientX-rect.left)/rect.width*W-L)/(R-L)*(last-first);index=points.reduce((best,p,i)=>Math.abs(Date.parse(p.date)-target)<Math.abs(Date.parse(points[best].date)-target)?i:best,0);show();};svg.onpointerleave=()=>{cursor.setAttribute('visibility','hidden');tip.textContent='';};holder.append(svg);
 }
 draw();observeChart(box,draw);return box;
}
function signedBar(value,maximum,format=pct){
 const box=el('div','signed-value'),plot=el('span','signed-plot'),zero=el('span','signed-zero');plot.setAttribute('aria-hidden','true');plot.append(zero);
 if(Number.isFinite(value)){const mark=el('span','signed-mark'+(value<0?' negative':''));mark.style.width=(Math.abs(value)/Math.max(1,maximum)*50)+'%';mark.style.left=(value<0?50-Math.abs(value)/Math.max(1,maximum)*50:50)+'%';if(value===0)mark.classList.add('is-zero');plot.append(mark);}
 const label=numericNode(value,'signed-number',format(value));box.append(plot,label);return box;
}
function observationBars(rows,{unit='%',label=r=>r.label,format=pct}={}){
 const box=el('div','observation-bars'),maximum=Math.max(1,...rows.map(r=>Math.abs(r.value)).filter(Number.isFinite));
 for(const r of rows){const row=el('div','observation-bar');row.dataset.observation=r.id||'';const name=el('span','bar-name',label(r));name.append(el('small','',dateText(r.observed_on)));row.append(name,signedBar(r.value,maximum,format));if(r.quality&&r.quality!=='available')row.append(el('span','badge caution',r.quality==='stale'?'前回値':'未取得'));box.append(row);}
 box.append(el('div','axis-note',`← −${number(maximum,1)}　　0　　+${number(maximum,1)} ${unit} →`));return box;
}
function pricePosition(close,low,high){
 const box=el('div','price-position');
 if(![close,low,high].every(Number.isFinite)||high<low){box.append(empty('直近高安のデータは未取得です。'));return box;}
 const minimum=Math.min(low,close),maximum=Math.max(high,close),span=maximum-minimum;
 const track=el('div','price-track'),band=el('span','price-band'),marker=el('span','price-marker');band.style.left=(span?(low-minimum)/span*100:50)+'%';band.style.width=(span?(high-low)/span*100:0)+'%';marker.style.left=(span?(close-minimum)/span*100:50)+'%';track.setAttribute('aria-hidden','true');track.append(band,marker);
 const labels=el('div','range-labels');labels.append(el('span','','安値 '+number(low)),el('strong','','終値 '+number(close)),el('span','','高値 '+number(high)));box.append(track,labels);return box;
}
function valuationRange(cases,quote,currency){
 const values=cases.filter(c=>Number.isFinite(c.value)),points=[...values.map(c=>({label:({bear:'弱気',base:'基本',bull:'強気'})[c.case]||c.case,value:c.value})),...(Number.isFinite(quote?.price)?[{label:'株価',value:quote.price,quote:true}]:[])],box=el('div','valuation-range');
 if(!values.length){box.append(empty('評価値は未算定です。'));return box;}
 const low=Math.min(...points.map(p=>p.value)),high=Math.max(...points.map(p=>p.value)),track=el('div','valuation-track');track.setAttribute('aria-hidden','true');
 const band=el('span','valuation-band');band.style.left=(high===low?50:(Math.min(...values.map(c=>c.value))-low)/(high-low)*90+5)+'%';band.style.width=(high===low?0:(Math.max(...values.map(c=>c.value))-Math.min(...values.map(c=>c.value)))/(high-low)*90)+'%';track.append(band);
 const labels=el('div','case-values');for(const p of points){const mark=el('span','valuation-dot'+(p.quote?' quote-dot':''));mark.style.left=(high===low?50:(p.value-low)/(high-low)*90+5)+'%';track.append(mark);const label=el('div',p.quote?'quote-case':'');label.append(el('span','meta',p.label),el('strong','',number(p.value)),el('small','',currency||'通貨未記録'));labels.append(label);}box.append(track,labels);return box;
}
