/**
 * Core API & State Management for DeepCool LM360 Dashboard
 */

let currentStatus = null;
let availableMetrics = {};
let availableFonts = [];
let availableEffects = [];
let currentStorageDir = '';
let currentAutostart = false;
let isFetchingStatus = false;
let brightnessDebounceTimer = null;

async function fetchStatus() {
  if (isFetchingStatus) return;
  isFetchingStatus = true;
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();
    currentStatus = data;
    availableMetrics = data.available_metrics || {};
    availableEffects = data.available_effects || [];
    availableFonts = data.available_fonts || [];
    currentStorageDir = data.media_storage_dir || '';
    if (typeof updateUI === 'function') {
      updateUI(data);
    }
  } catch (err) {
    console.error('Failed to fetch status:', err);
  } finally {
    isFetchingStatus = false;
  }
}

async function setMode(mode) {
  await fetch('/api/mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode })
  });
  fetchStatus();
}

async function toggleOrientation() {
  if (!currentStatus) return;
  const newOrient = currentStatus.orientation === 180 ? 0 : 180;
  await fetch('/api/orientation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ orientation: newOrient })
  });
  fetchStatus();
}

async function setTempUnit(unit) {
  await fetch('/api/temp_unit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unit })
  });
  fetchStatus();
}

function updateBrightnessLabel(val) {
  const pct = parseInt(val, 10);
  const badge = document.getElementById('brightnessBadge');
  if (badge) badge.innerText = `${pct}%`;
  [25, 50, 75, 100].forEach(p => {
    const btn = document.getElementById('bPreset' + p);
    if (btn) btn.className = 'preset-btn' + (Math.abs(pct - p) <= 5 ? ' active' : '');
  });
  clearTimeout(brightnessDebounceTimer);
  brightnessDebounceTimer = setTimeout(() => {
    fetch('/api/brightness/set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ percent: pct })
    });
  }, 60);
}

async function setBrightness(val) {
  const pct = parseInt(val, 10);
  const slider = document.getElementById('brightnessSlider');
  if (slider) slider.value = pct;
  updateBrightnessLabel(pct);
  clearTimeout(brightnessDebounceTimer);
  await fetch('/api/brightness/set', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ percent: pct })
  });
  fetchStatus();
}

function updateAutostartUI(enabled) {
  currentAutostart = !!enabled;
  const btn = document.getElementById('btnAutostart');
  if (btn) {
    if (currentAutostart) {
      btn.textContent = 'Startup: On';
      btn.className = 'device-toggle-btn active';
    } else {
      btn.textContent = 'Startup: Off';
      btn.className = 'device-toggle-btn';
    }
  }
}

async function toggleAutostart() {
  const nextVal = !currentAutostart;
  try {
    const res = await fetch('/api/autostart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enable: nextVal })
    });
    if (res.ok) {
      const data = await res.json();
      updateAutostartUI(data.autostart);
    }
  } catch (err) {
    console.error('Failed to toggle autostart:', err);
  }
}
