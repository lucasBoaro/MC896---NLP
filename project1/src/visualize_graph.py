"""Gera uma visualização HTML interativa a partir de nodes.csv e edges.csv."""

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NODES = ROOT / "outputs" / "full" / "v2" / "nodes.csv"
DEFAULT_EDGES = ROOT / "outputs" / "full" / "v2" / "edges.csv"
DEFAULT_OUTPUT = ROOT / "outputs" / "full" / "v2" / "graph.html"


def read_records(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        records = list(csv.DictReader(file))
    for record in records:
        record["attributes"] = json.loads(record.get("attributes") or "{}")
        for field in ("sentence_id", "start", "end"):
            if field in record and record[field] != "":
                record[field] = int(record[field])
    return records


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_html(nodes, edges):
    template = r'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Clinical Knowledge Graph</title>
  <style>
    :root {
      --bg:#f5f7fb; --surface:#ffffff; --surface-2:#eef2f8; --text:#142033;
      --muted:#66758a; --line:#dbe3ef; --shadow:0 18px 50px rgba(20,32,51,.10);
      --primary:#4357d9; --primary-soft:#e8ebff; --symptom:#ef6a6a; --exam:#3b82c4;
      --condition:#8b5cf6; --treatment:#18a87a; --case:#17243a; --warning:#d99022;
      --edge:#aeb9c8; --relation-treats:#11966d; --relation-indicates:#7c4ee4;
      --relation-before:#c77a12; --relation-structural:#aeb9c8;
    }
    [data-theme="dark"] {
      --bg:#0d1420; --surface:#151f2f; --surface-2:#1c293c; --text:#edf3fb;
      --muted:#9baabd; --line:#2b3a50; --shadow:0 20px 55px rgba(0,0,0,.32);
      --primary:#8e9bff; --primary-soft:#263058; --case:#dbe7f8; --edge:#52647b;
      --relation-treats:#42d3a1; --relation-indicates:#ad8cff;
      --relation-before:#f1ad4f; --relation-structural:#52647b;
    }
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;transition:background .2s,color .2s}
    button,select,input{font:inherit}
    button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid color-mix(in srgb,var(--primary) 30%,transparent);outline-offset:2px}
    .app{min-height:100vh}
    .hero{background:linear-gradient(125deg,#17243a 0%,#26375c 58%,#4357d9 135%);color:#fff;padding:28px 34px 86px;position:relative;overflow:hidden}
    .hero:after{content:"";position:absolute;width:360px;height:360px;border-radius:50%;right:-110px;top:-210px;background:rgba(255,255,255,.08)}
    .hero-row{max-width:1440px;margin:auto;display:flex;justify-content:space-between;align-items:flex-start;gap:24px;position:relative;z-index:1}
    .eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.7;font-weight:700}
    h1{font-size:clamp(28px,4vw,45px);line-height:1.05;margin:8px 0 9px;letter-spacing:-.04em}
    .subtitle{margin:0;color:rgba(255,255,255,.72);max-width:650px;font-size:15px}
    .icon-button{border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.09);color:#fff;border-radius:12px;padding:10px 13px;cursor:pointer}
    .shell{max-width:1440px;margin:-58px auto 0;padding:0 24px 36px;position:relative;z-index:2}
    .toolbar{display:grid;grid-template-columns:minmax(260px,1.2fr) minmax(180px,.7fr) auto;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:var(--shadow)}
    .field label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:700;margin:0 0 7px}
    .field select,.field input{width:100%;height:42px;border:1px solid var(--line);border-radius:11px;background:var(--surface-2);color:var(--text);padding:0 12px}
    .toolbar-actions{display:flex;align-items:flex-end;gap:9px}
    .button{height:42px;border:1px solid var(--line);border-radius:11px;background:var(--surface);color:var(--text);padding:0 15px;font-weight:650;cursor:pointer}
    .button:hover{background:var(--surface-2)}
    .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
    .stat{background:var(--surface);border:1px solid var(--line);border-radius:15px;padding:15px 17px}
    .stat-label{color:var(--muted);font-size:12px;margin-bottom:4px}
    .stat-value{font-size:25px;font-weight:750;letter-spacing:-.03em}
    .tabs{display:flex;gap:5px;border-bottom:1px solid var(--line);margin-top:18px}
    .tab{border:0;background:transparent;color:var(--muted);padding:12px 15px;font-weight:700;cursor:pointer;position:relative}
    .tab.active{color:var(--primary)}
    .tab.active:after{content:"";position:absolute;left:12px;right:12px;bottom:-1px;height:3px;background:var(--primary);border-radius:3px 3px 0 0}
    .panel{display:none;margin-top:14px}.panel.active{display:block}
    .graph-grid{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:14px}
    .graph-stage,.detail,.timeline-wrap,.relations-wrap{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:0 8px 24px rgba(20,32,51,.05)}
    .stage-head{display:flex;align-items:flex-end;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--line);gap:15px}
    .stage-title{font-weight:750}.stage-caption{color:var(--muted);font-size:12px;margin-top:2px}
    .graph-filter{width:210px;flex:0 0 auto}
    .legend-bar{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 16px;border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--surface-2) 48%,transparent)}
    .legend{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}
    .legend-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}
    .dot{width:9px;height:9px;border-radius:50%;background:var(--dot)}
    .line-key{width:24px;height:0;border-top:2px solid var(--key-color);display:inline-block}.line-key.before{border-top-style:dashed}.line-key.structural{border-top-width:1px;opacity:.55}
    .canvas-wrap{height:650px;overflow:hidden;position:relative;background:radial-gradient(circle at 40% 42%,color-mix(in srgb,var(--primary-soft) 48%,transparent),transparent 42%)}
    #graph-svg{width:100%;height:100%;cursor:grab;user-select:none}#graph-svg.dragging{cursor:grabbing}
    .edge{fill:none;cursor:pointer;transition:opacity .15s,stroke-width .15s}.edge:hover{opacity:1;stroke-width:4}
    .edge.structural{stroke:var(--relation-structural);stroke-width:1;opacity:.2}
    .edge.treats{stroke:var(--relation-treats);stroke-width:3;opacity:.92}
    .edge.indicates{stroke:var(--relation-indicates);stroke-width:3;opacity:.92}
    .edge.before{stroke:var(--relation-before);stroke-width:2.4;opacity:.88;stroke-dasharray:7 6}
    .edge-label{font-size:10px;font-weight:800;fill:var(--muted);paint-order:stroke;stroke:var(--surface);stroke-width:5px;stroke-linejoin:round;cursor:pointer}
    .edge-label.treats{fill:var(--relation-treats)}.edge-label.indicates{fill:var(--relation-indicates)}.edge-label.before{fill:var(--relation-before)}
    .node rect,.node circle{stroke:color-mix(in srgb,var(--node-color) 48%,var(--surface));stroke-width:1.2;fill:color-mix(in srgb,var(--node-color) 13%,var(--surface));filter:drop-shadow(0 5px 7px rgba(20,32,51,.10));transition:filter .15s,stroke-width .15s}
    .node:hover rect,.node:hover circle,.node.selected rect,.node.selected circle{stroke-width:3;filter:drop-shadow(0 8px 11px rgba(20,32,51,.18))}
    .node{cursor:pointer}.node .label{font-size:11px;font-weight:700;fill:var(--text);pointer-events:none}.node .meta{font-size:9px;fill:var(--muted);pointer-events:none}
    .detail{padding:20px;min-height:650px}.detail-kicker{text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-size:11px;font-weight:750}.detail h2{font-size:23px;line-height:1.15;margin:7px 0 8px;letter-spacing:-.025em}.detail-type{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:5px 9px;background:var(--surface-2);font-size:11px;font-weight:750}.detail-section{border-top:1px solid var(--line);padding-top:14px;margin-top:16px}.detail-section h3{font-size:12px;margin:0 0 9px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.detail p{font-size:13px;line-height:1.55;margin:0;word-break:break-word}.kv{display:grid;grid-template-columns:92px 1fr;gap:8px 10px;font-size:12px}.kv dt{color:var(--muted)}.kv dd{margin:0;font-weight:650}.empty{color:var(--muted);display:grid;place-items:center;text-align:center;height:540px;padding:25px}.empty-mark{font-size:38px;margin-bottom:10px}
    .timeline-wrap,.relations-wrap{padding:20px}.timeline-tools,.relation-tools{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.timeline-title{font-size:18px;font-weight:750}.check{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}.check input{accent-color:var(--primary)}
    .timeline-disclaimer{margin:0 0 22px;padding:12px 14px;border:1px solid color-mix(in srgb,var(--warning) 28%,var(--line));border-radius:12px;background:color-mix(in srgb,var(--warning) 8%,var(--surface));color:var(--muted);font-size:12px;line-height:1.45}
    .timeline-group-title{margin:0 0 14px;font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .untimed-block{margin-top:28px;padding-top:22px;border-top:1px solid var(--line)}.untimed-block[hidden]{display:none}
    .timeline{position:relative;padding-left:26px}.timeline:before{content:"";position:absolute;left:8px;top:7px;bottom:8px;width:2px;background:var(--line)}
    .event{position:relative;padding:0 0 18px 18px;cursor:pointer}.event:before{content:"";position:absolute;left:-23px;top:5px;width:12px;height:12px;border-radius:50%;background:var(--event-color);box-shadow:0 0 0 4px var(--surface),0 0 0 5px var(--line)}
    .event-card{border-bottom:1px solid var(--line);padding-bottom:15px;display:grid;grid-template-columns:145px minmax(0,1fr) auto;gap:14px;align-items:start}.event:last-child .event-card{border-bottom:0}.time-label{font-size:12px;font-weight:750;color:var(--event-color)}.event-name{font-size:14px;font-weight:750}.event-evidence{font-size:12px;color:var(--muted);margin-top:5px;line-height:1.45}.type-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
    .table-scroll{overflow:auto}.relations{width:100%;border-collapse:collapse;font-size:12px}.relations th{text-align:left;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;font-size:10px;padding:10px;border-bottom:1px solid var(--line)}.relations td{padding:12px 10px;border-bottom:1px solid var(--line);vertical-align:top}.relation-name{font-weight:800;color:var(--primary)}.evidence-cell{max-width:520px;color:var(--muted);line-height:1.4}
    .no-results{padding:60px 20px;text-align:center;color:var(--muted)}
    @media(max-width:950px){.graph-grid{grid-template-columns:1fr}.detail{min-height:auto}.canvas-wrap{height:540px}.empty{height:180px}.toolbar{grid-template-columns:1fr 1fr}.toolbar-actions{grid-column:1/-1}.stats{grid-template-columns:1fr 1fr}.event-card{grid-template-columns:115px 1fr}}
    @media(max-width:620px){.hero{padding:23px 18px 78px}.shell{padding:0 12px 24px}.toolbar{grid-template-columns:1fr}.toolbar-actions{grid-column:auto}.stats{gap:8px}.stat{padding:12px}.graph-stage,.detail,.timeline-wrap,.relations-wrap{border-radius:14px}.stage-head{align-items:flex-start;flex-direction:column}.graph-filter{width:100%}.legend-bar{align-items:flex-start;flex-direction:column}.legend{justify-content:flex-start}.canvas-wrap{height:470px}.event-card{grid-template-columns:1fr}.type-label{display:none}}
  </style>
</head>
<body>
<div class="app" id="app">
  <header class="hero">
    <div class="hero-row">
      <div><div class="eyebrow">NLP · Information Extraction</div><h1>Clinical Knowledge Graph</h1><p class="subtitle">Explore entidades, relações clínicas e a sequência temporal extraída dos relatos de caso.</p></div>
      <button class="icon-button" id="theme-button" type="button" aria-label="Alternar tema">◐ Tema</button>
    </div>
  </header>
  <main class="shell">
    <section class="toolbar" aria-label="Controles do grafo">
      <div class="field"><label for="case-select">Caso clínico</label><select id="case-select"></select></div>
      <div class="field"><label for="search-input">Buscar entidade</label><input id="search-input" type="search" placeholder="Ex.: pneumonia, CT, aspirin"></div>
      <div class="toolbar-actions"><button class="button" id="reset-button" type="button">Redefinir visualização</button></div>
    </section>
    <section class="stats" aria-live="polite">
      <div class="stat"><div class="stat-label">Entidades únicas</div><div class="stat-value" id="stat-nodes">0</div></div>
      <div class="stat"><div class="stat-label">Relações</div><div class="stat-value" id="stat-edges">0</div></div>
      <div class="stat"><div class="stat-label">Relações clínicas</div><div class="stat-value" id="stat-clinical">0</div></div>
      <div class="stat"><div class="stat-label">Eventos temporais</div><div class="stat-value" id="stat-time">0</div></div>
    </section>
    <nav class="tabs" aria-label="Visualizações">
      <button class="tab active" data-panel="graph-panel" type="button">Grafo</button>
      <button class="tab" data-panel="timeline-panel" type="button">Sequência de eventos</button>
      <button class="tab" data-panel="relations-panel" type="button">Relações</button>
    </nav>
    <section class="panel active" id="graph-panel">
      <div class="graph-grid">
        <div class="graph-stage">
          <div class="stage-head"><div><div class="stage-title" id="graph-title">Grafo do caso</div><div class="stage-caption">Arraste para mover, use a roda para ampliar e clique nos nós.</div><div class="stage-caption" id="graph-summary"></div></div><div class="field graph-filter"><label for="graph-relation-filter">Relações exibidas</label><select id="graph-relation-filter"><option value="entity">Entre entidades</option><option value="clinical">Clínicas</option><option value="temporal">Temporais</option><option value="structural">Com o caso</option><option value="all">Todas</option></select></div></div>
          <div class="legend-bar"><div class="legend" id="legend"></div><div class="legend" aria-label="Tipos de relação"><span class="legend-item"><span class="line-key" style="--key-color:var(--relation-treats)"></span>TREATS</span><span class="legend-item"><span class="line-key" style="--key-color:var(--relation-indicates)"></span>INDICATES</span><span class="legend-item"><span class="line-key before" style="--key-color:var(--relation-before)"></span>BEFORE</span><span class="legend-item"><span class="line-key structural" style="--key-color:var(--relation-structural)"></span>Com o caso</span></div></div>
          <div class="canvas-wrap"><svg id="graph-svg" viewBox="0 0 1200 700" role="img" aria-label="Grafo clínico interativo"></svg></div>
        </div>
        <aside class="detail" id="detail"><div class="empty"><div><div class="empty-mark">◎</div><strong>Selecione um nó</strong><p>Os atributos, a dose, o tempo e a frase de origem aparecerão aqui.</p></div></div></aside>
      </div>
    </section>
    <section class="panel" id="timeline-panel">
      <div class="timeline-wrap">
        <div class="timeline-tools"><div><div class="timeline-title">Sequência de eventos</div><div class="stage-caption">Ordem temporal parcial baseada somente em expressões de tempo e relações BEFORE.</div></div><label class="check"><input id="show-untimed" type="checkbox"> Também mostrar eventos sem posição temporal</label></div>
        <p class="timeline-disclaimer"><strong>Importante:</strong> a ordem em que uma informação aparece no texto não implica que ela tenha ocorrido antes ou depois de outra.</p>
        <h3 class="timeline-group-title">Ordem temporal identificada</h3>
        <div class="timeline" id="timeline"></div>
        <section class="untimed-block" id="untimed-block" hidden>
          <h3 class="timeline-group-title">Eventos sem posição temporal definida</h3>
          <div class="stage-caption">Exibidos abaixo apenas na ordem em que foram mencionados no relato.</div>
          <div class="timeline" id="untimed-timeline"></div>
        </section>
      </div>
    </section>
    <section class="panel" id="relations-panel">
      <div class="relations-wrap"><div class="relation-tools"><div><div class="timeline-title">Relações extraídas</div><div class="stage-caption">Cada linha preserva a frase usada como evidência.</div></div><div class="field"><label for="relation-filter">Tipo</label><select id="relation-filter"><option value="">Todas</option></select></div></div><div class="table-scroll"><table class="relations"><thead><tr><th>Origem</th><th>Relação</th><th>Destino</th><th>Evidência</th></tr></thead><tbody id="relations-body"></tbody></table></div></div>
    </section>
  </main>
</div>
<script>
const RAW_NODES=__NODES_JSON__;
const RAW_EDGES=__EDGES_JSON__;
const COLORS={Case:'var(--case)',Symptom:'var(--symptom)',Exam:'var(--exam)',Condition:'var(--condition)',Treatment:'var(--treatment)'};
const TYPE_LABEL={Case:'Caso',Symptom:'Sintoma',Exam:'Exame',Condition:'Condição',Treatment:'Tratamento'};
const SPECIAL=new Set(['TREATS','INDICATES','BEFORE']);
const state={caseId:'',query:'',relationMode:'entity',scale:1,tx:0,ty:0,selected:null};
const byId=new Map(RAW_NODES.map(n=>[n.node_id,n]));
const caseIds=[...new Set(RAW_NODES.filter(n=>n.type==='Case').map(n=>n.case_id))].sort();
const el=id=>document.getElementById(id);
const escapeHtml=value=>String(value??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const truncate=(value,size=24)=>value.length>size?value.slice(0,size-1)+'…':value;

function init(){
  el('case-select').innerHTML=caseIds.map(id=>`<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`).join('');
  state.caseId=caseIds[0]||'';
  const relations=[...new Set(RAW_EDGES.map(e=>e.relation))].sort();
  el('relation-filter').innerHTML+=""+relations.map(r=>`<option value="${r}">${r}</option>`).join('');
  el('legend').innerHTML=['Symptom','Exam','Condition','Treatment'].map(type=>`<span class="legend-item"><span class="dot" style="--dot:${COLORS[type]}"></span>${TYPE_LABEL[type]}</span>`).join('');
  el('case-select').addEventListener('change',e=>{state.caseId=e.target.value;state.selected=null;resetView();renderAll()});
  el('search-input').addEventListener('input',e=>{state.query=e.target.value.trim().toLowerCase();renderGraph()});
  el('graph-relation-filter').addEventListener('change',e=>{state.relationMode=e.target.value;state.selected=null;resetView();renderGraph();renderCaseDetail()});
  el('reset-button').addEventListener('click',()=>{state.query='';state.relationMode='entity';el('search-input').value='';el('graph-relation-filter').value='entity';state.selected=null;resetView();renderAll()});
  el('show-untimed').addEventListener('change',renderTimeline);
  el('relation-filter').addEventListener('change',renderRelations);
  el('theme-button').addEventListener('click',()=>{const root=document.documentElement;root.dataset.theme=root.dataset.theme==='dark'?'':'dark'});
  document.querySelectorAll('.tab').forEach(tab=>tab.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t===tab));
    document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id===tab.dataset.panel));
  }));
  setupPanZoom();renderAll();
}

function caseData(){
  const nodes=RAW_NODES.filter(n=>n.case_id===state.caseId);
  const ids=new Set(nodes.map(n=>n.node_id));
  return {nodes,edges:RAW_EDGES.filter(e=>e.case_id===state.caseId&&ids.has(e.source_id)&&ids.has(e.target_id))};
}

function aggregate(rawNodes,rawEdges){
  const groups=new Map(),originalToGroup=new Map();
  rawNodes.forEach(node=>{
    const key=node.type==='Case'?node.node_id:`${node.type}|${node.label}`;
    if(!groups.has(key))groups.set(key,{...node,id:key,count:0,occurrences:[],attributesList:[]});
    const group=groups.get(key);group.count++;group.occurrences.push(node);group.attributesList.push(node.attributes||{});originalToGroup.set(node.node_id,key);
  });
  const edgeMap=new Map();
  rawEdges.forEach(edge=>{
    const source=originalToGroup.get(edge.source_id),target=originalToGroup.get(edge.target_id);if(!source||!target)return;
    const key=`${source}|${edge.relation}|${target}`;
    if(!edgeMap.has(key))edgeMap.set(key,{...edge,id:key,source,target,count:0,evidenceList:[]});
    const item=edgeMap.get(key);item.count++;if(edge.evidence&&!item.evidenceList.includes(edge.evidence))item.evidenceList.push(edge.evidence);
  });
  return {nodes:[...groups.values()],edges:[...edgeMap.values()]};
}

function layoutNodes(nodes){
  const result=new Map(),caseNode=nodes.find(n=>n.type==='Case');
  if(caseNode)result.set(caseNode.id,{x:115,y:350,w:126,h:126});
  const columns={Symptom:330,Exam:550,Condition:790,Treatment:1030};
  Object.entries(columns).forEach(([type,x])=>{
    const list=nodes.filter(n=>n.type===type).sort((a,b)=>a.label.localeCompare(b.label));
    const cols=list.length>11?2:1,rows=Math.ceil(list.length/cols),gap=Math.min(58,570/Math.max(rows-1,1));
    list.forEach((node,index)=>{const col=Math.floor(index/rows),row=index%rows;result.set(node.id,{x:x+(col-(cols-1)/2)*135,y:65+row*gap,w:122,h:38})});
  });
  return result;
}

function renderAll(){renderStats();renderGraph();renderTimeline();renderRelations();if(!state.selected)renderCaseDetail()}
function renderStats(){
  const {nodes,edges}=caseData(),unique=new Set(nodes.filter(n=>n.type!=='Case').map(n=>`${n.type}|${n.label}`));
  el('stat-nodes').textContent=unique.size;el('stat-edges').textContent=edges.length;el('stat-clinical').textContent=edges.filter(e=>SPECIAL.has(e.relation)&&e.relation!=='BEFORE').length;el('stat-time').textContent=nodes.filter(n=>n.type!=='Case'&&(n.attributes?.time?.length||edges.some(e=>e.relation==='BEFORE'&&(e.source_id===n.node_id||e.target_id===n.node_id)))).length;
  el('graph-title').textContent=`Grafo do caso ${state.caseId}`;
}

function svgEl(name,attrs={}){const node=document.createElementNS('http://www.w3.org/2000/svg',name);Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,v));return node}
function graphEdgesForMode(edges){
  if(state.relationMode==='clinical')return edges.filter(edge=>edge.relation==='TREATS'||edge.relation==='INDICATES');
  if(state.relationMode==='temporal')return edges.filter(edge=>edge.relation==='BEFORE');
  if(state.relationMode==='structural')return edges.filter(edge=>byId.get(edge.source_id)?.type==='Case');
  if(state.relationMode==='entity')return edges.filter(edge=>byId.get(edge.source_id)?.type!=='Case');
  return edges;
}
function relationStyle(relation){return relation==='TREATS'?'treats':relation==='INDICATES'?'indicates':relation==='BEFORE'?'before':'structural'}
function edgePath(a,b){
  const horizontal=Math.abs(b.x-a.x)>45;
  if(!horizontal){const direction=b.y>=a.y?1:-1,startY=a.y+direction*a.h/2,endY=b.y-direction*b.h/2,bend=a.x+90;return `M ${a.x} ${startY} C ${bend} ${startY}, ${bend} ${endY}, ${b.x} ${endY}`}
  const direction=b.x>=a.x?1:-1,startX=a.x+direction*a.w/2,endX=b.x-direction*b.w/2,mid=(startX+endX)/2;
  return `M ${startX} ${a.y} C ${mid} ${a.y}, ${mid} ${b.y}, ${endX} ${b.y}`;
}
function renderGraph(){
  const svg=el('graph-svg');svg.replaceChildren();
  const raw=caseData(),visibleRawEdges=graphEdgesForMode(raw.edges),visibleIds=new Set(visibleRawEdges.flatMap(edge=>[edge.source_id,edge.target_id]));
  const visibleRawNodes=state.relationMode==='all'?raw.nodes:raw.nodes.filter(node=>visibleIds.has(node.node_id));
  const data=aggregate(visibleRawNodes,visibleRawEdges),positions=layoutNodes(data.nodes);
  el('graph-summary').textContent=visibleRawEdges.length?`${visibleRawEdges.length} ocorrências em ${data.edges.length} conexões únicas`:'Nenhuma relação deste grupo no caso selecionado';
  const defs=svgEl('defs');
  [['structural','var(--relation-structural)'],['treats','var(--relation-treats)'],['indicates','var(--relation-indicates)'],['before','var(--relation-before)']].forEach(([name,color])=>{const marker=svgEl('marker',{id:`arrow-${name}`,viewBox:'0 0 10 10',refX:'9',refY:'5',markerWidth:'7',markerHeight:'7',orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color}));defs.append(marker)});svg.append(defs);
  const viewport=svgEl('g',{id:'viewport',transform:`translate(${state.tx} ${state.ty}) scale(${state.scale})`});svg.append(viewport);
  const edgeLayer=svgEl('g'),nodeLayer=svgEl('g');viewport.append(edgeLayer,nodeLayer);
  data.edges.forEach(edge=>{const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)return;const style=relationStyle(edge.relation),line=svgEl('path',{d:edgePath(a,b),class:`edge ${style}`,'marker-end':`url(#arrow-${style})`});line.addEventListener('click',()=>showEdge(edge,data));edgeLayer.append(line);if(SPECIAL.has(edge.relation)){const text=svgEl('text',{x:(a.x+b.x)/2,y:(a.y+b.y)/2-7,class:`edge-label ${style}`,'text-anchor':'middle'});text.textContent=edge.relation+(edge.count>1?` ×${edge.count}`:'');text.addEventListener('click',()=>showEdge(edge,data));edgeLayer.append(text)}});
  if(!data.edges.length){const message=svgEl('text',{x:600,y:350,class:'edge-label','text-anchor':'middle'});message.textContent='Nenhuma relação deste grupo neste caso';viewport.append(message)}
  data.nodes.forEach(node=>{const p=positions.get(node.id);if(!p)return;const g=svgEl('g',{class:`node ${state.selected===node.id?'selected':''}`,style:`--node-color:${COLORS[node.type]}`});g.dataset.id=node.id;const shape=node.type==='Case'?svgEl('circle',{cx:p.x,cy:p.y,r:58}):svgEl('rect',{x:p.x-p.w/2,y:p.y-p.h/2,width:p.w,height:p.h,rx:11});g.append(shape);const label=svgEl('text',{x:p.x,y:p.y+(node.type==='Case'?0:1),class:'label','text-anchor':'middle','dominant-baseline':'middle'});const queryMatch=state.query&&`${node.label} ${node.mention_text}`.toLowerCase().includes(state.query);label.textContent=truncate(node.type==='Case'?'CASO':node.label,node.type==='Case'?12:19);if(state.query&&!queryMatch&&node.type!=='Case')g.style.opacity='.18';g.append(label);if(node.count>1){const meta=svgEl('text',{x:p.x,y:p.y+(node.type==='Case'?23:25),class:'meta','text-anchor':'middle'});meta.textContent=`${node.count} menções`;g.append(meta)}g.addEventListener('click',()=>{state.selected=node.id;renderGraph();showNode(node)});nodeLayer.append(g)});
  applyTransform();
}

function resetView(){state.scale=1;state.tx=0;state.ty=0;applyTransform()}
function applyTransform(){const viewport=el('viewport');if(viewport)viewport.setAttribute('transform',`translate(${state.tx} ${state.ty}) scale(${state.scale})`)}
function setupPanZoom(){
  const svg=el('graph-svg');let dragging=false,last=null;
  svg.addEventListener('wheel',event=>{event.preventDefault();state.scale=Math.max(.55,Math.min(2.5,state.scale*(event.deltaY<0?1.1:.9)));applyTransform()},{passive:false});
  svg.addEventListener('pointerdown',event=>{if(event.target.closest('.node'))return;dragging=true;last={x:event.clientX,y:event.clientY};svg.classList.add('dragging');svg.setPointerCapture(event.pointerId)});
  svg.addEventListener('pointermove',event=>{if(!dragging)return;state.tx+=(event.clientX-last.x)*(1200/svg.clientWidth);state.ty+=(event.clientY-last.y)*(700/svg.clientHeight);last={x:event.clientX,y:event.clientY};applyTransform()});
  svg.addEventListener('pointerup',()=>{dragging=false;svg.classList.remove('dragging')});
}

function renderCaseDetail(){const caseNode=caseData().nodes.find(n=>n.type==='Case');if(!caseNode)return;el('detail').innerHTML=`<div class="detail-kicker">Caso selecionado</div><h2>${escapeHtml(caseNode.case_id)}</h2><span class="detail-type"><span class="dot" style="--dot:${COLORS.Case}"></span>Caso clínico</span><div class="detail-section"><h3>Metadados</h3><dl class="kv"><dt>Artigo</dt><dd>${escapeHtml(caseNode.attributes.article_id||'—')}</dd><dt>Idade</dt><dd>${escapeHtml(caseNode.attributes.age||'—')}</dd><dt>Gênero</dt><dd>${escapeHtml(caseNode.attributes.gender||'—')}</dd></dl></div><div class="detail-section"><h3>Título</h3><p>${escapeHtml(caseNode.attributes.title||'—')}</p></div>`}
function showNode(node){
  const attrs=node.attributesList||[node.attributes||{}],merged={};attrs.forEach(item=>Object.entries(item).forEach(([k,v])=>{if(v!==''&&v!=null)merged[k]=v}));
  const evidence=[...new Set(node.occurrences.map(n=>n.evidence).filter(Boolean))].slice(0,3);
  const attrRows=Object.entries(merged).filter(([key])=>!['source'].includes(key)).map(([key,value])=>`<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(Array.isArray(value)?value.join(', '):value)}</dd>`).join('');
  el('detail').innerHTML=`<div class="detail-kicker">Entidade selecionada</div><h2>${escapeHtml(node.label)}</h2><span class="detail-type"><span class="dot" style="--dot:${COLORS[node.type]}"></span>${TYPE_LABEL[node.type]}</span><div class="detail-section"><h3>Ocorrências</h3><dl class="kv"><dt>Menções</dt><dd>${node.count}</dd><dt>Texto</dt><dd>${escapeHtml(node.occurrences.map(n=>n.mention_text).filter((v,i,a)=>a.indexOf(v)===i).join(', '))}</dd>${attrRows}</dl></div><div class="detail-section"><h3>Evidência</h3>${evidence.map(text=>`<p>“${escapeHtml(text)}”</p>`).join('<br>')}</div>`;
}
function showEdge(edge,data){const source=data.nodes.find(n=>n.id===edge.source),target=data.nodes.find(n=>n.id===edge.target);el('detail').innerHTML=`<div class="detail-kicker">Relação selecionada</div><h2>${escapeHtml(edge.relation)}</h2><div class="detail-section"><h3>Conexão</h3><p><strong>${escapeHtml(source?.label||edge.source)}</strong><br>↓ ${escapeHtml(edge.relation)}<br><strong>${escapeHtml(target?.label||edge.target)}</strong></p></div><div class="detail-section"><h3>Evidência</h3>${edge.evidenceList.slice(0,3).map(text=>`<p>“${escapeHtml(text)}”</p>`).join('<br>')}</div>`}

function eventOrder(a,b){return (a.sentence_id-b.sentence_id)||(a.start-b.start)}
function temporalOrder(events,beforeEdges){
  const eventIds=new Set(events.map(node=>node.node_id)),incoming=new Map(events.map(node=>[node.node_id,0])),outgoing=new Map(events.map(node=>[node.node_id,[]]));
  beforeEdges.forEach(edge=>{if(eventIds.has(edge.source_id)&&eventIds.has(edge.target_id)){outgoing.get(edge.source_id).push(edge.target_id);incoming.set(edge.target_id,incoming.get(edge.target_id)+1)}});
  const ready=events.filter(node=>incoming.get(node.node_id)===0).sort(eventOrder),ordered=[];
  while(ready.length){const node=ready.shift();ordered.push(node);outgoing.get(node.node_id).forEach(id=>{incoming.set(id,incoming.get(id)-1);if(incoming.get(id)===0){ready.push(byId.get(id));ready.sort(eventOrder)}})}
  return ordered.length===events.length?ordered:events.slice().sort(eventOrder);
}
function temporalLabel(node,beforeEdges){
  const times=node.attributes?.time||[];if(times.length)return times.join(' · ');
  const incoming=beforeEdges.find(edge=>edge.target_id===node.node_id),outgoing=beforeEdges.find(edge=>edge.source_id===node.node_id);
  if(incoming){const expression=incoming.attributes?.time_expression;return expression||`Depois de ${byId.get(incoming.source_id)?.label||'outro evento'}`}
  if(outgoing)return `Antes de ${byId.get(outgoing.target_id)?.label||'outro evento'}`;
  return 'Ordem temporal parcial';
}
function eventMarkup(node,label){return `<article class="event" data-node="${escapeHtml(node.node_id)}" style="--event-color:${COLORS[node.type]}"><div class="event-card"><div class="time-label">${escapeHtml(label)}</div><div><div class="event-name">${escapeHtml(node.label)}</div><div class="event-evidence">${escapeHtml(node.evidence)}</div></div><div class="type-label">${TYPE_LABEL[node.type]}</div></div></article>`}
function bindTimelineEvents(container){
  container.querySelectorAll('.event').forEach(item=>item.addEventListener('click',()=>{const node=byId.get(item.dataset.node);document.querySelector('[data-panel="graph-panel"]').click();state.relationMode='all';el('graph-relation-filter').value='all';const data=aggregate(caseData().nodes,caseData().edges),group=data.nodes.find(n=>n.occurrences.some(o=>o.node_id===node.node_id));state.selected=group.id;renderGraph();showNode(group)}));
}
function renderTimeline(){
  const {nodes,edges}=caseData(),allEvents=nodes.filter(n=>n.type!=='Case'),beforeEdges=edges.filter(edge=>edge.relation==='BEFORE');
  const temporalIds=new Set(beforeEdges.flatMap(edge=>[edge.source_id,edge.target_id]));
  allEvents.forEach(node=>{if(node.attributes?.time?.length)temporalIds.add(node.node_id)});
  const temporalEvents=temporalOrder(allEvents.filter(node=>temporalIds.has(node.node_id)),beforeEdges);
  const untimedEvents=allEvents.filter(node=>!temporalIds.has(node.node_id)).sort(eventOrder);
  el('timeline').innerHTML=temporalEvents.length?temporalEvents.map(node=>eventMarkup(node,temporalLabel(node,beforeEdges))).join(''):`<div class="no-results"><strong>Nenhuma relação temporal foi identificada neste caso.</strong><br>Não há expressão de tempo associada nem relação BEFORE entre as entidades extraídas.</div>`;
  const showUntimed=el('show-untimed').checked;el('untimed-block').hidden=!showUntimed;
  el('untimed-timeline').innerHTML=showUntimed?(untimedEvents.length?untimedEvents.map(node=>eventMarkup(node,`Frase ${node.sentence_id+1} · ordem textual`)).join(''):`<div class="no-results">Todos os eventos extraídos possuem alguma informação temporal.</div>`):'';
  bindTimelineEvents(el('timeline'));if(showUntimed)bindTimelineEvents(el('untimed-timeline'));
}
function renderRelations(){
  const filter=el('relation-filter').value,{edges}=caseData(),list=edges.filter(e=>!filter||e.relation===filter);
  el('relations-body').innerHTML=list.length?list.map(edge=>{const source=byId.get(edge.source_id),target=byId.get(edge.target_id);return `<tr><td><strong>${escapeHtml(source?.label||edge.source_id)}</strong><br><span class="type-label">${escapeHtml(TYPE_LABEL[source?.type]||'')}</span></td><td class="relation-name">${escapeHtml(edge.relation)}</td><td><strong>${escapeHtml(target?.label||edge.target_id)}</strong><br><span class="type-label">${escapeHtml(TYPE_LABEL[target?.type]||'')}</span></td><td class="evidence-cell">${escapeHtml(edge.evidence||'—')}</td></tr>`}).join(''):`<tr><td colspan="4" class="no-results">Nenhuma relação deste tipo no caso.</td></tr>`;
}
init();
</script>
</body>
</html>'''
    return template.replace("__NODES_JSON__", safe_json(nodes)).replace("__EDGES_JSON__", safe_json(edges))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Gera o explorador HTML do grafo clínico.")
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    nodes = read_records(args.nodes)
    edges = read_records(args.edges)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(nodes, edges), encoding="utf-8")
    print(f"Nós carregados: {len(nodes)}")
    print(f"Arestas carregadas: {len(edges)}")
    print(f"Visualização: {args.output}")


if __name__ == "__main__":
    main()
