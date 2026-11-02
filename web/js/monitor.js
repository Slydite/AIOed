/**
 * Hardware Monitor & Telemetry HUD Module
 */

function renderThemes(themes, activeThemeId, themeConfig) {
  const container = document.getElementById('themesContainer');
  if (!container) return;
  container.innerHTML = '';

  (themes || []).forEach(t => {
    const div = document.createElement('div');
    div.className = 'theme-card' + (t.id === activeThemeId ? ' active' : '');
    div.onclick = () => selectTheme(t.id);
    div.innerHTML = `
      <div class="theme-title">${t.name}</div>
      <div class="theme-desc">${t.description}</div>
    `;
    container.appendChild(div);
  });

  const activeThemeObj = (themes || []).find(t => t.id === activeThemeId);
  const slotsBox = document.getElementById('slotsInputs');
  if (!slotsBox) return;
  slotsBox.innerHTML = '';

  if (activeThemeObj && activeThemeObj.slots) {
    activeThemeObj.slots.forEach(slot => {
      const row = document.createElement('div');
      row.className = 'slot-row';
      const currentVal = (themeConfig && themeConfig[slot.id]) || slot.default;

      let optionsHtml = '';
      slot.options.forEach(optKey => {
        const m = (typeof availableMetrics !== 'undefined' && availableMetrics[optKey]) || { name: optKey };
        const selected = optKey === currentVal ? 'selected' : '';
        optionsHtml += `<option value="${optKey}" ${selected}>${m.name} (${optKey})</option>`;
      });

      row.innerHTML = `
        <span class="control-label" style="font-size: 13px;">${slot.name}:</span>
        <select onchange="changeSlot('${activeThemeId}', '${slot.id}', this.value)">
          ${optionsHtml}
        </select>
      `;
      slotsBox.appendChild(row);
    });
  }
}

async function selectTheme(theme_id) {
  await fetch('/api/theme', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme_id })
  });
  fetchStatus();
}

async function changeSlot(theme_id, slot_id, metric) {
  await fetch('/api/theme/slot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme_id, slot_id, metric })
  });
  fetchStatus();
}

function renderSensors(s, unit) {
  if (!s) return;
  const grid = document.getElementById('sensorsGrid');
  if (!grid) return;
  const tempSuffix = '°' + (unit || 'C');

  const items = [
    { label: 'CPU Temp', val: `${Math.round(s.cpu_temp || 0)}${tempSuffix}` },
    { label: 'CPU Power', val: `${(s.cpu_power || 0).toFixed(1)} W` },
    { label: 'CPU Load', val: `${(s.cpu_load || 0).toFixed(0)} %` },
    { label: 'CPU Clock', val: `${((s.cpu_clock || 0)/1000).toFixed(2)} GHz` },
    { label: 'GPU Temp', val: `${Math.round(s.gpu_temp || 0)}${tempSuffix}` },
    { label: 'GPU Power', val: `${(s.gpu_power || 0).toFixed(1)} W` },
    { label: 'GPU Load', val: `${(s.gpu_load || 0).toFixed(0)} %` },
    { label: 'RAM Load', val: `${(s.ram_load || 0).toFixed(0)} %` },
    { label: s.fps_app ? `FPS (${s.fps_app})` : 'FPS', val: s.fps_avg ? `${s.fps_avg.toFixed(0)} avg / ${s.fps_1pct.toFixed(0)} 1%` : '—' },
  ];

  grid.innerHTML = items.map(i => `
    <div class="sensor-item">
      <div class="sensor-k">${i.label}</div>
      <div class="sensor-v">${i.val}</div>
    </div>
  `).join('');
}
