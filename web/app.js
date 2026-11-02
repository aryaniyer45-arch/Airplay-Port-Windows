// Talks to the Python backend (window.pywebview.api) and drives the UI.
// The receiver stays running while the app is open; "Back to menu" does NOT
// stop it (so it stays instantly discoverable), only "Turn off" does.
'use strict';

const $ = (id) => document.getElementById(id);
let coverTs = 0;
let apiReady = false;
let uiMode = 'menu';          // 'menu' | 'active'
let playing = true;

function fillSelect(sel, items, current) {
  sel.innerHTML = '';
  items.forEach((it) => {
    const o = document.createElement('option');
    o.value = it; o.textContent = it;
    if (it === current) o.selected = true;
    sel.appendChild(o);
  });
}

async function loadConfig() {
  const c = await window.pywebview.api.config();
  $('name').value = c.name || 'Windows PC';
  fillSelect($('preset'), c.presets, c.preset);
  fillSelect($('sink'), c.sinks, c.sink);
  $('fullscreen').checked = !!c.fullscreen;
  $('engineWarn').classList.toggle('hidden', c.engine_found);
}

function opts() {
  return {
    name: $('name').value,
    preset: $('preset').value,
    sink: $('sink').value,
    fullscreen: $('fullscreen').checked,
  };
}

const STATUS = {
  idle:      { cls: 'idle',      text: 'Idle' },
  ready:     { cls: 'ready',     text: 'Ready' },
  connected: { cls: 'connected', text: 'Connected' },
  playing:   { cls: 'playing',   text: 'Playing' },
};

function setChip(status) {
  const s = STATUS[status] || STATUS.idle;
  $('chip').className = 'chip ' + s.cls;
  $('chip-text').textContent = s.text;
}

let lastMeta = {};
function renderMeta(meta) {
  if (JSON.stringify(meta) === JSON.stringify(lastMeta)) return;
  lastMeta = meta;
  $('title').textContent = meta.title || 'Now playing';
  $('artist').textContent = meta.artist || '';
  let album = meta.album || '';
  if (meta.album_artist && meta.album_artist !== meta.artist) {
    album = (album ? album + ' · ' : '') + meta.album_artist;
  }
  $('album').textContent = album;
}

async function refreshCover(ts) {
  if (ts === coverTs) return;
  coverTs = ts;
  if (!ts) { clearCover(); return; }
  const url = await window.pywebview.api.cover();
  if (url) {
    $('art').src = url;
    const bd = $('backdrop');
    bd.style.backgroundImage = `url("${url}")`;
    bd.classList.add('show');
  }
}
function clearCover() {
  $('art').removeAttribute('src');
  $('backdrop').classList.remove('show');
}

function applyState(s) {
  setChip(s.running ? s.status : 'idle');

  const inActive = uiMode === 'active';
  const isPlaying = s.status === 'playing' || (s.meta && s.meta.title);

  $('idle').classList.toggle('hidden', inActive);
  $('activeBar').classList.toggle('hidden', !inActive);
  $('playing').classList.toggle('hidden', !(inActive && isPlaying));

  // menu: show the "receiver on" banner if the engine is live
  $('runningBanner').classList.toggle('hidden', !(uiMode === 'menu' && s.running));
  if (s.running && s.running_name) $('runName').textContent = s.running_name;

  if (inActive) {
    if (isPlaying) { renderMeta(s.meta || {}); }
    else {
      $('activeHint').textContent =
        s.status === 'connected' ? 'Connected — start playing on your iPhone.'
                                 : 'Ready — pick this PC on your iPhone (Screen Mirroring or AirPlay audio).';
    }
  }
  if (!s.running) { lastMeta = {}; }
}

async function tick() {
  if (!apiReady) return;
  try {
    applyState(await window.pywebview.api.state());
    const s2 = await window.pywebview.api.state();
    await refreshCover(s2.cover_ts || 0);
  } catch (e) { /* backend not ready */ }
}

function wire() {
  $('startBtn').onclick = async () => {
    const r = await window.pywebview.api.start(opts());
    if (!r.ok) { alert(r.error || 'Could not start.'); return; }
    uiMode = 'active';
    tick();
  };
  $('backBtn').onclick = () => { uiMode = 'menu'; tick(); };   // keeps engine running
  $('offBtn').onclick = async () => {
    await window.pywebview.api.stop();
    uiMode = 'menu';
    tick();
  };

  // media controls (DACP -> iPhone)
  const media = async (cmd) => {
    const r = await window.pywebview.api.media(cmd);
    if (r && !r.ok && r.error) console.log('media:', r.error);
    return r;
  };
  $('prev').onclick = () => media('previtem');
  $('next').onclick = () => media('nextitem');
  $('playpause').onclick = async () => {
    const r = await media('playpause');
    if (r && r.ok) { playing = !playing; $('playpause').textContent = playing ? '⏸' : '▶'; }
  };

  $('settingsToggle').onclick = () => {
    const box = $('settings');
    box.classList.toggle('hidden');
    $('settingsToggle').textContent = box.classList.contains('hidden') ? 'Settings ▾' : 'Settings ▴';
  };
  const lb = $('locateBtn');
  if (lb) lb.onclick = async () => {
    const r = await window.pywebview.api.locate();
    if (r && r.ok) $('engineWarn').classList.add('hidden');
  };
}

window.addEventListener('pywebviewready', async () => {
  apiReady = true;
  wire();
  await loadConfig();
  tick();
  setInterval(tick, 600);
});
