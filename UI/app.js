document.addEventListener('DOMContentLoaded', () => {
    // Elements - API Server Config
    const apiUrlInput = document.getElementById('api-url-input');
    const checkApiBtn = document.getElementById('check-api-btn');
    const apiStatusBadge = document.getElementById('api-status-badge');

    // Default to deployed EC2 endpoint, or restore previous user input from localStorage
    const savedApiUrl = localStorage.getItem('financial_rag_api_url') || 'http://13.61.154.83:8000';
    if (apiUrlInput) {
        apiUrlInput.value = savedApiUrl;
    }

    function getBaseUrl() {
        if (!apiUrlInput) return 'http://13.61.154.83:8000';
        const url = apiUrlInput.value.trim() || 'http://13.61.154.83:8000';
        return url.replace(/\/+$/, '');
    }

    // Health check logic for API connection
    async function checkApiHealth() {
        const url = getBaseUrl();
        localStorage.setItem('financial_rag_api_url', url);
        apiStatusBadge.className = 'badge badge-connecting';
        apiStatusBadge.textContent = 'Checking...';

        try {
            const res = await fetch(`${url}/health`, { method: 'GET' });
            if (res.ok) {
                const data = await res.json();
                if (data.status === 'healthy') {
                    apiStatusBadge.className = 'badge badge-success';
                    apiStatusBadge.textContent = '● Connected (Healthy)';
                } else {
                    apiStatusBadge.className = 'badge badge-connecting';
                    apiStatusBadge.textContent = '● Degraded';
                }
            } else {
                apiStatusBadge.className = 'badge badge-error';
                apiStatusBadge.textContent = `● HTTP ${res.status}`;
            }
        } catch (err) {
            apiStatusBadge.className = 'badge badge-error';
            apiStatusBadge.textContent = '● Offline / Unreachable';
        }
    }

    if (checkApiBtn) {
        checkApiBtn.addEventListener('click', checkApiHealth);
    }
    if (apiUrlInput) {
        apiUrlInput.addEventListener('change', checkApiHealth);
    }

    // Run initial health check on page load
    checkApiHealth();

    // Elements - Navigation Tabs
    const tabBtnQa = document.getElementById('tab-btn-qa');
    const tabBtnUpload = document.getElementById('tab-btn-upload');
    const viewQa = document.getElementById('view-qa');
    const viewUpload = document.getElementById('view-upload');

    // Elements - Global Loading
    const loadingOverlay = document.getElementById('loading');
    const loadingText = document.getElementById('loading-text');

    // Elements - Q&A View
    const queryForm = document.getElementById('query-form');
    const questionInput = document.getElementById('question');
    const limitInput = document.getElementById('limit');
    const resultsLayout = document.getElementById('results');
    const imagesContainer = document.getElementById('images-container');
    const answerContainer = document.getElementById('answer-container');

    // Elements - Upload View
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('pdf-file-input');
    const fileInfoBox = document.getElementById('file-info-box');
    const selectedFileName = document.getElementById('selected-file-name');
    const selectedFileSize = document.getElementById('selected-file-size');
    const removeFileBtn = document.getElementById('remove-file-btn');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadStatus = document.getElementById('upload-status');

    let currentFile = null;

    // ── Tab Switching Logic ───────────────────────────────────────────────────
    tabBtnQa.addEventListener('click', () => {
        tabBtnQa.classList.add('active');
        tabBtnUpload.classList.remove('active');
        viewQa.classList.remove('hidden');
        viewUpload.classList.add('hidden');
    });

    tabBtnUpload.addEventListener('click', () => {
        tabBtnUpload.classList.add('active');
        tabBtnQa.classList.remove('active');
        viewUpload.classList.remove('hidden');
        viewQa.classList.add('hidden');
    });

    // ── Q&A Query Form Submission ─────────────────────────────────────────────
    queryForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const question = questionInput.value.trim();
        const limit = parseInt(limitInput.value, 10);
        if (!question) return;

        // Show loading and clear previous answers
        loadingText.textContent = 'Retrieving context from Qdrant and generating answer via Gemini...';
        loadingOverlay.classList.remove('hidden');
        resultsLayout.classList.add('hidden');
        imagesContainer.innerHTML = '';
        answerContainer.innerHTML = '';

        try {
            const currentBaseUrl = getBaseUrl();
            const response = await fetch(`${currentBaseUrl}/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question, limit })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server returned status ${response.status}`);
            }

            const data = await response.json();

            // 1. Render base64 context images on the left
            if (data.images && data.images.length > 0) {
                data.images.forEach((imgB64, index) => {
                    const card = document.createElement('div');
                    card.className = 'image-card';

                    const header = document.createElement('div');
                    header.className = 'image-header';
                    header.innerHTML = `<span>Page Reference ${index + 1}</span>`;

                    const img = document.createElement('img');
                    img.src = `data:image/jpeg;base64,${imgB64}`;
                    img.alt = `Reference Page ${index + 1}`;

                    card.appendChild(header);
                    card.appendChild(img);
                    imagesContainer.appendChild(card);
                });
            } else {
                imagesContainer.innerHTML = '<p class="info-text">No reference pages were returned for this query.</p>';
            }

            // 2. Render markdown text answer on the right
            if (data.answer) {
                answerContainer.innerHTML = marked.parse(data.answer);
            } else {
                answerContainer.innerHTML = '<p class="info-text">No answer generated.</p>';
            }

            resultsLayout.classList.remove('hidden');

        } catch (error) {
            console.error('Error executing query:', error);
            alert(`Query Failed: ${error.message}`);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });

    // ── Document Upload Logic ────────────────────────────────────────────────
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    function setSelectedFile(file) {
        if (!file) return;

        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showUploadStatus('Please select a valid PDF file.', 'error');
            return;
        }

        currentFile = file;
        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = formatFileSize(file.size);
        fileInfoBox.classList.remove('hidden');
        uploadBtn.disabled = false;
        hideUploadStatus();
    }

    function clearSelectedFile() {
        currentFile = null;
        fileInput.value = '';
        fileInfoBox.classList.add('hidden');
        uploadBtn.disabled = true;
    }

    function showUploadStatus(message, type = 'success') {
        uploadStatus.textContent = message;
        uploadStatus.className = `status-alert ${type}`;
        uploadStatus.classList.remove('hidden');
    }

    function hideUploadStatus() {
        uploadStatus.classList.add('hidden');
    }

    // Drag & Drop handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setSelectedFile(e.dataTransfer.files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setSelectedFile(e.target.files[0]);
        }
    });

    removeFileBtn.addEventListener('click', () => {
        clearSelectedFile();
        hideUploadStatus();
    });

    // Upload to S3 via deployed API
    uploadBtn.addEventListener('click', async () => {
        if (!currentFile) return;

        hideUploadStatus();
        loadingText.textContent = `Uploading ${currentFile.name} to Amazon S3 via EC2 backend...`;
        loadingOverlay.classList.remove('hidden');
        uploadBtn.disabled = true;

        const formData = new FormData();
        formData.append('file', currentFile);

        try {
            const currentBaseUrl = getBaseUrl();
            const response = await fetch(`${currentBaseUrl}/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
            }

            const result = await response.json();
            showUploadStatus(
                `🎉 ${result.message} Check your EC2 worker container logs to watch the ingestion process.`,
                'success'
            );
            clearSelectedFile();

        } catch (err) {
            console.error('Upload failed:', err);
            showUploadStatus(`Upload Error: ${err.message}`, 'error');
            uploadBtn.disabled = false;
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });
});
