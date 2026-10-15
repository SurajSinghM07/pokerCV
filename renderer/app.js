const state = {
  ws: null,
  connected: false,
  reconnectTimer: null,
  reconnectDelay: 1000,
  maxReconnectDelay: 10000,
  frameCount: 0,
  lastEquity: null,
  settingsOpen: false,
  consoleOpen: false,
};
const WS_URL = 'ws://127.0.0.1:8765';
const $ = (id) => document.getElementById(id);
const dom = {
  canvas: $('video-canvas'),
  videoOverlay: $('video-overlay'),
  fpsBadge: $('fps-badge'),
  fpsValue: $('fps-value'),
  connectionStatus: $('connection-status'),
  statusDot: document.querySelector('.status-dot'),
  statusText: document.querySelector('.status-text'),
  equityWaiting: $('equity-waiting'),
  equityData: $('equity-data'),
  barWin: $('bar-win'),
  barTie: $('bar-tie'),
  barLose: $('bar-lose'),
  valWin: $('val-win'),
  valTie: $('val-tie'),
  valLose: $('val-lose'),
  stackedWin: $('stacked-win'),
  stackedTie: $('stacked-tie'),
  stackedLose: $('stacked-lose'),
  handRank: $('hand-rank'),
  simInfo: $('sim-info'),
  computingIndicator: $('computing-indicator'),
  actionRec: $('action-rec'),
  actionBadge: $('action-badge'),
  phaseBadge: $('phase-badge'),
  playerCards: $('player-cards'),
  communityCards: $('community-cards'),
  zonePlayer: $('zone-player'),
  zoneCommunity: $('zone-community'),
  settingsToggle: $('settings-toggle'),
  settingsBody: $('settings-body'),
  settingCamera: $('setting-camera'),
  settingCameraDevice: $('setting-camera-device'),
  settingConfidence: $('setting-confidence'),
  settingDebounce: $('setting-debounce'),
  settingSims: $('setting-sims'),
  valConfidence: $('val-confidence'),
  valDebounce: $('val-debounce'),
  valSims: $('val-sims'),
  btnReset: $('btn-reset'),
  btnRestartPython: $('btn-restart-python'),
  consoleToggle: $('console-toggle'),
  consoleBody: $('console-body'),
  consoleOutput: $('console-output'),
  btnMinimize: $('btn-minimize'),
  btnMaximize: $('btn-maximize'),
  btnClose: $('btn-close'),
  appVersion: $('app-version'),
};
const ctx = dom.canvas.getContext('2d');
const frameImage = new Image();
function connect() {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) return;
  logConsole('Connecting to backend...', 'info');
  state.ws = new WebSocket(WS_URL);
  state.ws.binaryType = 'blob';
  state.ws.onopen = () => {
    state.connected = true;
    state.reconnectDelay = 1000;
    setConnectionStatus(true);
    logConsole('Connected to Python backend', 'info');
  };
  state.ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleMessage(data);
    } catch (e) {
    }
  };
  state.ws.onclose = () => {
    state.connected = false;
    setConnectionStatus(false);
    scheduleReconnect();
  };
  state.ws.onerror = () => {
  };
}
function scheduleReconnect() {
  if (state.reconnectTimer) return;
  state.reconnectTimer = setTimeout(() => {
    state.reconnectTimer = null;
    state.reconnectDelay = Math.min(state.reconnectDelay * 1.5, state.maxReconnectDelay);
    connect();
  }, state.reconnectDelay);
}
function sendMessage(data) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(data));
  }
}
function setConnectionStatus(connected) {
  dom.statusDot.classList.toggle('connected', connected);
  dom.statusText.textContent = connected ? 'Connected' : 'Disconnected';
}
function handleMessage(data) {
  switch (data.type) {
    case 'frame':
      renderFrame(data.data);
      break;
    case 'state':
      updateState(data);
      break;
    case 'pong':
      break;
    case 'camera_list':
      updateCameraList(data.cameras, data.active);
      break;
  }
}
function updateCameraList(cameras, active) {
  const select = dom.settingCameraDevice;
  const current = select.dataset.loaded === '1' ? parseInt(select.value) : active;
  select.innerHTML = '';
  (cameras || []).forEach((idx) => {
    const opt = document.createElement('option');
    opt.value = idx;
    opt.textContent = `Camera ${idx}`;
    select.appendChild(opt);
  });
  select.value = current;
  select.dataset.loaded = '1';
}
function renderFrame(base64Data) {
  frameImage.onload = () => {
    if (dom.canvas.width !== frameImage.naturalWidth || dom.canvas.height !== frameImage.naturalHeight) {
      dom.canvas.width = frameImage.naturalWidth;
      dom.canvas.height = frameImage.naturalHeight;
    }
    ctx.drawImage(frameImage, 0, 0);
    state.frameCount++;
    dom.videoOverlay.classList.add('hidden');
    dom.fpsBadge.classList.add('visible');
  };
  frameImage.src = `data:image/jpeg;base64,${base64Data}`;
}
function updateState(data) {
  const gs = data.game_state;
  const equity = data.equity;
  if (data.fps != null) {
    dom.fpsValue.textContent = data.fps.toFixed(0);
  }
  updatePhase(gs.phase);
  updateCardChips(dom.playerCards, gs.player_hand, 'player');
  updateCardChips(dom.communityCards, gs.community, 'community');
  dom.zonePlayer.classList.toggle('active', gs.player_hand.length > 0);
  dom.zoneCommunity.classList.toggle('active', gs.community.length > 0);
  if (equity && gs.player_hand.length === 2) {
    showEquity(equity);
  } else {
    hideEquity();
  }
}
function updatePhase(phase) {
  const badge = dom.phaseBadge;
  const labels = {
    waiting: 'WAITING',
    preflop: 'PRE-FLOP',
    flop: 'FLOP',
    turn: 'TURN',
    river: 'RIVER',
  };
  badge.textContent = labels[phase] || phase.toUpperCase();
  badge.className = 'phase-badge ' + (phase || 'waiting');
}
const SUIT_SYMBOLS = { h: '♥', d: '♦', c: '♣', s: '♠' };
const SUIT_NAMES = { h: 'hearts', d: 'diamonds', c: 'clubs', s: 'spades' };
function cardDisplay(cardStr) {
  const rank = cardStr.slice(0, -1);
  const suit = cardStr.slice(-1);
  const symbol = SUIT_SYMBOLS[suit] || suit;
  const suitClass = SUIT_NAMES[suit] || '';
  const displayRank = rank === 'T' ? '10' : rank;
  return { display: `${displayRank}${symbol}`, suitClass };
}
function updateCardChips(container, cards, zoneType) {
  if (!cards || cards.length === 0) {
    container.innerHTML = '<span class="card-placeholder">—</span>';
    return;
  }
  const placeholder = container.querySelector('.card-placeholder');
  if (placeholder) placeholder.remove();
  const existingMap = new Map();
  container.querySelectorAll('.card-chip').forEach(el => {
    existingMap.set(el.dataset.card, el);
  });
  existingMap.forEach((el, card) => {
    if (!cards.includes(card)) {
      el.remove();
      existingMap.delete(card);
    }
  });
  cards.forEach((card, index) => {
    let chip = existingMap.get(card);
    if (!chip) {
      const { display, suitClass } = cardDisplay(card);
      chip = document.createElement('span');
      chip.className = `card-chip ${suitClass}`;
      chip.dataset.card = card;
      chip.textContent = display;
      existingMap.set(card, chip);
    }
    if (container.children[index] !== chip) {
      container.insertBefore(chip, container.children[index] || null);
    }
  });
}
function showEquity(equity) {
  dom.equityWaiting.style.display = 'none';
  dom.equityData.style.display = 'block';
  animateValue(dom.barWin, 'width', equity.win);
  animateValue(dom.barTie, 'width', equity.tie);
  animateValue(dom.barLose, 'width', equity.lose);
  dom.stackedWin.style.width = equity.win + '%';
  dom.stackedTie.style.width = equity.tie + '%';
  dom.stackedLose.style.width = equity.lose + '%';
  updateEquityValue(dom.valWin, equity.win);
  updateEquityValue(dom.valTie, equity.tie);
  updateEquityValue(dom.valLose, equity.lose);
  dom.handRank.textContent = equity.hand_rank || '';
  dom.simInfo.textContent = `${(equity.samples).toLocaleString()} sims • ${equity.computation_ms.toFixed(0)}ms`;
  if (equity.recommendation) {
    dom.actionRec.style.display = 'flex';
    dom.actionBadge.textContent = equity.recommendation;
    dom.actionBadge.className = 'action-badge ' + equity.recommendation.toLowerCase();
  } else {
    dom.actionRec.style.display = 'none';
  }
  state.lastEquity = equity;
}
function hideEquity() {
  dom.equityWaiting.style.display = '';
  dom.equityData.style.display = 'none';
  dom.actionRec.style.display = 'none';
}
function animateValue(el, prop, value) {
  el.style[prop] = value + '%';
}
function updateEquityValue(el, value) {
  const newText = value.toFixed(1) + '%';
  if (el.textContent !== newText) {
    el.textContent = newText;
    el.classList.add('updated');
    setTimeout(() => el.classList.remove('updated'), 500);
  }
}
function logConsole(msg, type = '') {
  const line = document.createElement('div');
  line.className = `console-line ${type}`;
  const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
  line.textContent = `[${timestamp}] ${msg}`;
  dom.consoleOutput.appendChild(line);
  while (dom.consoleOutput.children.length > 200) {
    dom.consoleOutput.removeChild(dom.consoleOutput.firstChild);
  }
  dom.consoleOutput.scrollTop = dom.consoleOutput.scrollHeight;
}
function initSettings() {
  dom.settingsToggle.addEventListener('click', () => {
    state.settingsOpen = !state.settingsOpen;
    dom.settingsBody.style.display = state.settingsOpen ? 'block' : 'none';
    dom.settingsToggle.classList.toggle('open', state.settingsOpen);
  });
  dom.consoleToggle.addEventListener('click', () => {
    state.consoleOpen = !state.consoleOpen;
    dom.consoleBody.style.display = state.consoleOpen ? 'block' : 'none';
    dom.consoleToggle.classList.toggle('open', state.consoleOpen);
  });
  dom.settingCamera.addEventListener('change', (e) => {
    sendMessage({ type: 'toggle_camera', enabled: e.target.checked });
    logConsole(`Camera feed ${e.target.checked ? 'enabled' : 'disabled'}`, 'info');
    if (!e.target.checked) {
      dom.videoOverlay.classList.remove('hidden');
      dom.fpsBadge.classList.remove('visible');
    }
  });
  dom.settingCameraDevice.addEventListener('change', (e) => {
    const deviceIndex = parseInt(e.target.value);
    sendMessage({ type: 'switch_camera', device_index: deviceIndex });
    logConsole(`Switching to camera ${deviceIndex}...`, 'info');
    dom.videoOverlay.classList.remove('hidden');
    dom.fpsBadge.classList.remove('visible');
  });
  dom.settingConfidence.addEventListener('input', (e) => {
    dom.valConfidence.textContent = parseFloat(e.target.value).toFixed(2);
  });
  dom.settingConfidence.addEventListener('change', (e) => {
    sendMessage({ type: 'update_config', confidence: parseFloat(e.target.value) });
    logConsole(`Confidence threshold → ${e.target.value}`, 'info');
  });
  dom.settingDebounce.addEventListener('input', (e) => {
    dom.valDebounce.textContent = e.target.value;
  });
  dom.settingDebounce.addEventListener('change', (e) => {
    sendMessage({ type: 'update_config', debounce_frames: parseInt(e.target.value) });
    logConsole(`Debounce frames → ${e.target.value}`, 'info');
  });
  dom.settingSims.addEventListener('input', (e) => {
    const v = parseInt(e.target.value);
    dom.valSims.textContent = v >= 1000 ? (v / 1000).toFixed(0) + 'K' : v;
  });
  dom.settingSims.addEventListener('change', (e) => {
    sendMessage({ type: 'update_config', num_simulations: parseInt(e.target.value) });
    logConsole(`Simulations → ${e.target.value}`, 'info');
  });
  dom.btnReset.addEventListener('click', () => {
    sendMessage({ type: 'reset' });
    logConsole('State reset', 'info');
    hideEquity();
    updateCardChips(dom.playerCards, [], 'player');
    updateCardChips(dom.communityCards, [], 'community');
    updatePhase('waiting');
  });
  dom.btnRestartPython.addEventListener('click', async () => {
    logConsole('Restarting Python backend...', 'info');
    if (window.electronAPI) {
      await window.electronAPI.restartPython();
    }
  });
}
function initTitleBar() {
  if (!window.electronAPI) return;
  dom.btnMinimize.addEventListener('click', () => window.electronAPI.minimize());
  dom.btnMaximize.addEventListener('click', () => window.electronAPI.maximize());
  dom.btnClose.addEventListener('click', () => window.electronAPI.close());
  window.electronAPI.onPythonLog((msg) => logConsole(msg, 'info'));
  window.electronAPI.onPythonError((msg) => logConsole(msg, 'error'));
  window.electronAPI.getAppInfo().then((info) => {
    if (info && info.version) {
      dom.appVersion.textContent = `v${info.version}`;
    }
  });
}
function startHeartbeat() {
  setInterval(() => {
    if (state.connected) {
      sendMessage({ type: 'ping' });
    }
  }, 15000);
}
function init() {
  initTitleBar();
  initSettings();
  startHeartbeat();
  setTimeout(connect, 2000);
  logConsole('pokerCV initialized', 'info');
  logConsole('Waiting for Python backend to start...', 'info');
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}