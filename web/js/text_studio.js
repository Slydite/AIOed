/**
 * Text Animation Studio Module
 * 2D Interactive Drag-and-Drop Visual Stage, Dynamic Multi-Element Cards,
 * Color Pickers, Typography, Background Textures & Video Loop Baking
 */

const FONT_CSS_MAP = {
  "orbitron": "'Orbitron', sans-serif",
  "press_start": "'Press Start 2P', monospace",
  "share_tech": "'Share Tech Mono', monospace",
  "vt323": "'VT323', monospace",
  "impact": "Impact, sans-serif",
  "consolas": "Consolas, monospace",
  "arial": "Arial, sans-serif",
  "bahnschrift": "Bahnschrift, sans-serif",
  "segoe": "'Segoe UI', sans-serif",
  "courier": "'Courier New', monospace",
  "comic": "'Comic Sans MS', cursive"
};

let activeTextConfig = { elements: [], bg_color: '#070A12', bg_style: 'grid', speed: 1.0 };
let selectedElemId = null;
let textStudioInitialized = false;
let textUpdateDebounce = null;

function replaceTagsPreview(txt) {
  if (!txt) return '';
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const timeStr = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const dateStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

  let res = txt.replace(/{time}/g, timeStr).replace(/{date}/g, dateStr);
  const s = (typeof currentStatus !== 'undefined' && currentStatus) ? currentStatus.sensors : null;
  if (s) {
    res = res.replace(/{cpu_temp}/g, `${Math.round(s.cpu_temp || 0)}°C`);
    res = res.replace(/{gpu_temp}/g, `${Math.round(s.gpu_temp || 0)}°C`);
    res = res.replace(/{cpu_load}/g, `${Math.round(s.cpu_load || 0)}%`);
    res = res.replace(/{gpu_load}/g, `${Math.round(s.gpu_load || 0)}%`);
    res = res.replace(/{cpu_power}/g, `${Math.round(s.cpu_power || 0)}W`);
    res = res.replace(/{gpu_power}/g, `${Math.round(s.gpu_power || 0)}W`);
    res = res.replace(/{ram_load}/g, `${Math.round(s.ram_load || 0)}%`);
    res = res.replace(/{cpu_clock}/g, s.cpu_clock ? `${(s.cpu_clock / 1000).toFixed(2)}GHz` : '');
  } else {
    res = res.replace(/{cpu_temp}/g, '45°C');
    res = res.replace(/{gpu_temp}/g, '42°C');
    res = res.replace(/{cpu_load}/g, '12%');
    res = res.replace(/{gpu_load}/g, '8%');
    res = res.replace(/{cpu_power}/g, '35W');
    res = res.replace(/{gpu_power}/g, '40W');
    res = res.replace(/{ram_load}/g, '25%');
    res = res.replace(/{cpu_clock}/g, '4.2GHz');
  }
  return res;
}

function populateTextStudio(cfg, fonts, effects) {
  if (!cfg) return;
  if (fonts) availableFonts = fonts;
  if (effects) availableEffects = effects;

  if (!textStudioInitialized) {
    activeTextConfig = JSON.parse(JSON.stringify(cfg));
    if (!activeTextConfig.elements || !activeTextConfig.elements.length) {
      activeTextConfig.elements = [
        { id: 'elem_1', text: 'CYBER DEEPCOOL', font: 'orbitron', font_size: 22, x: -1, y: 50, align: 'center', color: '#00ffcc', glow_color: '#0077ff', effect: 'neon_pulse' },
        { id: 'elem_2', text: '{time}  ●  LIQUID COOLED', font: 'orbitron', font_size: 14, x: -1, y: 140, align: 'center', color: '#0088ff', glow_color: '#0077ff', effect: 'neon_pulse' }
      ];
    }
    if (!selectedElemId && activeTextConfig.elements.length > 0) {
      selectedElemId = activeTextConfig.elements[0].id;
    }

    const bgPicker = document.getElementById('bgColorPicker');
    const bgHex = document.getElementById('bgColorHex');
    const bgStyleSel = document.getElementById('bgStyleSelect');
    const spdSlider = document.getElementById('speedSlider');
    const spdVal = document.getElementById('speedVal');

    if (bgPicker) bgPicker.value = activeTextConfig.bg_color || '#070a12';
    if (bgHex) bgHex.value = activeTextConfig.bg_color || '#070a12';
    if (bgStyleSel) bgStyleSel.value = activeTextConfig.bg_style || 'grid';
    if (spdSlider) spdSlider.value = activeTextConfig.speed || 1.0;
    if (spdVal) spdVal.innerText = `${activeTextConfig.speed || 1.0}x`;

    renderStage();
    renderElementsCards();
    textStudioInitialized = true;
  }
}

function updateStageSensorTexts() {
  (activeTextConfig.elements || []).forEach(elem => {
    const el = document.getElementById('stageElem_' + elem.id);
    if (el && !el.classList.contains('dragging')) {
      el.innerText = replaceTagsPreview(elem.text);
      updateElementStagePosition(el, elem);
    }
  });
}

function renderStage() {
  const stage = document.getElementById('layoutStage');
  if (!stage) return;
  stage.style.backgroundColor = activeTextConfig.bg_color || '#070a12';
  stage.className = 'layout-stage bg-' + (activeTextConfig.bg_style || 'grid');

  stage.innerHTML = '<div class="stage-cross-x"></div><div class="stage-cross-y"></div>';

  (activeTextConfig.elements || []).forEach(elem => {
    const el = document.createElement('div');
    el.id = 'stageElem_' + elem.id;
    el.className = 'stage-elem' + (elem.id === selectedElemId ? ' selected' : '');
    el.innerText = replaceTagsPreview(elem.text);

    const cssFont = FONT_CSS_MAP[elem.font] || 'sans-serif';
    el.style.fontFamily = cssFont;
    el.style.fontSize = (elem.font_size || 20) + 'px';
    el.style.color = elem.color || '#00ffcc';
    el.style.textShadow = `0 0 6px ${elem.glow_color || '#0077ff'}`;

    stage.appendChild(el);

    updateElementStagePosition(el, elem);
    attachStageElemDrag(el, elem);
  });
}

function updateElementStagePosition(el, elem) {
  const width = el.offsetWidth;
  const height = el.offsetHeight;

  const isOverflow = width > 320;
  el.classList.toggle('overflow-warning', isOverflow);
  updateOverflowBadge(elem.id, isOverflow, width);

  if (elem.x !== undefined && elem.x >= 0) {
    el.style.left = elem.x + 'px';
    el.style.right = 'auto';
    el.style.transform = 'none';
  } else {
    if (elem.align === 'left') {
      el.style.left = '16px';
      el.style.right = 'auto';
      el.style.transform = 'none';
    } else if (elem.align === 'right') {
      el.style.left = Math.max(0, 320 - width - 16) + 'px';
      el.style.right = 'auto';
      el.style.transform = 'none';
    } else {
      el.style.left = Math.max(0, Math.round((320 - width) / 2)) + 'px';
      el.style.right = 'auto';
      el.style.transform = 'none';
    }
  }

  if (elem.y !== undefined && elem.y >= 0) {
    el.style.top = elem.y + 'px';
  } else {
    el.style.top = Math.max(0, Math.round((240 - height) / 2)) + 'px';
  }
}

function updateOverflowBadge(elemId, isOverflow, width) {
  const badge = document.getElementById('badge_overflow_' + elemId);
  if (badge) {
    if (isOverflow) {
      badge.innerHTML = `<span class="overflow-warn-pill">⚠️ ${width}px / 320px (Too Wide)</span>`;
    } else {
      badge.innerHTML = '';
    }
  }
}

function attachStageElemDrag(el, elem) {
  el.onmousedown = (e) => {
    selectElement(elem.id);
    el.classList.add('dragging');
    const startMouseX = e.clientX;
    const startMouseY = e.clientY;
    const startElemX = parseInt(el.style.left || '0', 10);
    const startElemY = parseInt(el.style.top || '0', 10);
    document.body.style.cursor = 'grabbing';
    e.preventDefault();

    function onMouseMove(moveEv) {
      const dx = moveEv.clientX - startMouseX;
      const dy = moveEv.clientY - startMouseY;
      const newX = Math.max(0, Math.min(310, startElemX + dx));
      const newY = Math.max(0, Math.min(220, startElemY + dy));

      elem.x = newX;
      elem.y = newY;

      el.style.left = newX + 'px';
      el.style.top = newY + 'px';
      el.style.transform = 'none';

      const coords = document.getElementById('stageCoords');
      if (coords) coords.innerText = `X: ${newX}px  Y: ${newY}px`;

      const xSlider = document.getElementById(`xSlider_${elem.id}`);
      const xVal = document.getElementById(`xVal_${elem.id}`);
      if (xSlider) xSlider.value = newX;
      if (xVal) xVal.innerText = newX;

      const ySlider = document.getElementById(`ySlider_${elem.id}`);
      const yVal = document.getElementById(`yVal_${elem.id}`);
      if (ySlider) ySlider.value = newY;
      if (yVal) yVal.innerText = newY;

      const isOverflow = el.offsetWidth > 320;
      el.classList.toggle('overflow-warning', isOverflow);
      updateOverflowBadge(elem.id, isOverflow, el.offsetWidth);

      queueTextUpdate();
    }

    function onMouseUp() {
      el.classList.remove('dragging');
      document.body.style.cursor = 'default';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      queueTextUpdate();
    }

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };
}

function selectElement(id) {
  selectedElemId = id;
  document.querySelectorAll('.stage-elem').forEach(el => {
    el.classList.toggle('selected', el.id === 'stageElem_' + id);
  });
  document.querySelectorAll('.elem-card').forEach(c => {
    c.classList.toggle('selected', c.id === 'elemCard_' + id);
  });
}

function renderElementsCards() {
  const container = document.getElementById('elementsContainer');
  if (!container) return;
  container.innerHTML = '';

  (activeTextConfig.elements || []).forEach((elem, idx) => {
    const card = document.createElement('div');
    card.id = 'elemCard_' + elem.id;
    card.className = 'elem-card' + (elem.id === selectedElemId ? ' selected' : '');
    card.onclick = (e) => {
      if (!e.target.closest('input, button, select, .color-swatch, .tag-chip, .effect-pill')) {
        selectElement(elem.id);
      }
    };

    const deleteBtn = activeTextConfig.elements.length > 1
      ? `<button class="elem-delete-btn" onclick="deleteTextElement('${elem.id}')">🗑️ Remove</button>`
      : '';

    let fontOpts = '';
    (availableFonts || []).forEach(f => {
      fontOpts += `<option value="${f.id}" ${f.id === elem.font ? 'selected' : ''}>${f.name}</option>`;
    });

    let effPills = '';
    (availableEffects || []).forEach(eff => {
      const act = eff.id === elem.effect ? ' active' : '';
      effPills += `<div class="effect-pill${act}" title="${eff.desc}" onclick="setElementEffect('${elem.id}', '${eff.id}')">${eff.name}</div>`;
    });

    const xDisplay = elem.x >= 0 ? elem.x : 'Auto';
    const yDisplay = elem.y >= 0 ? elem.y : 'Auto';

    card.innerHTML = `
      <div class="elem-card-header">
        <div class="elem-title">
          <span>Text Element #${idx + 1}</span>
          <span id="badge_overflow_${elem.id}"></span>
        </div>
        ${deleteBtn}
      </div>

      <!-- Text input & Telemetry Tag Chips -->
      <div>
        <input type="text" id="textInput_${elem.id}" value="${elem.text || ''}" placeholder="Enter text or telemetry tags..." oninput="onElementTextChanged('${elem.id}', this.value)">
        <div class="tag-chips">
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{time}')">+ {time}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{date}')">+ {date}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{cpu_temp}')">+ {cpu_temp}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{gpu_temp}')">+ {gpu_temp}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{cpu_load}')">+ {cpu_load}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{gpu_load}')">+ {gpu_load}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{cpu_power}')">+ {cpu_power}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{gpu_power}')">+ {gpu_power}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{ram_load}')">+ {ram_load}</span>
          <span class="tag-chip" onclick="insertTagToElement('${elem.id}', '{cpu_clock}')">+ {cpu_clock}</span>
        </div>
      </div>

      <!-- Font Family & Font Size -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 12px;">
        <div>
          <label class="control-label">Font Family</label>
          <select id="fontSelect_${elem.id}" onchange="setElementFont('${elem.id}', this.value)" style="margin-top: 6px;">
            ${fontOpts}
          </select>
        </div>

        <div>
          <div style="display: flex; justify-content: space-between;">
            <label class="control-label">Font Size</label>
            <span id="fontSizeVal_${elem.id}" class="control-desc" style="color: var(--accent); font-weight: 700;">${elem.font_size || 20}px</span>
          </div>
          <input type="range" id="fontSizeSlider_${elem.id}" min="8" max="64" step="1" value="${elem.font_size || 20}" oninput="setElementFontSize('${elem.id}', this.value)" style="margin-top: 8px;">
        </div>
      </div>

      <!-- 2D X & Y Positions -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 12px;">
        <div>
          <div style="display: flex; justify-content: space-between;">
            <label class="control-label">X Position</label>
            <div>
              <span id="xVal_${elem.id}" class="control-desc" style="color: var(--accent); font-weight: 700;">${xDisplay}</span>
              <button class="btn btn-sm" style="padding: 1px 6px; font-size: 10px; margin-left: 6px;" onclick="centerElementX('${elem.id}')">Center X</button>
            </div>
          </div>
          <input type="range" id="xSlider_${elem.id}" min="0" max="300" step="1" value="${elem.x >= 0 ? elem.x : 0}" oninput="setElementX('${elem.id}', this.value)" style="margin-top: 8px;">
        </div>

        <div>
          <div style="display: flex; justify-content: space-between;">
            <label class="control-label">Y Position</label>
            <div>
              <span id="yVal_${elem.id}" class="control-desc" style="color: var(--accent); font-weight: 700;">${yDisplay}</span>
              <button class="btn btn-sm" style="padding: 1px 6px; font-size: 10px; margin-left: 6px;" onclick="centerElementY('${elem.id}')">Center Y</button>
            </div>
          </div>
          <input type="range" id="ySlider_${elem.id}" min="0" max="220" step="1" value="${elem.y >= 0 ? elem.y : 0}" oninput="setElementY('${elem.id}', this.value)" style="margin-top: 8px;">
        </div>
      </div>

      <!-- Alignment -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
        <label class="control-label">Alignment</label>
        <div class="align-group">
          <button class="align-btn ${elem.align === 'left' ? 'active' : ''}" onclick="setElementAlign('${elem.id}', 'left')">Left</button>
          <button class="align-btn ${elem.align === 'center' || !elem.align ? 'active' : ''}" onclick="setElementAlign('${elem.id}', 'center')">Center</button>
          <button class="align-btn ${elem.align === 'right' ? 'active' : ''}" onclick="setElementAlign('${elem.id}', 'right')">Right</button>
        </div>
      </div>

      <!-- Colors: Primary Text & Glow Accent -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 12px;">
        <div>
          <label class="control-label">Text Color</label>
          <div style="display: flex; gap: 8px; align-items: center; margin-top: 6px;">
            <input type="color" id="colorPicker_${elem.id}" value="${elem.color || '#00ffcc'}" oninput="setElementColor('${elem.id}', this.value, 'colorHex_${elem.id}')" style="width: 44px; height: 32px; padding: 0; cursor: pointer; border-radius: 4px;">
            <input type="text" id="colorHex_${elem.id}" value="${elem.color || '#00ffcc'}" style="font-family: monospace; font-size: 12px; width: 90px;" onchange="updateElementColorHex('${elem.id}', 'colorPicker_${elem.id}', this.value)">
          </div>
          <div class="color-swatches">
            <div class="color-swatch" style="background: #00ffcc;" onclick="setElementColorPreset('${elem.id}', '#00ffcc', 'colorPicker_${elem.id}', 'colorHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #0088ff;" onclick="setElementColorPreset('${elem.id}', '#0088ff', 'colorPicker_${elem.id}', 'colorHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #ff007f;" onclick="setElementColorPreset('${elem.id}', '#ff007f', 'colorPicker_${elem.id}', 'colorHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #00ff66;" onclick="setElementColorPreset('${elem.id}', '#00ff66', 'colorPicker_${elem.id}', 'colorHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #ffbe0b;" onclick="setElementColorPreset('${elem.id}', '#ffbe0b', 'colorPicker_${elem.id}', 'colorHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #ffffff;" onclick="setElementColorPreset('${elem.id}', '#ffffff', 'colorPicker_${elem.id}', 'colorHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #ff3344;" onclick="setElementColorPreset('${elem.id}', '#ff3344', 'colorPicker_${elem.id}', 'colorHex_${elem.id}')"></div>
          </div>
        </div>

        <div>
          <label class="control-label">Glow / Secondary Color</label>
          <div style="display: flex; gap: 8px; align-items: center; margin-top: 6px;">
            <input type="color" id="glowPicker_${elem.id}" value="${elem.glow_color || '#0077ff'}" oninput="setElementGlowColor('${elem.id}', this.value, 'glowHex_${elem.id}')" style="width: 44px; height: 32px; padding: 0; cursor: pointer; border-radius: 4px;">
            <input type="text" id="glowHex_${elem.id}" value="${elem.glow_color || '#0077ff'}" style="font-family: monospace; font-size: 12px; width: 90px;" onchange="updateElementGlowHex('${elem.id}', 'glowPicker_${elem.id}', this.value)">
          </div>
          <div class="color-swatches">
            <div class="color-swatch" style="background: #0077ff;" onclick="setElementGlowPreset('${elem.id}', '#0077ff', 'glowPicker_${elem.id}', 'glowHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #ff0055;" onclick="setElementGlowPreset('${elem.id}', '#ff0055', 'glowPicker_${elem.id}', 'glowHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #00ff99;" onclick="setElementGlowPreset('${elem.id}', '#00ff99', 'glowPicker_${elem.id}', 'glowHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #7928ca;" onclick="setElementGlowPreset('${elem.id}', '#7928ca', 'glowPicker_${elem.id}', 'glowHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #ffaa00;" onclick="setElementGlowPreset('${elem.id}', '#ffaa00', 'glowPicker_${elem.id}', 'glowHex_${elem.id}')"></div>
            <div class="color-swatch" style="background: #334466;" onclick="setElementGlowPreset('${elem.id}', '#334466', 'glowPicker_${elem.id}', 'glowHex_${elem.id}')"></div>
          </div>
        </div>
      </div>

      <!-- Animation Effect -->
      <div style="margin-top: 14px;">
        <label class="control-label">Animation Effect</label>
        <div class="effect-pills">
          ${effPills}
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function onElementTextChanged(id, val) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.text = val;
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    stageEl.innerText = replaceTagsPreview(val);
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function insertTagToElement(id, tag) {
  const input = document.getElementById('textInput_' + id);
  if (!input) return;
  input.value += (input.value ? '  ●  ' : '') + tag;
  onElementTextChanged(id, input.value);
}

function setElementFont(id, fontKey) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.font = fontKey;
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    stageEl.style.fontFamily = FONT_CSS_MAP[fontKey] || 'sans-serif';
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function setElementFontSize(id, size) {
  const s = parseInt(size, 10);
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.font_size = s;
  const valBadge = document.getElementById('fontSizeVal_' + id);
  if (valBadge) valBadge.innerText = s + 'px';
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    stageEl.style.fontSize = s + 'px';
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function setElementX(id, x) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  const val = parseInt(x, 10);
  elem.x = val;
  const valLabel = document.getElementById('xVal_' + id);
  if (valLabel) valLabel.innerText = val;
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function centerElementX(id) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.x = -1;
  elem.align = 'center';
  const valLabel = document.getElementById('xVal_' + id);
  if (valLabel) valLabel.innerText = 'Auto';
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function setElementY(id, y) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  const val = parseInt(y, 10);
  elem.y = val;
  const valLabel = document.getElementById('yVal_' + id);
  if (valLabel) valLabel.innerText = val;
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function centerElementY(id) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.y = -1;
  const valLabel = document.getElementById('yVal_' + id);
  if (valLabel) valLabel.innerText = 'Auto';
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function setElementAlign(id, align) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.align = align;
  elem.x = -1;
  const valLabel = document.getElementById('xVal_' + id);
  if (valLabel) valLabel.innerText = 'Auto';
  renderElementsCards();
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    updateElementStagePosition(stageEl, elem);
  }
  queueTextUpdate();
}

function setElementColor(id, hex, hexId) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.color = hex;
  const hexInput = document.getElementById(hexId);
  if (hexInput) hexInput.value = hex;
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    stageEl.style.color = hex;
  }
  queueTextUpdate();
}

function updateElementColorHex(id, pickerId, val) {
  if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
    const picker = document.getElementById(pickerId);
    if (picker) picker.value = val;
    setElementColor(id, val, 'colorHex_' + id);
  }
}

function setElementColorPreset(id, hex, pickerId, hexId) {
  const picker = document.getElementById(pickerId);
  if (picker) picker.value = hex;
  setElementColor(id, hex, hexId);
}

function setElementGlowColor(id, hex, hexId) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.glow_color = hex;
  const hexInput = document.getElementById(hexId);
  if (hexInput) hexInput.value = hex;
  const stageEl = document.getElementById('stageElem_' + id);
  if (stageEl) {
    stageEl.style.textShadow = `0 0 6px ${hex}`;
  }
  queueTextUpdate();
}

function updateElementGlowHex(id, pickerId, val) {
  if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
    const picker = document.getElementById(pickerId);
    if (picker) picker.value = val;
    setElementGlowColor(id, val, 'glowHex_' + id);
  }
}

function setElementGlowPreset(id, hex, pickerId, hexId) {
  const picker = document.getElementById(pickerId);
  if (picker) picker.value = hex;
  setElementGlowColor(id, hex, hexId);
}

function setElementEffect(id, effId) {
  const elem = activeTextConfig.elements.find(e => e.id === id);
  if (!elem) return;
  elem.effect = effId;
  renderElementsCards();
  queueTextUpdate();
}

function addTextElement() {
  const newId = 'elem_' + Date.now().toString(36);
  const newElem = {
    id: newId,
    text: 'NEW TEXT',
    font: 'orbitron',
    font_size: 18,
    x: -1,
    y: Math.min(200, 30 + activeTextConfig.elements.length * 45),
    align: 'center',
    color: '#00ffcc',
    glow_color: '#0077ff',
    effect: 'neon_pulse'
  };
  activeTextConfig.elements.push(newElem);
  selectedElemId = newId;
  renderStage();
  renderElementsCards();
  queueTextUpdate();
}

function deleteTextElement(id) {
  if (activeTextConfig.elements.length <= 1) {
    alert('You must have at least one text element');
    return;
  }
  activeTextConfig.elements = activeTextConfig.elements.filter(e => e.id !== id);
  if (selectedElemId === id) {
    selectedElemId = activeTextConfig.elements[0].id;
  }
  renderStage();
  renderElementsCards();
  queueTextUpdate();
}

function onGlobalColorChanged(pickerId, hexId, key) {
  const picker = document.getElementById(pickerId);
  const hexInput = document.getElementById(hexId);
  if (!picker) return;
  const val = picker.value;
  if (hexInput) hexInput.value = val;
  activeTextConfig[key] = val;
  renderStage();
  queueTextUpdate();
}

function updateGlobalColorHex(pickerId, val, key) {
  if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
    const picker = document.getElementById(pickerId);
    if (picker) picker.value = val;
    activeTextConfig[key] = val;
    renderStage();
    queueTextUpdate();
  }
}

function setGlobalColorPreset(val, key) {
  const picker = document.getElementById('bgColorPicker');
  const hexInput = document.getElementById('bgColorHex');
  if (picker) picker.value = val;
  if (hexInput) hexInput.value = val;
  activeTextConfig[key] = val;
  renderStage();
  queueTextUpdate();
}

function onBgStyleChanged(val) {
  activeTextConfig.bg_style = val;
  renderStage();
  queueTextUpdate();
}

function onSpeedSliderChanged() {
  const slider = document.getElementById('speedSlider');
  const valBadge = document.getElementById('speedVal');
  const s = parseFloat(slider ? slider.value : '1.0');
  if (valBadge) valBadge.innerText = s.toFixed(1) + 'x';
  activeTextConfig.speed = s;
  queueTextUpdate();
}

function queueTextUpdate() {
  clearTimeout(textUpdateDebounce);
  textUpdateDebounce = setTimeout(() => {
    const payload = {
      elements: activeTextConfig.elements,
      bg_color: activeTextConfig.bg_color || '#070a12',
      bg_style: activeTextConfig.bg_style || 'grid',
      speed: parseFloat(activeTextConfig.speed || 1.0)
    };
    sendTextConfig(payload);
  }, 60);
}

async function sendTextConfig(cfg) {
  await fetch('/api/text/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg)
  });
}

async function bakeTextAnimation() {
  const firstText = (activeTextConfig.elements && activeTextConfig.elements[0]) ? activeTextConfig.elements[0].text : 'Banner';
  const name = prompt('Name for video loop in library:', 'Text: ' + firstText.slice(0, 16));
  if (!name) return;

  const btn = event ? event.target : null;
  const originalText = btn ? btn.innerText : '';
  if (btn) {
    btn.innerText = '⏳ Baking...';
    btn.disabled = true;
  }

  try {
    const res = await fetch('/api/text/bake', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, duration_sec: 4.0, fps: 24 })
    });
    if (res.ok) {
      alert('Successfully saved animated text to Video Library!');
      await fetchStatus();
    } else {
      alert('Error baking text: ' + (await res.text()));
    }
  } catch (err) {
    alert('Error: ' + err);
  } finally {
    if (btn) {
      btn.innerText = originalText;
      btn.disabled = false;
    }
  }
}
