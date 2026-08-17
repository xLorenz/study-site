/**
 * mindmap.js — canonical interactive mind map engine (D3 v7, radial tree).
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the DATA, COLORS and ICONS consts at the top.
 * Do not modify the functions below — they are the canonical implementation.
 *
 * Layout contract:
 *   - ONE layout pass runs on the FULL tree at startup. Every node receives
 *     a FIXED angle and radius that never change afterwards — collapsing or
 *     expanding a branch only hides/shows nodes at their precomputed spots,
 *     it never re-lays-out or moves the other nodes.
 *   - Links are STRAIGHT lines between the fixed positions of parent and
 *     child (never curves, so they always align exactly with the nodes).
 *   - Decorative concentric rings are drawn as SVG circles centered on the
 *     root, inside the zoomed group: they zoom and pan together with the map.
 *   - Labels sit horizontally beside each node (right side for the right
 *     half of the map, left side for the left half) and are vertically
 *     centered on the node, even when wrapped onto multiple lines.
 *
 * Required HTML (see templates/04-mind-map.md):
 *   #map-container (svg mounts here)
 *   #panelOverlay, #detailPanel (#panelTitle, #panelBreadcrumb, #panelCatBar, #panelBody, #panelClose)
 *   #searchBox (#searchInput, #searchClose)
 *   #tooltip
 *   buttons: #resetBtn, #expandAllBtn, #collapseAllBtn, #searchToggleBtn
 *   badge:   #nodeCount
 */

const DATA = {
  name: 'Subject Name',
  cat: 'root',
  children: [
    {
      name: 'Topic',
      cat: 'topic-key',
      children: [
        {
          name: 'Sub-topic',
          cat: 'topic-key',
          children: [
            {
              name: 'Concept',
              cat: 'topic-key',
              desc: 'Short description (tooltip)',
              detail: '<div class="detail-section"><h3>Title</h3><p>HTML content…</p></div>'
            }
          ]
        }
      ]
    }
  ]
};

/* Keys must match every .cat value used in DATA. Pick hues from the subject theme. */
const COLORS = {};

/* Icon per category (emoji), fallbacks by depth are built in. */
const ICONS = {};

/* ── Fixed layout: one pass on the FULL tree ──
   d3.tree produces (x = angle in radians over [0, 2π], y = radius).
   posMap stores every node's angle/radius once; rendering reads from it, so
   positions never depend on which branches happen to be expanded. */
const RADIUS = 760;   /* radial extent (tree depth spacing) */

const treeLayout = d3.tree().size([2 * Math.PI, RADIUS]);

const fullRoot = d3.hierarchy(DATA);
treeLayout(fullRoot);
/* Unique, stable join keys. d3 coerces join keys to STRINGS, so using the
   data objects themselves (d.data) yields "[object Object]" for every node
   and the join only ever matches ONE element — every update would re-enter
   all nodes (the whole map re-animating). Each node gets a numeric uid
   instead, so stable nodes always merge in place. */
fullRoot.each((d, i) => { d.uid = i; });
const posMap = new Map();
fullRoot.each(d => posMap.set(d.data, { x: d.x, y: d.y }));

const collapsed = new Set();   /* data refs of collapsed (hidden) nodes */

function nodePos(d){
  const p = posMap.get(d.data);
  const a = p.x - Math.PI / 2;
  return [Math.cos(a) * p.y, Math.sin(a) * p.y];
}

function isRightSide(d){
  const p = posMap.get(d.data);
  return Math.cos(p.x - Math.PI / 2) >= 0;
}

function getRadius(d){ return d.depth === 0 ? 30 : d.depth === 1 ? 22 : d.depth === 2 ? 17 : 14; }

function getColor(d){
  let cur = d;
  while (cur){
    if (COLORS[cur.data.cat]) return COLORS[cur.data.cat];
    cur = cur.parent;
  }
  return '#6a6a7a';
}

function getIcon(d){
  if (d.data.icon) return d.data.icon;
  if (ICONS[d.data.cat]) return ICONS[d.data.cat];
  if (d.depth === 0) return '🎓';
  if (d.depth === 1) return '📦';
  return '•';
}

/* ── SVG scaffolding ── */
const container = document.getElementById('map-container');
const svg = d3.select('#map-container').append('svg')
  .attr('width', '100%').attr('height', '100%')
  .style('display', 'block');
const g = svg.append('g');

/* Decorative rings, centered on the root INSIDE the zoomed group: they move
   with the map instead of floating statically in the background. */
const RING_FRACS = [0.25, 0.5, 0.75, 1];
const rings = g.append('g').attr('class', 'rings');
rings.selectAll('circle').data(RING_FRACS).enter().append('circle')
  .attr('class', 'ring')
  .attr('r', f => f * RADIUS)
  .attr('cx', 0).attr('cy', 0);

const linksLayer = g.append('g').attr('class', 'links');
const nodesLayer = g.append('g').attr('class', 'nodes');

const zoom = d3.zoom()
  .scaleExtent([0.15, 6])
  .on('zoom', (event) => { g.attr('transform', event.transform); });
svg.call(zoom)
  .on('dblclick.zoom', null);   /* no double-click-to-zoom: it fights with node clicks */

/* ── Visible subset (fixed positions, no re-layout) ── */
function visibleNodes(){
  const out = [];
  (function walk(d){
    out.push(d);
    if (collapsed.has(d.data) || !d.children) return;
    d.children.forEach(walk);
  })(fullRoot);
  return out;
}

/* ── Search state ── */
let searchActive = false;
let searchQuery = '';

/* ── Render ──
   animate=false makes the change instant (no entrance/exit transitions):
   used for whole-map operations (root toggle, expand all, collapse all) —
   those change dozens of nodes at once, so animating them looks like the
   entire map is re-animating. Only single-branch toggles animate. */
function update(opts){
  opts = opts || {};
  const vis = visibleNodes();
  document.getElementById('nodeCount').textContent = vis.length + ' nodos';
  const visData = new Set(vis.map(d => d.data));

  /* Animation is only for SMALL batches: single-branch toggles reveal/hide a
     handful of nodes. Whenever a change touches many nodes at once (root
     toggle, expand all, collapse all, or any large branch), the change is
     instant — dozens of nodes popping in/out at once reads as "the whole map
     is animating". This is enforced HERE on the batch size, so it holds for
     every code path, no matter who calls update(). */
  const diff = vis.length - nodesLayer.selectAll('g.node').size();
  const animate = opts.animate !== false && Math.abs(diff) <= 12;

  /* Straight links between the fixed positions, tinted by the child's color */
  const links = [];
  vis.forEach(d => { if (d.parent && visData.has(d.parent.data)) links.push([d.parent, d]); });
  const linkSel = linksLayer.selectAll('line').data(links, d => d[1].uid);
  if (animate){
    linkSel.exit().transition().duration(150).style('opacity', 0).remove();
  } else {
    linkSel.exit().remove();
  }
  const linkJoin = linkSel.enter().append('line').attr('class', 'link').style('opacity', 0)
    .merge(linkSel)
    .style('stroke', d => getColor(d[1]))
    .attr('x1', d => nodePos(d[0])[0]).attr('y1', d => nodePos(d[0])[1])
    .attr('x2', d => nodePos(d[1])[0]).attr('y2', d => nodePos(d[1])[1]);
  if (animate){
    linkJoin.transition().duration(200).delay(60).style('opacity', 0.85);
  } else {
    linkJoin.style('opacity', 0.85);
  }

  /* Nodes */
  const nodeSel = nodesLayer.selectAll('g.node').data(vis, d => d.uid);
  if (animate){
    nodeSel.exit().transition().duration(150).style('opacity', 0).remove();
  } else {
    nodeSel.exit().remove();
  }

  const enter = nodeSel.enter().append('g')
    .attr('class', animate ? 'node node-enter' : 'node')
    .style('animation-delay', (d, i) => Math.min(i * 10, 200) + 'ms');

  /* The entrance animation lives on .node-enter only and is removed after it
     finishes, so a collapsed/expanded branch can never re-animate the other
     nodes — stable nodes never carry the animation class. */
  enter.on('animationend', function(){ this.classList.remove('node-enter'); });

  enter.append('circle').attr('class', 'node-circle')
    .attr('r', getRadius);
  enter.append('text').attr('class', 'node-icon')
    .attr('text-anchor', 'middle').attr('dy', '0.34em')
    .text(getIcon);
  enter.append('text').attr('class', 'node-label')
    .attr('text-anchor', d => isRightSide(d) ? 'start' : 'end')
    .attr('x', d => { const r = getRadius(d); return isRightSide(d) ? r + 14 : -(r + 14); })
    .call(wrapLabel, 88);

  enter.merge(nodeSel)
    .style('color', d => getColor(d))
    .attr('transform', d => {
      const p = nodePos(d);
      return 'translate(' + p[0] + ',' + p[1] + ')';
    })
    .classed('match', d => !!searchQuery && (d.data.name + ' ' + (d.data.desc || '')).toLowerCase().includes(searchQuery))
    .classed('root-node', d => d.depth === 0)
    .on('click', (event, d) => toggleNode(d))
    .on('mouseover', (event, d) => showTooltip(event, d))
    .on('mousemove', moveTooltip)
    .on('mouseleave', hideTooltip);
}

/* Label wrapping: tspans only (never a .text() call on top of them), with
   the line block vertically centered on the node. */
function wrapLabel(sel, limit){
  sel.each(function(){
    const node = this;
    /* The name comes from the bound datum — the label is built ONLY from
       tspans, never from a .text() call, so it can never double-render. */
    const text = d3.select(node).datum().data.name;
    const words = text.split(/\s+/);
    const lines = [];
    let line = '';
    words.forEach(w => {
      const test = line ? line + ' ' + w : w;
      if (test.length > Math.floor(limit / 6.4)){ lines.push(line); line = w; }
      else { line = test; }
    });
    if (line) lines.push(line);
    node.textContent = '';
    const lh = 11;
    lines.forEach((l, i) => {
      const t = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
      t.setAttribute('x', node.getAttribute('x'));
      t.setAttribute('dy', (i === 0 ? -(lines.length - 1) * lh / 2 : lh) + 'px');
      t.textContent = l;
      node.appendChild(t);
    });
  });
}

/* ── Interactions ── */
function toggleNode(d){
  if (d.children || collapsed.has(d.data)){
    if (collapsed.has(d.data)) collapsed.delete(d.data);
    else collapsed.add(d.data);
    /* Whole-map toggles (the root) change 30+ nodes at once — instant,
       no animation. Only single-branch toggles animate. */
    update({ animate: d.depth !== 0 });
  }
  if (d.data.desc || d.data.detail) openDetail(d);
}

function openDetail(d){
  const crumbs = [];
  let cur = d;
  while (cur){ crumbs.unshift(cur.data.name); cur = cur.parent; }
  document.getElementById('panelTitle').textContent = (d.depth === 0 ? (getIcon(d) === '🎓' ? '🎓 ' : '') : '') + d.data.name;
  document.getElementById('panelBreadcrumb').textContent = crumbs.join(' › ');
  document.getElementById('panelCatBar').style.background = getColor(d);
  const body = document.getElementById('panelBody');
  let html = '';
  if (d.data.desc) html += '<div class="panel-desc">' + d.data.desc + '</div>';
  if (d.data.detail) html += '<div class="panel-detail">' + d.data.detail + '</div>';
  body.innerHTML = html;
  document.getElementById('panelOverlay').classList.add('visible');
  document.getElementById('detailPanel').classList.add('open');
  renderMath();
}

/* ── Math: KaTeX with unicode fallback (canonical) ── */
function renderMath(){
  if (window.renderMathInElement){
    try {
      renderMathInElement(document.body, {
        delimiters: [
          { left: '$$', right: '$$', display: false },
          { left: '$', right: '$', display: false },
          { left: '\\(', right: '\\)', display: false }
        ],
        throwOnError: false
      });
      return;
    } catch (e){}
  }
  if (!katexTried) return;
  stripMathMarkers();
}

function stripMathMarkers(){
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(n => {
    if (n.parentElement && (n.parentElement.tagName === 'SCRIPT' || n.parentElement.tagName === 'STYLE')) return;
    const t = n.nodeValue;
    if (t.indexOf('$') !== -1) n.nodeValue = t.replace(/\$\$[^$]*?\$\$/g, '').replace(/\$[^$\n]*?\$/g, '').replace(/\\\([^)]*?\\\)/g, '');
  });
}

let katexTried = false;
const KATEX_CDNS = [
  { css: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css', js: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js', auto: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js' },
  { css: 'https://unpkg.com/katex@0.16.11/dist/katex.min.css', js: 'https://unpkg.com/katex@0.16.11/dist/katex.min.js', auto: 'https://unpkg.com/katex@0.16.11/dist/contrib/auto-render.min.js' },
  { css: 'https://cdnjs.cloudflare.com/ajax/libs/katex/0.16.11/katex.min.css', js: 'https://cdnjs.cloudflare.com/ajax/libs/katex/0.16.11/katex.min.js', auto: 'https://cdnjs.cloudflare.com/ajax/libs/katex/0.16.11/contrib/auto-render.min.js' }
];
let katexCdnIdx = 0;
function loadKaTeX(){
  if (katexTried) return;
  katexTried = true;
  const cdn = KATEX_CDNS[katexCdnIdx];
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = cdn.css;
  document.head.appendChild(css);
  let remaining = 2;
  let failed = false;
  const done = () => {
    remaining--;
    if (remaining === 0 && !failed){ renderMath(); }
    else if (failed) tryNext();
  };
  const fail = () => { failed = true; tryNext(); };
  const tryNext = () => {
    if (katexCdnIdx + 1 < KATEX_CDNS.length){
      katexCdnIdx++;
      katexTried = false;
      loadKaTeX();
    } else {
      renderMath();
    }
  };
  const main = document.createElement('script');
  main.src = cdn.js;
  main.onload = done;
  main.onerror = fail;
  document.head.appendChild(main);
  const auto = document.createElement('script');
  auto.src = cdn.auto;
  auto.onload = done;
  auto.onerror = fail;
  document.head.appendChild(auto);
  /* Safety: never leave formulas unrendered — fallback after 5s */
  setTimeout(() => { if (!window.renderMathInElement){ failed = true; tryNext(); } }, 5000);
  setTimeout(() => { if (!window.renderMathInElement) stripMathMarkers(); }, 6000);
}

function closePanel(){
  document.getElementById('panelOverlay').classList.remove('visible');
  document.getElementById('detailPanel').classList.remove('open');
}

function expandAll(){
  collapsed.clear();
  update({ animate: false });
}

function collapseAll(){
  fullRoot.each(d => { if (d.depth >= 1 && d.children) collapsed.add(d.data); });
  update({ animate: false });
}

function resetZoom(){
  const w = container.clientWidth, h = container.clientHeight;
  const s = Math.min(w, h) / (2 * RADIUS * 1.06);
  svg.transition().duration(450).call(
    zoom.transform, d3.zoomIdentity.translate(w / 2, h / 2).scale(s)
  );
}

function toggleSearch(){
  searchActive = !searchActive;
  document.getElementById('searchBox').classList.toggle('open', searchActive);
  if (searchActive){
    const input = document.getElementById('searchInput');
    input.value = '';
    input.focus();
  } else {
    clearMatch();
  }
}

function onSearch(){
  searchQuery = document.getElementById('searchInput').value.trim().toLowerCase();
  update();
}

function clearMatch(){
  searchQuery = '';
  document.getElementById('searchInput').value = '';
  update();
}

function showTooltip(event, d){
  if (!d.data.desc) return;
  const t = document.getElementById('tooltip');
  t.textContent = d.data.desc;
  t.classList.add('visible');
  moveTooltip(event);
}

function moveTooltip(event){
  const t = document.getElementById('tooltip');
  const pad = 14;
  const x = Math.min(event.clientX + pad, window.innerWidth - t.offsetWidth - 12);
  const y = Math.min(event.clientY + pad, window.innerHeight - t.offsetHeight - 12);
  t.style.left = x + 'px';
  t.style.top = y + 'px';
}

function hideTooltip(){
  document.getElementById('tooltip').classList.remove('visible');
}

/* ── Wire controls & keyboard ── */
document.getElementById('resetBtn').addEventListener('click', resetZoom);
document.getElementById('expandAllBtn').addEventListener('click', expandAll);
document.getElementById('collapseAllBtn').addEventListener('click', collapseAll);
document.getElementById('searchToggleBtn').addEventListener('click', toggleSearch);
document.getElementById('searchClose').addEventListener('click', toggleSearch);
document.getElementById('searchInput').addEventListener('input', onSearch);
document.getElementById('panelClose').addEventListener('click', closePanel);
document.getElementById('panelOverlay').addEventListener('click', closePanel);
document.addEventListener('keydown', e => {
  if (e.key === '/' && !searchActive && document.activeElement.tagName !== 'INPUT'){
    e.preventDefault();
    toggleSearch();
  } else if (e.key === 'Escape'){
    if (searchActive) toggleSearch();
    else closePanel();
  }
});

/* ── Go ── */
update();
resetZoom();
loadKaTeX();