/**
 * Migration Agent — Frontend Application Logic
 * Handles: file upload, WebSocket streaming, results rendering, tabs, copy/download
 */

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  files: [],          // File objects queued for upload
  jobId: null,        // Active migration job ID
  ws: null,           // WebSocket connection
  result: null,       // Full migration result JSON
  activeTab: 'analysis',
  activeJavaFile: 0,
  activeTestFile: 0,
  inputMode: 'upload', // 'upload' or 'local'
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const dropZone        = $('drop-zone');
const fileInput       = $('file-input');
const folderInput     = $('folder-input');
const fileList        = $('file-list');
const apiKeyInput     = $('api-key');
const modelSelect     = $('model-select');
const migrateBtn      = $('migrate-btn');
const btnText         = $('btn-text');
const btnSpinner      = $('btn-spinner');
const progressSec     = $('progress-section');
const progressFill    = $('progress-fill');
const progressPct     = $('progress-pct');
const progressLbl     = $('progress-label');
const terminal        = $('terminal');
const resultsSec      = $('results-section');

const tabModeUpload   = $('tab-mode-upload');
const tabModeLocal    = $('tab-mode-local');
const panelModeUpload = $('panel-mode-upload');
const panelModeLocal  = $('panel-mode-local');
const localPathInput  = $('local-path-input');
const browseFilesBtn  = $('browse-files-btn');
const browseFolderBtn = $('browse-folder-btn');

// ── Input Mode Toggle ────────────────────────────────────────────────────────
tabModeUpload.addEventListener('click', () => {
  tabModeUpload.classList.add('active');
  tabModeLocal.classList.remove('active');
  panelModeUpload.style.display = 'block';
  panelModeLocal.style.display = 'none';
  state.inputMode = 'upload';
});

tabModeLocal.addEventListener('click', () => {
  tabModeLocal.classList.add('active');
  tabModeUpload.classList.remove('active');
  panelModeLocal.style.display = 'block';
  panelModeUpload.style.display = 'none';
  state.inputMode = 'local';
});

// ── File Handling ─────────────────────────────────────────────────────────────

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => addFiles([...e.target.files]));
folderInput.addEventListener('change', e => addFiles([...e.target.files]));

browseFilesBtn.addEventListener('click', e => {
  e.stopPropagation();
  fileInput.click();
});

browseFolderBtn.addEventListener('click', e => {
  e.stopPropagation();
  folderInput.click();
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  addFiles([...e.dataTransfer.files]);
});

function addFiles(incoming) {
  const allowed = ['.cs', '.csproj', '.json', '.xml', '.txt', '.config', '.zip'];
  for (const file of incoming) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext) && !file.name.includes('.')) continue;
    
    const path = file.webkitRelativePath || file.name;
    if (!state.files.find(f => (f.webkitRelativePath || f.name) === path)) {
      state.files.push(file);
    }
  }
  renderFileList();
}

function renderFileList() {
  fileList.innerHTML = '';
  state.files.forEach((file, i) => {
    const chip = document.createElement('div');
    chip.className = 'file-chip';
    chip.innerHTML = `
      <span>📄 ${escHtml(file.webkitRelativePath || file.name)}</span>
      <span class="file-size">${formatBytes(file.size)}</span>
      <span class="remove-btn" data-idx="${i}" title="Remove">✕</span>
    `;
    fileList.appendChild(chip);
  });
  fileList.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      state.files.splice(+e.target.dataset.idx, 1);
      renderFileList();
    });
  });
}

// ── Migrate Button ────────────────────────────────────────────────────────────

migrateBtn.addEventListener('click', startMigration);

async function startMigration() {
  if (!validateInputs()) return;

  setLoading(true);
  clearTerminal();
  showProgressSection(true);
  hideResults();

  const formData = new FormData();
  
  if (state.inputMode === 'upload') {
    termLog('info', `🚀 Submitting ${state.files.length} file(s) to migration agent...`);
    for (const file of state.files) {
      formData.append('files', file, file.webkitRelativePath || file.name);
    }
  } else {
    const localPath = localPathInput.value.trim();
    termLog('info', `🚀 Direct scanning local folder: ${localPath}...`);
    formData.append('directory_path', localPath);
  }
  
  formData.append('api_key', apiKeyInput.value.trim());
  formData.append('model', modelSelect.value);

  try {
    termLog('info', `🚀 Submitting ${state.files.length} file(s) to migration agent...`);
    const resp = await fetch('/api/migrate', { method: 'POST', body: formData });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }

    const { job_id } = await resp.json();
    state.jobId = job_id;
    termLog('success', `✅ Job created: ${job_id}`);

    // Connect WebSocket
    connectWebSocket(job_id);

  } catch (err) {
    termLog('error', `❌ ${err.message}`);
    setLoading(false);
    showProgressSection(false);
  }
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

function connectWebSocket(jobId) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url   = `${proto}://${location.host}/api/ws/${jobId}`;

  state.ws = new WebSocket(url);

  state.ws.onopen = () => {
    termLog('info', '🔌 WebSocket connected — streaming live events...');
  };

  state.ws.onmessage = e => {
    let payload;
    try { payload = JSON.parse(e.data); }
    catch { return; }

    handleHookEvent(payload);
  };

  state.ws.onerror = () => {
    termLog('error', '⚠️  WebSocket error — falling back to polling...');
    pollStatus(jobId);
  };

  state.ws.onclose = () => {
    termLog('info', '🔌 WebSocket closed');
    // If not done, start polling
    if (state.jobId) pollStatus(jobId);
  };
}

function handleHookEvent(payload) {
  const { event, message, data } = payload;

  switch (event) {
    case 'MIGRATION_START':
    case 'FILES_UPLOADED':
    case 'ANALYSIS_DONE':
    case 'RAG_RETRIEVED':
    case 'LLM_GENERATING':
    case 'CONVERSION_DONE':
    case 'TESTS_GENERATED':
    case 'PACKAGING':
      termLog('info', message);
      updateProgress(data?.progress ?? estimateProgress(event), message);
      break;

    case 'LLM_STREAM':
      // Show streaming chunks in a subtle way
      appendStreamChunk(data?.chunk || message || '');
      break;

    case 'MIGRATION_COMPLETE':
      termLog('success', message);
      updateProgress(100, '🎉 Complete!');
      state.jobId = null;
      state.ws?.close();
      fetchAndDisplayResult(payload.job_id);
      break;

    case 'MIGRATION_ERROR':
      termLog('error', message || '❌ Migration failed');
      setLoading(false);
      break;

    case 'CONNECTED':
      termLog('info', message);
      break;
  }
}

const PROGRESS_MAP = {
  MIGRATION_START:  5,  FILES_UPLOADED: 10,
  ANALYSIS_DONE:   30,  RAG_RETRIEVED:  50,
  LLM_GENERATING:  55,  CONVERSION_DONE: 75,
  TESTS_GENERATED: 88,  PACKAGING:       92,
};
function estimateProgress(event) { return PROGRESS_MAP[event] ?? 50; }

// ── Polling Fallback ──────────────────────────────────────────────────────────

function pollStatus(jobId) {
  const timer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/migrate/${jobId}/status`);
      if (!resp.ok) return;
      const status = await resp.json();

      updateProgress(status.progress, status.current_step);
      termLog('info', status.current_step);

      if (status.status === 'complete') {
        clearInterval(timer);
        state.jobId = null;
        fetchAndDisplayResult(jobId);
      } else if (status.status === 'error') {
        clearInterval(timer);
        termLog('error', `❌ ${status.error}`);
        setLoading(false);
      }
    } catch (err) {
      clearInterval(timer);
      termLog('error', `Polling error: ${err.message}`);
      setLoading(false);
    }
  }, 1500);
}

// ── Fetch & Display Result ────────────────────────────────────────────────────

async function fetchAndDisplayResult(jobId) {
  try {
    termLog('info', '📥 Fetching full migration result...');
    const resp = await fetch(`/api/migrate/${jobId}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const result = await resp.json();
    state.result = result;
    displayResult(result);
    setLoading(false);

  } catch (err) {
    termLog('error', `Failed to fetch result: ${err.message}`);
    setLoading(false);
  }
}

function displayResult(result) {
  resultsSec.style.display = 'block';
  resultsSec.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Stats
  $('stat-java').textContent   = result.total_java_files || result.java_files?.length || 0;
  $('stat-tests').textContent  = result.total_test_files || result.test_files?.length || 0;
  $('stat-version').textContent = result.analysis?.dotnet_version || '?';

  const fw = result.analysis?.frameworks_detected || [];
  $('stat-fw').textContent = fw.length;

  // Success banner
  const jCount = result.java_files?.length || 0;
  const tCount = result.test_files?.length || 0;
  $('banner-detail').textContent =
    `${jCount} Java file${jCount !== 1 ? 's' : ''}, ${tCount} test file${tCount !== 1 ? 's' : ''} generated`;

  // Analysis tab
  renderAnalysis(result.analysis || {});

  // Java files tab
  renderCodeTab('java-files-container', 'java-file-selector', result.java_files || [], 'java');

  // Test files tab
  renderCodeTab('test-files-container', 'test-file-selector', result.test_files || [], 'java');

  // Config tab
  renderConfig(result.pom_xml || '', result.application_yml || '');

  // Notes tab
  renderNotes(result.notes || {});

  // Update tab counts
  setTabCount('tab-java', result.java_files?.length || 0);
  setTabCount('tab-tests', result.test_files?.length || 0);

  // Download button
  const dlBtn = $('download-btn');
  dlBtn.onclick = () => { window.location.href = `/api/migrate/${result.job_id}/download`; };
  dlBtn.removeAttribute('disabled');
}

// ── Render Helpers ────────────────────────────────────────────────────────────

function renderAnalysis(analysis) {
  const fw   = analysis.frameworks_detected || [];
  const deps = analysis.dependencies || [];
  const cons = analysis.migration_considerations || [];

  $('analysis-frameworks').innerHTML = fw.length
    ? fw.map(f => `<span class="tag">${escHtml(f)}</span>`).join('')
    : '<span class="tag">None detected</span>';

  $('analysis-deps').innerHTML = deps.length
    ? deps.map(d => `<span class="tag cyan">${escHtml(d)}</span>`).join('')
    : '<span class="tag cyan">None</span>';

  $('analysis-version').textContent = analysis.dotnet_version || 'Unknown';

  $('analysis-considerations').innerHTML = cons.length
    ? cons.map(c => `<div class="consideration-item">${escHtml(c)}</div>`).join('')
    : '<div class="consideration-item">No specific considerations noted</div>';
}

function renderCodeTab(containerId, selectorId, files, lang) {
  const container = $(containerId);
  const selector  = $(selectorId);

  if (!files.length) {
    container.innerHTML = `<div class="empty-state"><div class="icon">📭</div><p>No files generated</p></div>`;
    selector.innerHTML = '';
    return;
  }

  // File selector buttons
  selector.innerHTML = files.map((f, i) => {
    const short = f.filename.split('/').pop();
    return `<button class="file-select-btn ${i === 0 ? 'active' : ''}" data-idx="${i}">${escHtml(short)}</button>`;
  }).join('');

  selector.querySelectorAll('.file-select-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      selector.querySelectorAll('.file-select-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      showCodeFile(container, files[+btn.dataset.idx], lang);
    });
  });

  // Show first file
  showCodeFile(container, files[0], lang);
}

function showCodeFile(container, file, lang) {
  const short = file.filename.split('/').pop();
  container.innerHTML = `
    <div class="code-wrapper">
      <div class="code-header">
        <span class="code-lang">${escHtml(file.filename)}</span>
        <button class="copy-btn" onclick="copyCode(this)">📋 Copy</button>
      </div>
      <pre class="code-content language-${lang}"><code>${escHtml(file.content)}</code></pre>
    </div>
  `;
  // Syntax highlight if Prism is available
  if (window.Prism) Prism.highlightAll();
}

function renderConfig(pomXml, appYml) {
  const pomContainer = $('pom-container');
  const ymlContainer = $('yml-container');

  pomContainer.innerHTML = `
    <div class="code-wrapper">
      <div class="code-header">
        <span class="code-lang">pom.xml</span>
        <button class="copy-btn" onclick="copyCode(this)">📋 Copy</button>
      </div>
      <pre class="code-content language-xml"><code>${escHtml(pomXml || '<!-- Not generated -->')}</code></pre>
    </div>`;

  ymlContainer.innerHTML = `
    <div class="code-wrapper">
      <div class="code-header">
        <span class="code-lang">application.yml</span>
        <button class="copy-btn" onclick="copyCode(this)">📋 Copy</button>
      </div>
      <pre class="code-content language-yaml"><code>${escHtml(appYml || '# Not generated')}</code></pre>
    </div>`;

  if (window.Prism) Prism.highlightAll();
}

function renderNotes(notes) {
  const decisions = notes.key_decisions || [];
  const risks     = notes.potential_risks || [];

  $('notes-decisions').innerHTML = decisions.length
    ? decisions.map(d => `<div class="note-item decision"><span class="icon">💡</span><span>${escHtml(d)}</span></div>`).join('')
    : '<div class="note-item decision"><span class="icon">💡</span><span>No specific decisions noted</span></div>';

  $('notes-risks').innerHTML = risks.length
    ? risks.map(r => `<div class="note-item risk"><span class="icon">⚠️</span><span>${escHtml(r)}</span></div>`).join('')
    : '<div class="note-item risk"><span class="icon">⚠️</span><span>No significant risks identified</span></div>';
}

// ── Terminal ──────────────────────────────────────────────────────────────────

let streamBuffer = '';
let streamLine   = null;

function termLog(type, msg) {
  const line = document.createElement('div');
  line.className = `term-line ${type}`;
  line.innerHTML = `
    <span class="term-prefix">[${timestamp()}]</span>
    <span class="term-msg">${escHtml(msg)}</span>
  `;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
  streamLine = null;
  streamBuffer = '';
}

function appendStreamChunk(chunk) {
  if (!streamLine) {
    streamLine = document.createElement('div');
    streamLine.className = 'term-line stream';
    streamLine.innerHTML = `<span class="term-prefix">[LLM]</span><span class="term-msg"></span>`;
    terminal.appendChild(streamLine);
  }
  streamBuffer += chunk;
  const msgEl = streamLine.querySelector('.term-msg');
  // Show only last 120 chars of stream to avoid bloat
  msgEl.textContent = streamBuffer.slice(-120);
  terminal.scrollTop = terminal.scrollHeight;
}

function clearTerminal() {
  terminal.innerHTML = `<div class="term-line"><span class="term-prefix">[SYS]</span><span class="term-msg">Terminal ready — awaiting migration events...<span class="term-cursor"></span></span></div>`;
  streamLine = null;
  streamBuffer = '';
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`panel-${target}`)?.classList.add('active');
    state.activeTab = target;
  });
});

function setTabCount(tabId, count) {
  const tab = $(tabId);
  if (!tab) return;
  let badge = tab.querySelector('.tab-count');
  if (!badge) {
    badge = document.createElement('span');
    badge.className = 'tab-count';
    tab.appendChild(badge);
  }
  badge.textContent = count;
}

// ── Copy to Clipboard ─────────────────────────────────────────────────────────

window.copyCode = function(btn) {
  const pre = btn.closest('.code-wrapper').querySelector('pre');
  const text = pre.textContent;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '✅ Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = '📋 Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
};

// ── UI State Helpers ──────────────────────────────────────────────────────────

function setLoading(loading) {
  migrateBtn.disabled = loading;
  btnText.textContent  = loading ? 'Migrating...' : '⚡ Migrate to Java Spring Boot';
  btnSpinner.style.display = loading ? 'block' : 'none';
}

function showProgressSection(show) {
  progressSec.style.display = show ? 'block' : 'none';
}

function hideResults() {
  resultsSec.style.display = 'none';
}

function updateProgress(pct, label) {
  const clamped = Math.min(100, Math.max(0, pct ?? 0));
  progressFill.style.width = clamped + '%';
  progressPct.textContent  = clamped + '%';
  if (label) progressLbl.textContent = label;
}

function validateInputs() {
  if (state.inputMode === 'upload') {
    if (!state.files.length) {
      alert('Please upload at least one .NET file or folder (.cs, .csproj, etc.)');
      return false;
    }
  } else {
    if (!localPathInput.value.trim()) {
      alert('Please enter a local directory path.');
      return false;
    }
  }
  return true;
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function escHtml(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1024 / 1024).toFixed(1) + ' MB';
}

function timestamp() {
  return new Date().toLocaleTimeString('en-US', { hour12: false });
}

// ── Init ──────────────────────────────────────────────────────────────────────
clearTerminal();
console.log('%c.NET → Java Migration Agent', 'color: #7c3aed; font-size: 18px; font-weight: bold;');
console.log('%cReady. Upload .NET files and configure Groq to start.', 'color: #06b6d4;');
