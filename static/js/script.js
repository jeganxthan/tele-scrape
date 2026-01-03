// Navigation
document.querySelectorAll('.nav-links li').forEach(item => {
    item.addEventListener('click', function () {
        // Remove active class from all
        document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
        document.querySelectorAll('.view').forEach(view => view.classList.remove('active'));

        // Add to clicked
        this.classList.add('active');
        const tabId = this.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');

        // Update header
        document.querySelector('header h1').textContent =
            tabId.charAt(0).toUpperCase() + tabId.slice(1).replace('-', ' ');
    });
});

function switchTab(tabId) {
    document.querySelector(`[data-tab="${tabId}"]`).click();
}

// Notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('notification-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'fa-info-circle';
    if (type === 'success') icon = 'fa-check-circle';
    if (type === 'error') icon = 'fa-circle-xmark';

    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// --- API Interactions ---

// 1. Generalized Scraper
async function scrapeContent(type) {
    let inputId = '';
    if (type === 'anime') inputId = 'animeInput';
    if (type === 'movie') inputId = 'movieInput';
    if (type === 'series') inputId = 'seriesInput';

    const name = document.getElementById(inputId).value;
    if (!name) return showToast(`Please enter a ${type} name`, 'error');

    // Move result container to active tab
    const activeView = document.querySelector('.view.active .glass-panel');
    const resContainer = document.getElementById('resultContainer');
    if (resContainer && activeView) {
        activeView.appendChild(resContainer);
        resContainer.classList.remove('hidden');
    }

    const output = document.getElementById('jsonOutput');
    const loader = document.querySelector('.loader');

    if (output) output.innerText = 'Scraping...';
    if (loader) loader.classList.remove('hidden');

    try {
        const response = await fetch(`/scrape/${type}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name })
        });

        const result = await response.json();

        if (loader) loader.classList.add('hidden');
        if (response.ok && result.status === 'success') {
            if (output) output.innerText = JSON.stringify(result.data, null, 2);
            showToast('Scraping successful', 'success');
        } else {
            if (output) output.innerText = `Error: ${result.message}`;
            showToast('Scraping failed', 'error');
        }
    } catch (err) {
        if (loader) loader.classList.add('hidden');
        if (output) output.innerText = `Network Error: ${err}`;
        showToast('Network error', 'error');
    }
}

// 2. DB Viewer (Movies & Series only)
async function loadDatabase() {
    try {
        const response = await fetch('/db/collections');
        const res = await response.json();

        if (res.status === 'success') {
            const movies = res.data.movies;
            const series = res.data.series;

            const mList = document.getElementById('movieList');
            if (mList) mList.innerHTML = movies.map(m => `<li>${m.title} <span>${new Date(m.created_at).toLocaleDateString()}</span></li>`).join('');

            const sList = document.getElementById('seriesList');
            if (sList) sList.innerHTML = series.map(s => `<li>${s.show_title} <span>${new Date(s.created_at).toLocaleDateString()}</span></li>`).join('');

            showToast('Database loaded', 'success');
        }
    } catch (e) { console.error(e); }
}

// 3. Full CSV Table
async function loadFullCsvTable() {
    try {
        const response = await fetch('/uploads/all');
        const res = await response.json();

        if (res.status === 'success') {
            const tbody = document.querySelector('#recentUploadsTable tbody');
            if (tbody) {
                tbody.innerHTML = res.data.map(item => `
                    <tr>
                        <td>${item.title || item.filename}</td>
                        <td><code>${item.file_code}</code></td>
                        <td>${item.file_size || '-'}</td>
                    </tr>
                `).join('');
            }
        }
    } catch (e) { console.error(e); }
}

// Auto load on tab switch
document.querySelectorAll('.nav-links li').forEach(item => {
    item.addEventListener('click', function () {
        const tab = this.getAttribute('data-tab');
        if (tab === 'database') loadDatabase();
        if (tab === 'upload') loadFullCsvTable();
        if (tab === 'popular') loadPopularTitles();
    });
});

// 4. MKV Process
async function triggerMKV() {
    const log = document.getElementById('mkvLog');
    log.innerText = 'Starting MKV process...\\n';

    try {
        const response = await fetch('/process/mkv', { method: 'POST' });
        const result = await response.json();

        if (response.ok) {
            log.innerText += 'Success: ' + result.message;
            showToast('MKV process completed', 'success');
        } else {
            log.innerText += 'Error: ' + result.message;
            showToast('MKV process failed', 'error');
        }
    } catch (err) {
        log.innerText += 'Network Error: ' + err;
    }
}

// 5. Upload Batch (Simplified)
async function triggerUpload() {
    const log = document.getElementById('uploadLog');
    const progContainer = document.getElementById('uploadProgress');
    const progBar = document.getElementById('progressBar');
    const progFile = document.getElementById('progressFile');
    const progCount = document.getElementById('progressCount');
    const progPercent = document.getElementById('progressPercent');

    log.innerText = 'Initializing upload process...\n';
    progContainer.classList.remove('hidden');
    const liveList = document.getElementById('liveUploadList');
    if (liveList) liveList.innerHTML = '';
    showToast('Batch upload started', 'info');

    try {
        const response = await fetch('/upload/movies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ delete_after: true })
        });

        const initResult = await response.json();
        if (!response.ok) {
            log.innerText += 'Error: ' + initResult.message;
            progContainer.classList.add('hidden');
            return showToast(initResult.message, 'error');
        }

        log.innerText += 'Background thread started. Polling status...\n';

        let processedCount = 0;
        let lastRefreshTime = Date.now();

        // Polling loop
        const pollInterval = setInterval(async () => {
            try {
                const statusRes = await fetch('/upload/status');
                const status = await statusRes.json();

                if (status.total_files > 0) {
                    progFile.innerText = `Current: ${status.current_file}`;
                    progCount.innerText = `${status.current_index}/${status.total_files}`;
                    progBar.style.width = `${status.current_file_percent}%`;
                    progPercent.innerText = `${status.current_file_percent}%`;
                } else if (!status.is_uploading) {
                    progFile.innerText = 'No files found in downloads folder';
                }

                // Live updates for completed files
                if (status.results && status.results.length > processedCount) {
                    for (let i = processedCount; i < status.results.length; i++) {
                        const item = status.results[i];
                        if (liveList) {
                            const div = document.createElement('div');
                            div.className = 'live-item fade-in';
                            div.innerHTML = `<span>${item.uploaded ? '✅' : '❌'} ${item.file}</span> <small>${item.file_code || ''}</small>`;
                            liveList.prepend(div);
                            if (liveList.children.length > 5) liveList.lastChild.remove();
                        }
                    }
                    processedCount = status.results.length;
                    loadFullCsvTable();
                    lastRefreshTime = Date.now();
                } else if (status.is_uploading && Date.now() - lastRefreshTime > 10000) {
                    loadFullCsvTable();
                    lastRefreshTime = Date.now();
                }

                if (!status.is_uploading) {
                    clearInterval(pollInterval);
                    log.innerText += '\nUpload session completed.\n';

                    if (status.results && status.results.length > 0) {
                        status.results.forEach(res => {
                            const icon = res.uploaded ? '✅' : '❌';
                            log.innerText += `${icon} ${res.file} (Code: ${res.file_code || '-'}) \n`;
                        });
                    } else if (status.total_files === 0) {
                        log.innerText += '⚠️ No video files were found to upload in the "downloads" directory.\n';
                    }

                    showToast('Batch upload finished', 'success');
                    loadFullCsvTable();
                    setTimeout(() => progContainer.classList.add('hidden'), 10000);
                }
            } catch (pollErr) {
                console.error('Polling error:', pollErr);
            }
        }, 1000);

    } catch (err) {
        log.innerText += 'Network Error: ' + err;
        progContainer.classList.add('hidden');
    }
}

// 6. Popular Titles Management
let allTitles = [];

async function loadPopularTitles() {
    try {
        const response = await fetch('/db/collections');
        const res = await response.json();

        if (res.status === 'success') {
            const movies = res.data.movies;
            const series = res.data.series;
            const popular = res.data.popular || [];

            // Build Popular List
            const pList = document.getElementById('popularList');
            if (pList) {
                pList.innerHTML = popular.map(p => `
                    <li>
                        ${p.title} 
                        <button class="delete-btn" onclick="deletePopularTitle('${p.id}')">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </li>`).join('');
            }

            // Setup Autocomplete Source
            allTitles = [
                ...movies.map(m => ({ title: m.title, category: 'movie' })),
                ...series.map(s => ({ title: s.show_title, category: 'series' }))
            ];

            setupAutocomplete(document.getElementById("popularInput"), allTitles);

            showToast('Popular titles loaded', 'success');
        }
    } catch (e) { console.error(e); }
}

async function addPopularTitle() {
    const input = document.getElementById('popularInput');
    const title = input.value;
    if (!title) return;

    const match = allTitles.find(t => t.title.toLowerCase() === title.toLowerCase());
    const category = match ? match.category : 'movie';

    try {
        const response = await fetch('/db/popular', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: title, category: category })
        });
        const res = await response.json();
        if (response.ok) {
            showToast('Popular title added', 'success');
            input.value = '';
            loadPopularTitles();
        } else {
            showToast(res.message, 'error');
        }
    } catch (e) { showToast('Error adding title', 'error'); }
}

async function deletePopularTitle(id) {
    if (!confirm('Remove from popular list?')) return;
    try {
        const response = await fetch(`/db/popular/${id}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('Removed', 'success');
            loadPopularTitles();
        } else {
            showToast('Failed to remove', 'error');
        }
    } catch (e) { showToast('Error deleting', 'error'); }
}

// Autocomplete Logic
function setupAutocomplete(inp, arr) {
    if (!inp) return;

    inp.removeEventListener("input", inputHandler);
    inp.addEventListener("input", inputHandler);

    function inputHandler(e) {
        let a, b, i, val = this.value;
        closeAllLists();
        if (!val) { return false; }

        a = document.createElement("DIV");
        a.setAttribute("id", this.id + "autocomplete-list");
        a.setAttribute("class", "autocomplete-items");

        this.parentNode.appendChild(a);

        let count = 0;
        for (i = 0; i < arr.length; i++) {
            if (arr[i].title.substr(0, val.length).toUpperCase() == val.toUpperCase()) {
                if (count > 10) break;
                b = document.createElement("DIV");
                b.innerHTML = "<strong>" + arr[i].title.substr(0, val.length) + "</strong>";
                b.innerHTML += arr[i].title.substr(val.length);
                b.innerHTML += "<input type='hidden' value='" + arr[i].title + "'>";
                b.addEventListener("click", function (e) {
                    inp.value = this.getElementsByTagName("input")[0].value;
                    closeAllLists();
                });
                a.appendChild(b);
                count++;
            }
        }
    }

    function closeAllLists(elmnt) {
        var x = document.getElementsByClassName("autocomplete-items");
        for (var i = 0; i < x.length; i++) {
            if (elmnt != x[i] && elmnt != inp) {
                x[i].parentNode.removeChild(x[i]);
            }
        }
    }
    document.addEventListener("click", function (e) {
        closeAllLists(e.target);
    });
}

// 7. CSV Update
async function triggerCSVUpdate() {
    const log = document.getElementById('csvLog');
    if (log) log.innerText = 'Updating CSV...';
    showToast('Updating CSV...', 'info');

    try {
        const response = await fetch('/update/csv', { method: 'POST' });
        const result = await response.json();

        if (response.ok) {
            if (log) log.innerText = 'Success: ' + result.message;
            showToast('CSV Updated', 'success');
        } else {
            if (log) log.innerText = 'Error: ' + result.message;
            showToast('Update failed', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
}
