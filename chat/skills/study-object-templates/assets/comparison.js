/**
 * comparison.js - canonical comparison matrix engine.
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the CONCEPTS and DIMENSIONS consts at the top.
 * Do not modify the functions below - they are the canonical implementation.
 *
 * Data model (see templates/14-comparison-matrix.md):
 *   CONCEPTS: [{ key:'newton', label:'Mecanica de Newton', color:'#5b7fc4' }]
 *   DIMENSIONS: [{ id:'d1', label:'Fuerzas que intervienen',
 *                  cells: { newton:'<p>...</p>', energia:'<p>...</p>' } }]
 *     - cells is keyed by CONCEPTS[].key; every concept needs a cell for
 *       every dimension (write '-' or 'No aplica' when there is nothing).
 *
 * Rules enforced here:
 *   - Matrix: rows = dimensions, columns = concepts. First column (dimension
 *     label) is sticky on horizontal scroll. Long cells collapse to two
 *     lines and expand in place on click ("expandir/contraer").
 *   - Column focus buttons: hovering/focusing a concept column dims the
 *     others; clicking a focus chip pins it (click again to unpin).
 *   - Search filters rows whose label OR any cell contains the text.
 *   - Print: full matrix, every cell expanded, focus pins cleared.
 *
 * Required HTML (see templates/14-comparison-matrix.md):
 *   #cmpSearch, #cmpCount, #cmpFocusBar, #cmpTable,
 *   #cmpTHead, #cmpTBody, #cmpReset
 */

const CONCEPTS = [
  /* Fill me. { key:'concepto', label:'Concepto', color:'#5b7fc4' } - 2 to 4 columns. */
];

const DIMENSIONS = [
  /* Fill me. { id:'d1', label:'Dimension', cells: { concepto1:'<p>...</p>', concepto2:'<p>...</p>' } } */
];

/* ---- state ---- */
const state = { query: '', focus: null, expanded: new Set() };

const $ = (id) => document.getElementById(id);

function norm(s){
  return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function buildFocusBar(){
  const bar = $('cmpFocusBar');
  bar.innerHTML = '';
  CONCEPTS.forEach(c => {
    const b = document.createElement('button');
    b.className = 'focus-chip';
    b.dataset.k = c.key;
    b.style.setProperty('--fc', c.color);
    b.textContent = c.label;
    b.addEventListener('click', () => {
      state.focus = state.focus === c.key ? null : c.key;
      render();
    });
    bar.appendChild(b);
  });
}

function render(){
  const rows = DIMENSIONS.filter(d => {
    if (state.query === '') return true;
    const hay = norm(d.label + ' ' + CONCEPTS.map(c => d.cells[c.key] || '').join(' '));
    return hay.includes(state.query);
  });

  $('cmpCount').textContent = rows.length + ' de ' + DIMENSIONS.length + ' dimensiones';

  const head = $('cmpTHead');
  head.innerHTML = '<tr><th class="dim-head">Dimensi\u00f3n</th>' +
    CONCEPTS.map(c => '<th class="concept-head" data-k="' + c.key + '" style="--fc:' + c.color + '">' + c.label + '</th>').join('') + '</tr>';

  const body = $('cmpTBody');
  body.innerHTML = '';
  rows.forEach(d => {
    const tr = document.createElement('tr');
    tr.innerHTML = '<th class="dim-label" scope="row">' + d.label + '</th>' +
      CONCEPTS.map(c => {
        const cell = d.cells[c.key] || '<p class="muted">-</p>';
        const expanded = state.expanded.has(d.id + ':' + c.key);
        const t = document.createElement('div');
        t.innerHTML = cell;
        const text = (t.textContent || '').trim();
        const needsClip = text.length > 160;
        return '<td class="cell" data-k="' + c.key + '">' +
          '<div class="cell-body' + (expanded ? ' expanded' : '') + '">' + cell + '</div>' +
          (needsClip ? '<button class="cell-toggle">' + (expanded ? 'Contraer' : 'Expandir') + '</button>' : '') +
        '</td>';
      }).join('');
    body.appendChild(tr);
  });

  body.querySelectorAll('.cell-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const td = btn.closest('td');
      const dim = td.closest('tr').querySelector('.dim-label').textContent;
      const d = rows.find(r => r.label === dim);
      const c = td.dataset.k;
      const key = d.id + ':' + c;
      if (state.expanded.has(key)) state.expanded.delete(key);
      else state.expanded.add(key);
      render();
    });
  });

  document.querySelectorAll('#cmpTable th.concept-head').forEach(th => {
    th.addEventListener('click', () => {
      state.focus = state.focus === th.dataset.k ? null : th.dataset.k;
      render();
    });
  });

  body.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('mouseenter', () => {
      tr.querySelectorAll('.cell').forEach(td => {
        td.classList.toggle('dimmed', !!state.focus && td.dataset.k !== state.focus);
      });
    });
    tr.addEventListener('mouseleave', () => {
      tr.querySelectorAll('.cell').forEach(td => td.classList.remove('dimmed'));
    });
  });

  document.querySelectorAll('.concept-head, .cell').forEach(el => {
    el.classList.toggle('dimmed', !!state.focus && el.dataset.k !== state.focus);
  });
  document.querySelectorAll('.focus-chip').forEach(chip => {
    chip.classList.toggle('active', chip.dataset.k === state.focus);
  });
  renderMath();
}

/* ---- Math: KaTeX with unicode fallback (canonical) ---- */
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
      document.querySelectorAll('.formula,.cc-formula,.code-block').forEach(el => {
        if (el.querySelector('.katex')){
          let seen = false;
          el.childNodes.forEach(n => {
            if (n.nodeType === 3){ if (seen) n.nodeValue = ''; }
            else if (n.nodeType === 1 && (n.classList.contains('katex') || n.querySelector('.katex'))) seen = true;
          });
        }
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
  setTimeout(() => { if (!window.renderMathInElement){ failed = true; tryNext(); } }, 5000);
  setTimeout(() => { if (!window.renderMathInElement) stripMathMarkers(); }, 6000);
}

document.addEventListener('DOMContentLoaded', () => {
  buildFocusBar();
  $('cmpSearch').addEventListener('input', (e) => { state.query = e.target.value.trim(); render(); });
  $('cmpReset').addEventListener('click', () => {
    state.query = '';
    state.focus = null;
    state.expanded = new Set();
    $('cmpSearch').value = '';
    render();
  });
  render();
  loadKaTeX();
});