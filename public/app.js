const state = {
  settings: null,
  tree: [],
  selectedMedia: null,
  artifacts: [],
  selectedArtifact: null,
  reportArtifact: null,
  subtitles: [],
  speakers: [],
  libraryViewMode: 'folder',
  libraryGroupMode: 'directory',
  workbenchSplit: Number(localStorage.getItem('workbenchSplit') || 60),
  textScale: Number(localStorage.getItem('textScale') || 1),
  activeSubtitleIndex: -1,
  lastAutoScrollAt: 0,
  activeJobId: null,
  jobTimer: null
};

const els = {
  libraryView: document.querySelector('#libraryView'),
  workbenchView: document.querySelector('#workbenchView'),
  backToLibraryBtn: document.querySelector('#backToLibraryBtn'),
  openFoldersBtn: document.querySelector('#openFoldersBtn'),
  foldersOverlay: document.querySelector('#foldersOverlay'),
  closeFoldersBtn: document.querySelector('#closeFoldersBtn'),
  openSettingsBtn: document.querySelector('#openSettingsBtn'),
  settingsOverlay: document.querySelector('#settingsOverlay'),
  closeSettingsBtn: document.querySelector('#closeSettingsBtn'),
  activePath: document.querySelector('#activePath'),
  addFolderForm: document.querySelector('#addFolderForm'),
  folderInput: document.querySelector('#folderInput'),
  pickFolderBtn: document.querySelector('#pickFolderBtn'),
  folderPathList: document.querySelector('#folderPathList'),
  folderTree: document.querySelector('#folderTree'),
  scanStatus: document.querySelector('#scanStatus'),
  folderViewBtn: document.querySelector('#folderViewBtn'),
  listViewBtn: document.querySelector('#listViewBtn'),
  allMediaBtn: document.querySelector('#allMediaBtn'),
  byDirectoryBtn: document.querySelector('#byDirectoryBtn'),
  refreshBtn: document.querySelector('#refreshBtn'),
  decreaseFontBtn: document.querySelector('#decreaseFontBtn'),
  increaseFontBtn: document.querySelector('#increaseFontBtn'),
  copyMediaPathBtn: document.querySelector('#copyMediaPathBtn'),
  copyContextBtn: document.querySelector('#copyContextBtn'),
  copyContextPanelBtn: document.querySelector('#copyContextPanelBtn'),
  videoFrame: document.querySelector('#videoFrame'),
  videoPlayer: document.querySelector('#videoPlayer'),
  audioFrame: document.querySelector('#audioFrame'),
  audioPlayer: document.querySelector('#audioPlayer'),
  audioTitle: document.querySelector('#audioTitle'),
  audioMeta: document.querySelector('#audioMeta'),
  emptyPlayer: document.querySelector('#emptyPlayer'),
  resizeHandle: document.querySelector('#resizeHandle'),
  subtitleList: document.querySelector('#subtitleList'),
  loadArtifactsBtn: document.querySelector('#loadArtifactsBtn'),
  copySubtitlePathBtn: document.querySelector('#copySubtitlePathBtn'),
  reportTitle: document.querySelector('#reportTitle'),
  reportViewer: document.querySelector('#reportViewer'),
  copyReportPathBtn: document.querySelector('#copyReportPathBtn'),
  contextViewer: document.querySelector('#contextViewer'),
  speakerEditor: document.querySelector('#speakerEditor'),
  saveSpeakersBtn: document.querySelector('#saveSpeakersBtn'),
  artifactList: document.querySelector('#artifactList'),
  artifactTitle: document.querySelector('#artifactTitle'),
  artifactViewer: document.querySelector('#artifactViewer'),
  copyArtifactPathBtn: document.querySelector('#copyArtifactPathBtn'),
  speakerMode: document.querySelector('#speakerMode'),
  recognitionLanguage: document.querySelector('#recognitionLanguage'),
  transcribeBtn: document.querySelector('#transcribeBtn'),
  jobStatus: document.querySelector('#jobStatus'),
  jobStage: document.querySelector('#jobStage'),
  jobDuration: document.querySelector('#jobDuration'),
  jobProgressBar: document.querySelector('#jobProgressBar'),
  jobLog: document.querySelector('#jobLog'),
  asrModel: document.querySelector('#asrModel'),
  outputLanguage: document.querySelector('#outputLanguage'),
  translationTarget: document.querySelector('#translationTarget'),
  scanDepth: document.querySelector('#scanDepth'),
  saveSettingsBtn: document.querySelector('#saveSettingsBtn'),
  checkEnvBtn: document.querySelector('#checkEnvBtn'),
  deployEnvBtn: document.querySelector('#deployEnvBtn'),
  installSkillsBtn: document.querySelector('#installSkillsBtn'),
  downloadAsrBtn: document.querySelector('#downloadAsrBtn'),
  downloadDiarBtn: document.querySelector('#downloadDiarBtn'),
  envResults: document.querySelector('#envResults'),
  toast: document.querySelector('#toast')
};

await boot();

async function boot() {
  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' });
  }
  bindEvents();
  applyTextScale();
  await loadSettings();
  await scan();
  showLibrary();
}

function bindEvents() {
  els.addFolderForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const value = els.folderInput.value.trim();
    if (!value) return;
    await api('/api/folders', { method: 'POST', body: { path: value } });
    els.folderInput.value = '';
    await loadSettings();
    renderFolderPaths();
    await scan();
    toast('已添加文件夹');
  });
  els.pickFolderBtn.addEventListener('click', pickFolder);

  els.backToLibraryBtn.addEventListener('click', showLibrary);
  els.openFoldersBtn.addEventListener('click', openFolders);
  els.closeFoldersBtn.addEventListener('click', closeFolders);
  els.foldersOverlay.addEventListener('click', (event) => {
    if (event.target === els.foldersOverlay) closeFolders();
  });
  els.openSettingsBtn.addEventListener('click', openSettings);
  els.closeSettingsBtn.addEventListener('click', closeSettings);
  els.settingsOverlay.addEventListener('click', (event) => {
    if (event.target === els.settingsOverlay) closeSettings();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeSettings();
      closeFolders();
    }
  });
  els.refreshBtn.addEventListener('click', scan);
  els.decreaseFontBtn.addEventListener('click', () => adjustTextScale(-0.06));
  els.increaseFontBtn.addEventListener('click', () => adjustTextScale(0.06));
  els.folderViewBtn.addEventListener('click', () => setLibraryViewMode('folder'));
  els.listViewBtn.addEventListener('click', () => setLibraryViewMode('list'));
  els.allMediaBtn.addEventListener('click', () => setLibraryGroupMode('all'));
  els.byDirectoryBtn.addEventListener('click', () => setLibraryGroupMode('directory'));
  els.loadArtifactsBtn.addEventListener('click', loadArtifacts);
  els.copyMediaPathBtn.addEventListener('click', () => copyText(state.selectedMedia?.path, '已复制媒体路径'));
  els.copySubtitlePathBtn.addEventListener('click', () => {
    const subtitle = state.artifacts.find((item) => item.name === 'subtitles.srt');
    copyText(subtitle?.path, '已复制字幕路径');
  });
  els.copyArtifactPathBtn.addEventListener('click', () => copyText(state.selectedArtifact?.path, '已复制文件路径'));
  els.copyReportPathBtn.addEventListener('click', () => copyText(state.reportArtifact?.path, '已复制报告路径'));
  els.copyContextBtn.addEventListener('click', copyAiContext);
  els.copyContextPanelBtn.addEventListener('click', copyAiContext);
  els.saveSpeakersBtn.addEventListener('click', saveSpeakers);
  els.transcribeBtn.addEventListener('click', startTranscription);
  els.saveSettingsBtn.addEventListener('click', saveSettings);
  els.checkEnvBtn.addEventListener('click', checkEnv);
  els.deployEnvBtn.addEventListener('click', deployEnv);
  els.installSkillsBtn.addEventListener('click', installSkills);
  els.downloadAsrBtn.addEventListener('click', () => downloadModels({ asr: true, diarization: false }));
  els.downloadDiarBtn.addEventListener('click', () => downloadModels({ asr: false, diarization: true }));

  document.querySelectorAll('.tab').forEach((button) => {
    button.addEventListener('click', () => switchTab(button.dataset.tab));
  });

  [els.videoPlayer, els.audioPlayer].forEach((player) => {
    player.addEventListener('timeupdate', () => markActiveSubtitle(player.currentTime));
  });
  els.videoPlayer.addEventListener('loadedmetadata', updateVideoFrame);
  window.addEventListener('resize', updateVideoFrame);
  bindResizeHandle();
  applyWorkbenchSplit();
}

async function loadSettings() {
  const data = await api('/api/settings');
  state.settings = data.settings;
  els.speakerMode.value = data.settings.speakerMode;
  els.recognitionLanguage.value = data.settings.recognitionLanguage;
  els.outputLanguage.value = data.settings.outputLanguage;
  els.translationTarget.value = data.settings.translationTarget;
  els.scanDepth.value = data.settings.scanDepth;
  els.asrModel.innerHTML = data.modelVariants
    .map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`)
    .join('');
  els.asrModel.value = data.settings.asrModel;
  renderFolderPaths();
}

function showLibrary() {
  els.libraryView.classList.remove('hidden');
  els.workbenchView.classList.add('hidden');
  els.backToLibraryBtn.classList.add('hidden');
  els.activePath.textContent = '本地会议媒体工作台';
}

function showWorkbench() {
  els.libraryView.classList.add('hidden');
  els.workbenchView.classList.remove('hidden');
  els.backToLibraryBtn.classList.remove('hidden');
}

async function scan() {
  els.scanStatus.textContent = '扫描中';
  const data = await api('/api/scan');
  state.tree = data.tree;
  renderFinder();
  els.scanStatus.textContent = countFiles(data.tree);
}

async function pickFolder() {
  els.pickFolderBtn.disabled = true;
  try {
    const data = await api('/api/pick-folder', { method: 'POST', body: {} });
    if (!data.path) {
      toast('已取消选择');
      return;
    }
    els.folderInput.value = data.path;
    await loadSettings();
    renderFolderPaths();
    await scan();
    toast('已添加文件夹');
  } finally {
    els.pickFolderBtn.disabled = false;
  }
}

function renderFolderPaths() {
  const folders = state.settings?.folders || [];
  els.folderPathList.innerHTML = '';
  if (!folders.length) {
    els.folderPathList.innerHTML = '<div class="empty-state">还没有添加任何文件夹</div>';
    return;
  }
  for (const folder of folders) {
    const row = document.createElement('div');
    row.className = 'folder-path-row';
    row.innerHTML = `
      <span class="folder-path-text" title="${escapeHtml(folder)}">${escapeHtml(folder)}</span>
      <button class="secondary" type="button">移除</button>
    `;
    row.querySelector('button').addEventListener('click', () => removeFolder(folder));
    els.folderPathList.appendChild(row);
  }
}

async function removeFolder(folder) {
  await api('/api/folders', { method: 'DELETE', body: { path: folder } });
  await loadSettings();
  renderFolderPaths();
  await scan();
  toast('已移除文件夹');
}

function renderFinder() {
  els.folderTree.innerHTML = '';
  if (!state.tree.length) {
    els.folderTree.innerHTML = '<div class="empty-state">尚未添加文件夹</div>';
    return;
  }
  const files = allFiles();
  els.folderTree.classList.toggle('finder-list', state.libraryViewMode === 'list');
  els.folderTree.classList.toggle('finder-grid', state.libraryViewMode !== 'list');

  if (state.libraryGroupMode === 'all') {
    if (state.libraryViewMode === 'list') {
      els.folderTree.appendChild(renderListBlock({ name: '所有媒体', path: 'all', files }));
    } else {
      for (const file of files) els.folderTree.appendChild(renderFileTile(file));
    }
    return;
  }

  for (const block of allFoldersWithFiles()) {
    els.folderTree.appendChild(state.libraryViewMode === 'list' ? renderListBlock(block) : renderFolderBlock(block));
  }
}

function flattenFolders(folder) {
  return [folder, ...folder.folders.flatMap(flattenFolders)];
}

function allFoldersWithFiles() {
  return state.tree.flatMap((root) => flattenFolders(root)).filter((folder) => folder.files.length);
}

function allFiles() {
  return allFoldersWithFiles().flatMap((folder) => folder.files.map((file) => ({ ...file, groupName: folder.name })));
}

function renderFolderBlock(folder) {
  const wrap = document.createElement('div');
  wrap.className = 'folder-block';
  wrap.innerHTML = `<div class="folder-title" title="${escapeHtml(folder.path)}">${escapeHtml(folder.name)}</div>`;
  const content = document.createElement('div');
  content.className = 'folder-content';
  for (const file of folder.files) content.appendChild(renderFileTile(file));
  wrap.appendChild(content);
  return wrap;
}

function renderFileTile(file) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `file-tile ${state.selectedMedia?.path === file.path ? 'active' : ''}`;
  button.innerHTML = `
    <span class="file-icon">${file.kind === 'video' ? 'VID' : 'AUD'}</span>
    <span>
      <span class="file-name">${escapeHtml(file.name)}</span>
      <span class="file-meta">${formatBytes(file.size)}</span>
    </span>
  `;
  button.addEventListener('click', () => selectMedia(file));
  return button;
}

function renderListBlock(folder) {
  const wrap = document.createElement('div');
  wrap.className = 'list-block';
  if (state.libraryGroupMode === 'directory') {
    wrap.innerHTML = `<div class="list-title" title="${escapeHtml(folder.path)}">${escapeHtml(folder.name)}</div>`;
  }
  const list = document.createElement('div');
  list.className = 'file-list';
  for (const file of folder.files) list.appendChild(renderFileRow(file));
  wrap.appendChild(list);
  return wrap;
}

function renderFileRow(file) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `file-row-wide ${state.selectedMedia?.path === file.path ? 'active' : ''}`;
  button.innerHTML = `
    <span class="file-icon">${file.kind === 'video' ? 'VID' : 'AUD'}</span>
    <span class="file-wide-main">
      <span class="file-name-full">${escapeHtml(file.name)}</span>
      <span class="file-meta">${escapeHtml(file.groupName || file.directory)} · ${formatBytes(file.size)}</span>
    </span>
    <span class="file-meta">${formatDate(file.modifiedAt)}</span>
  `;
  button.addEventListener('click', () => selectMedia(file));
  return button;
}

async function selectMedia(file) {
  state.selectedMedia = file;
  state.selectedArtifact = null;
  state.subtitles = [];
  state.reportArtifact = null;
  els.activePath.textContent = file.path;
  showWorkbench();
  renderPlayer(file);
  await loadArtifacts();
  await loadSpeakers();
  await refreshContextPreview();
  await restoreJobForSelectedMedia();
}

function renderPlayer(file) {
  const mediaUrl = `/media?path=${encodeURIComponent(file.path)}`;
  const video = file.kind === 'video';
  els.videoFrame.style.display = video ? 'grid' : 'none';
  els.videoPlayer.style.display = video ? 'block' : 'none';
  els.audioFrame.style.display = video ? 'none' : 'grid';
  els.audioPlayer.style.display = video ? 'none' : 'block';
  els.emptyPlayer.style.display = 'none';
  const player = video ? els.videoPlayer : els.audioPlayer;
  const other = video ? els.audioPlayer : els.videoPlayer;
  other.pause();
  other.removeAttribute('src');
  player.src = mediaUrl;
  els.audioTitle.textContent = file.name;
  els.audioMeta.textContent = `${formatBytes(file.size)} · ${file.directory}`;
  player.load();
  requestAnimationFrame(updateVideoFrame);
}

async function loadArtifacts() {
  if (!state.selectedMedia) return;
  const data = await api(`/api/artifacts?path=${encodeURIComponent(state.selectedMedia.path)}`);
  state.artifacts = data.artifacts;
  renderArtifacts();
  await loadSubtitles();
  await loadReport();
}

async function loadSubtitles() {
  const srt = state.artifacts.find((item) => item.name === 'subtitles.srt');
  if (srt) {
    const content = await api(`/api/artifact?path=${encodeURIComponent(srt.path)}`);
    state.subtitles = parseSrt(content.content);
  } else {
    state.subtitles = [];
  }
  renderSubtitles();
}

async function loadReport() {
  const preferred = state.artifacts.find((item) => item.name === 'report.md')
    || state.artifacts.find((item) => item.name === 'summary.md')
    || state.artifacts.find((item) => item.type === 'transcript');
  state.reportArtifact = preferred || null;
  if (!preferred) {
    els.reportTitle.textContent = '输出报告';
    els.reportViewer.textContent = '还没有 summary.md 或 report.md。可以先转写，再复制 AI 上下文生成报告。';
    return;
  }
  const data = await api(`/api/artifact?path=${encodeURIComponent(preferred.path)}`);
  els.reportTitle.textContent = preferred.name;
  await renderDocument(els.reportViewer, data.content, preferred);
}

function renderArtifacts() {
  els.artifactList.innerHTML = '';
  if (!state.artifacts.length) {
    els.artifactList.innerHTML = '<div class="empty-state">还没有生成文件</div>';
    els.artifactTitle.textContent = '未选择文件';
    els.artifactViewer.textContent = '';
    return;
  }

  for (const artifact of state.artifacts) {
    const row = document.createElement('div');
    row.className = `artifact-row ${state.selectedArtifact?.path === artifact.path ? 'active' : ''}`;
    row.innerHTML = `
      <button class="artifact-open" type="button">
        <span>${artifactIcon(artifact.type)}</span>
        <span>
          <span class="artifact-name">${escapeHtml(artifact.name)}</span>
          <span class="artifact-meta">${escapeHtml(artifact.location)} · ${formatBytes(artifact.size)}</span>
        </span>
        <span class="artifact-meta">${escapeHtml(relativeDir(artifact.directory))}</span>
      </button>
      <a class="download-button" href="/download?path=${encodeURIComponent(artifact.path)}" download title="下载 ${escapeHtml(artifact.name)}">↓</a>
    `;
    row.querySelector('.artifact-open').addEventListener('click', () => selectArtifact(artifact));
    els.artifactList.appendChild(row);
  }
}

async function selectArtifact(artifact) {
  state.selectedArtifact = artifact;
  renderArtifacts();
  els.artifactTitle.textContent = artifact.name;
  if (artifact.type === 'audio') {
    await renderPlain(els.artifactViewer, 'audio.wav 可在文件系统中使用。');
    return;
  }
  const data = await api(`/api/artifact?path=${encodeURIComponent(artifact.path)}`);
  await renderDocument(els.artifactViewer, data.content, artifact);
}

function renderSubtitles() {
  els.subtitleList.innerHTML = '';
  if (!state.subtitles.length) {
    els.subtitleList.innerHTML = '<div class="empty-state">生成 subtitles.srt 后会显示可点击字幕</div>';
    return;
  }
  state.subtitles.forEach((subtitle, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'subtitle-row';
    button.dataset.start = subtitle.start;
    button.dataset.index = index;
    button.innerHTML = `
      <span class="subtitle-time">${formatTime(subtitle.start)}</span>
      <span class="subtitle-text">${escapeHtml(subtitle.text)}</span>
    `;
    button.addEventListener('click', () => seekTo(subtitle.start));
    els.subtitleList.appendChild(button);
  });
}

async function loadSpeakers() {
  if (!state.selectedMedia) return;
  const data = await api(`/api/speakers?path=${encodeURIComponent(state.selectedMedia.path)}`);
  state.speakers = data.speakers || [];
  renderSpeakers();
}

function renderSpeakers() {
  els.speakerEditor.innerHTML = '';
  if (!state.speakers.length) {
    els.speakerEditor.innerHTML = '<div class="empty-state">当前产物里没有检测到 Speaker 标签</div>';
    return;
  }
  for (const speaker of state.speakers) {
    const row = document.createElement('label');
    row.className = 'speaker-row';
    row.innerHTML = `
      <strong>${escapeHtml(speaker.id)}</strong>
      <input data-speaker-id="${escapeHtml(speaker.id)}" value="${escapeHtml(speaker.name)}">
    `;
    els.speakerEditor.appendChild(row);
  }
}

async function saveSpeakers() {
  if (!state.selectedMedia) return;
  const speakers = Array.from(els.speakerEditor.querySelectorAll('input')).map((input) => ({
    id: input.dataset.speakerId,
    name: input.value.trim() || input.dataset.speakerId
  }));
  const data = await api('/api/speakers', {
    method: 'POST',
    body: { mediaPath: state.selectedMedia.path, speakers }
  });
  toast(`已同步 ${data.changedFiles} 个文件`);
  await loadArtifacts();
  await loadSpeakers();
  await refreshContextPreview();
}

function seekTo(seconds) {
  const player = activePlayer();
  if (!player.src) return;
  player.currentTime = seconds;
  player.play().catch(() => {});
}

function markActiveSubtitle(seconds) {
  let active = null;
  let activeIndex = -1;
  const rows = Array.from(els.subtitleList.querySelectorAll('.subtitle-row'));
  for (const row of rows) {
    const index = Number(row.dataset.index);
    const subtitle = state.subtitles[index];
    row.classList.remove('active');
    if (subtitle && subtitle.start <= seconds && seconds < subtitle.end + 0.25) {
      active = row;
      activeIndex = index;
    } else if (subtitle && subtitle.start <= seconds) {
      active = row;
      activeIndex = index;
    }
  }
  if (!active) return;
  active.classList.add('active');
  if (activeIndex !== state.activeSubtitleIndex) {
    state.activeSubtitleIndex = activeIndex;
    centerSubtitle(active);
  } else if (Date.now() - state.lastAutoScrollAt > 2200) {
    keepSubtitleVisible(active);
  }
}

async function startTranscription() {
  if (!state.selectedMedia) {
    toast('先选择媒体文件');
    return;
  }
  els.transcribeBtn.disabled = true;
  els.jobLog.textContent = '启动转写任务...\n';
  renderJobStatus({ status: 'running', startedAt: new Date().toISOString(), logs: [] });
  try {
    const data = await api('/api/transcribe', {
      method: 'POST',
      body: {
        mediaPath: state.selectedMedia.path,
        speakerMode: els.speakerMode.value,
        recognitionLanguage: els.recognitionLanguage.value
      }
    });
    trackJob(data.job);
  } catch (error) {
    els.transcribeBtn.disabled = false;
    renderJobStatus(null);
    els.jobLog.textContent += `启动失败：${error.message}\n`;
  }
}

async function restoreJobForSelectedMedia() {
  clearInterval(state.jobTimer);
  state.activeJobId = null;
  els.transcribeBtn.disabled = false;
  if (!state.selectedMedia) {
    renderJobStatus(null);
    els.jobLog.textContent = '';
    return;
  }

  const storageKey = jobStorageKey(state.selectedMedia.path);
  const storedJobId = localStorage.getItem(storageKey);
  let job = null;
  if (storedJobId) {
    job = await fetchJob(storedJobId);
    if (!job || job.mediaPath !== state.selectedMedia.path) {
      localStorage.removeItem(storageKey);
      job = null;
    }
  }
  if (!job) {
    const data = await api(`/api/jobs?mediaPath=${encodeURIComponent(state.selectedMedia.path)}`);
    job = data.job || null;
  }

  if (!job) {
    renderJobStatus(null);
    els.jobLog.textContent = '';
    return;
  }
  trackJob(job);
}

function trackJob(job) {
  if (!job?.id) return;
  state.activeJobId = job.id;
  if (job.mediaPath) localStorage.setItem(jobStorageKey(job.mediaPath), job.id);
  renderJob(job);
  if (job.status === 'running') {
    pollJob(job.id);
  } else {
    clearInterval(state.jobTimer);
  }
}

async function pollJob(id) {
  clearInterval(state.jobTimer);
  const refresh = async () => {
    const job = await fetchJob(id);
    if (!job) {
      clearInterval(state.jobTimer);
      if (state.activeJobId === id) {
        state.activeJobId = null;
        els.transcribeBtn.disabled = false;
      }
      return;
    }
    renderJob(job);
    if (job.status !== 'running') {
      clearInterval(state.jobTimer);
      toast(job.status === 'completed' ? '任务完成' : '任务失败');
      if (job.mediaPath && state.selectedMedia?.path === job.mediaPath) {
        await loadArtifacts();
        await loadSpeakers();
        await refreshContextPreview();
      }
    }
  };
  await refresh();
  state.jobTimer = setInterval(async () => {
    await refresh();
  }, 1200);
}

async function fetchJob(id) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(id)}`, { quiet: true });
    return data.job;
  } catch {
    return null;
  }
}

function renderJob(job) {
  renderJobStatus(job);
  els.transcribeBtn.disabled = job?.status === 'running';
  els.jobLog.textContent = formatJobLogs(job);
  els.jobLog.scrollTop = els.jobLog.scrollHeight;
}

function renderJobStatus(job) {
  const status = job?.status || 'idle';
  els.jobStatus.className = `job-status ${status}`;
  els.jobStage.textContent = jobStageText(job);
  els.jobDuration.textContent = job ? elapsedTime(job.startedAt, job.endedAt) : '00:00';
  els.jobProgressBar.style.width = `${jobProgressValue(job)}%`;
}

function formatJobLogs(job) {
  if (!job) return '';
  if (!job.logs?.length) return job.status === 'running' ? '任务已启动，等待输出...\n' : '';
  return job.logs.map((entry) => `[${entry.stream}] ${entry.text}`).join('');
}

function jobStageText(job) {
  if (!job) return '尚未开始';
  if (job.status === 'completed') return '转写完成';
  if (job.status === 'failed') return '转写失败';
  const text = formatJobLogs(job);
  if (text.includes('Writing output files')) return '写入字幕和转写稿';
  if (text.includes('Running speaker diarization')) return '区分说话人';
  const chunk = latestAsrChunk(text);
  if (chunk) return `语音识别中 ${chunk.index}/${chunk.total}（${chunk.range}）`;
  if (text.includes('Running ASR')) return '语音识别中';
  if (text.includes('Preparing audio')) return '准备音频';
  if (text.includes('Loading ASR model')) return '加载识别模型';
  if (text.includes('Downloading ')) return '下载模型中';
  return '任务运行中';
}

function jobProgressValue(job) {
  if (!job) return 0;
  if (job.status === 'completed') return 100;
  if (job.status === 'failed') return 100;
  const text = formatJobLogs(job);
  if (text.includes('Writing output files')) return 92;
  if (text.includes('Running speaker diarization')) return 78;
  const chunk = latestAsrChunk(text);
  if (chunk) return Math.max(20, Math.min(76, 20 + Math.round((chunk.index / chunk.total) * 56)));
  if (text.includes('Running ASR')) return 46;
  if (text.includes('Preparing audio')) return 18;
  if (text.includes('Loading ASR model')) return 8;
  if (text.includes('Downloading ')) return 35;
  return 6;
}

function latestAsrChunk(text) {
  const matches = Array.from(text.matchAll(/Running ASR chunk (\d+)\/(\d+) \(([^)]+)\)/g));
  const match = matches.at(-1);
  if (!match) return null;
  return { index: Number(match[1]), total: Number(match[2]), range: match[3] };
}

function elapsedTime(startedAt, endedAt) {
  const start = startedAt ? new Date(startedAt).getTime() : Date.now();
  const end = endedAt ? new Date(endedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((end - start) / 1000));
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function jobStorageKey(mediaPath) {
  return `meetingAutoSummary.job.${mediaPath}`;
}

async function saveSettings() {
  const settings = {
    ...state.settings,
    speakerMode: els.speakerMode.value,
    recognitionLanguage: els.recognitionLanguage.value,
    outputLanguage: els.outputLanguage.value,
    translationTarget: els.translationTarget.value,
    asrModel: els.asrModel.value,
    scanDepth: Number(els.scanDepth.value || 5)
  };
  const data = await api('/api/settings', { method: 'PUT', body: settings });
  state.settings = data.settings;
  toast('设置已保存');
}

async function checkEnv() {
  const data = await api('/api/check');
  renderEnv(data.checks);
}

async function deployEnv() {
  const data = await api('/api/deploy-env', { method: 'POST', body: {} });
  renderEnv(data.steps.map((step) => ({
    label: step.label,
    ok: step.ok,
    detail: trimDetail(step.detail)
  })));
}

async function installSkills() {
  const data = await api('/api/install-skills', { method: 'POST', body: { targets: state.settings.installTargets } });
  renderEnv(data.results.map((item) => ({
    label: `Install ${item.target}`,
    ok: item.ok,
    detail: item.detail
  })));
}

async function downloadModels(options) {
  await saveSettings();
  const data = await api('/api/download-models', { method: 'POST', body: options });
  switchTab('run');
  closeSettings();
  els.jobLog.textContent = '启动模型下载任务...\n';
  pollJob(data.job.id);
}

function renderEnv(items) {
  els.envResults.innerHTML = items
    .map((item) => `
      <div class="env-row">
        <strong class="${item.ok ? 'ok' : 'bad'}">${item.ok ? 'OK' : 'NO'}</strong>
        <div>
          <strong>${escapeHtml(item.label)}</strong>
          <p>${escapeHtml(String(item.detail || ''))}</p>
        </div>
      </div>
    `)
    .join('');
}

async function copyAiContext() {
  if (!state.selectedMedia) {
    toast('先选择媒体文件');
    return;
  }
  const context = await getAiContext();
  await navigator.clipboard.writeText(context);
  els.contextViewer.textContent = context;
  toast('AI 上下文已复制');
}

async function refreshContextPreview() {
  if (!state.selectedMedia) {
    els.contextViewer.textContent = '';
    return;
  }
  els.contextViewer.textContent = await getAiContext();
}

async function renderDocument(element, content, artifact) {
  if (artifact?.name?.endsWith('.md')) {
    await renderMarkdown(element, content);
    return;
  }
  await renderPlain(element, content);
}

async function renderMarkdown(element, content) {
  element.classList.add('markdown-body');
  const raw = window.marked ? window.marked.parse(content, { gfm: true, breaks: false }) : `<pre>${escapeHtml(content)}</pre>`;
  element.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(raw, { ADD_TAGS: ['iframe'], ADD_ATTR: ['target'] }) : raw;
  element.querySelectorAll('pre code.language-mermaid, code.language-mermaid').forEach((node, index) => {
    const source = node.textContent;
    const host = document.createElement('div');
    host.className = 'mermaid';
    host.textContent = source;
    const pre = node.closest('pre') || node;
    pre.replaceWith(host);
    host.id = `mermaid-${Date.now()}-${index}`;
  });
  if (window.mermaid) {
    try {
      await window.mermaid.run({ nodes: element.querySelectorAll('.mermaid') });
    } catch (error) {
      console.warn('Mermaid render failed', error);
    }
  }
  if (window.MathJax?.typesetPromise) {
    try {
      await window.MathJax.typesetPromise([element]);
    } catch (error) {
      console.warn('MathJax render failed', error);
    }
  }
}

async function renderPlain(element, content) {
  element.classList.remove('markdown-body');
  element.innerHTML = `<pre class="plain-text">${escapeHtml(content)}</pre>`;
}

async function getAiContext() {
  const data = await api('/api/context', {
    method: 'POST',
    body: {
      mediaPath: state.selectedMedia.path,
      options: {
        targetLanguage: els.outputLanguage.value,
        translationTarget: els.translationTarget.value
      }
    }
  });
  return data.context;
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.id === `tab-${name}`));
}

function setLibraryViewMode(mode) {
  state.libraryViewMode = mode;
  els.folderViewBtn.classList.toggle('active', mode === 'folder');
  els.listViewBtn.classList.toggle('active', mode === 'list');
  renderFinder();
}

function setLibraryGroupMode(mode) {
  state.libraryGroupMode = mode;
  els.allMediaBtn.classList.toggle('active', mode === 'all');
  els.byDirectoryBtn.classList.toggle('active', mode === 'directory');
  renderFinder();
}

function openSettings() {
  els.settingsOverlay.classList.remove('hidden');
}

function closeSettings() {
  els.settingsOverlay.classList.add('hidden');
}

function openFolders() {
  renderFolderPaths();
  els.foldersOverlay.classList.remove('hidden');
}

function closeFolders() {
  els.foldersOverlay.classList.add('hidden');
}

function bindResizeHandle() {
  let dragging = false;
  const onMove = (event) => {
    if (!dragging) return;
    const rect = els.workbenchView.getBoundingClientRect();
    const x = Math.min(Math.max(event.clientX - rect.left, rect.width * 0.38), rect.width * 0.76);
    state.workbenchSplit = Math.round((x / rect.width) * 100);
    localStorage.setItem('workbenchSplit', String(state.workbenchSplit));
    applyWorkbenchSplit();
  };
  const stop = () => {
    dragging = false;
    document.body.classList.remove('resizing');
  };
  els.resizeHandle.addEventListener('pointerdown', (event) => {
    dragging = true;
    els.resizeHandle.setPointerCapture(event.pointerId);
    document.body.classList.add('resizing');
  });
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', stop);
}

function applyWorkbenchSplit() {
  const left = Math.min(Math.max(state.workbenchSplit, 38), 76);
  document.documentElement.style.setProperty('--workbench-left', `${left}fr`);
  document.documentElement.style.setProperty('--workbench-right', `${100 - left}fr`);
  requestAnimationFrame(updateVideoFrame);
}

function adjustTextScale(delta) {
  state.textScale = Math.min(1.28, Math.max(0.86, Number((state.textScale + delta).toFixed(2))));
  localStorage.setItem('textScale', String(state.textScale));
  applyTextScale();
  toast(`文字大小 ${Math.round(state.textScale * 100)}%`);
}

function applyTextScale() {
  document.documentElement.style.setProperty('--text-scale', state.textScale);
}

function centerSubtitle(row) {
  state.lastAutoScrollAt = Date.now();
  row.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

function keepSubtitleVisible(row) {
  const listRect = els.subtitleList.getBoundingClientRect();
  const rowRect = row.getBoundingClientRect();
  if (rowRect.top < listRect.top + 60 || rowRect.bottom > listRect.bottom - 60) {
    centerSubtitle(row);
  }
}

function updateVideoFrame() {
  if (!state.selectedMedia || state.selectedMedia.kind !== 'video') return;
  const ratio = els.videoPlayer.videoWidth && els.videoPlayer.videoHeight
    ? els.videoPlayer.videoWidth / els.videoPlayer.videoHeight
    : 16 / 9;
  const container = els.videoFrame.parentElement;
  if (!container) return;
  const width = Math.max(320, container.clientWidth);
  const subtitleReserve = Math.min(420, Math.max(260, window.innerHeight * 0.34));
  const maxHeight = Math.max(220, window.innerHeight - 112 - subtitleReserve);
  const availableHeight = Math.max(220, Math.min(maxHeight, width / ratio));
  els.videoFrame.style.height = `${Math.round(availableHeight)}px`;
  els.videoFrame.style.aspectRatio = `${ratio}`;
}

function parseSrt(content) {
  return content
    .replace(/\r/g, '')
    .split(/\n\n+/)
    .map((block) => {
      const lines = block.split('\n').filter(Boolean);
      const timeLine = lines.find((line) => line.includes('-->'));
      if (!timeLine) return null;
      const [startRaw, endRaw] = timeLine.split('-->').map((item) => item.trim());
      const text = lines.slice(lines.indexOf(timeLine) + 1).join(' ');
      return { start: parseSrtTime(startRaw), end: parseSrtTime(endRaw), text };
    })
    .filter(Boolean);
}

function parseSrtTime(value) {
  const match = value.match(/(\d+):(\d+):(\d+),(\d+)/);
  if (!match) return 0;
  const [, hours, minutes, seconds, millis] = match.map(Number);
  return hours * 3600 + minutes * 60 + seconds + millis / 1000;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || 'GET',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const data = await response.json();
  if (!response.ok) {
    if (!options.quiet) toast(data.error || '请求失败');
    throw new Error(data.error || 'Request failed');
  }
  return data;
}

async function copyText(value, message) {
  if (!value) {
    toast('没有可复制的内容');
    return;
  }
  await navigator.clipboard.writeText(value);
  toast(message);
}

function activePlayer() {
  return els.videoPlayer.style.display === 'block' ? els.videoPlayer : els.audioPlayer;
}

function countFiles(tree) {
  let count = 0;
  const walk = (folder) => {
    count += folder.files.length;
    folder.folders.forEach(walk);
  };
  tree.forEach(walk);
  return `${count} 个媒体`;
}

function artifactIcon(type) {
  if (type === 'audio') return 'AUD';
  if (type.includes('subtitles')) return 'SRT';
  if (type === 'transcript') return 'TXT';
  if (type === 'summary') return 'SUM';
  if (type === 'report') return 'RPT';
  return 'FILE';
}

function relativeDir(directory) {
  if (!directory) return '';
  const marker = '/meeting-auto-summary/';
  const index = directory.indexOf(marker);
  return index >= 0 ? directory.slice(index + marker.length) : directory;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function formatTime(seconds) {
  const rounded = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(rounded / 60);
  const secs = rounded % 60;
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function trimDetail(value) {
  const text = String(value || '').trim();
  return text.length > 420 ? `${text.slice(0, 420)}...` : text;
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => els.toast.classList.remove('show'), 1800);
}
