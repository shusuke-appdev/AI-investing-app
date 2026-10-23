/* App shell and six purpose-specific views. User strings never enter HTML markup. */
const payload=JSON.parse(document.getElementById('payload').textContent);
const bundles=payload.bundles||[payload.bundle],comparisonCache=new WeakMap();
const state={market:payload.bundle.inputs.market||'US',page:({stock:'stock',screen:'stock',policy:'policy',theme:'theme',diagnostics:'health'})[payload.bundle.workflow]||'overview',period:'6mo',stock:'',query:'',stockTab:'price',returnTo:null,pendingStock:null,dataView:'issues',stockMode:payload.bundle.workflow==='stock'?'saved':'candidates',screenTicker:null};
const marketName=key=>key==='JP'?'日本':'米国';
const reserved=new Set(['market','markets','theme','themes','comparisons','policy','policies','diagnostics']);
function validateSnapshot(b){
 const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
 if(!object(b)||![1,2,3].includes(b.schema_version)||!object(b.inputs)||!['US','JP'].includes(b.inputs.market)||!object(b.sections)||!['run_id','created_at','workflow'].every(k=>typeof b[k]==='string'&&b[k].length))throw Error('schema');
 const objectKeys=new Set(['analysis','ranking','primary_conditions','filings','filing_catalog','filing_valuation','valuation']);
 const arrayKeys=new Set(['data_status','items','candidates','fundamental_pending','sources','claims','annual','series','chart_data','filing_valuations','facts','accounting_reviews','segment_ledgers','reconciliations','derivations','interpretations']);
 function check(v,depth=0){if(depth>40)throw Error('depth');if(Array.isArray(v)){for(const x of v)check(x,depth+1);}else if(object(v)){for(const [k,x] of Object.entries(v)){if(x!=null&&objectKeys.has(k)&&!object(x))throw Error('shape');if(x!=null&&arrayKeys.has(k)&&!Array.isArray(x))throw Error('shape');if(k==='chart_data'&&Array.isArray(x))for(const p of x){if(!object(p))throw Error('point');if(p.name!=null&&(!/^\d{4}-\d{2}-\d{2}$/.test(p.name)||Number.isNaN(Date.parse(p.name))||new Date(p.name).toISOString().slice(0,10)!==p.name))throw Error('date');for(const f of ['price','volume','ma10','ma20','ma50','ma200'])if(p[f]!=null&&(typeof p[f]!=='number'||!Number.isFinite(p[f])))throw Error('value');}check(x,depth+1);}}else if(typeof v==='number'&&!Number.isFinite(v))throw Error('number');}
 for(const [key,packet] of Object.entries(b.sections)){if(!object(packet))throw Error('section');if(['markets','themes','comparisons'].includes(key))for(const market of ['US','JP'])if(packet[market]!=null&&!object(packet[market]))throw Error('market');}
 check(b);validateResearchV3(b);
 function connected(v){if(Array.isArray(v)){v.forEach(connected);return;}if(!object(v))return;if(v.connected!=null){const c=v.connected;if(!object(c)||c.version!=='connected-market-v1'||!Array.isArray(c.observations)||!Array.isArray(c.relations))throw Error('connected shape');const ids=new Set();for(const r of c.observations){if(!object(r)||typeof r.id!=='string'||!r.id||ids.has(r.id)||!['US','JP'].includes(r.market)||!['available','stale','unavailable'].includes(r.quality)||!Array.isArray(r.parents)||!r.parents.length||!r.parents.every(p=>typeof p==='string')||!['unit','window','series_id'].every(k=>typeof r[k]==='string'&&r[k])||r.value!=null&&(typeof r.value!=='number'||!Number.isFinite(r.value))||r.quality==='available'&&(r.value==null||typeof r.source!=='string'||!r.source.startsWith('https://')||!r.observed_on||!r.price_basis||r.period_end!==r.observed_on))throw Error('observation');ids.add(r.id);if(r.observed_on!=null&&(!/^\d{4}-\d{2}-\d{2}$/.test(r.observed_on)||new Date(r.observed_on).toISOString().slice(0,10)!==r.observed_on))throw Error('observation date');}for(const r of c.relations)if(!object(r)||!(r.kind in RELATION_LABELS)||['supports','weakens','different_horizon'].includes(r.kind)&&(!ids.has(r.from)||!ids.has(r.to)))throw Error('relation');}Object.values(v).forEach(connected);}connected(b);
 function refs(ids,sources,ticker){if(!Array.isArray(ids)||ids.some(id=>typeof id!=='string'||!sources.has(id)||sources.get(id).ticker!==ticker||sources.get(id).review!=='opened_and_checked'||sources.get(id).kind!=='primary'))throw Error('unreviewed source');}
 function financial(f,ticker){
  if(!object(f)||f.financial_history!=null&&!object(f.financial_history))throw Error('financial shape');
  const sources=new Map((f.sources||[]).map(s=>[s.id,s]));if(sources.size!==(f.sources||[]).length)throw Error('duplicate source');
  const numeric=v=>typeof v==='number'&&Number.isFinite(v);
  const tolerance=v=>{if(v==null)return 0;if(!numeric(v)||v<0)throw Error('tolerance');return v;};
  const quantity=(q,unit)=>{if(!object(q)||!numeric(q.value)||q.unit!==unit||!/^\d{4}-\d{2}-\d{2}$/.test(q.period_end))throw Error('quantity');refs(q.source_ids,sources,ticker);};
  const iso=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
  const factors={currency:1,thousand:1000,million:1000000,shares:1,thousand_shares:1000,million_shares:1000000,ratio:1,percent:.01};
  const flows=new Set(['revenue','operating_income','net_income','operating_cashflow','capex','fcff','ffo','affo','core_ffo','modified_ffo','depreciation','interest_paid','income_tax','working_capital_change','distributions','real_estate_gains','wc_receivables','wc_vendor_receivables','wc_inventory','wc_payables','corporate_operating_cost','core_ffo_unit_adjustment']);
  for(const fact of f.financial_history?.facts||[]){
   refs(fact.source_ids,sources,ticker);if(!numeric(fact.value)||!(fact.unit in factors)||!iso(fact.period_end)||!numeric(fact.value*factors[fact.unit]))throw Error('financial fact');
   if(flows.has(fact.metric)){
    if(!iso(fact.period_start))throw Error('flow period');const span=(Date.parse(fact.period_end)-Date.parse(fact.period_start))/86400000;
    if(!['annual','interim','fiscal_half','ttm'].includes(fact.period_type)||['annual','ttm'].includes(fact.period_type)&&(span<330||span>380)||fact.period_type==='fiscal_half'&&(span<150||span>200)||fact.period_type==='interim'&&(span<1||span>=330))throw Error('flow span');
    if(fact.period_type==='ttm'){
     if(!Array.isArray(fact.components)||fact.components.length<2)throw Error('ttm components');const parts=[...fact.components].sort((a,b)=>String(a.period_start).localeCompare(String(b.period_start)));let total=0;
     for(const [index,part] of parts.entries()){refs(part.source_ids,sources,ticker);if(!iso(part.period_start)||!iso(part.period_end)||!numeric(part.base_value)||Date.parse(part.period_start)>=Date.parse(part.period_end)||index&&Date.parse(parts[index-1].period_end)+86400000!==Date.parse(part.period_start))throw Error('ttm bounds');const original=f.financial_history.facts.find(o=>o.metric===fact.metric&&o.period_type!=='ttm'&&o.period_start===part.period_start&&o.period_end===part.period_end&&Math.abs(o.value*factors[o.unit]-part.base_value)<=Math.max(1e-6,Math.abs(part.base_value)*1e-9)&&part.source_ids.every(id=>o.source_ids.includes(id)));if(!original)throw Error('ttm original');total+=part.base_value;}
     if(parts[0].period_start!==fact.period_start||parts.at(-1).period_end!==fact.period_end||Math.abs(total-fact.value*factors[fact.unit])>Math.max(1e-6,Math.abs(total)*1e-9))throw Error('ttm sum');
    }
   }
  }
  for(const ledger of f.segment_ledgers||[]){
   refs(ledger.source_ids,sources,ticker);
   if(!Array.isArray(ledger.records)||!Array.isArray(ledger.reported_segments)||new Set(ledger.reported_segments).size!==ledger.reported_segments.length||ledger.records.length!==ledger.reported_segments.length||new Set(ledger.records.map(r=>r.name)).size!==ledger.records.length||ledger.records.some(r=>!ledger.reported_segments.includes(r.name)))throw Error('segments');
   for(const q of [...ledger.records.map(r=>r.quantity),ledger.elimination,ledger.consolidated_total]){quantity(q,'currency');if(q.period_end!==ledger.period_end||q.period_start!==ledger.period_start)throw Error('segment period');}
   if(new Set(ledger.records.map(r=>r.metric_name)).size!==1)throw Error('segment metric');
   const total=ledger.records.reduce((sum,r)=>sum+r.quantity.value,0)+ledger.elimination.value;if(!Number.isFinite(total)||Math.abs(total-ledger.consolidated_total.value)>Math.max(tolerance(ledger.rounding_tolerance),Math.abs(total)*1e-9))throw Error('segment total');
  }
  for(const review of f.accounting_reviews||[]){
   if(review.ticker!==ticker)throw Error('review issuer');
   if(review.amendments_status==='checked'&&!(review.amendment_source_ids||[]).length)throw Error('amendment source');refs(review.amendment_source_ids||[],sources,ticker);
   for(const item of review.items||[])refs(item.source_ids,sources,ticker);
   for(const r of review.reconciliations||[]){refs(r.source_ids,sources,ticker);if(!object(r.terms)||Object.values(r.terms).some(v=>!numeric(v))||!numeric(r.result)||Math.abs(Object.values(r.terms).reduce((a,v)=>a+v,0)-r.result)>Math.max(tolerance(r.rounding_tolerance),Math.abs(r.result)*1e-9))throw Error('adjustments');}
  }
  for(const d of f.derivations||[]){quantity(d.output,'currency');if(!Array.isArray(d.terms)||!d.terms.length)throw Error('derivation');for(const term of d.terms){quantity(term.quantity,'currency');if(!numeric(term.coefficient))throw Error('coefficient');}const total=d.terms.reduce((sum,t)=>sum+t.quantity.value*t.coefficient,0);if(!Number.isFinite(total)||Math.abs(total-d.output.value)>Math.max(1e-6,Math.abs(total)*1e-9))throw Error('derivation sum');}
  return quantity;
 }
 for(const [ticker,packet] of Object.entries(b.sections))if(!reserved.has(ticker)&&packet.filings){const quantity=financial(packet.filings,ticker);const identities=new Set();for(const r of packet.filing_valuations||[]){if(!object(r)||r.inputs!=null&&!object(r.inputs))throw Error('valuation shape');if(!r.inputs)continue;if(r.inputs.ticker!==ticker||!['fcff_dcf','sotp','residual_income','reit_multiple'].includes(r.method)||r.method!==r.inputs.method)throw Error('valuation issuer/method');for(const key of ['cash','debt','shares','fcff','book_equity','reit_cashflow','corporate_adjustment','noncontrolling_interest','nonoperating_assets'])if(r.inputs[key]!=null)quantity(r.inputs[key],key==='shares'?'shares':'currency');for(const c of r.cases||[])if(!object(c)||typeof c.value!=='number'||!Number.isFinite(c.value))throw Error('valuation case');const id=[ticker,r.method,r.inputs.shares?.period_end,r.method==='reit_multiple'?r.inputs.reit_metric:''].join('|');if(identities.has(id))throw Error('duplicate valuation');identities.add(id);}}
}
function el(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=String(text);return node;}
function textValue(value){if(value===null||value===undefined||value==='')return '未確認';if(typeof value==='number')return number(value,Number.isInteger(value)?0:2);if(typeof value==='boolean')return value?'あり':'なし';return String(value);}
function empty(message,command){const box=el('div','empty',message);if(command)box.append(el('code','',command));return box;}
function hasValue(value){return value!=null&&value!==''&&(typeof value!=='object'||Object.keys(value).length>0);}
function panel(title,meta='',market=''){const box=el('section','panel'),head=el('div','panelhead'),heading=el('h2','',title);if(market)heading.append(el('span','marketlabel',`（${market}）`));head.append(heading);if(meta)head.append(el('span','meta',meta));box.append(head);return box;}
function list(values,cls=''){const ul=el('ul',cls);for(const value of values||[])ul.append(el('li','',textValue(value)));return ul;}
function safeLink(url,title){try{const u=new URL(url);if(u.protocol==='https:'&&!u.username&&!u.password&&!/token|secret|api.?key|signature/i.test(u.search)){const a=el('a','',title||url);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}}catch{}return el('span','missing',title||'リンク未確認');}
function table(headers,rows,{sortable=false,compact=false}={}){
 const wrap=el('div','table-wrap'),t=el('table',compact?'compact':''),head=el('thead'),body=el('tbody'),tr=el('tr');let ordered=[...rows],sortColumn=-1,ascending=true;
 const draw=()=>{body.replaceChildren();for(const row of ordered){const r=el('tr');row.forEach((value,i)=>{const cell=el('td',headers[i]?.numeric?'num':'');if(value instanceof Node)cell.append(value);else cell.textContent=textValue(value);r.append(cell);});body.append(r);}};
 headers.forEach((header,i)=>{const th=el('th',header.numeric?'num':'');th.scope='col';if(sortable){const b=el('button','headbutton',header.label+' ↕');b.onclick=()=>{ascending=sortColumn===i?!ascending:true;sortColumn=i;ordered.sort((a,b)=>{const A=sortValue(a[i],header.numeric),B=sortValue(b[i],header.numeric);if(A==null)return B==null?0:1;if(B==null)return -1;return(typeof A==='number'&&typeof B==='number'?A-B:String(A).localeCompare(String(B),'ja',{numeric:true}))*(ascending?1:-1);});for(const c of tr.children)c.removeAttribute('aria-sort');th.setAttribute('aria-sort',ascending?'ascending':'descending');draw();};th.append(b);}else th.textContent=header.label;tr.append(th);});
 head.append(tr);t.append(head,body);wrap.append(t);draw();return wrap;
}
const H=(label,numeric=false)=>({label,numeric});
function numericNode(value,cls,text){const node=el('span',cls,text);node.dataset.sortValue=Number.isFinite(value)?String(value):'';return node;}
function percentNode(value){return numericNode(value,Number.isFinite(value)?value>=0?'pos':'neg':'missing',pct(value));}
function rankNode(value){return numericNode(value,'rank'+(value===1?' first':value===3?' third':''),value??'—');}
function sortValue(cell,numeric){if(cell instanceof Node){if('sortValue' in cell.dataset)return cell.dataset.sortValue===''?null:Number(cell.dataset.sortValue);cell=cell.textContent;}if(cell==null||cell==='未確認'||cell==='—')return null;if(numeric){const n=Number(String(cell).replace(/[%+,]/g,''));return Number.isFinite(n)?n:null;}return cell;}
function latestPacket(section,market=state.market){const plural=section==='policy'?'policies':section+'s';for(const bundle of [...bundles].reverse()){if(bundle.sections[plural]?.[market])return bundle.sections[plural][market];if(bundle.inputs.market===market&&bundle.sections[section])return bundle.sections[section];}return {};}
function marketAnalysis(){return latestPacket('market').analysis||{};}
function themePacket(){const packet=latestPacket('theme');return packet.ranking?packet:{ranking:marketAnalysis().trend_ranking||{}};}
function stocks(){const map=new Map();for(const bundle of bundles)for(const [ticker,packet] of Object.entries(bundle.sections)){if(!reserved.has(ticker))map.set(ticker,{...packet,market:['US','JP'].includes(packet.market)?packet.market:ticker.endsWith('.T')?'JP':bundle.inputs.market,run_id:bundle.run_id});}return [...map.entries()];}
function observationDates(row){const dates=row.observation_dates||[];return dates.length?dates.length===1?dateText(dates[0]):dateText(dates[0])+'–'+dateText(dates.at(-1)):'未確認';}
function subtractMonths(date,months){const d=new Date(date+'T00:00:00Z'),day=d.getUTCDate();d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()-months);const last=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,0)).getUTCDate();d.setUTCDate(Math.min(day,last));return d.toISOString().slice(0,10);}
function alignComparison(series,period){
 const iso=d=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(d).toISOString().slice(0,10)===d;
 const records=(series||[]).map(s=>({series:s,map:new Map((s.points||[]).filter(p=>iso(p.date)&&Number.isFinite(p.price)&&p.price>0).map(p=>[p.date,p.price]))}));
 const valid=records.filter(r=>r.map.size>=2),missing=records.filter(r=>r.map.size<2).map(r=>r.series.label);
 if(!valid.length)return {status:'unavailable',points:[],series:[],missing};
 const single=valid.length===1,maps=valid.map(r=>r.map),shared=[...maps[0].keys()].filter(d=>maps.every(m=>m.has(d))).sort();
 if(shared.length<2)return {status:'insufficient_data',points:[],series:valid.map(r=>r.series),missing};
 const cutoff=subtractMonths(shared.at(-1),{'1mo':1,'3mo':3,'6mo':6,'1y':12,'2y':24}[period]),dates=shared.filter(d=>d>=cutoff);
 if(dates.length<2)return {status:'insufficient_data',points:[],series:valid.map(r=>r.series),missing};
 const base=maps.map(m=>m.get(dates[0])),short=Date.parse(shared[0])-Date.parse(cutoff)>7*86400000;
 return {status:single||short?'partial':'available',singleSeries:single,short,missing,period,start:dates[0],end:dates.at(-1),series:valid.map((r,i)=>({...r.series,latest:r.map.get(dates.at(-1)),return_pct:(r.map.get(dates.at(-1))/base[i]-1)*100})),points:dates.map(date=>({date,values:maps.map((m,i)=>m.get(date)/base[i]*100)}))};
}
function comparison(market){for(const bundle of [...bundles].reverse()){const raw=bundle.sections.comparisons?.[market];if(raw){let cache=comparisonCache.get(bundle);if(!cache){cache={};comparisonCache.set(bundle,cache);}cache[market]??={};cache[market][state.period]??=alignComparison(raw.series,state.period);return cache[market][state.period];}}return {status:'unavailable',points:[],series:[]};}
function comparisonPanel(market){
 const view=comparison(market),box=panel(market==='US'?'米国株指数':'日本株指数',dateText(view.end)),quotes=el('div','index-quotes');box.dataset.comparison=market;
 for(const [i,series] of (view.series||[]).entries()){const quote=el('div','index-quote series-'+i);quote.append(el('span','quote-name',series.label),el('strong','',pct(series.return_pct)),el('small','',number(series.latest)));quotes.append(quote);}box.append(quotes,lineChart(view));
 const foot=el('div','chart-foot');foot.append(el('span','meta','開始＝100 · '+dateText(view.start)+'–'+dateText(view.end)));
 if(view.singleSeries)foot.append(el('span','badge caution',(view.missing||[]).join('・')+' 未取得'));
 if(view.short)foot.append(el('span','badge caution','履歴不足'));
 if((view.series||[]).some(s=>s.is_stale||s.observed_at&&Date.now()-Date.parse(s.observed_at)>7*86400000))foot.append(el('span','badge caution','前回値'));
 foot.append(nearbyDetail({series:view.series,missing:view.missing,period:view.period,start:view.start,end:view.end},'出典・価格基準'));box.append(foot);return box;
}
function periodControls(){const [box,select]=selectControl('period','指数期間',[['1mo','1か月'],['3mo','3か月'],['6mo','6か月'],['1y','1年'],['2y','2年']]);select.value=state.period;select.onchange=()=>{state.period=select.value;render();};return box;}
function pageHeading(title,controls){const head=el('div','page-heading');head.append(el('h2','page-title',title));if(controls)head.append(controls);return head;}
function dataState(row){
 const explicit=String(row.status||'').toLowerCase();
 if(['available','ok','success','complete'].includes(explicit))return row.is_stale?'stale':row.is_partial?'partial':'available';
 if(['stale','unavailable','partial','failed','error','insufficient_data','research_only'].includes(explicit))return explicit;
 return row.is_stale?'stale':row.is_partial?'partial':row.error?'unavailable':'available';
}
const DATA_LABELS={available:'取得済み',stale:'前回値',partial:'一部未取得',unavailable:'未取得',failed:'取得失敗',error:'取得失敗',insufficient_data:'履歴不足',research_only:'参考専用'};
function statusBadge(status){return el('span','badge '+(status==='available'?'':'caution'),DATA_LABELS[status]||status||'未確認');}
function datum(row){const box=el('span');box.append(document.createTextNode(Number.isFinite(row?.value)?number(row.value,2)+' '+(row.unit||''):'未取得'));if(row?.quality==='stale')box.append(statusBadge('stale'));return box;}
function snapshotRows(){const rows=[...(marketAnalysis().data_status||[]).map(r=>({...r,scope:state.market}))];for(const [ticker,packet] of stocks())for(const r of packet.analysis?.data_status||[])rows.push({...r,name:ticker+' / '+r.name,scope:ticker});return rows;}
function dataIssues(rows=snapshotRows()){
 const grouped=new Map();for(const r of rows){const status=dataState(r);if(status==='available')continue;const name=['US','JP'].includes(r.scope)?(r.name||'入力').split(' / ')[0]:r.name||'入力',key=[r.scope,name,r.source,status,r.observed_on,r.error].join('|');if(!grouped.has(key))grouped.set(key,{...r,name,status,count:0});grouped.get(key).count++;}return [...grouped.values()];
}
function observationSummary(c){
 const rows=c?.observations||[],get=id=>rows.find(r=>r.id===id),usable=r=>r?.quality==='available'&&Number.isFinite(r.value),ma=get('index:ma200_gap'),small=get('participation:iwm'),equal=get('participation:rsp');
 if(usable(ma)){const base='指数は200日線の'+(ma.value>=0?'上':'下')+'（'+pct(ma.value)+'）';const other=usable(small)?small:usable(equal)?equal:null;if(other&&other.observed_on===ma.observed_on)return base+'。'+(other.id.endsWith('iwm')?'小型株':'等加重')+'は市場に対し'+(other.value>=0?'優位':'劣後')+'（'+pct(other.value)+'）。';return base+'。';}
 return '市場の位置を確認できる価格入力が不足しています。';
}
function marketSummaryPanel(){
 const c=marketAnalysis().connected,rows=c?.observations||[],box=panel('市場の位置',marketName(state.market)),grid=el('div','metric-grid');
 for(const [id,label] of [['index:return_6m','6か月 / 126営業日'],['index:ma200_gap','200日線から'],['index:ma20_gap','20日線から'],['participation:sample','登録銘柄・200日線上'],['credit:level','米HY OAS'],['vix:level','米VIX']]){const r=rows.find(r=>r.id===id),cell=el('div','metric');cell.append(el('span','meta',label),el('strong','',Number.isFinite(displayObservation(r||{}).value)?number(r.value,1)+' '+(r.unit==='volatility points'?'pt':r.unit):'未取得'));if(r?.quality==='stale')cell.append(statusBadge('stale'));grid.append(cell);}
 if(c)box.append(grid,el('p','insight',observationSummary(c)));else box.append(table([H('項目'),H('状態'),H('観測')],environment(),{compact:true}));
 const links=el('div','market-links');for(const [page,label] of [['market','市場を詳しく'],['theme','テーマを比較'],['policy','確認事項']]){const b=el('button','text-button',label+' →');b.onclick=()=>openResearchPage(page);links.append(b);}box.append(links);return box;
}
function environment(){
 if(marketAnalysis().connected){const c=marketAnalysis().connected,rows=c.observations||[];return [['index:ma200_gap','中期 / 200日線乖離'],['index:ma20_gap','短期 / 20日線乖離'],['vix:level','米国ボラ / VIX'],['credit:level','米国信用 / HY OAS']].map(([id,label])=>{const r=rows.find(r=>r.id===id)||{};return [label,number(r.value)+' '+(r.unit||''),(r.observed_on||'未取得')+' / '+(r.quality||'unavailable')];});}
 const m=marketAnalysis(),evaln=m.evaluation||{},vol=m.volatility_regime||{},credit=m.credit_stress||{},trend=m.market_timeframes?.items?.find(i=>i.key==='current')||{};
 return [
 ['トレンド',trend.direction_label||evaln.status||'未確認',evaln.description||trend.evidence?.[0]||'市場環境は未取得'],
 ['ボラティリティ',vol.label||'未確認',vol.summary||'ボラ指標は未取得'],
 [state.market==='JP'?'米国信用（外部環境）':'クレジット',credit.status_label||'未確認',credit.summary||'信用指標は未取得'],
 ['リサーチ環境',m.is_stale?'古い入力':m.is_partial?'一部未確認':m.market_data&&Object.keys(m.market_data).length?'取得済み':'未確認',(m.quality_warnings||[]).length?'一部分析で取得不足。詳細はデータ状況へ。':'個別指標の基準日・取得状態を併記'],
 ];
}
function themeTable(rows,{compact=false,sortable=false}={}){return table([H('順位'),H('テーマ名'),H('1週',true),H('1か月',true),H('6か月',true),H('取得率',true),H('観測日')],rows.map(r=>[rankNode(r.rank),r.theme,percentNode(r.performance_1w),percentNode(r.performance_1m),percentNode(r.performance_6m),Number.isFinite(r.coverage_1m)?number(r.coverage_1m*(r.period_status?1:100),0)+'%':null,observationDates(r)]),{compact,sortable});}
function structureRows(){if(marketAnalysis().connected)return marketAnalysis().connected.observations.filter(r=>r.id.startsWith('participation:')).map(r=>[r.label,r.value,r.unit+' / '+r.window,(r.observed_on||'未取得')+' / '+r.quality]);const m=marketAnalysis(),micro=m.microstructure||{},leaders=m.flow_monitor?.leaders||[];return [
 ['IBD市場状態（代理）',m.ibd_regime?.label||null,null,m.ibd_regime?.rationale||'未確認'],
 ['流動性枯渇比（代理）',micro.liquidity?.liquidity_dryup_ratio??null,null,micro.liquidity?.status||'未確認'],
 ...leaders.slice(0,2).map(r=>[r.label||r.ticker,r.relative_return_20d??null,'20営業日・市場相対 %', 'ETF価格／出来高の代理、純資金流入額ではありません']),
 ];}
function riskRows(){if(marketAnalysis().connected)return marketAnalysis().connected.observations.filter(r=>['vix:level','credit:level','DGS10:level','JP10:level'].includes(r.id)).map(r=>[r.label+' '+r.unit,r.value,r.observed_on||'未取得',r.source+' / '+r.quality]);const m=marketAnalysis(),credit=m.credit_stress||{};return [
 ['VIX（米国）',m.volatility_regime?.metrics?.vix??null,null,m.volatility_regime?.source||'未確認'],
 ...(credit.indicators||[]).slice(0,2).map(r=>[r.label,r.latest??null,r.latest_date?dateText(r.latest_date):null,r.warning||credit.source||'未確認']),
 ];}
function overview(){
 const root=el('div','overview'),charts=el('div','grid two');root.append(pageHeading('市場から調査対象を絞る',periodControls()));charts.append(comparisonPanel('US'),comparisonPanel('JP'));root.append(charts);
 const bottom=el('div','overview-bottom');bottom.append(marketSummaryPanel(),themePreviewPanel());root.append(bottom);return root;
}
const LABELS={status:'取得・判定状態',summary:'要約',label:'項目',name:'名称',ticker:'銘柄',market:'市場',source:'出典',fetched_at:'取得日時',as_of:'観測日',observed_at:'観測日',data_as_of:'データ基準日',published_on:'公開日',accessed_on:'確認日',date:'観測日',latest_date:'観測日',period:'期間',currency:'通貨',unit:'単位',value:'値',latest:'直近値',price:'価格',current_price:'株価',close:'終値',change:'変化',change_1d:'前日比 %',delta_3m:'3か月変化',score:'既存参考点',weight:'重み',rationale:'根拠',reason:'理由',warning:'注意',warnings:'注意事項',quality_warnings:'取得・品質の注意',is_stale:'古いキャッシュ',is_partial:'一部取得不足',status_label:'状態',status_key:'状態コード',invalidation:'無効化条件',evidence:'根拠',source_ids:'参照資料ID',conditions:'条件',metrics:'指標',items:'項目',confidence:'確度',coverage:'取得率',method:'算出方法',limitations:'限界',assumptions:'仮定',inputs:'計算入力',risk_budget:'研究上の配分参考',signals:'シグナル',description:'説明',support:'支持条件',counterevidence:'反証',support_price:'支持価格',resistance_price:'抵抗価格',ma20:'20日平均',ma50:'50日平均',ma200:'200日平均',volume:'出来高',relative_return_20d:'20日市場相対 %',relative_return_60d:'60日市場相対 %',flow_pressure_z:'価格出来高の注目度 z',performance_1w:'1週リターン %',performance_1m:'1か月リターン %',performance_6m:'6か月リターン %',total_score:'総合テーマ点',rank:'順位',theme:'テーマ',data_quality:'データ状態',status_label:'状態',per_share:'1株価値',equity_value:'株式価値',enterprise_value:'事業価値',cases:'評価シナリオ',case:'シナリオ',growth:'成長率',wacc:'割引率',terminal_growth:'永久成長率',readiness:'用途',net_debt:'純有利子負債',shares:'株式数',cash:'現金',debt:'負債',segments:'セグメント',metric:'算定指標',multiple:'倍率',metric_name:'指標名',multiple_rationale:'倍率の根拠',market_type:'対象市場',source_type:'直接／代理区分',level:'警戒段階',verification:'確認の位置づけ',claims:'資料による観測',missing:'不足情報',sources:'一次資料・出典',verification_status:'確認状態',growth_rate:'成長率仮定',period_end:'期間末',period_start:'期間初',corporate_adjustment:'本社調整',fcff:'企業フリーキャッシュフロー',title:'資料名',publisher:'発行者',locator:'ページ・箇所',excerpt:'確認した短い抜粋',review:'確認状態',kind:'資料区分',text:'観測・説明',category:'区分'};
const labelFor=key=>LABELS[key]||payload.market_features[key]||payload.stock_features[key]||key;
function reference(value,depth=0){
 if(value==null||typeof value!=='object')return el('p',value==null?'missing':'',textValue(value));
 if(Array.isArray(value)){
  if(!value.length)return el('p','missing','対象なし／入力なし');
  if(value.every(v=>v==null||typeof v!=='object'))return list(value);
  if(value.every(v=>v&&typeof v==='object'&&!Array.isArray(v))){const keys=[...new Set(value.flatMap(v=>Object.keys(v)))].filter(k=>value.some(v=>v[k]==null||typeof v[k]!=='object'));const box=el('div');if(keys.length)box.append(table(keys.map(k=>H(labelFor(k),value.some(v=>typeof v[k]==='number')&&value.every(v=>v[k]==null||typeof v[k]==='number'))),value.map(v=>keys.map(k=>v[k]==null||typeof v[k]!=='object'?v[k]:'詳細')), {sortable:true,compact:true}));value.forEach((v,i)=>{const nested=Object.entries(v).filter(([k,item])=>item&&typeof item==='object');if(nested.length){const d=el('details','feature'),s=el('summary','',textValue(v.label||v.name||v.ticker||v.theme||v.case||`項目 ${i+1}`)+' · 詳細'),body=el('div','feature-body');for(const [key,item] of nested){body.append(el('h3','',labelFor(key)),reference(item,depth+1));}d.append(s,body);box.append(d);}});return box;}
  const box=el('div');value.forEach(v=>box.append(reference(v,depth+1)));return box;
 }
 const box=el('div'),scalars=Object.entries(value).filter(([,v])=>v==null||typeof v!=='object'),nested=Object.entries(value).filter(([,v])=>v&&typeof v==='object');
 if(scalars.length)box.append(table([H('項目'),H('観測・値')],scalars.map(([key,v])=>[labelFor(key),key==='url'?safeLink(v,'原資料を開く'):textValue(v)]),{compact:true}));
 const grid=el('div',depth<1?'reference-grid':'');for(const [key,v] of nested){const block=el('div','reference-block');block.append(el('h3','',labelFor(key)),reference(v,depth+1));grid.append(block);}box.append(grid);return box;
}
function featureDetails(analysis,catalog){const box=el('div');for(const [key,label] of Object.entries(catalog)){const d=el('details','feature'),s=el('summary','',label),body=el('div','feature-body');d.dataset.feature=key;const value=analysis[key];body.append(hasValue(value)?reference(value):empty('未取得・未対応・条件不成立のいずれかです。データ状況で取得状態を確認してください。'));if(key==='fomo_scan')body.append(el('p','meta','明示した米国ユニバースのみ：scripts/research.py market --market US --scan-fomo'));d.append(s,body);box.append(d);}return box;}
function marketPage(){return connectedMarketPage();}

function sourcePanel(filings){const box=panel('一次資料・事業見通し・カタリスト・リスク'),sources=filings.sources||[];if(!sources.length){box.append(empty('一次資料は未確認。推測による企業ストーリーは表示しません。'));return box;}const ul=el('ul','source-list');for(const s of sources){const li=el('li');li.append(safeLink(s.url,s.title),el('p','meta',`${s.publisher} · 公開 ${dateText(s.published_on)} · 確認 ${dateText(s.accessed_on)} · ${s.locator} · ${s.review}`),el('p','',s.excerpt));ul.append(li);}box.append(ul);for(const category of ['financial','segment','guidance','catalyst','risk','outlook']){const claims=(filings.claims||[]).filter(c=>c.category===category);if(claims.length)box.append(el('h3','',({financial:'財務',segment:'事業別',guidance:'会社見通し',catalyst:'変化のきっかけ',risk:'リスク・反証',outlook:'見通し'})[category]),reference(claims));}if(filings.financial_history)box.append(el('h3','','3年・最新中間の取得状態'),reference(filings.financial_history));if(filings.missing?.length)box.append(list(filings.missing,'warning-list'));return box;}

function policyPage(){const root=el('div','narrative'),p=latestPacket('policy');root.append(el('h2','page-title','方針 / 条件付きリサーチ'));if(!p.observations){root.append(empty('方針の根拠が未取得です。市場・テーマと最大5候補の主条件を同じ保存結果にまとめます。',`scripts/research.py policy --market ${state.market}`));if(p.synthesis)root.append(el('p','meta','旧版の記述は根拠との接続が未完成です。policyを再実行してください。'));return root;}const posture=panel(p.stance,'research_only');posture.append(el('p','',p.stance_reason),table([H('観測'),H('内容'),H('入力参照')],p.observations.map(r=>[r.label,r.observation,r.input_path])),el('h3','','反証・不足'),list(p.counterevidence),list(p.missing,'warning-list'),el('h3','','市場の無効化条件'),el('p','',p.invalidation));root.append(posture);for(const s of p.stocks||[]){const box=panel(s.ticker,'研究候補・注文指示ではありません');box.append(el('h3','','成立条件'),reference(s.support),el('h3','','未成立・反証'),reference(s.counterevidence),el('h3','','一次資料の観測'),reference(s.filing_observations),el('h3','','一次資料の反証'),reference(s.filing_risks),el('h3','','未確認'),reference(s.unconfirmed),list(s.next_checks,'warning-list'),el('h3','','無効化'),el('p','',s.invalidation),el('h3','','条件付きの次の確認'),list(s.conditional_checks));root.append(box);}root.append(el('h3','','次の確認'),list(p.next_checks));return root;}
function healthPage(){
 const root=el('div','data-page'),rows=snapshotRows(),issues=dataIssues(rows);root.append(pageHeading('データ'));
 const [control,select]=selectControl('data-view','表示範囲',[['issues','問題のある入力'],['all','すべての入力']]);select.value=state.dataView;select.onchange=()=>{state.dataView=select.value;render();};root.append(control);
 const health=panel(state.dataView==='all'?'すべての取得記録':'確認が必要な入力',state.dataView==='all'?rows.length+'件':issues.length+'件');
 if(state.dataView==='all')health.append(rows.length?table([H('入力'),H('状態'),H('観測日'),H('取得日時'),H('出典・補足')],rows.map(r=>[r.name,statusBadge(dataState(r)),dateText(r.observed_on),r.fetched_at,nearbyDetail(r,'記録を開く')]),{sortable:true}):empty('取得記録はありません。'));
 else health.append(issues.length?table([H('入力'),H('状態'),H('観測日'),H('原因')],issues.map(r=>[r.name+(r.count>1?' / '+r.count+'項目':''),statusBadge(r.status),dateText(r.observed_on),r.error||r.reason||'取得状態の記録を確認してください。'])):el('p','insight','記録された入力に取得上の問題はありません。'));root.append(health);
 const load=panel('保存結果を開く'),input=el('input'),label=el('label','','research.json（複数選択可）'),status=el('p','meta');input.type='file';input.id='load-snapshot';input.accept='.json,application/json';input.multiple=true;label.htmlFor=input.id;status.setAttribute('role','status');
 input.onchange=async()=>{const pending=[];for(const file of input.files){try{if(file.size>20*1024*1024)throw Error('size');const b=JSON.parse(await file.text());validateSnapshot(b);pending.push(b);}catch{status.textContent='保存形式が不正、または20MBを超えています。';return;}}if(!pending.length)return;bundles.push(...pending);state.page='overview';state.returnTo=null;render();window.scrollTo(0,0);document.getElementById('content').prepend(el('p','meta',pending.length+'件の保存結果を追加しました。'));};load.append(label,input,status);root.append(load);
 const help=el('details','feature'),body=el('div','feature-body');help.append(el('summary','','使い方・算定期間・保存結果の記録'),body);body.append(el('p','','市場→テーマ→銘柄の順で、価格位置と相対成績から調査対象を絞ります。個別銘柄の深掘りはCodexで銘柄名を指定してください。'),el('p','','指数期間は暦月、標準テーマは1週5・1か月21・6か月126営業日。テーマの強弱は構成銘柄中央値と市場とのポイント差です。'),el('p','','画面は保存入力による調査用です。売買指示ではありません。欠損は補完せず、個別株・資料・評価はそれぞれの観測日を使用します。'),table([H('処理'),H('保存日時'),H('実行ID')],bundles.map(b=>[b.workflow,b.created_at,b.run_id])));
 for(const warning of new Set(bundles.flatMap(b=>b.warnings||[])))body.append(el('p','meta',warning));root.append(help);
 const diagnostic=nearbyDetail({diagnostics:latestPacket('diagnostics'),diagnostic:latestPacket('diagnostic'),bundles},'診断・全保存入力');root.append(diagnostic);return root;
}
const paths={overview:'M3 10 12 3l9 7v11h-6v-7H9v7H3z',market:'M3 20h18M5 16l4-7 5 3 5-8M17 4h3v3',theme:'M4 5h5l3 3 3-3h5v14H4zM8 12h8M8 15h5',stock:'M3 4h18v16H3zM7 15v-3M12 15V8M17 15v-5',policy:'M6 5h12v16H6zM9 5V3h6v2M9 10h6M9 14h4',health:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 8v5M12 16h.01'};
function connectedPolicyPage(){
 const c=marketAnalysis().connected,root=el('div');root.append(pageHeading('確認事項 / '+marketName(state.market)));
 if(c){const relevant=(c.relations||[]).filter(r=>['weakens','incomparable'].includes(r.kind));const checks=panel('食い違い・不足と次の確認');checks.append(relevant.length?table([H('対象'),H('現在の観測'),H('次に確認すること')],relevant.map(r=>{const link=el('button','text-button',r.id+' →');link.onclick=()=>openResearchPage('market');return [link,relationCaption(r,c),r.next_check];})):el('p','insight','保存された接続分析に、食い違い・比較不能の記録はありません。'));root.append(checks);
 const p=latestPacket('policy');for(const stock of p.stocks||[]){const box=panel(stock.ticker);box.append(stockJump(stock.ticker),table([H('未成立条件'),H('値')],(stock.counterevidence||[]).map(r=>[r.label,r.value])),list(stock.next_checks||[]),nearbyDetail(stock,'条件・一次資料・反証の詳細'));root.append(box);}const details=el('details','feature');details.append(el('summary','','すべての接続と根拠'),connectionPanel(c));root.append(details);}
 else root.append(el('p','badge caution','旧方式の保存結果'),nearbyDetail(latestPacket('policy'),'保存された方針・反証・確認事項'));return root;
}
const pages={overview:['総覧',researchOverview],market:['市場',researchMarketPage],theme:['業種・テーマ',researchThemePage],stock:['銘柄',researchStockPage],policy:['確認事項',researchPolicyPage],health:['データ',researchHealthPage]};
const nav=document.getElementById('navigation');
for(const [key,[title]] of Object.entries(pages)){const button=el('button'),svg=svgNode('svg',{viewBox:'0 0 24 24','aria-hidden':'true'});svg.append(svgNode('path',{d:paths[key]}));button.dataset.page=key;if(['policy','health'].includes(key))button.classList.add('utility-nav');button.append(svg,el('span','',title));button.onclick=()=>{state.page=key;state.returnTo=null;if(key==='stock'){state.pendingStock=null;state.screenTicker=null;state.stockMode='candidates';}render();window.scrollTo(0,0);};nav.append(button);}
function render(){
 for(const observer of chartObservers)observer.disconnect();chartObservers.clear();
 document.querySelectorAll('[data-market]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.market===state.market)));for(const b of nav.children){if(b.dataset.page===state.page)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}
 const content=document.getElementById('content');content.replaceChildren(pages[state.page][1]());
 const records=marketAnalysis().connected?.observations||[],latest=records.filter(r=>r.market===state.market&&r.quality==='available'&&r.observed_on).map(r=>r.observed_on).sort().at(-1),quote=stocks().find(([t])=>t===state.stock)?.[1]?.analysis;
 document.getElementById('snapshot-date').textContent=state.page==='stock'?(state.stockMode==='candidates'?'候補観測 '+dateText(topdown()?.breadth?.observed_on||latest):'株価 '+dateText(stockQuote(quote||{}).observed_on)):latest?'市場観測 '+dateText(latest):'保存 '+dateText(bundles.at(-1).created_at);
 if(state.returnTo){const previous=state.returnTo,b=el('button','back-button','← '+(pages[previous.page]?.[0]||'前の画面')+'へ戻る');b.onclick=()=>{Object.assign(state,previous);render();window.scrollTo(0,0);};content.prepend(b);}
 if(['overview','market'].includes(state.page)&&latestPacket('market').refresh_failure)content.prepend(el('p','badge caution','市場：前回値 · '+dateText(latestPacket('market').refresh_failure.original_created_at)));
 document.body.classList.toggle('embedded',Boolean(payload.embedded));
}
function applyAppearance(value,notify=true){document.documentElement.dataset.theme=value;document.getElementById('appearance').value=value;if(notify&&payload.embedded&&window.parent!==window)window.parent.postMessage({type:'research-appearance',theme:value},location.origin);}
if(payload.embedded)window.addEventListener('message',event=>{if(event.source===window.parent&&event.origin===location.origin&&event.data?.type==='research-appearance'&&['auto','light','dark'].includes(event.data.theme))applyAppearance(event.data.theme,false);});
document.querySelectorAll('[data-market]').forEach(b=>b.onclick=()=>{state.market=b.dataset.market;state.returnTo=null;state.pendingStock=null;state.screenTicker=null;render();});document.getElementById('appearance').onchange=e=>applyAppearance(e.target.value);render();
