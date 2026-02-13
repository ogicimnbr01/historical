/**
 * Historical Shorts — Command Center
 * Premium Admin Panel JavaScript
 */

// ============================================================================
// Configuration
// ============================================================================
const CONFIG = {
    API_BASE_URL: 'https://cw42g7izf8.execute-api.us-east-1.amazonaws.com/v1',
    API_KEY: ''
};

// State
let videos = [];
let allVideos = []; // Cache for analytics
let selectedVideos = new Set();

// ============================================================================
// Initialize
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    loadStoredApiKey();
    loadDashboard();
});

// ============================================================================
// API Key Management
// ============================================================================
function setApiKey() {
    const input = document.getElementById('apiKeyInput');
    CONFIG.API_KEY = input.value;
    localStorage.setItem('admin_api_key', input.value);
    updateConnectionStatus(true);
    showToast('🔑 API Key saved!', 'success');
    loadDashboard();
}

function loadStoredApiKey() {
    const stored = localStorage.getItem('admin_api_key');
    if (stored) {
        CONFIG.API_KEY = stored;
        document.getElementById('apiKeyInput').value = stored;
        updateConnectionStatus(true);
    }
    localStorage.removeItem('admin_api_url');
}

function updateConnectionStatus(connected) {
    const el = document.getElementById('connectionStatus');
    if (connected) {
        el.innerHTML = '<span class="status-dot online"></span><span class="status-text">Connected</span>';
    } else {
        el.innerHTML = '<span class="status-dot offline"></span><span class="status-text">Disconnected</span>';
    }
}

// ============================================================================
// API Client
// ============================================================================
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'x-api-key': CONFIG.API_KEY
        }
    };

    if (body) options.body = JSON.stringify(body);

    const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, options);

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || `HTTP ${response.status}`);
    }

    return response.json();
}

// ============================================================================
// Navigation
// ============================================================================
function navigateTo(page) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    // Show target
    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.add('active');

    // Update nav
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add('active');

    // Load data
    switch (page) {
        case 'dashboard': loadDashboard(); break;
        case 'videos': loadVideos(); break;
        case 'analytics': loadAnalytics(); break;
        case 'generate': loadGenerateStats(); break;
        case 'jobs': loadJobs(); break;
    }
}

// ============================================================================
// Dashboard
// ============================================================================
async function loadDashboard() {
    if (!CONFIG.API_KEY) return;

    try {
        const stats = await apiCall('/stats');

        // KPI Cards
        animateValue('kpiTotal', stats.total || 0);
        animateValue('kpiComplete', stats.complete || 0);
        animateValue('kpiEligible', stats.eligible || 0);
        animateValue('kpiPending', stats.pending || 0);
        animateValue('kpiFailed', stats.failed || 0);
        animateValue('kpiTest', stats.test || 0);

        // Metric Cards
        document.getElementById('metricMAE').textContent =
            stats.mae !== null && stats.mae !== undefined ? stats.mae.toFixed(2) + '%' : '—';
        document.getElementById('metricCorr').textContent =
            stats.correlation !== null && stats.correlation !== undefined ? stats.correlation.toFixed(3) : '—';
        document.getElementById('metricSample').textContent = stats.sample_size_for_metrics || '0';
        document.getElementById('metricEligibleRate').textContent =
            (stats.eligible_rate || 0) + '%';

        // Load recent videos
        loadRecentVideos();
    } catch (error) {
        console.error('Dashboard load failed:', error);
        showToast('Dashboard: ' + error.message, 'error');
        updateConnectionStatus(false);
    }
}

function animateValue(id, target) {
    const el = document.getElementById(id);
    const current = parseInt(el.textContent) || 0;
    if (current === target) { el.textContent = target; return; }

    const duration = 600;
    const start = performance.now();

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(current + (target - current) * eased);
        if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
}

async function loadRecentVideos() {
    try {
        const data = await apiCall('/videos?limit=8');
        const recentVids = data.videos || [];
        const container = document.getElementById('recentVideos');

        if (recentVids.length === 0) {
            container.innerHTML = '<div class="empty-state">No videos yet</div>';
            return;
        }

        container.innerHTML = recentVids.map(v => `
            <div class="recent-video-row" onclick="navigateTo('videos'); setTimeout(() => viewVideo('${v.video_id}'), 300)">
                <span class="rv-title">${v.title_used || v.video_id}</span>
                <span class="rv-date">${formatDateShort(v.publish_time_utc)}</span>
                <span class="rv-metric">${v.category || '—'}</span>
                <span class="rv-metric">${v.predicted_retention ? Math.round(v.predicted_retention) + '%' : '—'}</span>
                <span class="rv-metric">${v.actual_retention ? Math.round(v.actual_retention) + '%' : '—'}</span>
                <span class="badge ${v.status || 'pending'}">${v.status || 'pending'}</span>
            </div>
        `).join('');
    } catch (e) {
        console.error('Recent videos failed:', e);
    }
}

// ============================================================================
// Videos Page
// ============================================================================
async function loadVideos() {
    if (!CONFIG.API_KEY) {
        showToast('Set API key first', 'error');
        return;
    }

    try {
        const params = new URLSearchParams();
        const status = document.getElementById('filterStatus').value;
        const eligible = document.getElementById('filterEligible').value;
        const mode = document.getElementById('filterMode').value;
        const fallback = document.getElementById('filterFallback').value;

        if (status) params.append('status', status);
        if (eligible) params.append('eligible', eligible);
        if (mode) params.append('mode', mode);
        if (fallback) params.append('fallback', fallback);

        const queryString = params.toString();
        const endpoint = queryString ? `/videos?${queryString}` : '/videos';
        const data = await apiCall(endpoint);
        videos = data.videos || [];

        renderVideosTable();
    } catch (error) {
        console.error('Failed to load videos:', error);
        showToast('Videos: ' + error.message, 'error');
    }
}

function renderVideosTable() {
    const tbody = document.getElementById('videosTableBody');
    tbody.innerHTML = '';

    videos.forEach(video => {
        const tr = document.createElement('tr');
        const isEligible = video.calibration_eligible === true;
        const isFallback = video.pipeline_executed === 'fallback';

        // Compute refine delta
        const firstHook = parseFloat(video.first_hook_score);
        const finalHook = parseFloat(video.final_hook_score);
        let deltaHTML = '<span class="delta-neutral">—</span>';
        if (!isNaN(firstHook) && !isNaN(finalHook)) {
            const delta = finalHook - firstHook;
            const cls = delta > 0 ? 'delta-positive' : delta < 0 ? 'delta-negative' : 'delta-neutral';
            deltaHTML = `<span class="${cls}">${delta > 0 ? '+' : ''}${delta.toFixed(1)}</span>`;
        }

        tr.innerHTML = `
            <td>
                <input type="checkbox" class="video-checkbox" data-id="${video.video_id}"
                    ${selectedVideos.has(video.video_id) ? 'checked' : ''}
                    onchange="toggleVideoSelect('${video.video_id}')">
            </td>
            <td class="cell-title" title="${video.title_used || '-'}">${truncate(video.title_used, 50)}</td>
            <td class="rv-date">${formatDateShort(video.publish_time_utc)}</td>
            <td class="cell-category">${video.category || '—'}</td>
            <td><span class="badge ${video.mode}">${video.mode || '—'}</span></td>
            <td class="cell-mono">${video.hook_score ? parseFloat(video.hook_score).toFixed(1) : '—'}</td>
            <td class="cell-mono">${video.predicted_retention ? Math.round(video.predicted_retention) + '%' : '—'}</td>
            <td class="cell-mono">${video.actual_retention ? Math.round(video.actual_retention) + '%' : '—'}</td>
            <td class="cell-mono">${deltaHTML}</td>
            <td><span class="badge ${video.status}">${video.status || 'pending'}</span></td>
            <td>
                <button class="action-btn" onclick="viewVideo('${video.video_id}')">View</button>
                ${video.status === 'test'
                ? `<button class="action-btn undo" onclick="unmarkTest('${video.video_id}')">↩</button>`
                : `<button class="action-btn test" onclick="markAsTest('${video.video_id}')">TEST</button>`
            }
            </td>
        `;
        tbody.appendChild(tr);
    });

    updateSelectedCount();
}

// ============================================================================
// Analytics Page
// ============================================================================
async function loadAnalytics() {
    if (!CONFIG.API_KEY) return;

    try {
        // Load all videos for analytics
        const data = await apiCall('/videos?limit=200');
        allVideos = data.videos || [];

        renderDeltaChart();
        renderCategoryChart();
        renderRefineChart();
        renderModeChart();
        renderScatterChart();
    } catch (error) {
        console.error('Analytics failed:', error);
        showToast('Analytics: ' + error.message, 'error');
    }
}

function renderDeltaChart() {
    const container = document.getElementById('deltaChart');
    const instrumented = allVideos.filter(v =>
        v.first_hook_score != null && v.final_hook_score != null
    );

    if (instrumented.length < 3) {
        container.innerHTML = '<div class="empty-state">Need 3+ instrumented videos for delta analysis</div>';
        document.getElementById('avgDelta').textContent = '—';
        document.getElementById('goodhartStatus').textContent = '—';
        return;
    }

    // Compute deltas
    const deltas = instrumented.map(v => ({
        delta: parseFloat(v.final_hook_score) - parseFloat(v.first_hook_score),
        retention: v.actual_retention ? parseFloat(v.actual_retention) : null,
        title: v.title_used || v.video_id
    }));

    // Average delta
    const avgDelta = deltas.reduce((s, d) => s + d.delta, 0) / deltas.length;
    document.getElementById('avgDelta').textContent = (avgDelta > 0 ? '+' : '') + avgDelta.toFixed(2);
    document.getElementById('avgDelta').style.color = avgDelta > 0 ? 'var(--green)' : 'var(--red)';

    // Goodhart: Pearson correlation between delta and retention
    const withRetention = deltas.filter(d => d.retention !== null);
    if (withRetention.length >= 5) {
        const ds = withRetention.map(d => d.delta);
        const rs = withRetention.map(d => d.retention);
        const corr = pearsonCorrelation(ds, rs);

        const statusEl = document.getElementById('goodhartStatus');
        const descEl = document.getElementById('goodhartDesc');

        if (corr !== null) {
            statusEl.textContent = corr.toFixed(3);
            if (corr > 0.3) {
                statusEl.style.color = 'var(--green)';
                descEl.textContent = '✅ Score delta correlates with retention';
            } else if (corr < 0.1) {
                statusEl.style.color = 'var(--red)';
                descEl.textContent = '❌ Self-optimization risk detected';
            } else {
                statusEl.style.color = 'var(--yellow)';
                descEl.textContent = '⚠️ Weak signal — more data needed';
            }
        }
    } else {
        document.getElementById('goodhartStatus').textContent = '⏳';
        document.getElementById('goodhartDesc').textContent = `${withRetention.length}/5 samples needed`;
    }

    // Bar chart of delta distribution
    const buckets = { '< -1': 0, '-1–0': 0, '0–1': 0, '1–2': 0, '2–3': 0, '3+': 0 };
    deltas.forEach(d => {
        if (d.delta < -1) buckets['< -1']++;
        else if (d.delta < 0) buckets['-1–0']++;
        else if (d.delta < 1) buckets['0–1']++;
        else if (d.delta < 2) buckets['1–2']++;
        else if (d.delta < 3) buckets['2–3']++;
        else buckets['3+']++;
    });

    const maxCount = Math.max(...Object.values(buckets), 1);
    container.innerHTML = `<div class="bar-chart">
        ${Object.entries(buckets).map(([label, count]) => `
            <div class="bar-item">
                <span class="bar-value">${count}</span>
                <div class="bar" style="height: ${(count / maxCount) * 160}px; background: ${label.startsWith('<') || label.startsWith('-') ? 'var(--red)' : 'var(--accent)'
        }"></div>
                <span class="bar-label">${label}</span>
            </div>
        `).join('')}
    </div>`;
}

function renderCategoryChart() {
    const container = document.getElementById('categoryChart');
    const withCategory = allVideos.filter(v => v.category && v.actual_retention);

    if (withCategory.length < 2) {
        container.innerHTML = '<div class="empty-state">Need complete videos with categories</div>';
        return;
    }

    // Group by category
    const cats = {};
    withCategory.forEach(v => {
        const cat = v.category;
        if (!cats[cat]) cats[cat] = [];
        cats[cat].push(parseFloat(v.actual_retention));
    });

    // Compute averages
    const catAvgs = Object.entries(cats)
        .map(([cat, rets]) => ({
            category: cat,
            avg: rets.reduce((s, r) => s + r, 0) / rets.length,
            count: rets.length
        }))
        .sort((a, b) => b.avg - a.avg);

    const maxAvg = Math.max(...catAvgs.map(c => c.avg), 1);

    container.innerHTML = `<div class="bar-chart">
        ${catAvgs.map(c => `
            <div class="bar-item">
                <span class="bar-value">${c.avg.toFixed(1)}%</span>
                <div class="bar" style="height: ${(c.avg / maxAvg) * 160}px; background: var(--green)"></div>
                <span class="bar-label">${truncate(c.category, 12)}<br><small>(n=${c.count})</small></span>
            </div>
        `).join('')}
    </div>`;
}

function renderRefineChart() {
    const container = document.getElementById('refineChart');
    const withRefine = allVideos.filter(v => v.refine_total != null && v.actual_retention);

    if (withRefine.length < 3) {
        container.innerHTML = '<div class="empty-state">Need more complete videos</div>';
        return;
    }

    // Bucket by refine count
    const buckets = { '0': [], '1': [], '2': [], '3': [], '4+': [] };
    withRefine.forEach(v => {
        const r = parseInt(v.refine_total) || 0;
        const key = r >= 4 ? '4+' : String(r);
        buckets[key].push(parseFloat(v.actual_retention));
    });

    const results = Object.entries(buckets)
        .filter(([_, rets]) => rets.length > 0)
        .map(([label, rets]) => ({
            label,
            avg: rets.reduce((s, r) => s + r, 0) / rets.length,
            count: rets.length
        }));

    const maxAvg = Math.max(...results.map(r => r.avg), 1);

    container.innerHTML = `<div class="bar-chart">
        ${results.map(r => `
            <div class="bar-item">
                <span class="bar-value">${r.avg.toFixed(1)}%</span>
                <div class="bar" style="height: ${(r.avg / maxAvg) * 160}px; background: var(--purple)"></div>
                <span class="bar-label">${r.label} refine<br><small>(n=${r.count})</small></span>
            </div>
        `).join('')}
    </div>`;
}

function renderModeChart() {
    const container = document.getElementById('modeChart');
    const withMode = allVideos.filter(v => v.mode && v.actual_retention);

    if (withMode.length < 2) {
        container.innerHTML = '<div class="empty-state">Need complete videos with mode data</div>';
        return;
    }

    const modes = {};
    withMode.forEach(v => {
        if (!modes[v.mode]) modes[v.mode] = [];
        modes[v.mode].push(parseFloat(v.actual_retention));
    });

    const modeAvgs = Object.entries(modes).map(([mode, rets]) => ({
        mode,
        avg: rets.reduce((s, r) => s + r, 0) / rets.length,
        count: rets.length
    }));

    const maxAvg = Math.max(...modeAvgs.map(m => m.avg), 1);

    container.innerHTML = `<div class="bar-chart">
        ${modeAvgs.map(m => `
            <div class="bar-item">
                <span class="bar-value">${m.avg.toFixed(1)}%</span>
                <div class="bar" style="height: ${(m.avg / maxAvg) * 160}px; background: ${m.mode === 'quality' ? 'var(--purple)' : 'var(--green)'
        }"></div>
                <span class="bar-label">${m.mode}<br><small>(n=${m.count})</small></span>
            </div>
        `).join('')}
    </div>`;
}

function renderScatterChart() {
    const container = document.getElementById('scatterChart');
    const complete = allVideos.filter(v =>
        v.predicted_retention && v.actual_retention && v.calibration_eligible
    );

    if (complete.length < 3) {
        container.innerHTML = '<div class="empty-state">Need 3+ complete eligible videos for scatter plot</div>';
        return;
    }

    const points = complete.map(v => ({
        x: parseFloat(v.predicted_retention),
        y: parseFloat(v.actual_retention),
        title: v.title_used || v.video_id
    }));

    const minVal = Math.min(...points.map(p => Math.min(p.x, p.y))) - 5;
    const maxVal = Math.max(...points.map(p => Math.max(p.x, p.y))) + 5;
    const range = maxVal - minVal;

    const dotsHtml = points.map(p => {
        const left = ((p.x - minVal) / range) * 100;
        const bottom = ((p.y - minVal) / range) * 100;
        return `<div class="dot" style="left: ${left}%; bottom: ${bottom}%" title="${p.title}\nPred: ${p.x.toFixed(1)}% | Act: ${p.y.toFixed(1)}%"></div>`;
    }).join('');

    container.innerHTML = `
        <div class="dot-plot">
            <div class="diagonal-line"></div>
            ${dotsHtml}
            <span class="axis-label x-axis">Predicted →</span>
            <span class="axis-label y-axis">Actual →</span>
        </div>
    `;
}

function pearsonCorrelation(x, y) {
    const n = x.length;
    if (n < 3) return null;

    const meanX = x.reduce((s, v) => s + v, 0) / n;
    const meanY = y.reduce((s, v) => s + v, 0) / n;

    const num = x.reduce((s, xi, i) => s + (xi - meanX) * (y[i] - meanY), 0);
    const denX = Math.sqrt(x.reduce((s, xi) => s + (xi - meanX) ** 2, 0));
    const denY = Math.sqrt(y.reduce((s, yi) => s + (yi - meanY) ** 2, 0));

    if (denX === 0 || denY === 0) return null;
    return num / (denX * denY);
}

// ============================================================================
// Generate Page
// ============================================================================
async function loadGenerateStats() {
    if (!CONFIG.API_KEY) return;

    try {
        const data = await apiCall('/videos?limit=100');
        const vids = data.videos || [];

        const now = new Date();
        const todayStr = now.toISOString().slice(0, 10);
        const weekAgo = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();

        const today = vids.filter(v => (v.publish_time_utc || '').startsWith(todayStr)).length;
        const week = vids.filter(v => (v.publish_time_utc || '') >= weekAgo).length;

        const withRetention = vids.filter(v => v.actual_retention);
        const avgRet = withRetention.length > 0
            ? (withRetention.reduce((s, v) => s + parseFloat(v.actual_retention), 0) / withRetention.length).toFixed(1) + '%'
            : '—';

        document.getElementById('genStatToday').textContent = today;
        document.getElementById('genStatWeek').textContent = week;
        document.getElementById('genStatAvgRet').textContent = avgRet;
    } catch (e) {
        console.error('Generate stats failed:', e);
    }
}

async function generateVideo() {
    if (!CONFIG.API_KEY) {
        showToast('Set API key first', 'error');
        return;
    }

    const mode = document.getElementById('genMode').value;
    const titleVariant = document.getElementById('genTitleVariant').value;
    const topicOverride = document.getElementById('genTopic').value.trim();
    const calibrationEligible = document.getElementById('genEligible').checked;
    const clientRequestId = 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    const payload = {
        mode, title_variant: titleVariant,
        calibration_eligible: calibrationEligible,
        client_request_id: clientRequestId
    };
    if (topicOverride) payload.topic_override = topicOverride;

    try {
        showToast('🚀 Starting video generation...', 'info');
        const response = await apiCall('/generate', 'POST', payload);

        if (response.job_id) {
            showToast(`✅ Generation started! Job: ${response.job_id}`, 'success');
            navigateTo('jobs');
        }
    } catch (error) {
        showToast('Generation failed: ' + error.message, 'error');
    }
}

async function generateTestVideo() {
    if (!CONFIG.API_KEY) {
        showToast('Set API key first', 'error');
        return;
    }

    if (!confirm('Generate a TEST video? It will be ineligible for calibration.')) return;

    const mode = document.getElementById('genMode').value;
    const titleVariant = document.getElementById('genTitleVariant').value;
    const topicOverride = document.getElementById('genTopic').value.trim();
    const clientRequestId = 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    const payload = {
        mode, title_variant: titleVariant,
        calibration_eligible: false,
        mark_as_test: true,
        client_request_id: clientRequestId
    };
    if (topicOverride) payload.topic_override = topicOverride;

    try {
        showToast('🧪 Starting TEST generation...', 'info');
        const response = await apiCall('/generate', 'POST', payload);

        if (response.job_id) {
            showToast(`✅ TEST generation started! Job: ${response.job_id}`, 'success');
            navigateTo('jobs');
        }
    } catch (error) {
        showToast('Test generation failed: ' + error.message, 'error');
    }
}

// ============================================================================
// Jobs Page
// ============================================================================
async function loadJobs() {
    if (!CONFIG.API_KEY) {
        showToast('Set API key first', 'error');
        return;
    }

    const timeline = document.getElementById('jobsTimeline');
    timeline.innerHTML = '<div class="empty-state">Loading jobs...</div>';

    try {
        const params = new URLSearchParams();
        const statusFilter = document.getElementById('jobStatusFilter')?.value;
        if (statusFilter) params.append('status', statusFilter);

        const endpoint = params.toString() ? `/jobs?${params}` : '/jobs';
        const data = await apiCall(endpoint);
        const jobs = data.jobs || [];

        if (jobs.length === 0) {
            timeline.innerHTML = '<div class="empty-state">No jobs in the last 24 hours</div>';
            return;
        }

        timeline.innerHTML = jobs.map(job => `
            <div class="job-card">
                <div class="job-header">
                    <span class="job-id">${job.job_id}</span>
                    <div class="header-right">
                        <span class="job-status ${job.status}">${job.status}</span>
                        <button class="btn-icon" onclick="deleteJob('${job.job_id}')" title="Delete">✕</button>
                    </div>
                </div>
                <div class="job-details">
                    <div>📅 ${formatDate(job.requested_at_utc)}</div>
                    ${job.params ? `<div>⚙️ Mode: ${job.params.mode || 'auto'} | Title: ${job.params.title_variant || 'auto'}</div>` : ''}
                    ${job.result_video_id ? `<div>🎬 Video: ${job.result_video_id}</div>` : ''}
                    ${job.error_message ? `<div>❌ ${job.error_message}</div>` : ''}
                </div>
                <div class="job-actions">
                    <button class="action-btn" onclick="viewJobLogs('${job.job_id}')">📋 Logs</button>
                    ${job.result_video_id ? `<button class="action-btn" onclick="viewVideo('${job.result_video_id}')">🎬 Video</button>` : ''}
                </div>
            </div>
        `).join('');
    } catch (error) {
        timeline.innerHTML = `<div class="empty-state">Error: ${error.message}</div>`;
        showToast('Jobs: ' + error.message, 'error');
    }
}

async function deleteJob(jobId) {
    if (!confirm(`Delete job ${jobId}?`)) return;
    try {
        await apiCall(`/jobs/${encodeURIComponent(jobId)}`, 'DELETE');
        showToast('Job deleted', 'success');
        loadJobs();
    } catch (error) {
        showToast('Delete failed: ' + error.message, 'error');
    }
}

// ============================================================================
// Video Detail Modal
// ============================================================================
async function viewVideo(videoId) {
    try {
        const video = await apiCall(`/videos/${encodeURIComponent(videoId)}`);

        document.getElementById('modalTitle').textContent = `Video: ${truncate(video.title_used || videoId, 40)}`;

        const firstHook = parseFloat(video.first_hook_score);
        const finalHook = parseFloat(video.final_hook_score);
        let deltaDisplay = '—';
        if (!isNaN(firstHook) && !isNaN(finalHook)) {
            const d = finalHook - firstHook;
            deltaDisplay = `<span class="${d > 0 ? 'delta-positive' : d < 0 ? 'delta-negative' : ''}">${d > 0 ? '+' : ''}${d.toFixed(2)}</span>`;
        }

        const body = document.getElementById('modalBody');
        body.innerHTML = `
            <div class="detail-grid">
                <div class="detail-item">
                    <label>Video ID</label>
                    <span class="detail-val" style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;">${video.video_id}</span>
                </div>
                <div class="detail-item">
                    <label>Publish Time</label>
                    <span class="detail-val">${formatDate(video.publish_time_utc)}</span>
                </div>
                <div class="detail-item">
                    <label>Mode</label>
                    <span class="badge ${video.mode}">${video.mode || '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Pipeline</label>
                    <span class="badge ${video.pipeline_executed === 'fallback' ? 'fallback' : 'v24'}">${video.pipeline_executed || 'v2.4'}</span>
                </div>

                <div class="detail-section-title">📊 Performance</div>

                <div class="detail-item">
                    <label>Predicted Retention</label>
                    <span class="detail-val cell-mono">${video.predicted_retention ? Math.round(video.predicted_retention) + '%' : '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Actual Retention</label>
                    <span class="detail-val cell-mono">${video.actual_retention ? Math.round(video.actual_retention) + '%' : 'Pending'}</span>
                </div>
                <div class="detail-item">
                    <label>Hook Score (Final)</label>
                    <span class="detail-val cell-mono">${video.hook_score || video.final_hook_score || '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Visual Relevance</label>
                    <span class="detail-val cell-mono">${video.visual_relevance || '—'}</span>
                </div>

                <div class="detail-section-title">🔬 Refine Delta</div>

                <div class="detail-item">
                    <label>First Hook Score</label>
                    <span class="detail-val cell-mono">${!isNaN(firstHook) ? firstHook.toFixed(2) : '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Final Hook Score</label>
                    <span class="detail-val cell-mono">${!isNaN(finalHook) ? finalHook.toFixed(2) : '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Hook Score Δ</label>
                    <span class="detail-val cell-mono">${deltaDisplay}</span>
                </div>
                <div class="detail-item">
                    <label>Total Refines</label>
                    <span class="detail-val cell-mono">${video.refine_total ?? '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Hook Refines</label>
                    <span class="detail-val cell-mono">${video.hook_refines ?? '—'}</span>
                </div>

                <div class="detail-section-title">📋 Metadata</div>

                <div class="detail-item">
                    <label>Category</label>
                    <span class="detail-val">${video.category || '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Era</label>
                    <span class="detail-val">${video.era || '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Topic Entity</label>
                    <span class="detail-val">${video.topic_entity || '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Title Used</label>
                    <span class="detail-val">${video.title_used || '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Title Variant</label>
                    <span class="detail-val">${video.title_variant_type || '—'}</span>
                </div>
                <div class="detail-item">
                    <label>Virality Score</label>
                    <span class="detail-val cell-mono">${video.virality_score || '—'}</span>
                </div>

                <div class="detail-section-title">⚙️ Control</div>

                <div class="detail-item">
                    <label>Status</label>
                    <select id="detailStatus" class="detail-select">
                        <option value="pending" ${video.status === 'pending' ? 'selected' : ''}>Pending</option>
                        <option value="linked" ${video.status === 'linked' ? 'selected' : ''}>Linked</option>
                        <option value="complete" ${video.status === 'complete' ? 'selected' : ''}>Complete</option>
                        <option value="failed" ${video.status === 'failed' ? 'selected' : ''}>Failed</option>
                        <option value="test" ${video.status === 'test' ? 'selected' : ''}>Test</option>
                    </select>
                </div>
                <div class="detail-item">
                    <label>Invalid Reason</label>
                    <select id="detailReason" class="detail-select">
                        <option value="">None</option>
                        <option value="test_run" ${video.invalid_reason === 'test_run' ? 'selected' : ''}>Test Run</option>
                        <option value="fallback" ${video.invalid_reason === 'fallback' ? 'selected' : ''}>Fallback</option>
                        <option value="topic_mismatch" ${video.invalid_reason === 'topic_mismatch' ? 'selected' : ''}>Topic Mismatch</option>
                        <option value="upload_failed" ${video.invalid_reason === 'upload_failed' ? 'selected' : ''}>Upload Failed</option>
                    </select>
                </div>
            </div>

            <!-- YouTube Link Section -->
            <div class="youtube-section">
                <h3>🔗 YouTube Link</h3>
                ${video.youtube_video_id ? `
                    <div class="linked-status">
                        <span class="linked-badge">✅ Linked</span>
                        <a href="${video.youtube_url || 'https://youtube.com/shorts/' + video.youtube_video_id}" target="_blank" class="youtube-link">
                            ${video.youtube_video_id}
                        </a>
                        <button class="btn-unlink" onclick="unlinkYouTube('${video.video_id}')">Unlink</button>
                    </div>
                ` : `
                    <div class="link-form">
                        <input type="text" id="youtubeUrlInput" placeholder="YouTube URL or Video ID" class="youtube-input" />
                        <button class="btn-link" onclick="linkYouTube('${video.video_id}')">Link</button>
                    </div>
                    <p class="link-hint">Supports: youtube.com/shorts/..., youtu.be/..., or video ID</p>
                `}
            </div>

            <div class="detail-actions">
                <button class="btn-delete" onclick="deleteVideo('${video.video_id}')">🗑️ Delete</button>
                <button class="btn-test" onclick="markAsTestFromModal('${video.video_id}')">Mark TEST</button>
                <button class="btn-save" onclick="saveVideoChanges('${video.video_id}')">Save Changes</button>
            </div>
        `;

        document.getElementById('videoModal').classList.remove('hidden');
    } catch (error) {
        showToast('Failed to load video: ' + error.message, 'error');
    }
}

function closeModal() {
    document.getElementById('videoModal').classList.add('hidden');
}

// Close on backdrop click
document.getElementById('videoModal')?.addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay')) closeModal();
});

async function markAsTestFromModal(videoId) {
    await markAsTest(videoId);
    closeModal();
}

async function saveVideoChanges(videoId) {
    try {
        const status = document.getElementById('detailStatus').value;
        const reason = document.getElementById('detailReason').value;

        const updates = { status, invalid_reason: reason || null };

        if (status === 'linked' || status === 'pending') {
            updates.calibration_eligible = true;
            if (!reason) updates.invalid_reason = null;
        }

        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', updates);
        closeModal();
        showToast('✅ Changes saved', 'success');
        loadVideos();
    } catch (error) {
        showToast('Save failed: ' + error.message, 'error');
    }
}

// ============================================================================
// Video Actions
// ============================================================================
function toggleVideoSelect(videoId) {
    if (selectedVideos.has(videoId)) selectedVideos.delete(videoId);
    else selectedVideos.add(videoId);
    updateSelectedCount();
}

function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll').checked;
    if (selectAll) videos.forEach(v => selectedVideos.add(v.video_id));
    else selectedVideos.clear();
    document.querySelectorAll('.video-checkbox').forEach(cb => cb.checked = selectAll);
    updateSelectedCount();
}

function updateSelectedCount() {
    document.getElementById('selectedCount').textContent = `${selectedVideos.size} selected`;
}

async function toggleEligible(videoId, isEligible) {
    try {
        const video = videos.find(v => v.video_id === videoId);
        if (isEligible && video && video.pipeline_executed === 'fallback') {
            if (!confirm('⚠️ Fallback video — setting eligible may pollute calibration. Continue?')) {
                loadVideos();
                return;
            }
        }

        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            calibration_eligible: isEligible
        });

        const idx = videos.findIndex(v => v.video_id === videoId);
        if (idx >= 0) videos[idx].calibration_eligible = isEligible;
    } catch (error) {
        showToast('Update failed: ' + error.message, 'error');
        loadVideos();
    }
}

async function markAsTest(videoId) {
    if (!confirm(`Mark ${videoId} as TEST?`)) return;

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            calibration_eligible: false,
            status: 'test',
            invalid_reason: 'test_run'
        });
        loadVideos();
    } catch (error) {
        showToast('Failed: ' + error.message, 'error');
    }
}

async function markSelectedAsTest() {
    if (selectedVideos.size === 0) {
        showToast('No videos selected', 'error');
        return;
    }

    if (!confirm(`Mark ${selectedVideos.size} videos as TEST?`)) return;

    try {
        await apiCall('/videos/bulk', 'POST', {
            video_ids: Array.from(selectedVideos),
            action: 'mark_as_test'
        });
        selectedVideos.clear();
        loadVideos();
    } catch (error) {
        showToast('Bulk update failed: ' + error.message, 'error');
    }
}

async function unmarkTest(videoId) {
    if (!confirm(`Restore ${videoId} from TEST?`)) return;

    try {
        const video = videos.find(v => v.video_id === videoId);
        const targetStatus = (video && video.youtube_video_id) ? 'linked' : 'pending';

        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            calibration_eligible: true,
            status: targetStatus,
            invalid_reason: null
        });
        loadVideos();
    } catch (error) {
        showToast('Unmark failed: ' + error.message, 'error');
    }
}

async function linkYouTube(videoId) {
    const input = document.getElementById('youtubeUrlInput');
    const youtubeUrl = input?.value?.trim();

    if (!youtubeUrl) {
        showToast('Enter a YouTube URL or Video ID', 'error');
        return;
    }

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            youtube_url: youtubeUrl
        });
        showToast('✅ Video linked!', 'success');
        closeModal();
        loadVideos();
    } catch (error) {
        showToast('Link failed: ' + error.message, 'error');
    }
}

async function unlinkYouTube(videoId) {
    if (!confirm('Unlink this YouTube video?')) return;

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            youtube_video_id: null,
            youtube_url: null,
            status: 'pending'
        });
        closeModal();
        loadVideos();
    } catch (error) {
        showToast('Unlink failed: ' + error.message, 'error');
    }
}

async function deleteVideo(videoId) {
    if (!confirm(`⚠️ Delete video ${videoId}?\n\nThis cannot be undone!`)) return;

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'DELETE');
        showToast('Video deleted', 'success');
        closeModal();
        loadVideos();
        loadDashboard();
    } catch (error) {
        showToast('Delete failed: ' + error.message, 'error');
    }
}

// ============================================================================
// Logs Modal
// ============================================================================
let currentLogsJobId = null;
let currentLogsData = [];

async function viewJobLogs(jobId) {
    currentLogsJobId = jobId;
    currentLogsData = [];

    document.getElementById('logsModalTitle').textContent = `📋 Logs: ${jobId}`;
    document.getElementById('logsContainer').innerHTML = '<div class="empty-state">Loading logs...</div>';
    document.getElementById('logsModal').classList.remove('hidden');

    try {
        const data = await apiCall(`/logs?job_id=${encodeURIComponent(jobId)}`);
        currentLogsData = data.logs || [];
        renderLogs(currentLogsData);
    } catch (error) {
        document.getElementById('logsContainer').innerHTML = `<div class="empty-state">Error: ${error.message}</div>`;
    }
}

function renderLogs(logs) {
    const container = document.getElementById('logsContainer');
    if (logs.length === 0) {
        container.innerHTML = '<div class="empty-state">No logs found</div>';
        return;
    }

    container.innerHTML = logs.map(log => `
        <div class="log-entry">
            <span class="log-time">${formatLogTime(log.ts_utc)}</span>
            <span class="log-level ${log.level}">${log.level}</span>
            <span class="log-component">${log.component}</span>
            <span class="log-message">${log.message || log.event}</span>
        </div>
    `).join('');
}

function filterLogs() {
    const comp = document.getElementById('logComponentFilter').value;
    const level = document.getElementById('logLevelFilter').value;

    let filtered = currentLogsData;
    if (comp) filtered = filtered.filter(l => l.component === comp);
    if (level) filtered = filtered.filter(l => l.level === level);
    renderLogs(filtered);
}

function closeLogsModal() {
    document.getElementById('logsModal').classList.add('hidden');
    currentLogsJobId = null;
    currentLogsData = [];
    document.getElementById('logComponentFilter').value = '';
    document.getElementById('logLevelFilter').value = '';
}

document.getElementById('logsModal')?.addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay')) closeLogsModal();
});

// ============================================================================
// Utilities
// ============================================================================
function truncate(str, len) {
    if (!str) return '—';
    return str.length > len ? str.substring(0, len) + '…' : str;
}

function formatDate(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleDateString('tr-TR') + ' ' + d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function formatDateShort(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' });
}

function formatLogTime(isoString) {
    if (!isoString) return '--:--:--';
    const d = new Date(isoString);
    return d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ============================================================================
// Toast Notifications
// ============================================================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
