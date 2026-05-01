/* Stack Hub web panel — single-page client. No frameworks, just vanilla JS. */
(() => {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => Array.from(document.querySelectorAll(sel));

    // --- DOM refs --------------------------------------------------------
    const ideaText = $('#ideaText');
    const micBtn = $('#micBtn');
    const micStatus = $('#micStatus');
    const langSelect = $('#lang');
    const composeBtn = $('#composeBtn');
    const draftBtn = $('#draftBtn');
    const detectBtn = $('#detectBtn');
    const postIdLabel = $('#postIdLabel');

    const panes = {
        brief: $('#pane-brief'),
        draft: $('#pane-draft'),
        detect: $('#pane-detect'),
        log: $('#pane-log'),
    };

    // --- App state -------------------------------------------------------
    const state = {
        postId: null,
    };

    // --- Tabs ------------------------------------------------------------
    $$('.tab').forEach((tab) => {
        tab.addEventListener('click', () => activateTab(tab.dataset.tab));
    });
    function activateTab(name) {
        $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
        Object.entries(panes).forEach(([key, el]) => el.classList.toggle('hidden', key !== name));
    }

    // --- Logging ---------------------------------------------------------
    function log(message, kind = 'info') {
        const line = document.createElement('div');
        line.className = `log-line ${kind}`;
        const ts = new Date().toLocaleTimeString();
        line.textContent = `[${ts}] ${message}`;
        const placeholder = panes.log.querySelector('p.italic');
        if (placeholder) placeholder.remove();
        panes.log.appendChild(line);
        panes.log.scrollTop = panes.log.scrollHeight;
    }

    // --- Step status pills ----------------------------------------------
    function setStepStatus(step, state) {
        const el = document.querySelector(`.step-status[data-step="${step}"]`);
        if (!el) return;
        const labels = { busy: '⏳', ok: '✓', fail: '✗', idle: '—' };
        el.textContent = labels[state] || '—';
        el.dataset.state = state;
    }

    // --- Voice input (Web Speech API) -----------------------------------
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let recording = false;

    micBtn.addEventListener('click', () => {
        if (!SR) {
            micStatus.textContent = 'Voice input not supported in this browser. Try Chrome.';
            return;
        }
        if (recording) {
            recognition.stop();
            return;
        }
        recognition = new SR();
        recognition.lang = langSelect.value === 'auto' ? 'bn-BD' : langSelect.value;
        recognition.continuous = true;
        recognition.interimResults = true;
        let finalText = ideaText.value;

        recognition.onstart = () => {
            recording = true;
            micBtn.classList.add('recording');
            micStatus.textContent = `Listening (${recognition.lang})…`;
        };
        recognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) finalText += transcript;
                else interim += transcript;
            }
            ideaText.value = finalText + (interim ? ` ${interim}` : '');
        };
        recognition.onerror = (event) => {
            micStatus.textContent = `Mic error: ${event.error}`;
        };
        recognition.onend = () => {
            recording = false;
            micBtn.classList.remove('recording');
            micStatus.textContent = 'Stopped.';
        };
        try {
            recognition.start();
        } catch (e) {
            micStatus.textContent = `Could not start mic: ${e.message}`;
        }
    });

    // --- API helpers ----------------------------------------------------
    async function apiPost(path, body) {
        const res = await fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {}),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return res.json();
    }

    // --- Compose brief --------------------------------------------------
    composeBtn.addEventListener('click', async () => {
        const idea = ideaText.value.trim();
        if (!idea) {
            log('Idea is empty', 'error');
            return;
        }
        composeBtn.disabled = true;
        composeBtn.innerHTML = '<span class="spin"></span> Composing…';
        log('Composing brief from idea…');
        try {
            const data = await apiPost('/api/brief', { idea, target_lang: 'en' });
            state.postId = data.post_id;
            postIdLabel.textContent = data.post_id;
            renderBrief(data);
            activateTab('brief');
            draftBtn.disabled = false;
            detectBtn.disabled = true;
            setStepStatus('draft', 'idle');
            setStepStatus('detect', 'idle');
            log(`Brief ready: ${data.working_title}`, 'success');
        } catch (e) {
            log(`Brief failed: ${e.message}`, 'error');
        } finally {
            composeBtn.disabled = false;
            composeBtn.innerHTML = '✨ Compose Brief';
        }
    });

    function renderBrief(data) {
        const lines = [];
        lines.push(`# ${data.working_title}`);
        if (data.needed_translation) {
            lines.push(`> _Translated from ${data.source_language}: "${data.original_text.slice(0, 200)}${data.original_text.length > 200 ? '…' : ''}"_`);
        }
        lines.push(``, `**Hook pattern:** ${data.target_hook} · **Framework:** ${data.target_framework}`);
        lines.push(``, `## One Big Idea`, data.one_big_idea);
        lines.push(``, `## Why this why now`, data.why_now);
        lines.push(``, `## Reader Transformation`, data.reader_transformation);
        if (data.forbidden_moves.length) {
            lines.push(``, `## Forbidden Moves`);
            data.forbidden_moves.forEach((m) => lines.push(`- ${m}`));
        }
        panes.brief.innerHTML = marked.parse(lines.join('\n'));
    }

    // --- Generate draft -------------------------------------------------
    draftBtn.addEventListener('click', async () => {
        if (!state.postId) return;
        draftBtn.disabled = true;
        setStepStatus('draft', 'busy');
        log('Generating draft (this may take 20-60 seconds)…');
        try {
            const data = await apiPost(`/api/draft/${state.postId}`, {});
            panes.draft.innerHTML =
                `<div class="text-xs text-stone-500 mb-3">${data.word_count} words · ${data.draft_path}</div>` +
                marked.parse(data.text);
            activateTab('draft');
            setStepStatus('draft', 'ok');
            detectBtn.disabled = false;
            log(`Draft ready: ${data.word_count} words`, 'success');
        } catch (e) {
            setStepStatus('draft', 'fail');
            log(`Draft failed: ${e.message}`, 'error');
        } finally {
            draftBtn.disabled = false;
        }
    });

    // --- Detector -------------------------------------------------------
    detectBtn.addEventListener('click', async () => {
        if (!state.postId) return;
        detectBtn.disabled = true;
        setStepStatus('detect', 'busy');
        log('Running AI-tells detector…');
        try {
            const data = await apiPost(`/api/detect/${state.postId}`, {});
            renderDetector(data);
            activateTab('detect');
            setStepStatus('detect', data.passed ? 'ok' : 'fail');
            log(
                data.passed
                    ? `Detector PASS (${data.detector})`
                    : `Detector FAIL: ${data.flags.length} flags`,
                data.passed ? 'success' : 'error',
            );
        } catch (e) {
            setStepStatus('detect', 'fail');
            log(`Detector failed: ${e.message}`, 'error');
        } finally {
            detectBtn.disabled = false;
        }
    });

    function renderDetector(data) {
        const head = `
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-semibold ${data.passed ? 'text-green-700' : 'text-red-700'}">
                    ${data.passed ? 'PASS' : 'FAIL'} — ${data.flags.length} flag${data.flags.length === 1 ? '' : 's'}
                </h3>
                <span class="text-xs text-stone-400 font-mono">${data.detector}</span>
            </div>
        `;
        const flags = data.flags
            .map(
                (f) => `
                <div class="flag-row">
                    <div class="flex items-center justify-between">
                        <span class="flag-pattern">${escapeHtml(f.pattern)}</span>
                        <span class="flag-line">~line ${f.line_approx}</span>
                    </div>
                    <div class="flag-snippet">${escapeHtml(f.snippet)}</div>
                </div>
            `,
            )
            .join('');
        panes.detect.innerHTML = head + (data.flags.length ? flags : '<p class="text-stone-500 text-sm italic">No AI tells found. The draft is clear of the kill-list patterns.</p>');
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    // --- Boot -----------------------------------------------------------
    if (!SR) {
        micStatus.textContent = 'Voice input requires Chrome/Safari. Type instead.';
    } else {
        micStatus.textContent = 'Click mic, then speak.';
    }
    log('Ready. Type or speak your idea, then click "Compose Brief".', 'success');
})();
