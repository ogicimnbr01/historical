/**
 * Calibration Admin Panel - JavaScript
 * API integration and UI logic
 */

// Configuration - Update this after terraform apply
const CONFIG = {
    // API Gateway URL
    API_BASE_URL: 'https://cw42g7izf8.execute-api.us-east-1.amazonaws.com/v1',
    API_KEY: ''
};

// State
let videos = [];
let selectedVideos = new Set();

// ============================================================================
// API Key Management
// ============================================================================
function setApiKey() {
    const input = document.getElementById('apiKeyInput');
    CONFIG.API_KEY = input.value;
    localStorage.setItem('admin_api_key', input.value);
    loadDashboard();
    alert('API Key saved!');
}

function loadStoredApiKey() {
    const stored = localStorage.getItem('admin_api_key');
    if (stored) {
        CONFIG.API_KEY = stored;
        document.getElementById('apiKeyInput').value = stored;
    }

    // Clear any corrupted URL from localStorage
    localStorage.removeItem('admin_api_url');
}

// ============================================================================
// API Calls
// ============================================================================
async function apiCall(endpoint, method = 'GET', body = null) {
    if (!CONFIG.API_BASE_URL) {
        // Prompt for API URL on first call
        const url = prompt('Enter API Gateway URL (e.g., https://xxx.execute-api.us-east-1.amazonaws.com/v1):');
        if (url) {
            CONFIG.API_BASE_URL = url.replace(/\/$/, ''); // Remove trailing slash
            localStorage.setItem('admin_api_url', CONFIG.API_BASE_URL);
        } else {
            throw new Error('API URL is required');
        }
    }

    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'x-api-key': CONFIG.API_KEY
        }
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

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
function showDashboard() {
    document.getElementById('dashboard').classList.remove('hidden');
    document.getElementById('videoList').classList.add('hidden');
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.nav-btn')[0].classList.add('active');
    loadDashboard();
}

function showVideoList() {
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('videoList').classList.remove('hidden');
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.nav-btn')[1].classList.add('active');
    loadVideos();
}

// ============================================================================
// Dashboard
// ============================================================================
async function loadDashboard() {
    if (!CONFIG.API_KEY) {
        console.log('No API key set');
        return;
    }

    try {
        const stats = await apiCall('/stats');

        document.getElementById('statTotal').textContent = stats.total || 0;
        document.getElementById('statEligible').textContent = stats.eligible || 0;
        document.getElementById('statPending').textContent = stats.pending || 0;
        document.getElementById('statComplete').textContent = stats.complete || 0;
        document.getElementById('statFailed').textContent = stats.failed || 0;
        document.getElementById('statTest').textContent = stats.test || 0;

        document.getElementById('metricMAE').textContent = stats.mae !== null ? stats.mae.toFixed(2) : '-';
        document.getElementById('metricCorr').textContent = stats.correlation !== null ? stats.correlation.toFixed(3) : '-';
        document.getElementById('metricSample').textContent = stats.sample_size_for_metrics || 0;
        document.getElementById('metricEligibleRate').textContent = `${stats.eligible_rate || 0}%`;
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        alert('Failed to load dashboard: ' + error.message);
    }
}

// ============================================================================
// Video List
// ============================================================================
async function loadVideos() {
    if (!CONFIG.API_KEY) {
        alert('Please set API key first');
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
        alert('Failed to load videos: ' + error.message);
    }
}

function renderVideosTable() {
    const tbody = document.getElementById('videosTableBody');
    tbody.innerHTML = '';

    videos.forEach(video => {
        const tr = document.createElement('tr');

        const isEligible = video.calibration_eligible === true;
        const isFallback = video.pipeline_executed === 'fallback';

        tr.innerHTML = `
            <td>
                <input type="checkbox" class="video-checkbox" data-id="${video.video_id}" 
                    ${selectedVideos.has(video.video_id) ? 'checked' : ''} 
                    onchange="toggleVideoSelect('${video.video_id}')">
            </td>
            <td class="video-id-cell">${video.video_id}</td>
            <td class="title-cell" title="${video.title_used || '-'}">${truncate(video.title_used, 60)}</td>
            <td>${formatDate(video.publish_time_utc)}</td>
            <td><span class="badge ${video.mode}">${video.mode || '-'}</span></td>
            <td>${Math.round(video.predicted_retention || 0)}%</td>
            <td>${video.actual_retention ? Math.round(video.actual_retention) + '%' : '-'}</td>
            <td><span class="badge ${isFallback ? 'fallback' : 'v23'}">${isFallback ? 'fallback' : 'v2.3'}</span></td>
            <td>
                <label class="toggle">
                    <input type="checkbox" ${isEligible ? 'checked' : ''} 
                        onchange="toggleEligible('${video.video_id}', this.checked)">
                    <span class="slider"></span>
                </label>
            </td>
            <td><span class="badge ${video.status}">${video.status || 'pending'}</span></td>
            <td>
                <button class="action-btn view" onclick="viewVideo('${video.video_id}')">View</button>
                <button class="action-btn test" onclick="markAsTest('${video.video_id}')">TEST</button>
            </td>
        `;

        tbody.appendChild(tr);
    });

    updateSelectedCount();
}

function truncate(str, len) {
    if (!str) return '-';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

function formatDate(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ============================================================================
// Video Selection
// ============================================================================
function toggleVideoSelect(videoId) {
    if (selectedVideos.has(videoId)) {
        selectedVideos.delete(videoId);
    } else {
        selectedVideos.add(videoId);
    }
    updateSelectedCount();
}

function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll').checked;

    if (selectAll) {
        videos.forEach(v => selectedVideos.add(v.video_id));
    } else {
        selectedVideos.clear();
    }

    document.querySelectorAll('.video-checkbox').forEach(cb => {
        cb.checked = selectAll;
    });

    updateSelectedCount();
}

function updateSelectedCount() {
    document.getElementById('selectedCount').textContent = `${selectedVideos.size} selected`;
}

// ============================================================================
// Video Actions
// ============================================================================
async function toggleEligible(videoId, isEligible) {
    try {
        // Warning for fallback videos
        const video = videos.find(v => v.video_id === videoId);
        if (isEligible && video && video.pipeline_executed === 'fallback') {
            if (!confirm('⚠️ This is a fallback video. Setting as eligible may pollute calibration data. Continue?')) {
                // Revert the toggle
                loadVideos();
                return;
            }
        }

        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            calibration_eligible: isEligible
        });

        // Update local state
        const idx = videos.findIndex(v => v.video_id === videoId);
        if (idx >= 0) {
            videos[idx].calibration_eligible = isEligible;
        }
    } catch (error) {
        alert('Failed to update: ' + error.message);
        loadVideos(); // Reload to revert UI
    }
}

async function markAsTest(videoId) {
    if (!confirm(`Mark ${videoId} as TEST? This will set eligible=false, status=test, reason=test_run`)) {
        return;
    }

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            calibration_eligible: false,
            status: 'test',
            invalid_reason: 'test_run'
        });

        loadVideos();
    } catch (error) {
        alert('Failed to mark as test: ' + error.message);
    }
}

async function markSelectedAsTest() {
    if (selectedVideos.size === 0) {
        alert('No videos selected');
        return;
    }

    if (!confirm(`Mark ${selectedVideos.size} videos as TEST?`)) {
        return;
    }

    try {
        await apiCall('/videos/bulk', 'POST', {
            video_ids: Array.from(selectedVideos),
            action: 'mark_as_test'
        });

        selectedVideos.clear();
        loadVideos();
    } catch (error) {
        alert('Failed to bulk update: ' + error.message);
    }
}

// ============================================================================
// Video Detail Modal
// ============================================================================
async function viewVideo(videoId) {
    try {
        const video = await apiCall(`/videos/${encodeURIComponent(videoId)}`);

        document.getElementById('modalTitle').textContent = `Video: ${truncate(videoId, 30)}`;

        const body = document.getElementById('modalBody');
        body.innerHTML = `
            <div class="detail-grid">
                <div class="detail-item">
                    <label>Video ID</label>
                    <span>${video.video_id}</span>
                </div>
                <div class="detail-item">
                    <label>Publish Time</label>
                    <span>${formatDate(video.publish_time_utc)}</span>
                </div>
                <div class="detail-item">
                    <label>Mode</label>
                    <span>${video.mode || '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Pipeline</label>
                    <span class="badge ${video.pipeline_executed === 'fallback' ? 'fallback' : 'v23'}">
                        ${video.pipeline_executed || 'v2.3'}
                    </span>
                </div>
                <div class="detail-item">
                    <label>Predicted Retention</label>
                    <span>${Math.round(video.predicted_retention || 0)}%</span>
                </div>
                <div class="detail-item">
                    <label>Actual Retention</label>
                    <span>${video.actual_retention ? Math.round(video.actual_retention) + '%' : 'Pending'}</span>
                </div>
                <div class="detail-item">
                    <label>Hook Score</label>
                    <span>${video.hook_score || '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Visual Relevance</label>
                    <span>${video.visual_relevance || '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Era</label>
                    <span>${video.era || '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Topic Entity</label>
                    <span>${video.topic_entity || '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Title Used</label>
                    <span>${video.title_used || '-'}</span>
                </div>
                <div class="detail-item">
                    <label>Title Variant</label>
                    <span>${video.title_variant_type || '-'}</span>
                </div>
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
            <div class="youtube-link-section">
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
                        <button class="btn-link" onclick="linkYouTube('${video.video_id}')">Link Video</button>
                    </div>
                    <p class="link-hint">Supports: youtube.com/shorts/..., youtu.be/..., or video ID</p>
                `}
            </div>
            
            <div class="detail-actions">
                <button class="btn-delete" onclick="deleteVideo('${video.video_id}')">🗑️ Delete</button>
                <button class="btn-test" onclick="markAsTestFromModal('${video.video_id}')">Mark as TEST</button>
                <button class="btn-save" onclick="saveVideoChanges('${video.video_id}')">Save Changes</button>
            </div>
        `;

        document.getElementById('videoModal').classList.remove('hidden');
    } catch (error) {
        alert('Failed to load video: ' + error.message);
    }
}

function closeModal() {
    document.getElementById('videoModal').classList.add('hidden');
}

async function markAsTestFromModal(videoId) {
    await markAsTest(videoId);
    closeModal();
}

async function saveVideoChanges(videoId) {
    try {
        const status = document.getElementById('detailStatus').value;
        const reason = document.getElementById('detailReason').value;

        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            status: status,
            invalid_reason: reason || null
        });

        closeModal();
        loadVideos();
    } catch (error) {
        alert('Failed to save: ' + error.message);
    }
}

async function linkYouTube(videoId) {
    const input = document.getElementById('youtubeUrlInput');
    const youtubeUrl = input?.value?.trim();

    if (!youtubeUrl) {
        alert('Please enter a YouTube URL or Video ID');
        return;
    }

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            youtube_url: youtubeUrl
        });

        alert('✅ Video linked successfully!');
        closeModal();
        loadVideos();
    } catch (error) {
        alert('Failed to link: ' + error.message);
    }
}

async function unlinkYouTube(videoId) {
    if (!confirm('Unlink this YouTube video?')) {
        return;
    }

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'PATCH', {
            youtube_video_id: null,
            youtube_url: null,
            status: 'pending'
        });

        closeModal();
        loadVideos();
    } catch (error) {
        alert('Failed to unlink: ' + error.message);
    }
}

async function deleteVideo(videoId) {
    if (!confirm(`⚠️ Delete video ${videoId}?\n\nThis cannot be undone!`)) {
        return;
    }

    try {
        await apiCall(`/videos/${encodeURIComponent(videoId)}`, 'DELETE');

        alert('✅ Video deleted');
        closeModal();
        loadVideos();
        loadDashboard();
    } catch (error) {
        alert('Failed to delete: ' + error.message);
    }
}

// Close modal on outside click
document.getElementById('videoModal').addEventListener('click', function (e) {
    if (e.target === this) {
        closeModal();
    }
});

// ============================================================================
// Initialize
// ============================================================================
document.addEventListener('DOMContentLoaded', function () {
    loadStoredApiKey();

    // Auto-load dashboard if API key is set
    if (CONFIG.API_KEY) {
        loadDashboard();
    }
});
