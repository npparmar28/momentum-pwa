const refreshBtn = document.getElementById('refreshBtn');
const updatedAt = document.getElementById('updatedAt');
const list = document.getElementById('list');

// 🔗 Path to JSON file (same repo)
const JSON_PATH = 'data/trending.json';

async function loadData(showLoader = true) {
  if (showLoader) {
    list.innerHTML = `<div class="card">⏳ Loading latest data...</div>`;
  }
  try {
    const res = await fetch(`${JSON_PATH}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    render(data);
  } catch (err) {
    console.error(err);
    list.innerHTML = `<div class="card">⚠️ Unable to load data. Check your internet or try again later.</div>`;
  }
}

function render(data) {
  updatedAt.textContent = 'Updated: ' + (data.generated_at_ist || data.generated_at_utc || '(unknown)');
  const arr = data.results || [];

  if (arr.length === 0) {
    list.innerHTML = `<div class="card">No data found yet.</div>`;
    return;
  }

  list.innerHTML = '';
  arr.slice(0, 50).forEach(item => {
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
        <div>
          <div class="sym">${item.Symbol} ${item.Matched ? '<span class="tag">Google</span>' : ''}</div>
          <div class="meta">
            Pre-open Δ: ${item["%ChangePreOpen"] ?? '-'}% • 
            Open: ${item.OpenPrice ?? '-'} • 
            Prev: ${item.PrevClose ?? '-'}
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-weight:700;font-size:15px">${item.LTP ?? '-'}</div>
          <div class="meta">Vol: ${item.Volume ?? '-'}</div>
          <div class="meta">%FromOpen: ${item["%FromOpen"] ?? '-'}</div>
        </div>
      </div>
    `;
    list.appendChild(el);
  });
}

// 🌀 Refresh button — always clickable
refreshBtn.addEventListener('click', () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = 'Refreshing...';
  loadData().finally(() => {
    setTimeout(() => {
      refreshBtn.disabled = false;
      refreshBtn.textContent = 'Refresh';
    }, 600);
  });
});

// Initial load
loadData();
