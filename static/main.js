const elMessages = document.getElementById('messages');
const elInput = document.getElementById('input');
const elSend = document.getElementById('send');
const elRtMode = document.getElementById('rtMode');
const elNewChat = document.getElementById('newChat');
const elCfg = document.getElementById('cfg');
const elMcpRt = document.getElementById('mcpRt');
const elMcpCard = document.getElementById('mcpCard');
const elMcpTool = document.getElementById('mcpTool');
const elMcpPanel = document.getElementById('mcpPanel');
const elMcpToggle = document.getElementById('mcpToggle');
const elMcpClear = document.getElementById('mcpClear');

// Limit MCP buffer to avoid flooding UI
const MCP_MAX_CHARS = 50_000; // ~50KB text
const MCP_MAX_EVENTS = 50; // last 50 events
let mcpEventCount = 0;
function mcpAppend(text) {
  if (!text) return;
  // Cap by events
  mcpEventCount += 1;
  if (mcpEventCount > MCP_MAX_EVENTS) {
    // Drop oldest half to keep it responsive
    const content = elMcpRt.textContent;
    if (content.length > 0) {
      const mid = Math.floor(content.length / 2);
      elMcpRt.textContent = content.slice(mid);
    }
    mcpEventCount = Math.floor(MCP_MAX_EVENTS / 2);
  }
  // Cap by chars
  elMcpRt.textContent += (elMcpRt.textContent ? '\n\n' : '') + text;
  if (elMcpRt.textContent.length > MCP_MAX_CHARS) {
    elMcpRt.textContent = elMcpRt.textContent.slice(-MCP_MAX_CHARS);
  }
}

// Maintain latest event per tool
const mcpByTool = new Map();
function updateToolSelector() {
  const tools = Array.from(mcpByTool.keys());
  const sel = elMcpTool;
  const curr = sel.value;
  sel.innerHTML = '';
  for (const t of tools) {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  }
  if (tools.length && (!curr || !tools.includes(curr))) {
    sel.value = tools[tools.length - 1];
  } else if (curr) {
    sel.value = curr;
  }
}

function renderToolCard() {
  const tool = elMcpTool.value;
  const ev = mcpByTool.get(tool);
  if (!tool || !ev) { elMcpCard.innerHTML = ''; return; }
  const { tool: t, response, function: fn } = ev;
  let html = '';
  // Per-tool concise rendering
  if (t === 'full_market_picture' || t === 'full_market_picture' || t === 'full_market_picture') {
    const snap = (response && response.marketSnapshot) || {};
    const sig = (response && response.signal) || {};
    html = `
      <div class="kv"><span>Mid</span><b>${snap.mid ?? '-'}</b></div>
      <div class="kv"><span>Funding</span><b>${snap.funding ?? '-'}</b></div>
      <div class="kv"><span>OI</span><b>${snap.OI ?? '-'}</b></div>
      <div class="kv"><span>Premium</span><b>${snap.premium ?? '-'}</b></div>
      <div class="kv"><span>Signal</span><b>${sig.label ?? '-'} ${sig.score != null ? `(${sig.score})` : ''}</b></div>
    `;
  } else if (t === 'orderbook') {
    const d = (response && response.bids) ? response : (response && response.data) ? response.data : response;
    const bids = (d && d.bids) ? d.bids.slice(0, 5) : [];
    const asks = (d && d.asks) ? d.asks.slice(0, 5) : [];
    const row = (r) => `<div class="row"><span>${r[0]}</span><span>${r[1]}</span></div>`;
    html = `
      <div class="section"><h4>Bids</h4>${bids.map(row).join('') || '<div class="muted">No data</div>'}</div>
      <div class="section"><h4>Asks</h4>${asks.map(row).join('') || '<div class="muted">No data</div>'}</div>
    `;
  } else if (t === 'trades') {
    const arr = Array.isArray(response) ? response : (response && response.data) ? response.data : [];
    const rows = arr.slice(-10).map(tr => `<div class="row"><span>${tr.time || tr.t || ''}</span><span>${tr.px || tr.price || ''}</span><span>${tr.sz || tr.size || ''}</span></div>`).join('');
    html = rows || '<div class="muted">No data</div>';
  } else {
    // Fallback: short JSON
    let body = JSON.stringify(response ?? ev, null, 2) || '';
    if (body.length > 2000) body = body.slice(0, 2000) + '\n…trimmed…';
    html = `<pre>${body}</pre>`;
  }
  elMcpCard.innerHTML = `
    <div class="mcp-card-header">${t}${fn ? ` · ${fn}` : ''}</div>
    <div class="mcp-card-body">${html}</div>
  `;
}

function addMessage(role, text, meta) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  if (role === 'assistant') {
    const bubble = document.createElement('div');
    bubble.className = 'assistant-bubble';
    bubble.textContent = text;
    wrap.appendChild(bubble);
    if (meta) {
      const m = document.createElement('div');
      m.className = 'meta';
      m.textContent = meta;
      wrap.appendChild(m);
    }
  } else {
    wrap.textContent = text;
  }
  elMessages.appendChild(wrap);
  elMessages.scrollTop = elMessages.scrollHeight;
}

async function send() {
  const text = elInput.value.trim();
  if (!text) return;
  addMessage('user', text);
  elInput.value = '';
  const btnText = elSend.textContent;
  elSend.textContent = '…';
  elSend.disabled = true;
  try {
    // Stream tokens via SSE; also show MCP/RT panel
    elMcpRt.textContent = '';
    mcpEventCount = 0;
    mcpByTool.clear();
    updateToolSelector();
    renderToolCard();
    const sse = new EventSource(`/api/chat_stream?` + new URLSearchParams({ message: text, rt_mode: elRtMode.value }));
    let acc = '';
    sse.addEventListener('rt', (ev) => {
      try { mcpAppend(ev.data || ''); } catch (_) {}
    });
    sse.addEventListener('mcp', (ev) => {
      try {
        const d = JSON.parse(ev.data);
        // Track latest per tool and re-render selected card
        const tool = d.tool || 'unknown';
        mcpByTool.set(tool, d);
        updateToolSelector();
        renderToolCard();
      } catch (_) {}
    });
    sse.addEventListener('draft', (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (!elMessages.lastChild || !elMessages.lastChild.classList.contains('assistant')) {
          addMessage('assistant', d);
        } else {
          elMessages.lastChild.querySelector('.assistant-bubble').textContent = d;
        }
      } catch (_) {}
    });
    sse.addEventListener('token', (ev) => {
      const t = JSON.parse(ev.data);
      if (!elMessages.lastChild || !elMessages.lastChild.classList.contains('assistant')) {
        addMessage('assistant', '');
      }
      acc += t;
      elMessages.lastChild.querySelector('.assistant-bubble').textContent = acc;
      elMessages.scrollTop = elMessages.scrollHeight;
    });
    sse.addEventListener('error', (ev) => {
      addMessage('assistant', `Error: ${ev.data || ''}`);
    });
    sse.addEventListener('done', () => {
      sse.close();
    });
  } catch (e) {
    addMessage('assistant', `Error: ${e.message}`);
  }
  elSend.textContent = btnText;
  elSend.disabled = false;
}

elSend.addEventListener('click', send);
elInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') send();
});
elNewChat.addEventListener('click', () => {
  elMessages.innerHTML = '';
});

// MCP panel controls
if (elMcpToggle) {
  elMcpToggle.addEventListener('click', () => {
    const collapsed = elMcpPanel.classList.toggle('collapsed');
    elMcpToggle.textContent = collapsed ? 'Show' : 'Hide';
    elMcpToggle.setAttribute('aria-expanded', String(!collapsed));
  });
}
if (elMcpClear) {
  elMcpClear.addEventListener('click', () => {
    elMcpRt.textContent = '';
    mcpEventCount = 0;
    mcpByTool.clear();
    updateToolSelector();
    renderToolCard();
  });
}
if (elMcpTool) {
  elMcpTool.addEventListener('change', renderToolCard);
}

async function loadConfig() {
  try {
    const resp = await fetch('/api/config');
    const data = await resp.json();
    if (data.ok) {
      elCfg.textContent = `${data.model || ''}`;
    }
  } catch (_) {
    elCfg.textContent = '';
  }
}

loadConfig();


