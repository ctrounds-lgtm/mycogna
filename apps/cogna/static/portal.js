const api = `${window.location.origin}/api`;

const state = {
  token: localStorage.getItem('portalToken') || '',
  user: null,
  currentCognaId: null,
  editingCognaId: null,
  humeConsentGiven: false,  // true once guardian confirms the consent modal this session
};

const screens = ['authScreen', 'forgotScreen', 'resetScreen', 'dashboardScreen', 'createCognaScreen', 'cognaDetailScreen'];

// ── Slider descriptions ──
const sliderDescs = {
  warmth: [
    [0,  34, 'Leads with deep tenderness — safety and warmth above all.'],
    [34, 66, 'Balanced between warmth and directness.'],
    [66, 101, 'Candid and straight — no softening, just honest talk.'],
  ],
  validation: [
    [0,  34, 'Primarily affirms and reflects — a mirror of the heart.'],
    [34, 66, 'Balanced between affirming and gently challenging.'],
    [66, 101, 'Asks the hard questions and nudges toward growth.'],
  ],
  tone: [
    [0,  34, 'Light, playful, and full of ease.'],
    [34, 66, 'Balanced between playful and serious.'],
    [66, 101, 'Holds space with weight and emotional gravity.'],
  ],
  structure: [
    [0,  34, 'Offers clear steps and a practical road forward.'],
    [34, 66, 'Balanced between step-by-step guidance and open exploration.'],
    [66, 101, 'Asks open questions and trusts the person to find their own path.'],
  ],
  stance: [
    [0,  34, 'A safe harbor — wraps around and protects.'],
    [34, 66, 'Balanced between protecting and empowering.'],
    [66, 101, 'Believes in their capability — nudges toward their own strength.'],
  ],
};

function getDesc(param, val) {
  for (const [lo, hi, text] of (sliderDescs[param] || [])) {
    if (val >= lo && val < hi) return text;
  }
  return '';
}

// ── Screen navigation ──
function showScreen(id) {
  screens.forEach(sid => {
    document.getElementById(sid).classList.toggle('hidden', sid !== id);
  });
}

// ── Request helper ──
function authHeaders() {
  return { Authorization: `Bearer ${state.token}` };
}

async function req(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: opts.headers || {} });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try { const b = await res.json(); if (b.detail) detail = typeof b.detail === 'string' ? b.detail : Array.isArray(b.detail) ? b.detail.map(e => e.msg || String(e)).join('; ') : JSON.stringify(b.detail); } catch {}
    throw new Error(detail);
  }
  return res.json();
}

function showError(elId, msg) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
}

function clearError(elId) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = '';
  el.classList.add('hidden');
}

function showDetailStatus(msg, isError) {
  const el = document.getElementById('detailStatus');
  el.textContent = msg;
  el.className = 'status-msg' + (isError ? ' error' : '');
  el.classList.remove('hidden');
}

function clearDetailStatus() {
  document.getElementById('detailStatus').classList.add('hidden');
}

// ── Dashboard loader ──
async function loadDashboard() {
  const data = await req(`${api}/auth/me`, { headers: authHeaders() });
  state.user = data.user;
  document.getElementById('dashWelcome').textContent = `Welcome back, ${state.user.name}`;
  document.getElementById('accessCodeValue').textContent = state.user.child_access_code || '—';

  // Set up tab locking based on tier
  const tierOrder = ['A', 'B', 'C', 'D', 'E'];
  const rawTier = state.user.tier || 'A';
  const tier = tierOrder.includes(rawTier) ? rawTier : 'B';
  const userTierIdx = tierOrder.indexOf(tier);

  tierOrder.forEach((t, idx) => {
    const btn = document.getElementById('dashTab' + t);
    if (idx > userTierIdx) {
      btn.classList.add('locked');
      btn.title = 'Upgrade to unlock';
    }
  });

  // Start on the user's highest tier tab
  const startTab = tier;
  portal.switchDashTab(startTab);

  if (tier === 'D' || userTierIdx >= 3) {
    const cognaData = await req(`${api}/cognas`, { headers: authHeaders() });
    renderCognaGrid(cognaData.cognas);
  }

  showScreen('dashboardScreen');
}

function renderCognaGrid(cognas) {
  const grid = document.getElementById('cognaGrid');
  if (!cognas.length) {
    grid.innerHTML = `<div class="empty-state"><p>No Cognas yet.</p><p>Each Cogna is one voice — Mom, a friend, a coach. Add one to get started.</p></div>`;
    return;
  }
  grid.innerHTML = cognas.map(c => {
    const initial = (c.name || '?')[0].toUpperCase();
    const voiceOk = (c.voice_sample || c.elevenlabs_voice_id || c.hume_config_id || c.hume_voice_id) ? '✅' : '⚠️';
    const photoOk = c.photo ? '✅' : '⚠️';
    return `
      <div class="cogna-card" onclick="portal.openCogna('${c.id}')">
        <div class="cogna-card-avatar">${initial}</div>
        <div class="cogna-card-name">${c.name}</div>
        <div class="cogna-card-rel">${c.relationship || ''}</div>
        <div class="cogna-card-status">
          <span>${voiceOk} Voice</span>
          <span>${photoOk} Photo</span>
        </div>
      </div>`;
  }).join('');
}

async function openCognaDetail(cogna) {
  state.currentCognaId = cogna.id;
  const initial = (cogna.name || '?')[0].toUpperCase();
  document.getElementById('detailAvatar').textContent = initial;
  document.getElementById('detailName').textContent = cogna.name;
  document.getElementById('detailRelationship').textContent = cogna.relationship || '';

  const isHumeEVI = !!(cogna.hume_config_id || cogna.hume_voice_id);
  const hasVoice = !!(cogna.voice_sample || cogna.elevenlabs_voice_id || isHumeEVI);
  const hasPhoto = !!cogna.photo;
  const hasTested = isHumeEVI || !!cogna.last_tested_at;

  function setCheck(id, ok, label) {
    const el = document.getElementById(id);
    el.innerHTML = `<span>${ok ? '✅' : '⚠️'}</span> ${label}`;
    el.className = 'check-item' + (ok ? ' done' : '');
  }
  setCheck('checkVoice', hasVoice, 'Voice sample');
  setCheck('checkPhoto', hasPhoto, 'Photo');
  setCheck('checkTested', hasTested, 'Voice tested');

  const preview = document.getElementById('photoPreview');
  if (cogna.photo) {
    preview.innerHTML = `<img src="${cogna.photo}" alt="Photo">`;
    preview.classList.remove('hidden');
  } else {
    preview.classList.add('hidden');
  }

  // Voice saved banner
  const voiceBanner = document.getElementById('voiceSavedBanner');
  if (hasVoice) {
    voiceBanner.classList.remove('hidden');
  } else {
    voiceBanner.classList.add('hidden');
  }

  document.getElementById('testResult').classList.add('hidden');
  const testForm = document.getElementById('testVoiceForm');
  const testHint = document.getElementById('humeTestHint');
  if (isHumeEVI) {
    testForm.classList.add('hidden');
    if (testHint) testHint.classList.remove('hidden');
  } else {
    testForm.classList.remove('hidden');
    if (testHint) testHint.classList.add('hidden');
  }
  document.getElementById('voiceSampleFile').value = '';
  document.getElementById('voiceFilename').textContent = 'No file chosen';
  document.getElementById('photoFile').value = '';
  document.getElementById('photoFilename').textContent = 'No file chosen';
  showScreen('cognaDetailScreen');
}

function resetCreateForm() {
  document.getElementById('cognaName').value = '';
  document.getElementById('cognaRelationship').value = '';
  document.getElementById('cognaTOE').value = '';
  document.getElementById('cognaAvatar').textContent = '?';
  ['warmth', 'validation', 'tone', 'structure', 'stance'].forEach(p => {
    const key = p.charAt(0).toUpperCase() + p.slice(1);
    document.getElementById('slider' + key).value = 50;
    portal.updateSlider(p, 50);
  });
  document.querySelectorAll('input[name=voiceBackend]')[0].checked = true;
  document.getElementById('ttsVoiceField').classList.remove('hidden');
  document.getElementById('ttsVoice').value = 'nova';
  document.getElementById('elevenlabsField').classList.add('hidden');
  document.getElementById('elevenlabsVoiceId').value = '';
  document.getElementById('humeField').classList.add('hidden');
  document.getElementById('humeConfigId').value = '';
  document.getElementById('humeVoiceId').value = '';
  state.humeConsentGiven = false;
  clearError('createCognaError');

  const saveBtn = document.querySelector('#createCognaScreen .save-btn');
  saveBtn.textContent = 'Save this Cogna voice →';
  saveBtn.onclick = portal.saveCogna;
  state.editingCognaId = null;
}

function getSliderValues() {
  return {
    warmth: parseInt(document.getElementById('sliderWarmth').value),
    validation: parseInt(document.getElementById('sliderValidation').value),
    tone: parseInt(document.getElementById('sliderTone').value),
    structure: parseInt(document.getElementById('sliderStructure').value),
    stance: parseInt(document.getElementById('sliderStance').value),
  };
}

// ── Public portal API ──
const portal = {
  showLogin() {
    showScreen('authScreen');
    this.switchTab('login');
  },

  showForgotPassword() {
    clearError('forgotError');
    document.getElementById('forgotEmail').value = '';
    document.getElementById('forgotSuccess').classList.add('hidden');
    showScreen('forgotScreen');
  },

  switchTab(tab) {
    document.getElementById('loginForm').classList.toggle('hidden', tab !== 'login');
    document.getElementById('registerForm').classList.toggle('hidden', tab !== 'register');
    document.getElementById('tabLogin').classList.toggle('active', tab === 'login');
    document.getElementById('tabRegister').classList.toggle('active', tab === 'register');
  },

  logout() {
    state.token = '';
    state.user = null;
    localStorage.removeItem('portalToken');
    showScreen('authScreen');
  },

  updateAvatar(name) {
    const initial = (name.trim()[0] || '?').toUpperCase();
    document.getElementById('cognaAvatar').textContent = initial;
  },

  updateSlider(param, val) {
    val = parseInt(val, 10);
    const fill = document.getElementById(param + 'Fill');
    const badge = document.getElementById(param + 'Badge');
    const desc = document.getElementById(param + 'Desc');
    if (fill) fill.style.width = val + '%';
    if (badge) badge.textContent = val;
    if (desc) desc.textContent = getDesc(param, val);
  },

  updateVoiceBackend(val) {
    document.getElementById('ttsVoiceField').classList.toggle('hidden', val !== 'tts');
    document.getElementById('elevenlabsField').classList.toggle('hidden', val !== 'elevenlabs');
    document.getElementById('humeField').classList.toggle('hidden', val !== 'hume');
    if (val === 'hume' && !state.humeConsentGiven) {
      // Show consent modal; revert selection if guardian cancels
      document.getElementById('humeConsentCheck').checked = false;
      document.getElementById('humeConsentModal').classList.remove('hidden');
    }
  },

  confirmHumeConsent() {
    if (!document.getElementById('humeConsentCheck').checked) {
      document.getElementById('humeConsentCheck').focus();
      return;
    }
    state.humeConsentGiven = true;
    document.getElementById('humeConsentModal').classList.add('hidden');
  },

  cancelHumeConsent() {
    document.getElementById('humeConsentModal').classList.add('hidden');
    // Revert radio to tts
    const ttsRadio = document.querySelector('input[name=voiceBackend][value=tts]');
    if (ttsRadio) { ttsRadio.checked = true; portal.updateVoiceBackend('tts'); }
    state.humeConsentGiven = false;
  },

  async showDashboard() {
    await loadDashboard();
  },

  showCreateCogna() {
    resetCreateForm();
    showScreen('createCognaScreen');
  },

  async saveCogna() {
    const name = document.getElementById('cognaName').value.trim();
    if (!name) { showError('createCognaError', 'Please enter a voice name.'); return; }

    const backendEl = document.querySelector('input[name=voiceBackend]:checked');
    const voiceBackend = backendEl ? backendEl.value : 'tts';

    if (voiceBackend === 'hume' && !state.humeConsentGiven) {
      showError('createCognaError', 'Please accept the Hume data processing consent before saving.');
      return;
    }

    const elevenlabsVoiceId = voiceBackend === 'elevenlabs'
      ? document.getElementById('elevenlabsVoiceId').value.trim() || null
      : null;
    const humeVoiceId = voiceBackend === 'hume'
      ? document.getElementById('humeVoiceId').value.trim() || null
      : null;
    const humeConfigId = voiceBackend === 'hume'
      ? document.getElementById('humeConfigId').value.trim() || null
      : null;

    const ttsVoice = voiceBackend === 'tts' ? document.getElementById('ttsVoice').value : null;
    const payload = {
      name,
      relationship: document.getElementById('cognaRelationship').value.trim(),
      term_of_endearment: document.getElementById('cognaTOE').value.trim(),
      params: { ...getSliderValues(), ...(ttsVoice ? { tts_voice: ttsVoice } : {}) },
      voice_backend: voiceBackend,
      elevenlabs_voice_id: elevenlabsVoiceId,
      hume_voice_id: humeVoiceId,
      hume_config_id: humeConfigId,
    };

    try {
      clearError('createCognaError');
      const result = await req(`${api}/cognas`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (voiceBackend === 'hume') {
        await req(`${api}/cognas/${result.cogna.id}/hume-consent`, {
          method: 'POST',
          headers: authHeaders(),
        });
      }
      await openCognaDetail(result.cogna);
    } catch (err) {
      showError('createCognaError', err.message);
    }
  },

  async openCogna(cognaId) {
    try {
      const result = await req(`${api}/cognas/${cognaId}`, { headers: authHeaders() });
      await openCognaDetail(result.cogna);
    } catch (err) {
      alert(err.message);
    }
  },

  async editCogna() {
    if (!state.currentCognaId) return;
    const result = await req(`${api}/cognas/${state.currentCognaId}`, { headers: authHeaders() });
    const c = result.cogna;

    document.getElementById('cognaName').value = c.name;
    document.getElementById('cognaRelationship').value = c.relationship || '';
    document.getElementById('cognaTOE').value = c.term_of_endearment || '';
    portal.updateAvatar(c.name);

    const params = c.params || {};
    ['warmth', 'validation', 'tone', 'structure', 'stance'].forEach(p => {
      const val = params[p] !== undefined ? params[p] : 50;
      document.getElementById('slider' + p.charAt(0).toUpperCase() + p.slice(1)).value = val;
      portal.updateSlider(p, val);
    });

    const backend = c.voice_backend || 'tts';
    // If cogna already has hume consent on record, skip the consent modal on edit
    if (backend === 'hume' && c.hume_consent?.accepted) state.humeConsentGiven = true;
    document.querySelectorAll('input[name=voiceBackend]').forEach(r => { r.checked = r.value === backend; });
    portal.updateVoiceBackend(backend);
    if (c.params?.tts_voice) document.getElementById('ttsVoice').value = c.params.tts_voice;
    if (c.elevenlabs_voice_id) document.getElementById('elevenlabsVoiceId').value = c.elevenlabs_voice_id;
    if (c.hume_config_id) document.getElementById('humeConfigId').value = c.hume_config_id;
    if (c.hume_voice_id) document.getElementById('humeVoiceId').value = c.hume_voice_id;

    state.editingCognaId = state.currentCognaId;
    clearError('createCognaError');

    const saveBtn = document.querySelector('#createCognaScreen .save-btn');
    saveBtn.textContent = 'Save changes →';
    saveBtn.onclick = portal.updateCogna;

    showScreen('createCognaScreen');
  },

  async updateCogna() {
    const cognaId = state.editingCognaId;
    if (!cognaId) return;

    const name = document.getElementById('cognaName').value.trim();
    if (!name) { showError('createCognaError', 'Please enter a voice name.'); return; }

    const backendEl = document.querySelector('input[name=voiceBackend]:checked');
    const voiceBackend = backendEl ? backendEl.value : 'tts';

    if (voiceBackend === 'hume' && !state.humeConsentGiven) {
      showError('createCognaError', 'Please accept the Hume data processing consent before saving.');
      return;
    }

    const elevenlabsVoiceId = voiceBackend === 'elevenlabs'
      ? document.getElementById('elevenlabsVoiceId').value.trim() || null
      : null;
    const humeVoiceId = voiceBackend === 'hume'
      ? document.getElementById('humeVoiceId').value.trim() || null
      : null;
    const humeConfigId = voiceBackend === 'hume'
      ? document.getElementById('humeConfigId').value.trim() || null
      : null;

    const ttsVoice = voiceBackend === 'tts' ? document.getElementById('ttsVoice').value : null;
    const payload = {
      name,
      relationship: document.getElementById('cognaRelationship').value.trim(),
      term_of_endearment: document.getElementById('cognaTOE').value.trim(),
      params: { ...getSliderValues(), ...(ttsVoice ? { tts_voice: ttsVoice } : {}) },
      voice_backend: voiceBackend,
      elevenlabs_voice_id: elevenlabsVoiceId,
      hume_voice_id: humeVoiceId,
      hume_config_id: humeConfigId,
    };

    try {
      clearError('createCognaError');
      await req(`${api}/cognas/${cognaId}`, {
        method: 'PUT',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (voiceBackend === 'hume') {
        await req(`${api}/cognas/${cognaId}/hume-consent`, {
          method: 'POST',
          headers: authHeaders(),
        });
      }
      resetCreateForm();
      await portal.openCogna(cognaId);
    } catch (err) {
      showError('createCognaError', err.message);
    }
  },

  async deleteCogna() {
    const cognaId = state.currentCognaId;
    const name = document.getElementById('detailName').textContent;
    if (!cognaId) return;
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      await req(`${api}/cognas/${cognaId}`, { method: 'DELETE', headers: authHeaders() });
      await portal.showDashboard();
    } catch (err) {
      alert('Could not delete: ' + err.message);
    }
  },

  copyAccessCode() {
    const code = document.getElementById('accessCodeValue').textContent;
    navigator.clipboard.writeText(code).then(() => {
      const btn = document.getElementById('copyBtn');
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
  },

  onVoiceFileChange(input) {
    document.getElementById('voiceFilename').textContent = input.files[0]?.name || 'No file chosen';
  },

  onPhotoFileChange(input) {
    document.getElementById('photoFilename').textContent = input.files[0]?.name || 'No file chosen';
  },

  // ── Stories / Storyteller ──

  switchDashTab(tab) {
    const tier = (state.user && state.user.tier) || 'A';
    const tierOrder = ['A', 'B', 'C', 'D'];
    const userTierIdx = tierOrder.indexOf(tier);
    const tabIdx = tierOrder.indexOf(tab);

    ['A', 'B', 'C', 'D'].forEach(t => {
      document.getElementById('dashTab' + t).classList.toggle('active', t === tab);
      const panel = document.getElementById('panel' + t);
      if (panel) panel.classList.add('hidden');
    });
    document.getElementById('panelLocked').classList.add('hidden');

    // C tab shows for everyone — tier gating will be added when billing is live
    if (tab === 'C') {
      document.getElementById('panelC').classList.remove('hidden');
      return;
    }

    // Check if this tab is above the user's tier
    if (tabIdx > userTierIdx) {
      const labels = { A: 'Free Storyteller', B: 'Unlimited Storyteller', C: 'AI Assisted', D: 'AI Companion' };
      document.getElementById('lockedTitle').textContent = `Upgrade to unlock ${labels[tab]}`;
      document.getElementById('lockedBody').textContent = `Your current plan doesn't include the ${labels[tab]} tier. Upgrade to access this feature.`;
      document.getElementById('panelLocked').classList.remove('hidden');
      return;
    }

    document.getElementById('panel' + tab).classList.remove('hidden');

    if (tab === 'A') portal.loadStoryPanel('A');
    else if (tab === 'B') portal.loadStoryPanel('B');
    else if (tab === 'D' && state.user) {
      req(`${api}/cognas`, { headers: authHeaders() })
        .then(d => renderCognaGrid(d.cognas))
        .catch(err => console.error(err.message));
      portal.loadUsage();
    }
  },

  async loadStoryPanel(tier) {
    try {
      const [codesData, promptsData, recsData] = await Promise.all([
        req(`${api}/storyteller/user-codes?tier=${tier}`, { headers: authHeaders() }),
        req(`${api}/storyteller/prompts`, { headers: authHeaders() }),
        req(`${api}/storyteller/recordings?tier=${tier}`, { headers: authHeaders() }),
      ]);
      portal._renderPromoCodes(codesData.codes || [], tier);
      if (tier === 'A') portal._renderPrompts(promptsData.prompts || []);
      portal._renderRecordings(recsData.recordings || [], tier);

      // Enforce free tier: disable generate button if already has 1 active code
      if (tier === 'A') {
        const activeCount = (codesData.codes || []).filter(c => c.active).length;
        const btn = document.getElementById('generateBtnA');
        if (btn) { btn.disabled = activeCount >= 1; btn.title = activeCount >= 1 ? 'Free tier allows 1 active code' : ''; }
      }
    } catch (err) {
      console.error('loadStoryPanel error:', err.message);
    }
  },

  // Legacy alias
  async loadStories() { return portal.loadStoryPanel('A'); },

  async loadUsage() {
    try {
      const data = await req(`${api}/auth/usage`, { headers: authHeaders() });
      const pct = Math.min(100, data.percent_used || 0);
      document.getElementById('usageLabel').textContent =
        `${data.used_minutes} / ${data.cap_minutes} min`;
      const bar = document.getElementById('usageBar');
      bar.style.width = pct + '%';
      bar.style.background = pct >= 100 ? '#C45E4A' : pct >= 80 ? '#E8A84C' : 'var(--gold)';
      const warning = document.getElementById('usageWarning');
      if (pct >= 80) {
        warning.style.display = 'block';
        warning.textContent = pct >= 100
          ? `Monthly limit reached (${data.cap_minutes} min). Conversations are paused until the 1st of next month.`
          : `Approaching your monthly limit — ${data.remaining_minutes} minutes remaining.`;
        warning.style.color = pct >= 100 ? '#C45E4A' : '#8a6a1a';
      } else {
        warning.style.display = 'none';
      }
    } catch (err) {
      console.error('loadUsage error:', err.message);
    }
  },

  _renderPromoCodes(codes, tier) {
    const suffix = tier || 'A';
    const el = document.getElementById('promoCodesList' + suffix);
    if (!el) return;
    if (!codes.length) {
      el.innerHTML = `<div class="empty-state"><p>No ${suffix}-codes yet. Generate one to get started.</p></div>`;
      return;
    }
    el.innerHTML = codes.map(c => `
      <div class="story-item">
        <div class="story-item-main">
          <div class="story-item-code">${c.code}${c.active ? '' : ' <span style="opacity:0.4;font-size:11px;font-weight:400">(inactive)</span>'}</div>
          ${c.description ? `<div class="story-item-desc">${c.description}</div>` : ''}
        </div>
        <div class="story-item-actions">
          <button class="copy-code-btn" onclick="portal.copyCode('${c.code}', this)">Copy</button>
          ${c.active ? `<button class="story-action-btn" onclick="portal.deactivateCode('${c.code}', '${suffix}')">Deactivate</button>` : ''}
        </div>
      </div>`).join('');
  },

  _renderPrompts(prompts) {
    const el = document.getElementById('promptsList');
    portal._promptsOrder = prompts;
    if (!prompts.length) {
      el.innerHTML = '<div class="empty-state"><p>No prompts yet.</p></div>';
      return;
    }
    el.innerHTML = prompts.map((p, i) => `
      <div class="story-item">
        <div class="story-item-reorder">
          <button class="reorder-btn" onclick="portal.movePrompt('${p.id}','up')" ${i === 0 ? 'disabled' : ''}>↑</button>
          <button class="reorder-btn" onclick="portal.movePrompt('${p.id}','down')" ${i === prompts.length - 1 ? 'disabled' : ''}>↓</button>
        </div>
        <div class="story-item-main">
          <div class="story-item-text">${p.text}${p.active ? '<span class="active-badge">Active</span>' : ''}</div>
          <div class="story-item-meta">${p.created_at ? new Date(p.created_at).toLocaleDateString() : ''}</div>
        </div>
        <div class="story-item-actions">
          <button class="story-action-btn${p.active ? '' : ' activate'}" onclick="portal.activatePrompt('${p.id}')">${p.active ? 'Deactivate' : 'Set Active'}</button>
          <button class="story-action-btn" onclick="portal.deletePrompt('${p.id}')">Delete</button>
        </div>
      </div>`).join('');
  },

  async movePrompt(promptId, direction) {
    const prompts = portal._promptsOrder || [];
    const idx = prompts.findIndex(p => p.id === promptId);
    const newIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (newIdx < 0 || newIdx >= prompts.length) return;
    [prompts[idx], prompts[newIdx]] = [prompts[newIdx], prompts[idx]];
    portal._renderPrompts([...prompts]);
    try {
      await req(`${api}/storyteller/prompts/reorder`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: prompts.map(p => p.id) }),
      });
    } catch (err) {
      console.error('Reorder failed:', err.message);
    }
  },

  _renderRecordings(recs, tier) {
    const t = tier || 'A';
    portal['_allRecordings_' + t] = recs;

    const filterRow = document.getElementById('recordingsFilterRow' + t);
    const filterEl = document.getElementById('recordingsFilter' + t);
    if (recs.length && filterRow && filterEl) {
      const seen = new Set();
      const options = [{ code: '', label: `All ${t}-codes` }];
      recs.forEach(r => {
        if (!seen.has(r.promo_code)) {
          seen.add(r.promo_code);
          options.push({ code: r.promo_code, label: r.promo_code_label ? `${r.promo_code_label} (${r.promo_code})` : r.promo_code });
        }
      });
      filterEl.innerHTML = options.map(o => `<option value="${o.code}">${o.label}</option>`).join('');
      filterRow.classList.remove('hidden');
    } else if (filterRow) {
      filterRow.classList.add('hidden');
    }

    portal._renderRecordingRows(recs, t);
  },

  _renderRecordingRows(recs, tier) {
    const t = tier || 'A';
    const el = document.getElementById('recordingsList' + t);
    if (!el) return;
    if (!recs.length) {
      el.innerHTML = '<div class="empty-state"><p>No recordings yet.</p></div>';
      return;
    }
    el.innerHTML = recs.map(r => `
      <div class="story-item">
        <div class="story-item-main">
          <div class="story-item-meta" style="margin-bottom:4px">
            ${r.promo_code_label ? `<strong style="color:var(--ink)">${r.promo_code_label}</strong> &nbsp;·&nbsp; ` : ''}<span style="color:var(--gold);font-family:'Courier New',monospace">${r.promo_code}</span> &nbsp;·&nbsp; ${r.created_at ? new Date(r.created_at).toLocaleString() : ''}
          </div>
          <div class="recording-transcript">${r.transcript || '<em style="opacity:0.4">No transcript</em>'}</div>
        </div>
      </div>`).join('');
  },

  filterRecordings(code, tier) {
    const t = tier || 'A';
    const recs = portal['_allRecordings_' + t] || [];
    portal._renderRecordingRows(code ? recs.filter(r => r.promo_code === code) : recs, t);
  },

  async generatePromoCode(tier) {
    const t = tier || 'A';
    const desc = prompt('Optional: enter a label for this code (e.g. "Sister Cities 2026")') || '';
    try {
      await req(`${api}/storyteller/user-codes`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: desc, tier: t }),
      });
      await portal.loadStoryPanel(t);
    } catch (err) {
      alert('Error: ' + err.message);
    }
  },

  copyCode(code, btn) {
    navigator.clipboard.writeText(code).then(() => {
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = orig; }, 2000);
    });
  },

  async deactivateCode(code, tier) {
    if (!confirm(`Deactivate user code ${code}? New accounts can no longer be created with this code. Existing accounts are unaffected.`)) return;
    try {
      await req(`${api}/storyteller/user-codes/${code}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      await portal.loadStoryPanel(tier || 'A');
    } catch (err) {
      alert('Error: ' + err.message);
    }
  },

  async createPrompt() {
    const text = document.getElementById('newPromptText').value.trim();
    if (!text) { alert('Please enter a prompt.'); return; }
    try {
      await req(`${api}/storyteller/prompts`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      document.getElementById('newPromptText').value = '';
      await portal.loadStories();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  },

  async activatePrompt(promptId) {
    try {
      await req(`${api}/storyteller/prompts/${promptId}/activate`, {
        method: 'PUT',
        headers: authHeaders(),
      });
      await portal.loadStories();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  },

  async deletePrompt(promptId) {
    if (!confirm('Delete this prompt?')) return;
    try {
      await req(`${api}/storyteller/prompts/${promptId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      await portal.loadStories();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  },
};

window.portal = portal;

// ── Form event listeners ──
document.getElementById('loginForm').addEventListener('submit', async e => {
  e.preventDefault();
  clearError('loginError');
  try {
    const result = await req(`${api}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: document.getElementById('loginEmail').value,
        password: document.getElementById('loginPassword').value,
      }),
    });
    state.token = result.token;
    localStorage.setItem('portalToken', result.token);
    await loadDashboard();
  } catch (err) {
    showError('loginError', err.message);
  }
});

document.getElementById('registerForm').addEventListener('submit', async e => {
  e.preventDefault();
  clearError('registerError');
  const password = document.getElementById('registerPassword').value;
  const confirm = document.getElementById('registerConfirm').value;
  if (password !== confirm) {
    showError('registerError', 'Passwords do not match.');
    return;
  }
  try {
    const result = await req(`${api}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: document.getElementById('registerName').value,
        email: document.getElementById('registerEmail').value,
        password,
        setup_type: document.getElementById('setupForChild').checked ? 'guardian' : 'self',
      }),
    });
    state.token = result.token;
    localStorage.setItem('portalToken', result.token);
    await loadDashboard();
  } catch (err) {
    showError('registerError', err.message);
  }
});

document.getElementById('voiceSampleForm').addEventListener('submit', async e => {
  e.preventDefault();
  const file = document.getElementById('voiceSampleFile').files[0];
  if (!file) return;
  const btn = document.getElementById('voiceUploadBtn');
  btn.textContent = 'Uploading…';
  btn.disabled = true;
  const body = new FormData();
  body.append('file', file);
  try {
    await req(`${api}/cognas/${state.currentCognaId}/sample`, {
      method: 'POST',
      headers: authHeaders(),
      body,
    });
    const result = await req(`${api}/cognas/${state.currentCognaId}`, { headers: authHeaders() });
    await openCognaDetail(result.cogna);
  } catch (err) {
    showDetailStatus(err.message, true);
    btn.textContent = 'Upload voice sample';
    btn.disabled = false;
  }
});

document.getElementById('photoForm').addEventListener('submit', async e => {
  e.preventDefault();
  const file = document.getElementById('photoFile').files[0];
  if (!file) return;
  const body = new FormData();
  body.append('file', file);
  try {
    await req(`${api}/cognas/${state.currentCognaId}/photo`, {
      method: 'POST',
      headers: authHeaders(),
      body,
    });
    const result = await req(`${api}/cognas/${state.currentCognaId}`, { headers: authHeaders() });
    await openCognaDetail(result.cogna);
    showDetailStatus('✅ Photo saved.', false);
  } catch (err) {
    showDetailStatus(err.message, true);
  }
});

document.getElementById('testVoiceForm').addEventListener('submit', async e => {
  e.preventDefault();
  const message = document.getElementById('testMessage').value.trim();
  if (!message) return;
  try {
    const result = await req(`${api}/cognas/${state.currentCognaId}/test`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const testResult = document.getElementById('testResult');
    testResult.innerHTML = `
      <p style="font-size:13px;color:var(--ink-muted);margin-bottom:8px">Audio generated:</p>
      <audio controls src="${result.audio_url}" style="width:100%"></audio>
    `;
    testResult.classList.remove('hidden');
    showDetailStatus('Voice test generated.', false);
    document.getElementById('checkTested').innerHTML = '<span>✅</span> Voice tested';
    document.getElementById('checkTested').className = 'check-item done';
  } catch (err) {
    showDetailStatus(err.message, true);
  }
});

document.getElementById('forgotForm').addEventListener('submit', async e => {
  e.preventDefault();
  clearError('forgotError');
  document.getElementById('forgotSuccess').classList.add('hidden');
  try {
    await req(`${api}/auth/request-reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: document.getElementById('forgotEmail').value }),
    });
    const successEl = document.getElementById('forgotSuccess');
    successEl.textContent = 'Check your email for a reset link. It expires in 1 hour.';
    successEl.classList.remove('hidden');
    document.querySelector('#forgotForm button[type=submit]').disabled = true;
  } catch (err) {
    showError('forgotError', err.message);
  }
});

document.getElementById('resetForm').addEventListener('submit', async e => {
  e.preventDefault();
  clearError('resetError');
  const password = document.getElementById('resetPassword').value;
  const confirm = document.getElementById('resetConfirm').value;
  if (password !== confirm) { showError('resetError', 'Passwords do not match.'); return; }
  if (password.length < 8) { showError('resetError', 'Password must be at least 8 characters.'); return; }
  const token = new URLSearchParams(window.location.search).get('reset_token');
  try {
    await req(`${api}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    });
    // Strip token from URL and go to login
    history.replaceState({}, '', window.location.pathname);
    portal.showLogin();
    document.getElementById('loginError').textContent = '';
    // Show a one-time success hint on the login form
    const hint = document.createElement('p');
    hint.style.cssText = 'color:#7aab8a;font-size:0.9rem;margin-bottom:8px';
    hint.textContent = 'Password updated! Sign in with your new password.';
    document.getElementById('loginForm').prepend(hint);
    setTimeout(() => hint.remove(), 8000);
  } catch (err) {
    showError('resetError', err.message);
  }
});

// ── Init ──
async function init() {
  // Check for password reset token in URL
  const resetToken = new URLSearchParams(window.location.search).get('reset_token');
  if (resetToken) {
    showScreen('resetScreen');
    return;
  }
  if (!state.token) { showScreen('authScreen'); return; }
  try {
    await loadDashboard();
  } catch {
    localStorage.removeItem('portalToken');
    state.token = '';
    showScreen('authScreen');
  }
}

init();
