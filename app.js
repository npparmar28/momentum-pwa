const refreshBtn = document.getElementById('refreshBtn');
const updatedAt = document.getElementById('updatedAt');
const list = document.getElementById('list');

const JSON_PATH = 'data/trending.json'; // if hosting via GitHub Pages from same repo

async function loadData(){
  try {
    const r = await fetch(JSON_PATH + '?t=' + Date.now());
    if(!r.ok) throw new Error('Not found');
    const data = await r.json();
    render(data);
  } catch (err) {
    console.error(err);
    list.innerHTML = `<div class="card">Unable to load data. Try again later.</div>`;
  }
}

function render(data){
  updatedAt.textContent = 'Updated: ' + (data.generated_at_ist || data.generated_at_utc || '');
  const arr = data.results || [];
  if(arr.length === 0){
    list.innerHTML = `<div class="card">No results yet.</div>`;
    return;
  }
  list.innerHTML = '';
  arr.slice(0, 50).forEach(item => {
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <div class="sym">${item.Symbol} <span class="tag">${item.Matched ? 'Google' : 'NSE'}</span></div>
          <div class="meta">PreOpen Δ: ${item["%ChangePreOpen"] ?? '-'}% • Open: ${item.OpenPrice} • PrevClose: ${item.PrevClose}</div>
        </div>
        <div style="text-align:right">
          <div style="font-weight:700">${item.LTP ?? '-'}</div>
          <div class="meta">Vol: ${item.Volume ?? '-'}</div>
          <div class="meta">%FromOpen: ${item["%FromOpen"] ?? '-'}</div>
        </div>
      </div>
    `;
    list.appendChild(el);
  });
}

refreshBtn.addEventListener('click', loadData);
loadData();
