/* Connected market views. Saved observations only; no new signals or acquisition. */
const MARKET_GROUPS=[
 ['structure','市場構造・研究姿勢',['evaluation','ibd_regime','regime_playbook','microstructure','monitor','strategy_regime']],
 ['flow','テーマと資金の動き',['momentum','market_distortions','trend_ranking','opportunity_themes','sector_flow','flow_monitor','flow_alignment']],
 ['risk','リスクとセンチメント',['credit_stress','volatility_regime','vix_sq_alert','sentiment','composite_sentiment','top_risk_signposts']],
 ['outlook','見通し・ドライバー',['market_timeframes','market_driver_monitor','short_horizon_forecast']],
 ['prices','基本市況・価格',['market_data','market_charts','important_levels','cross_market']],
 ['japan','日本固有の条件',['japan_conditions']],
 ['optional','明示取得の参考分析',['fomo_scan','options']],
];
const MARKET_FACTS={
 evaluation:[['状態','status'],['根拠','description']],
 ibd_regime:[['状態（代理）','label'],['根拠','rationale']],
 regime_playbook:[['研究姿勢','stance'],['次の確認','think_about'],['避ける条件','avoid']],
 microstructure:[['巻き戻し（代理）','unwind_level'],['流動性','liquidity.status'],['HV20','hv20']],
 monitor:[['SPY売り抜け','distribution_spy'],['Nasdaq売り抜け','distribution_ndx'],['過熱','climax'],['利回り差','yield_spread']],
 strategy_regime:[['研究姿勢','label'],['根拠','rationale'],['無効化条件','invalidation']],
 important_levels:[['価格水準','summary']],
 flow_alignment:[['整合','alignment_label'],['観測','summary']],
 credit_stress:[['信用状態','status_label'],['観測','summary']],
 volatility_regime:[['ボラ状態','label'],['観測','summary']],
 vix_sq_alert:[['警戒','label'],['観測','summary']],
 sentiment:[['心理状態','label'],['観測','summary']],
 composite_sentiment:[['複合状態','state_label'],['観測','summary']],
 top_risk_signposts:[['兆候','label'],['観測','summary']],
 market_timeframes:[['見通し','summary']],
 market_driver_monitor:[['ドライバー','summary']],
 flow_monitor:[['資金注目度（代理）','summary']],
};
function marketPath(value,path){return path.split('.').reduce((v,k)=>v?.[k],value);}
function compactObservation(value){
 if(value==null)return null;
 if(typeof value!=='object')return textValue(value);
 if(Array.isArray(value)){const first=compactObservation(value[0]);return first==null?null:first+(value.length>1?` / ほか${value.length-1}件（内訳へ）`:'');}
 const words=['label','status_label','state_label','direction_label','summary','reason','rationale','status','count','value'].filter(k=>value[k]!=null&&typeof value[k]!=='object').map(k=>textValue(value[k]));
 return words.slice(0,2).join(' / ')||null;
}
function nearbyDetail(value,title='内訳・出典を確認'){
 const d=el('details','feature'),body=el('div','feature-body');d.append(el('summary','',title),body);
 d.addEventListener('toggle',()=>{if(d.open&&!body.childNodes.length)body.append(hasValue(value)?reference(value):el('p','missing','未取得・適用対象外です。取得状態はデータ状況で確認してください。'));});
 return d;
}
function observedMarketRows(key,value){
 const items=Array.isArray(value.items)?value.items:[];
 if(key==='momentum')return table([H('保存期間'),H('上昇側の先頭 / 下降側の末尾'),H('騰落 %',true)],Object.entries(value).flatMap(([period,rows])=>{
  if(!Array.isArray(rows)||!rows.length)return [[period,'未取得',percentNode(null)]];
  const up=rows.find(r=>Number.isFinite(r.performance)&&r.performance>=0),down=rows.filter(r=>Number.isFinite(r.performance)&&r.performance<0).at(-1);
  return [up,down].filter(Boolean).map(r=>[period,r.theme,percentNode(r.performance)]);
 }),{compact:true});
 if(key==='flow_monitor'&&value.leaders?.length)return table([H('ETF注目度（代理）'),H('20営業日・市場相対 %',true)],value.leaders.slice(0,3).map(r=>[r.label||r.ticker,percentNode(r.relative_return_20d)]),{compact:true});
 if(key==='market_timeframes'&&items.length)return table([H('時間軸'),H('方向'),H('確度')],items.map(r=>[r.label,r.direction_label||r.status,r.confidence]),{compact:true});
 if(key==='market_driver_monitor'&&items.length)return table([H('系列'),H('実値',true),H('5日変化',true),H('20日変化',true)],items.map(r=>[r.label,numericNode(r.value,'',number(r.value)+(r.unit==='percent'?'%':'')),r.change_5d_bp!=null?number(r.change_5d_bp)+' bp':percentNode(r.change_5d),r.change_20d_bp!=null?number(r.change_20d_bp)+' bp':percentNode(r.change_20d)]),{compact:true});
 if(key==='top_risk_signposts'&&items.length)return table([H('兆候'),H('保存判定'),H('値',true)],items.map(r=>[r.label,r.status,numericNode(r.value,'',number(r.value))]),{compact:true});
 if(key==='important_levels'&&items.length)return table([H('系列'),H('終値',true),H('支持',true),H('抵抗',true),H('状態')],items.map(r=>[r.label,numericNode(r.close,'',number(r.close)),numericNode(r.support,'',number(r.support)),numericNode(r.resistance,'',number(r.resistance)),r.behavior_label]),{compact:true});
 if(key==='japan_conditions'&&items.length)return table([H('条件'),H('確認状態'),H('観測')],items.map(r=>[r.title,(r.status==='unavailable'?'未確認':r.status_label||r.status)+' / '+(r.source_type==='proxy'?'代理':r.source_type==='direct'?'直接':r.source_type||'出典未確認'),r.proxy_observation||r.value]),{compact:true});
 return null;
}
function marketFeature(key,m){
 const value=m[key],box=el('section','market-feature');box.dataset.feature=key;box.append(el('h3','',payload.market_features[key]||key));
 const update=m.field_updates?.[key];if(update?.status==='not_updated')box.append(el('p','caution','今回の対象外 / 旧保存値・元の日付を維持。元スナップショット作成 '+update.original_snapshot_created_at));
 if(!hasValue(value)){box.append(el('p','missing','未取得・適用対象外。0や成立条件としては扱いません。'),nearbyDetail(value));return box;}
 const rows=(MARKET_FACTS[key]||[['観測','summary'],['状態','label'],['状態','status']]).map(([label,path])=>[label,compactObservation(marketPath(value,path))]).filter(([,v])=>v!=null&&v!=='');
 if(!rows.length&&typeof value!=='object')rows.push(['保存値',textValue(value)]);
 if(!rows.length&&Array.isArray(value))rows.push(['保存項目',value.length+'件']);
 if(!rows.length&&typeof value==='object')for(const [name,item] of Object.entries(value).slice(0,3)){const text=compactObservation(item);if(text!=null)rows.push([labelFor(name),text]);}
 const facts=el('dl','market-facts');for(const [label,value] of rows)facts.append(el('dt','',label),el('dd','',value));if(!rows.length)facts.append(el('dd','meta','保存された観測の内訳を確認してください。'));box.append(facts);
 const special=observedMarketRows(key,value),items=Array.isArray(value.items)?value.items:[];
 if(special)box.append(special);else if(items.length){const lines=items.slice(0,3).map(v=>[v.label||v.theme||v.ticker||v.name||v.key||'観測',compactObservation(v)||'詳細に保存']);box.append(table([H('主要項目'),H('観測')],lines,{compact:true}));}
 const context=[];for(const k of ['source','as_of','data_as_of','fetched_at'])if(value[k]!=null&&typeof value[k]!=='object')context.push((k==='source'?'出典':k==='fetched_at'?'取得':'基準日')+' '+textValue(value[k]));
 if(value.is_stale)context.push('古い入力');if(value.is_partial||value.status==='partial')context.push('一部未確認');
 if(key==='credit_stress'&&state.market==='JP')context.unshift('米国信用：日本市場の外部環境参考');
 if(context.length)box.append(el('p','meta',context.join(' / ')));
 box.append(nearbyDetail(value));return box;
}
function openResearchPage(page,theme){
 state.returnTo={page:state.page,market:state.market,stock:state.stock,pendingStock:state.pendingStock,stockTab:state.stockTab,returnTo:state.returnTo};state.page=page;if(theme){state.themeFocus={market:state.market,theme};}render();window.scrollTo(0,0);
}
function legacyMarketPage(){
 const root=el('div','connected-market'),m=marketAnalysis();root.append(el('h2','page-title',`市場 / ${marketName(state.market)}`));
 const summary=el('div','market-summary');
 for(const [target,title,value] of [
  ['structure','市場の状態',m.strategy_regime?.label||m.ibd_regime?.label||m.evaluation?.status],
  ['flow','資金・テーマの整合',m.flow_alignment?.alignment_label||m.flow_monitor?.status],
  ['risk','リスクの兆候',m.top_risk_signposts?.summary||m.volatility_regime?.label],
 ]){const a=el('a');a.href='#market-'+target;a.append(el('span','meta',title),el('strong','',value||'未確認'),el('p','meta','保存された観測と根拠へ ↓'));summary.append(a);}root.append(summary);
 const jumps=el('nav','market-jumps');jumps.setAttribute('aria-label','市場内の分析');
 for(const [id,title] of MARKET_GROUPS){if(id==='japan'&&state.market!=='JP')continue;const a=el('a','',title);a.href='#market-'+id;jumps.append(a);}const policy=el('button','headbutton','市場方針を見る →');policy.onclick=()=>openResearchPage('policy');jumps.append(policy);root.append(jumps);
 const layout=el('div','market-layout');
 for(const [id,title,keys] of MARKET_GROUPS){if(id==='japan'&&state.market!=='JP')continue;const box=panel(title);box.id='market-'+id;box.classList.add('market-section');
  if(id==='prices'){box.classList.add('market-wide');box.append(marketSnapshotPanel(m));const history=marketHistoryPanel(m.market_charts);history.dataset.feature='market_charts';box.append(history);}
  if(id==='optional'){
   box.classList.add('market-wide');for(const key of keys){const v=m[key],d=nearbyDetail(v,`${payload.market_features[key]} / ${v?.status||'未取得'} — 明示取得のみ`);d.dataset.feature=key;
    if(key==='options'){const body=d.querySelector('.feature-body');d.addEventListener('toggle',()=>{if(d.open){body.replaceChildren(optionsPanel(m));} });}
    box.append(d);}box.append(el('p','meta','展開しても取得しません。取得・過熱スキャンはCodexで明示した場合のみです。'));layout.append(box);continue;
  }
  for(const key of keys){if(['market_data','market_charts','short_horizon_forecast','trend_ranking'].includes(key))continue;box.append(marketFeature(key,m));}
  if(id==='flow'){
   const ranking=m.trend_ranking||{},top=ranking.items?.slice(0,5)||[],row=el('section','market-feature');row.dataset.feature='trend_ranking';row.append(el('h3','',ranking.profile==='standard'?'標準・6か月市場相対順位 / 代表銘柄へ':'総合テーマ順位 / 代表銘柄へ'));
   const links=top.map(r=>{const b=el('button','headbutton',r.theme+' →');b.onclick=()=>openResearchPage('theme',r.theme);return [rankNode(r.rank),b,percentNode(r.performance_1m)];});row.append(links.length?table([H('順位'),H('テーマ'),H('1か月',true)],links,{compact:true}):el('p','missing','テーマ順位は未取得です。'),nearbyDetail(ranking));box.append(row);
   const linksbox=el('div','market-links'),themes=el('button','','全テーマ・代表銘柄を見る →');themes.onclick=()=>openResearchPage('theme');linksbox.append(themes);box.append(linksbox);
  }
  if(id==='outlook'){const forecast=forecastPanel(m);forecast.dataset.feature='short_horizon_forecast';box.append(forecast);}
  layout.append(box);
 }
 if(m.legacy_trend_ranking){const old=panel('旧総合テーマ順位 / 研究参考','元スナップショット '+m.legacy_trend_ranking.snapshot_created_at);old.append(themeTable(m.legacy_trend_ranking.ranking.items||[]),nearbyDetail(m.legacy_trend_ranking));layout.append(old);}root.append(layout,interpretationPanels(state.market));return root;
}

const RELATION_LABELS={supports:'支える',weakens:'弱める',different_horizon:'時間軸が異なる',reference:'参考',incomparable:'比較不能 / 未確認'};
const OBS_UNITS={'%':'%','pp':'ポイント差','bp':'bp','index':'指数ポイント','JPY':'円','price':'価格','volume':'出来高','volatility points':'ボラポイント'};
function relativeNode(value){return numericNode(value,Number.isFinite(value)?value>=0?'pos':'neg':'missing',Number.isFinite(value)?(value>=0?'+':'')+number(value,1)+' pp':'未確認');}
function indexObservation(r){return r.id.startsWith('index:')||r.id.startsWith('^NDX:')||r.id.startsWith('1306.T:');}
function observationWindow(r){return r.window.replace(/(\d+)sessions?/,'$1営業日');}
function connectedEvidenceTable(rows){
 return rows.length?table([H('観測 / 対象'),H('実値',true),H('単位・期間'),H('観測日 / 品質')],rows.map(r=>[r.label+' / '+r.market,numericNode(r.value,'',number(r.value,2)),(OBS_UNITS[r.unit]||r.unit)+' / '+observationWindow(r),(r.observed_on||'未確認')+' / '+(r.quality==='available'?'確認済み':r.quality==='stale'?'古い観測':'未取得')+(r.quality!=='available'&&r.reason?' / '+r.reason:'')]),{compact:true}):empty('この問いの根拠が未取得です。');
}

function savedObservation(c,id){return (c?.observations||[]).find(r=>r.id===id);}
function displayObservation(r){return {...r,value:r.quality==='unavailable'?null:r.value};}
function relationCaption(r,c){
 const a=savedObservation(c,r.from),b=savedObservation(c,r.to),valid=x=>x?.quality==='available'&&Number.isFinite(x.value);
 if(!a&&!b)return r.observation||'観測未取得';
 const value=x=>valid(x)?number(x.value,1)+' '+x.unit:x?.quality==='stale'?'前回値':'未取得';
 if(!valid(a)||!valid(b))return (a?.label||r.from||'入力')+' '+value(a)+' / '+(b?.label||r.to||'入力')+' '+value(b);
 if(r.kind==='incomparable')return a.label+' '+value(a)+' / '+b.label+' '+value(b)+'（比較条件未一致）';
 const sign=x=>x>0?'上昇':x<0?'低下':'横ばい';
 if(r.id==='広い参加')return '指数は'+sign(a.value)+'（'+pct(a.value)+'）、'+(b.id==='participation:sample'?'登録銘柄の200日線上は '+pct(b.value):'等加重は相対的に'+(b.value>0?'優位':b.value<0?'劣後':'横ばい')+'（'+pct(b.value)+'）')+'。';
 if(r.id==='中期と短期')return '200日線の'+(a.value>=0?'上':'下')+' '+pct(a.value)+' / 20日線の'+(b.value>=0?'上':'下')+' '+pct(b.value)+'。';
 if(r.id==='価格と信用')return '指数 '+pct(a.value)+' / 信用スプレッド '+number(b.value,1)+' bp（'+(b.value>0?'拡大':b.value<0?'縮小':'横ばい')+'）。';
 if(r.id==='名目と実質金利')return '名目10年 '+number(a.value,1)+' bp / 実質10年 '+number(b.value,1)+' bp。';
 return a.label+' '+value(a)+' / '+b.label+' '+value(b);
}
function connectionPanel(c,title='観測から分かること'){
 const box=panel(title),grid=el('div','connection-readings');box.dataset.question='5';
 for(const r of c.relations||[]){const article=el('article','connection-reading');article.dataset.relation=r.id;article.append(el('h3','',r.id+(r.scope==='US'&&state.market==='JP'?' / 米国参考':'')),el('p','',relationCaption(r,c)),nearbyDetail(r,'根拠・反証・確認対象'));grid.append(article);}box.append(grid);return box;
}
function themeModeNote(packet){
 const ranking=packet.ranking||{},notes=[];if(packet.refresh_failure)notes.push('前回値');if(ranking.profile!=='standard')notes.push('旧方式');
 const dates=ranking.items?.[0]?.observation_dates||[];if(notes.length){const note=el('p','badge caution',notes.join(' / ')+(dates.length?' · '+observationDates(ranking.items[0]):''));return note;}return null;
}
function themePreviewPanel(){
 const packet=themePacket(),ranking=packet.ranking||{},standard=ranking.profile==='standard',period=standard?'6m':'1m',rows=(ranking.items||[]).filter(r=>!standard||r.rank_6m!=null).slice(0,5);
 const box=panel(standard?'強いテーマ / 市場相対Top5':'テーマTop5 / 旧総合順位',marketName(state.market));box.dataset.preview='themes';const note=themeModeNote(packet);if(note)box.append(note);
 const maximum=Math.max(1,...rows.map(r=>Math.abs(r[standard?'relative_6m':'performance_1m'])).filter(Number.isFinite)),list=el('div','theme-preview');
 for(const r of rows){const row=el('div','theme-preview-row'),button=el('button','text-button',r.theme+' →');button.onclick=()=>openResearchPage('theme',r.theme);row.append(rankNode(r.rank),button,signedBar(r[standard?'relative_6m':'performance_1m'],maximum,standard?v=>Number.isFinite(v)?(v>0?'+':'')+number(v,1)+' pp':'未確認':pct));list.append(row);}box.append(rows.length?list:empty('順位を確定できるテーマがありません。'));
 box.append(el('p','meta',standard?'6か月・126営業日 / 構成中央値 − '+ranking.benchmark:'旧総合順位 / 横棒は1か月リターン'));
 const go=el('button','text-button','全テーマ・代表銘柄を比較 →');go.onclick=()=>openResearchPage('theme');box.append(go);return box;
}
function connectedMarketPage(){
 const m=marketAnalysis(),c=m.connected;if(!c){const root=legacyMarketPage();root.prepend(el('p','badge caution','旧方式の保存結果'));return root;}
 const root=el('div','connected-market standard-market'),rows=c.observations||[],grid=el('div','question-grid');root.append(pageHeading('市場 / '+marketName(state.market),periodControls()));
 const trajectory=comparisonPanel(state.market);trajectory.dataset.question='1';grid.append(trajectory);
 const position=panel('移動平均と短期の価格位置');position.dataset.question='2';const ma=rows.filter(r=>r.market===state.market&&indexObservation(r)&&/:ma(20|50|200)_gap$/.test(r.id)).map(displayObservation);
 position.append(observationBars(ma));const get=id=>savedObservation(c,'index:'+id),close=get('close'),low=get('low20'),high=get('high20');position.append(el('h3','','主指数 / 直近20営業日の高安'),pricePosition(displayObservation(close||{}).value,displayObservation(low||{}).value,displayObservation(high||{}).value),el('p','meta',dateText(close?.observed_on)));grid.append(position);
 const breadth=panel('上昇に参加している範囲');breadth.dataset.question='1';const relative=rows.filter(r=>['participation:rsp','participation:iwm'].includes(r.id)).map(displayObservation);if(relative.length)breadth.append(observationBars(relative,{label:r=>r.id.endsWith('rsp')?'等加重 / SPY・6か月比率':'小型株 / SPY・6か月比率'}));const share=savedObservation(c,'participation:sample');if(share){const meter=el('div','breadth-meter'),fill=el('span');const value=displayObservation(share).value;if(Number.isFinite(value)){fill.style.width=Math.max(0,Math.min(100,value))+'%';meter.append(fill);}meter.setAttribute('aria-hidden','true');breadth.append(el('h3','','登録銘柄 / 200日線より上'),meter,el('p','metric-inline',pct(value)+' · '+dateText(share.observed_on)),nearbyDetail(share,'対象銘柄・算定根拠'));}breadth.append(el('p','insight',observationSummary(c)));grid.append(breadth);
 const themes=themePreviewPanel();themes.dataset.question='3';grid.append(themes);
 const rates=panel('金利・信用の変化','1か月 / bp');rates.dataset.question='4';const changes=rows.filter(r=>r.unit==='bp'&&r.id.endsWith(':change_1m')).map(displayObservation);rates.append(observationBars(changes,{unit:'bp',label:r=>r.label.replace(' / 21観測変化',''),format:v=>Number.isFinite(v)?(v>0?'+':'')+number(v,1)+' bp':'未取得'}));rates.append(table([H('水準'),H('実値',true),H('観測日')],rows.filter(r=>r.unit==='%'&&r.id.endsWith(':level')).map(r=>[r.label,datum(displayObservation(r)),dateText(r.observed_on)]),{compact:true}));grid.append(rates);
 const risks=panel('為替・原油とボラティリティ');risks.dataset.question='4';risks.append(observationBars(rows.filter(r=>['JPY=X:return_1m','CL=F:return_1m'].includes(r.id)).map(displayObservation),{label:r=>r.label.replace(' / 1m騰落',' / 1か月')}));const vix=savedObservation(c,'vix:level'),cell=el('div','metric');cell.append(el('span','meta','米VIX / ポイント'),el('strong','',number(displayObservation(vix||{}).value,1)),el('small','',dateText(vix?.observed_on)));risks.append(cell);
 if(state.market==='JP'){const j=c.jpx||{};risks.append(el('h3','','海外投資家・週次現物'));if(['available','stale'].includes(j.status)){const week=j.current_week;risks.append(table([H('期間'),H('買越額 / 円',true)],[['最新週 '+week.period_start+'–'+week.period_end,numericNode(week.net_amount,'',number(week.net_amount,0))],['非重複4週',numericNode(j.four_week_net,'',number(j.four_week_net,0))]]));if(j.status==='stale')risks.append(statusBadge('stale'));}else risks.append(el('p','badge caution','週次需給は未取得'));risks.append(nearbyDetail(j,'需給の出典・期間・取得状態'));}grid.append(risks);root.append(grid);
 const events=panel('次の公式イベント');events.dataset.question='2';events.append(c.events?.length?table([H('日付'),H('予定'),H('時刻')],c.events.map(e=>[e.date+(e.next_policy_meeting?' / 次回会合':''),safeLink(e.source,e.label),e.local_time||'未定']),{compact:true}):el('p','missing','イベント予定は未取得です。'));const failed=(c.event_sources||[]).filter(e=>e.status!=='available');if(failed.length)events.append(el('p','badge caution',failed.map(e=>e.provider).join('・')+' 未取得'));events.append(nearbyDetail(c.event_sources,'予定の出典・取得状態'));root.append(events,connectionPanel(c),nearbyDetail(c,'全観測・出典・計算内訳'));
 const legacy=el('details','feature');legacy.append(el('summary','','その他の分析 / 既存29項目'));legacy.addEventListener('toggle',()=>{if(legacy.open&&legacy.childNodes.length===1)legacy.append(legacyMarketPage());});root.append(legacy);return root;
}
const themeHeaderSort=new Map();
function standardThemeTable(rows,period,expand=false,{legacy=false}={}){
 const wrap=el('div','table-wrap theme-ranking'),t=el('table'),head=el('thead'),header=el('tr'),key=state.market+':'+legacy+':'+period;
 const rank=r=>r[legacy?'rank':'rank_'+period],metric=r=>r[(legacy?'performance_':'relative_')+period],coverage=r=>Number.isFinite(r['coverage_'+period])?r['coverage_'+period]*(legacy?100:1):null;
 let ordered=[...rows];const maximum=Math.max(1,...rows.map(r=>Math.abs(metric(r))).filter(Number.isFinite));
 const columns=[['順位',rank,true],['テーマ',r=>r.theme,false],[legacy?'リターン %':'市場との差 pp',metric,true],['騰落率 %',r=>r['performance_'+period],true],['代表銘柄',r=>(r.representative_tickers||[]).slice(0,3).join(' '),false],['取得率',coverage,true]];
 const draw=()=>{for(const body of Array.from(t.tBodies))body.remove();const sort=themeHeaderSort.get(key);if(sort){const accessor=columns[sort.column][1];ordered.sort((a,b)=>{const A=accessor(a),B=accessor(b);return A==null?(B==null?0:1):B==null?-1:(typeof A==='number'?A-B:String(A).localeCompare(String(B),'ja'))*(sort.ascending?1:-1);});}
 for(const [i,r] of ordered.entries()){
  const body=el('tbody'),row=el('tr'),detail=el('tr','theme-expansion'),cell=el('td'),expandedKey=state.market+'\u0000'+r.theme,button=el('button','theme-toggle'),arrow=el('span','disclosure','▸');body.dataset.themeRow=r.theme;cell.colSpan=columns.length;cell.id='theme-members-'+i;detail.append(cell);detail.hidden=true;arrow.setAttribute('aria-hidden','true');button.setAttribute('aria-label',r.theme);button.append(arrow,el('span','',r.theme));button.dataset.themeToggle=r.theme;
  const sync=()=>{const open=themeExpanded.has(expandedKey);button.setAttribute('aria-expanded',String(open));button.setAttribute('aria-controls',cell.id);arrow.textContent=open?'▾':'▸';detail.hidden=!open;if(open&&!cell.childNodes.length){if(legacy)cell.append(themeMembers(r));else{const members=r.stocks||[],memberMax=Math.max(1,...members.map(s=>Math.abs(s.periods?.[period]?.relative_return)).filter(Number.isFinite));cell.append(table([H('構成銘柄'),H('市場との差 pp',true),H('騰落率 %',true),H('個別分析')],members.map(s=>[s.ticker,signedBar(s.periods?.[period]?.relative_return,memberMax,v=>Number.isFinite(v)?number(v,1)+' pp':'未確認'),percentNode(s.periods?.[period]?.return),stockJump(s.ticker,s,period)]),{compact:true}));}cell.append(nearbyDetail(r,'算定根拠・観測日・除外理由'));}};
  button.onclick=expand?()=>{if(themeExpanded.has(expandedKey))themeExpanded.delete(expandedKey);else themeExpanded.add(expandedKey);sync();}:()=>openResearchPage('theme',r.theme);
  const name=el('div','theme-name-cell');name.append(button);if(rank(r)==null)name.append(el('span','badge caution','順位未確定'));const ps=r.period_status?.[period];const periods=rows.map(item=>item.period_status?.[period]?.observation_dates||[]).filter(d=>d.length===2),dateCounts=new Map();for(const d of periods){const k=d.join('/');dateCounts.set(k,(dateCounts.get(k)||0)+1);}const commonDates=[...dateCounts].sort((a,b)=>b[1]-a[1])[0]?.[0];if(ps?.observation_dates?.length&&ps.observation_dates.join('/')!==commonDates)name.append(el('span','badge caution',ps.observation_dates.map(dateText).join('–')));if(ps?.status==='stale')name.append(statusBadge('stale'));if(ps&&ps.status!=='available'&&ps.status!=='stale'&&rank(r)!=null)name.append(statusBadge(ps.status));
  const reps=el('div','representative-strip');for(const ticker of (r.representative_tickers||[]).slice(0,3))reps.append(stockJump(ticker,r.stocks?.find(s=>s.ticker===ticker),period));
  const bar=signedBar(metric(r),maximum,legacy?pct:v=>Number.isFinite(v)?(v>0?'+':'')+number(v,1)+' pp':'未確認');
  [rankNode(rank(r)),name,bar,percentNode(r['performance_'+period]),reps,Number.isFinite(coverage(r))?number(coverage(r),0)+'%':'未確認'].forEach((v,j)=>{const td=el('td',columns[j][2]?'num':'');if(v instanceof Node)td.append(v);else td.textContent=v;row.append(td);});body.append(row);if(expand){body.append(detail);sync();}t.append(body);
 }};
 columns.forEach(([label,,numeric],i)=>{const th=el('th',numeric?'num':'');th.scope='col';if(expand){const button=el('button','headbutton',label+' ↕');button.onclick=()=>{const previous=themeHeaderSort.get(key),ascending=previous?.column===i?!previous.ascending:true;themeHeaderSort.set(key,{column:i,ascending});for(const cell of header.children)cell.removeAttribute('aria-sort');th.setAttribute('aria-sort',ascending?'ascending':'descending');draw();};th.append(button);}else th.textContent=label;header.append(th);});head.append(header);t.append(head);wrap.append(t);draw();const remembered=themeHeaderSort.get(key);if(remembered&&expand)header.children[remembered.column].setAttribute('aria-sort',remembered.ascending?'ascending':'descending');return wrap;
}
function standardThemePage(packet){
 const root=el('div'),ranking=packet.ranking,controls=el('div','subcontrols'),search=el('input'),[pb,period]=selectControl('theme-period','期間',[['6m','6か月'],['1m','1か月'],['1w','1週']]),[db,direction]=selectControl('theme-direction','方向',[['all','全て'],['up','上昇'],['down','下降']]),[sb,sort]=selectControl('theme-sort','順位',[['relative','市場相対上位'],['relative-asc','市場相対下位'],['coverage','取得率']]);
 search.type='search';search.id='theme-search';search.setAttribute('aria-label','テーマ検索');search.placeholder='テーマ検索';controls.append(search,pb,db,sb);root.append(pageHeading('テーマ / '+marketName(state.market)),controls);const note=themeModeNote(packet);if(note)root.append(note);
 const remembered=themeControls.get('standard:'+state.market);if(remembered){search.value=remembered.search;period.value=remembered.period;direction.value=remembered.direction;sort.value=remembered.sort;}if(state.themeFocus?.market===state.market){search.value=state.themeFocus.theme;period.value='6m';direction.value='all';sort.value='relative';themeExpanded.add(state.market+'\u0000'+search.value);state.themeFocus=null;}
 const definition=el('p','meta'),holder=el('div');const draw=()=>{
  const p=period.value;themeControls.set('standard:'+state.market,{search:search.value,period:p,direction:direction.value,sort:sort.value});let rows=(ranking.items||[]).filter(r=>r.theme.toLowerCase().includes(search.value.toLowerCase())&&(direction.value==='all'||Number.isFinite(r['relative_'+p])&&(direction.value==='up'?r['relative_'+p]>=0:r['relative_'+p]<0)));
  rows.sort((a,b)=>sort.value==='coverage'?(b['coverage_'+p]??-1)-(a['coverage_'+p]??-1):a['rank_'+p]==null?(b['rank_'+p]==null?0:1):b['rank_'+p]==null?-1:(a['rank_'+p]-b['rank_'+p])*(sort.value==='relative-asc'?-1:1));
  const dates=[...new Set((ranking.items||[]).flatMap(r=>r.period_status?.[p]?.observation_dates||[]))].sort();definition.textContent=({'1w':'5','1m':'21','6m':'126'})[p]+'営業日 / 構成中央値 − '+ranking.benchmark+' / '+(dates.length?dateText(dates[0])+'–'+dateText(dates.at(-1)):'観測日未確認')+' / 横棒は0基準';holder.replaceChildren(rows.length?standardThemeTable(rows,p,true):empty('一致するテーマはありません。'));
 };for(const control of [search,period,direction,sort])control[control===search?'oninput':'onchange']=()=>{themeHeaderSort.delete(state.market+':false:'+period.value);draw();};draw();root.append(definition,holder,nearbyDetail({method:ranking.method,quality:ranking.quality_warnings,leaders:packet.leaders},'順位の方式・候補の確認状態'));return root;
}
