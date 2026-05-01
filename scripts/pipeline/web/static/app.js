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
        draftText: '',
        draftPath: '',
        wordCount: 0,
        flags: [],
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
    function setStepStatus(step, statusName) {
        const el = document.querySelector(`.step-status[data-step="${step}"]`);
        if (!el) return;
        const labels = { busy: '⏳', ok: '✓', fail: '✗', idle: '—' };
        el.textContent = labels[statusName] || '—';
        el.dataset.state = statusName;
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
            state.draftText = '';
            state.flags = [];
            postIdLabel.textContent = data.post_id;
            renderBrief(data);
            renderDraft(); // clear draft pane
            renderDetector(null); // clear detector pane
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
        lines.push(``, `**Hook pattern:** ${data.target_hook} · **Framework:** ${data.target_framework}`);
        lines.push(``, `## One Big Idea`, data.one_big_idea);
        lines.push(``, `## Why this why now`, data.why_now);
        lines.push(``, `## Reader Transformation`, data.reader_transformation);
        if (data.forbidden_moves.length) {
            lines.push(``, `## Forbidden Moves`);
            data.forbidden_moves.forEach((m) => lines.push(`- ${m}`));
        }

        // Always show the source idea, in full. If translation happened, show
        // both the original and the English version side-by-side so the writer
        // never loses sight of what they actually said.
        lines.push(``, `## Source Idea`);
        if (data.needed_translation) {
            lines.push(``, `**Original (${data.source_language}):**`);
            lines.push(``, blockquote(data.original_text));
            lines.push(``, `**Translated to ${data.target_language || 'en'}:**`);
            lines.push(``, blockquote(data.translated_text));
        } else {
            lines.push(
                ``,
                `_Source language: ${data.source_language || 'unknown'} (no translation needed)._`,
            );
            lines.push(``, blockquote(data.original_text));
        }

        panes.brief.innerHTML = marked.parse(lines.join('\n'));
    }

    /** Wrap multi-line text in markdown quote markers so paragraph breaks survive. */
    function blockquote(text) {
        if (!text) return '';
        return text
            .split('\n')
            .map((line) => (line.trim() ? `> ${line}` : '>'))
            .join('\n');
    }

    // --- Generate draft -------------------------------------------------
    draftBtn.addEventListener('click', async () => {
        if (!state.postId) return;
        draftBtn.disabled = true;
        setStepStatus('draft', 'busy');
        log('Generating draft (this may take 20-60 seconds)…');
        try {
            const data = await apiPost(`/api/draft/${state.postId}`, {});
            state.draftText = data.text;
            state.draftPath = data.draft_path;
            state.wordCount = data.word_count;
            state.flags = []; // clear stale flags
            renderDraft();
            renderDetector(null);
            activateTab('draft');
            setStepStatus('draft', 'ok');
            setStepStatus('detect', 'idle');
            detectBtn.disabled = false;
            log(`Draft ready: ${data.word_count} words`, 'success');
        } catch (e) {
            setStepStatus('draft', 'fail');
            log(`Draft failed: ${e.message}`, 'error');
        } finally {
            draftBtn.disabled = false;
        }
    });

    /**
     * Render the Draft pane. If `state.flags` is non-empty, wrap each flagged
     * snippet in <mark id="flag-N"> so we can scroll to it from the Detector
     * tab.
     *
     * Strategy: insert sentinel tokens around each snippet in the markdown
     * source first, run marked.parse(), then replace tokens with <mark>
     * tags. Going through markdown rendering preserves structure; tokens
     * survive the parser as plain text inside paragraphs.
     */
    function renderDraft() {
        if (!state.draftText) {
            panes.draft.innerHTML = '<p class="text-stone-400 italic">Generate a draft once a brief exists.</p>';
            return;
        }

        const meta = `<div class="text-xs text-stone-500 mb-3">${state.wordCount} words · <code>${escapeHtml(state.draftPath)}</code></div>`;

        if (!state.flags.length) {
            panes.draft.innerHTML = meta + marked.parse(state.draftText);
            return;
        }

        // Sort longest first so a shorter snippet contained inside a longer
        // one doesn't pre-claim the match.
        const sorted = state.flags
            .map((f, idx) => ({ ...f, idx }))
            .sort((a, b) => b.snippet.length - a.snippet.length);

        let withTokens = state.draftText;
        sorted.forEach((flag) => {
            const lower = withTokens.toLowerCase();
            const pos = lower.indexOf(flag.snippet.toLowerCase());
            if (pos < 0) return;
            const before = withTokens.slice(0, pos);
            const match = withTokens.slice(pos, pos + flag.snippet.length);
            const after = withTokens.slice(pos + flag.snippet.length);
            withTokens = `${before}__FLAGOPEN${flag.idx}__${match}__FLAGCLOSE${flag.idx}__${after}`;
        });

        let html = marked.parse(withTokens);
        sorted.forEach((flag) => {
            const safePattern = escapeHtml(flag.pattern);
            const open =
                `<mark class="flag-highlight" id="flag-${flag.idx}" ` +
                `title="${safePattern} (~line ${flag.line_approx})">`;
            html = html
                .split(`__FLAGOPEN${flag.idx}__`).join(open)
                .split(`__FLAGCLOSE${flag.idx}__`).join('</mark>');
        });

        panes.draft.innerHTML = meta + html;
    }

    // --- Detector -------------------------------------------------------
    detectBtn.addEventListener('click', async () => {
        if (!state.postId) return;
        detectBtn.disabled = true;
        setStepStatus('detect', 'busy');
        log('Running AI-tells detector…');
        try {
            const data = await apiPost(`/api/detect/${state.postId}`, {});
            state.flags = data.flags || [];
            renderDetector(data);
            renderDraft(); // re-render with highlights
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

    /**
     * Render the Detector pane. `data` may be null to clear the pane (used
     * when a new draft is generated). Each flag row becomes clickable;
     * clicking switches to the Draft tab and scrolls to the matching mark.
     */
    function renderDetector(data) {
        if (!data) {
            panes.detect.innerHTML = '<p class="text-stone-400 italic">Run the detector after generating a draft.</p>';
            return;
        }
        const head = `
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-semibold ${data.passed ? 'text-green-700' : 'text-red-700'}">
                    ${data.passed ? 'PASS' : 'FAIL'} — ${data.flags.length} flag${data.flags.length === 1 ? '' : 's'}
                </h3>
                <span class="text-xs text-stone-400 font-mono">${data.detector}</span>
            </div>
        `;
        if (!data.flags.length) {
            panes.detect.innerHTML = head + '<p class="text-stone-500 text-sm italic">No AI tells found. The draft is clear of the kill-list patterns.</p>';
            return;
        }
        const hint = '<p class="text-xs text-stone-500 mb-3">Click a flag to jump to its highlighted location in the draft.</p>';
        const rows = data.flags
            .map(
                (f, idx) => `
                <div class="flag-row" data-flag-idx="${idx}" tabindex="0" role="button">
                    <div class="flex items-center justify-between">
                        <span class="flag-pattern">${escapeHtml(f.pattern)}</span>
                        <span class="flag-line">~line ${f.line_approx}</span>
                    </div>
                    <div class="flag-snippet">${escapeHtml(f.snippet)}</div>
                </div>
            `,
            )
            .join('');
        panes.detect.innerHTML = head + hint + rows;

        panes.detect.querySelectorAll('.flag-row').forEach((row) => {
            row.addEventListener('click', () => jumpToFlag(parseInt(row.dataset.flagIdx, 10)));
            row.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    jumpToFlag(parseInt(row.dataset.flagIdx, 10));
                }
            });
        });
    }

    function jumpToFlag(idx) {
        activateTab('draft');
        const target = document.getElementById(`flag-${idx}`);
        if (!target) {
            log(`Flag #${idx} could not be located in the rendered draft (snippet may not match).`, 'error');
            return;
        }
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.classList.add('flag-flash');
        setTimeout(() => target.classList.remove('flag-flash'), 1500);
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
