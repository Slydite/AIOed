/**
 * Application Bootstrap, Coordination & Global Event Listeners
 */

function updateUI(data) {
  if (!data) return;

  // Status pills
  const usbDot = document.getElementById('usbDot');
  const usbText = document.getElementById('usbText');
  if (usbDot && usbText) {
    if (data.usb_connected) {
      usbDot.className = 'dot dot-online';
      usbText.innerText = 'USB: Connected';
    } else {
      usbDot.className = 'dot dot-offline';
      usbText.innerText = 'USB: Disconnected';
    }
  }

  const sensorText = document.getElementById('sensorText');
  if (sensorText) {
    sensorText.innerText = data.sensor_source === 'jzfs_bridge' ? 'Bridge: Live DCS2' : 'Bridge: psutil';
  }

  const fpsVal = document.getElementById('fpsVal');
  if (fpsVal && typeof data.fps === 'number') {
    fpsVal.innerText = data.fps.toFixed(1);
  }

  // Mode buttons
  ['monitor', 'media', 'text', 'off'].forEach(m => {
    const btn = document.getElementById('btnMode' + m.charAt(0).toUpperCase() + m.slice(1));
    if (btn) btn.className = 'btn' + (data.mode === m ? ' active' : '') + (m === 'off' ? ' btn-danger' : '');
  });

  // Panel visibility based on mode
  const themeSec = document.getElementById('themeSection');
  const mediaSec = document.getElementById('mediaSection');
  const textSec = document.getElementById('textSection');

  if (themeSec) themeSec.style.display = data.mode === 'monitor' ? 'block' : 'none';
  if (mediaSec) mediaSec.style.display = data.mode === 'media' ? 'block' : 'none';
  if (textSec) textSec.style.display = data.mode === 'text' ? 'block' : 'none';

  // Orientation
  const orientDisp = document.getElementById('orientDisplay');
  if (orientDisp) {
    orientDisp.innerText = `Orientation: ${data.orientation}° ${data.orientation === 180 ? '(Inverted)' : '(Normal)'}`;
  }

  // Brightness UI
  let bPct = data.brightness_percent ?? data.brightness ?? 100;
  if (bPct <= 5) bPct = bPct * 20;

  const bSlider = document.getElementById('brightnessSlider');
  const bBadge = document.getElementById('brightnessBadge');
  if (bSlider) bSlider.value = bPct;
  if (bBadge) bBadge.innerText = `${bPct}%`;

  [25, 50, 75, 100].forEach(p => {
    const btn = document.getElementById('bPreset' + p);
    if (btn) btn.className = 'preset-btn' + (Math.abs(bPct - p) <= 5 ? ' active' : '');
  });

  // Temp Unit buttons
  const btnC = document.getElementById('btnUnitC');
  const btnF = document.getElementById('btnUnitF');
  if (btnC) btnC.className = 'btn btn-sm' + (data.temp_unit === 'C' ? ' active' : '');
  if (btnF) btnF.className = 'btn btn-sm' + (data.temp_unit === 'F' ? ' active' : '');

  // Autostart status
  if (typeof updateAutostartUI === 'function') {
    updateAutostartUI(data.autostart);
  }

  // Storage location text
  const storText = document.getElementById('currentStorageDirText');
  if (storText) {
    storText.innerText = data.media_storage_dir || 'Default (media_store)';
  }

  // Render Themes & Slots
  if (typeof renderThemes === 'function') {
    renderThemes(data.available_themes, data.active_theme, data.theme_config);
  }

  // Render Media Library
  if (typeof renderMedia === 'function') {
    renderMedia(data.media_list, data.active_media_id);
  }

  // Populate Text Studio options
  if (typeof populateTextStudio === 'function') {
    populateTextStudio(data.text_config, data.available_fonts, data.available_effects);
  }

  if (data.mode === 'text' && typeof textStudioInitialized !== 'undefined' && textStudioInitialized) {
    if (typeof updateStageSensorTexts === 'function') {
      updateStageSensorTexts();
    }
  }

  // Render Sensors HUD
  if (typeof renderSensors === 'function') {
    renderSensors(data.sensors, data.temp_unit);
  }
}

// Reconnection for live preview stream
const previewImg = document.getElementById('previewImg');
if (previewImg) {
  previewImg.onerror = () => {
    setTimeout(() => {
      previewImg.src = '/api/preview/stream?t=' + Date.now();
    }, 1000);
  };
}

// Drag & drop handlers for upload zone
const dropArea = document.getElementById('uploadZone');
if (dropArea) {
  ['dragenter', 'dragover'].forEach(name => {
    dropArea.addEventListener(name, (e) => {
      e.preventDefault();
      dropArea.classList.add('dragover');
    }, false);
  });
  ['dragleave', 'drop'].forEach(name => {
    dropArea.addEventListener(name, (e) => {
      e.preventDefault();
      dropArea.classList.remove('dragover');
    }, false);
  });
  dropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    if (typeof handleFileUpload === 'function') {
      handleFileUpload(e.dataTransfer.files);
    }
  }, false);
}

// Boot sequence
document.addEventListener('DOMContentLoaded', () => {
  if (typeof fetchStatus === 'function') {
    fetchStatus();
    setInterval(fetchStatus, 2000);
  }
});

// Immediate trigger if document is already parsed
if (document.readyState === 'complete' || document.readyState === 'interactive') {
  if (typeof fetchStatus === 'function') {
    fetchStatus();
  }
}
