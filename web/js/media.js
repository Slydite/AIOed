/**
 * Media Library, Upload, and Video Crop/Trim Module
 */

let isUploading = false;
let activeCropMediaId = null;
let selectedCropMode = 'center';

function renderMedia(mediaList, activeMediaId) {
  const grid = document.getElementById('mediaGrid');
  if (!grid) return;
  grid.innerHTML = '';

  if (!mediaList || mediaList.length === 0) {
    grid.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; grid-column: 1/-1; padding: 10px;">No animations in library. Drop a GIF or MP4 above!</div>';
    return;
  }

  mediaList.forEach(m => {
    const card = document.createElement('div');
    card.className = 'media-card' + (m.id === activeMediaId ? ' active' : '');
    card.onclick = (e) => {
      if (e.target.closest('button')) return;
      selectMedia(m.id);
    };

    const activeBadge = m.id === activeMediaId ? '<span class="media-active-pill">ACTIVE</span>' : '';
    const cropBtn = m.has_source ? `<button class="media-action-btn" onclick="openCropModal('${m.id}')">Crop</button>` : '';

    card.innerHTML = `
      ${activeBadge}
      <button class="media-delete-btn" title="Delete" onclick="deleteMedia('${m.id}')">✕</button>
      <img class="media-thumb" src="/api/media/${m.id}/thumb.jpg" alt="${m.name}">
      <div class="media-info">
        <div class="media-name" title="${m.name}">${m.name}</div>
        <div class="media-meta">
          <span>${m.type.toUpperCase()}</span>
          <span>${m.fps} FPS</span>
        </div>
        <div class="media-actions">
          ${cropBtn}
        </div>
      </div>
    `;
    grid.appendChild(card);
  });
}

async function selectMedia(media_id) {
  await fetch('/api/media/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ media_id })
  });
  fetchStatus();
}

async function deleteMedia(media_id) {
  if (!confirm('Delete this media loop from library?')) return;
  await fetch(`/api/media/${media_id}`, { method: 'DELETE' });
  fetchStatus();
}

async function handleFileUpload(files) {
  if (!files || files.length === 0 || isUploading) return;
  const file = files[0];
  const formData = new FormData();
  formData.append('file', file);
  formData.append('crop_mode', 'center');

  const zone = document.getElementById('uploadZone');
  if (zone) {
    zone.innerHTML = '<div style="color: var(--accent); font-weight: 600;">Encoding & baking RGB565 frames...</div>';
  }
  isUploading = true;

  try {
    const res = await fetch('/api/media/upload', {
      method: 'POST',
      body: formData
    });
    if (res.ok) {
      await fetchStatus();
    } else {
      alert('Upload failed: ' + (await res.text()));
    }
  } catch (err) {
    alert('Upload error: ' + err);
  } finally {
    isUploading = false;
    if (zone) {
      zone.innerHTML = `
        <input type="file" id="fileInput" style="display: none;" accept=".gif,.mp4,.webm,.png,.jpg,.jpeg" onchange="handleFileUpload(this.files)">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.8" style="margin-bottom: 8px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        <div class="upload-text">Click or drag & drop GIF or MP4 here to import</div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Smart 4:3 center crop & instant RGB565 pre-baking</div>
      `;
    }
  }
}

function toggleStorageEdit() {
  const box = document.getElementById('storageEditBox');
  if (!box) return;
  const isVisible = box.style.display !== 'none';
  box.style.display = isVisible ? 'none' : 'block';
  if (!isVisible) {
    const input = document.getElementById('storagePathInput');
    if (input) {
      input.value = (typeof currentStorageDir !== 'undefined' && currentStorageDir) ? currentStorageDir : 'media_store';
    }
  }
}

async function saveStorageLocation() {
  const input = document.getElementById('storagePathInput');
  const newPath = input ? input.value.trim() : '';
  if (!newPath) {
    alert('Please enter a valid folder path');
    return;
  }
  const check = document.getElementById('moveExistingCheck');
  const moveExisting = check ? check.checked : false;

  const btn = event ? event.target : null;
  const origText = btn ? btn.innerText : '';
  if (btn) {
    btn.innerText = 'Switching...';
    btn.disabled = true;
  }

  try {
    const res = await fetch('/api/media/storage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ storage_dir: newPath, move_existing: moveExisting })
    });
    if (res.ok) {
      const data = await res.json();
      alert(`Storage folder updated successfully to: ${data.storage_dir}\nLoaded ${data.item_count} items.`);
      const box = document.getElementById('storageEditBox');
      if (box) box.style.display = 'none';
      await fetchStatus();
    } else {
      alert('Failed to update storage folder: ' + (await res.text()));
    }
  } catch (err) {
    alert('Error: ' + err);
  } finally {
    if (btn) {
      btn.innerText = origText;
      btn.disabled = false;
    }
  }
}

async function openCropModal(mediaId) {
  activeCropMediaId = mediaId;
  const modal = document.getElementById('cropModal');
  const video = document.getElementById('modalVideo');
  if (modal) modal.classList.add('open');

  if (video) {
    video.src = `/api/media/${mediaId}/source`;
    video.load();
  }

  try {
    const probeRes = await fetch(`/api/media/${mediaId}/probe`);
    if (probeRes.ok) {
      const info = await probeRes.json();
      const trimStart = document.getElementById('trimStart');
      const trimEnd = document.getElementById('trimEnd');
      if (trimStart) trimStart.value = 0.0;
      if (trimEnd) {
        trimEnd.value = info.duration > 0 ? Math.min(10.0, info.duration) : 5.0;
        trimEnd.max = info.duration || 30.0;
      }
    }
  } catch (e) {
    console.error(e);
  }
}

function closeCropModal() {
  const modal = document.getElementById('cropModal');
  if (modal) modal.classList.remove('open');
  const video = document.getElementById('modalVideo');
  if (video) {
    video.pause();
    video.src = '';
  }
  activeCropMediaId = null;
}

function setCropMode(mode) {
  selectedCropMode = mode;
  ['center', 'fit', 'stretch'].forEach(m => {
    const btn = document.getElementById('btnCrop' + m.charAt(0).toUpperCase() + m.slice(1));
    if (btn) btn.className = 'btn btn-sm' + (m === mode ? ' active' : '');
  });
}

function onTrimChange() {
  const trimStart = document.getElementById('trimStart');
  const s = parseFloat(trimStart ? trimStart.value : '0') || 0;
  const video = document.getElementById('modalVideo');
  if (video) video.currentTime = s;
}

async function applyCropAndSave() {
  if (!activeCropMediaId) return;
  const btn = document.getElementById('btnApplyCrop');
  const origText = btn ? btn.innerText : '';
  if (btn) {
    btn.innerText = '⏳ Processing with FFmpeg...';
    btn.disabled = true;
  }

  const trimStart = document.getElementById('trimStart');
  const trimEnd = document.getElementById('trimEnd');
  const cropFps = document.getElementById('cropFps');

  const payload = {
    crop_mode: selectedCropMode,
    start_sec: parseFloat(trimStart ? trimStart.value : '0') || 0.0,
    end_sec: parseFloat(trimEnd ? trimEnd.value : '5') || 5.0,
    fps: parseFloat(cropFps ? cropFps.value : '24') || 24.0
  };

  try {
    const res = await fetch(`/api/media/${activeCropMediaId}/reprocess`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeCropModal();
      await fetchStatus();
      await selectMedia(activeCropMediaId);
    } else {
      alert('Crop failed: ' + (await res.text()));
    }
  } catch (err) {
    alert('Error: ' + err);
  } finally {
    if (btn) {
      btn.innerText = origText;
      btn.disabled = false;
    }
  }
}
