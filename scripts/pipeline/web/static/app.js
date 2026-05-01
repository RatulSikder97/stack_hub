/* Stack Hub Studio — single-page client. Vanilla JS, no framework. */
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
    const polishBtn = $('#polishBtn');
    const clearBtn = $('#clearBtn');
    const postIdLabel = $('#postIdLabel');
    const recDot = $('#recDot');
    const recState = $('#recState');
    const recTimer = $('#recTimer');
    const visualizerCanvas = $('#micVisualizer');

    const panes = {
        brief: $('#pane-brief'),
        draft: $('#pane-draft'),
        detect: $('#pane-detect'),
        translate: $('#pane-translate'),
        log: $('#pane-log'),
    };

    const translateBtn = $('#translateBtn');
    const translateInput = $('#translateInput');
    const translateTarget = $('#translateTarget');
    const translateResult = $('#translateResult');

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

    function setStepStatus(step, statusName) {
        const el = document.querySelector(`.step-status[data-step="${step}"]`);
        if (!el) return;
        const labels = { busy: '⏳', ok: '✓', fail: '✗', idle: '—' };
        el.textContent = labels[statusName] || '—';
        el.dataset.state = statusName;
    }

    // ----------------------------------------------------------------
    // Studio state machine: ready / live / paused
    // ----------------------------------------------------------------
    const studio = {
        state: 'ready',
        startedAt: 0,
        timerHandle: null,
        finalText: '', // committed text from speech recognition
        interimText: '', // currently-being-spoken
        pausePeriodTimer: null,
        pauseParagraphTimer: null,
    };

    // Tunables for auto-punctuation (ms)
    const PERIOD_PAUSE_MS = 700;
    const PARAGRAPH_PAUSE_MS = 1800;

    function setStudioState(next) {
        studio.state = next;
        recDot.className = 'rec-dot ' + (next === 'live' ? 'live' : next === 'paused' ? 'paused' : '');
        recState.textContent = next === 'live' ? 'Live' : next === 'paused' ? 'Paused' : 'Ready';
        recState.dataset.state = next;
        micBtn.classList.toggle('recording', next === 'live');
        micBtn.classList.toggle('paused', next === 'paused');
    }

    function startTimer() {
        studio.startedAt = Date.now();
        recTimer.textContent = '00:00';
        if (studio.timerHandle) clearInterval(studio.timerHandle);
        studio.timerHandle = setInterval(() => {
            const elapsed = Math.floor((Date.now() - studio.startedAt) / 1000);
            const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const ss = String(elapsed % 60).padStart(2, '0');
            recTimer.textContent = `${mm}:${ss}`;
        }, 250);
    }
    function stopTimer() {
        if (studio.timerHandle) clearInterval(studio.timerHandle);
        studio.timerHandle = null;
    }

    // ----------------------------------------------------------------
    // Auto-punctuation on pause
    // ----------------------------------------------------------------
    function clearPauseTimers() {
        if (studio.pausePeriodTimer) clearTimeout(studio.pausePeriodTimer);
        if (studio.pauseParagraphTimer) clearTimeout(studio.pauseParagraphTimer);
        studio.pausePeriodTimer = null;
        studio.pauseParagraphTimer = null;
    }
    function schedulePauseHandlers() {
        clearPauseTimers();
        studio.pausePeriodTimer = setTimeout(() => {
            studio.finalText = appendPeriod(studio.finalText);
            renderTranscript();
            setStudioState('paused');
        }, PERIOD_PAUSE_MS);
        studio.pauseParagraphTimer = setTimeout(() => {
            studio.finalText = appendParagraphBreak(studio.finalText);
            renderTranscript();
        }, PARAGRAPH_PAUSE_MS);
    }
    function appendPeriod(text) {
        const trimmed = text.replace(/\s+$/, '');
        if (!trimmed) return text;
        // Already punctuated? Don't double-up.
        if (/[.!?।॥।]\s*$/.test(trimmed)) return trimmed + ' ';
        // Bengali/Hindi danda for indic langs, period for everything else.
        const lang = (langSelect.value || '').toLowerCase();
        const punct = lang.startsWith('bn') || lang.startsWith('hi') ? '।' : '.';
        return trimmed + punct + ' ';
    }
    function appendParagraphBreak(text) {
        const trimmed = text.replace(/\s+$/, '');
        if (!trimmed) return text;
        if (trimmed.endsWith('\n\n')) return trimmed;
        return trimmed + '\n\n';
    }
    function renderTranscript() {
        ideaText.value =
            studio.finalText +
            (studio.interimText ? (studio.finalText.endsWith('\n') ? '' : ' ') + studio.interimText : '');
    }

    // ----------------------------------------------------------------
    // Web Audio level visualizer (concentric pulse)
    // ----------------------------------------------------------------
    let audioCtx = null;
    let analyser = null;
    let mediaStream = null;
    let visualizerHandle = null;

    async function startVisualizer() {
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioCtx.createMediaStreamSource(mediaStream);
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            drawVisualizer();
        } catch (e) {
            log(`Mic visualizer unavailable: ${e.message}`, 'error');
        }
    }
    function stopVisualizer() {
        if (visualizerHandle) cancelAnimationFrame(visualizerHandle);
        visualizerHandle = null;
        if (mediaStream) {
            mediaStream.getTracks().forEach((t) => t.stop());
            mediaStream = null;
        }
        if (audioCtx) {
            audioCtx.close().catch(() => {});
            audioCtx = null;
        }
        analyser = null;
        // Reset canvas
        const ctx = visualizerCanvas.getContext('2d');
        ctx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
    }
    function drawVisualizer() {
        if (!analyser) return;
        const canvas = visualizerCanvas;
        const ctx = canvas.getContext('2d');
        const W = canvas.width;
        const H = canvas.height;
        const cx = W / 2;
        const cy = H / 2;
        const buf = new Uint8Array(analyser.frequencyBinCount);

        const tick = () => {
            visualizerHandle = requestAnimationFrame(tick);
            if (!analyser) return;
            analyser.getByteFrequencyData(buf);
            // Average level 0-1
            let sum = 0;
            for (let i = 0; i < buf.length; i++) sum += buf[i];
            const avg = sum / buf.length / 255;
            ctx.clearRect(0, 0, W, H);

            const isLive = studio.state === 'live';
            const baseColor = isLive ? '239, 68, 68' : '139, 92, 246';

            // Concentric breathing rings
            for (let i = 0; i < 4; i++) {
                const t = (Date.now() / 1000 + i * 0.4) % 1;
                const radius = 60 + t * 75 + avg * 40;
                const alpha = (1 - t) * (0.18 + avg * 0.6);
                ctx.beginPath();
                ctx.arc(cx, cy, radius, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(${baseColor}, ${alpha.toFixed(3)})`;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }
            // Frequency bars in a circle
            const bars = 64;
            for (let i = 0; i < bars; i++) {
                const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
                const v = buf[Math.floor((i / bars) * buf.length)] / 255;
                const inner = 56;
                const outer = inner + 4 + v * 38;
                const x1 = cx + Math.cos(angle) * inner;
                const y1 = cy + Math.sin(angle) * inner;
                const x2 = cx + Math.cos(angle) * outer;
                const y2 = cy + Math.sin(angle) * outer;
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.strokeStyle = `rgba(${baseColor}, ${(0.2 + v * 0.7).toFixed(3)})`;
                ctx.lineWidth = 2;
                ctx.lineCap = 'round';
                ctx.stroke();
            }
        };
        tick();
    }

    // ----------------------------------------------------------------
    // Voice input via Web Speech API
    // ----------------------------------------------------------------
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    micBtn.addEventListener('click', async () => {
        if (!SR) {
            micStatus.textContent = 'Voice input requires Chrome or Safari.';
            return;
        }
        if (studio.state !== 'ready' && recognition) {
            recognition.stop();
            return;
        }

        // Sync existing textarea content into our buffer so user can type then dictate.
        studio.finalText = ideaText.value;
        studio.interimText = '';

        recognition = new SR();
        recognition.lang = langSelect.value === 'auto' ? 'bn-BD' : langSelect.value;
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onstart = async () => {
            setStudioState('live');
            startTimer();
            await startVisualizer();
            micStatus.textContent = `Listening (${recognition.lang}) · pause for punctuation`;
        };
        recognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    studio.finalText += transcript;
                } else {
                    interim += transcript;
                }
            }
            studio.interimText = interim;
            renderTranscript();
            // Whenever the user is actively speaking, return to LIVE state and
            // (re)schedule the silence timers.
            setStudioState('live');
            schedulePauseHandlers();
        };
        recognition.onerror = (event) => {
            micStatus.textContent = `Mic error: ${event.error}`;
            log(`Mic error: ${event.error}`, 'error');
        };
        recognition.onend = () => {
            clearPauseTimers();
            stopTimer();
            stopVisualizer();
            setStudioState('ready');
            micStatus.textContent = 'Stopped.';
            recognition = null;
        };

        try {
            recognition.start();
        } catch (e) {
            micStatus.textContent = `Could not start mic: ${e.message}`;
        }
    });

    clearBtn.addEventListener('click', () => {
        studio.finalText = '';
        studio.interimText = '';
        ideaText.value = '';
    });

    // ----------------------------------------------------------------
    // Polish: send the transcript through /api/translate with same source
    // and target language to clean up punctuation/casing.
    // (Translate prompt preserves wording — good enough for repunctuation.)
    // ----------------------------------------------------------------
    polishBtn.addEventListener('click', async () => {
        const text = ideaText.value.trim();
        if (!text) {
            log('Nothing to polish.', 'error');
            return;
        }
        const originalLabel = polishBtn.innerHTML;
        polishBtn.disabled = true;
        polishBtn.innerHTML = '<span class="spin"></span>';
        try {
            // Detect source via a tiny translate-to-English round-trip.
            const probe = await apiPost('/api/translate', {
                text,
                target_lang: 'en',
            });
            // If already English, we just take the translated_text (which is a
            // cleaned version). For other languages, the *original* preserved
            // by the model is usually re-punctuated as part of detection.
            // For real round-trip stability we re-translate to source.
            let polished = text;
            if (probe.source_language === 'en' || probe.target_language === probe.source_language) {
                polished = probe.translated_text || text;
            } else {
                const back = await apiPost('/api/translate', {
                    text: probe.translated_text,
                    target_lang: probe.source_language,
                });
                polished = back.translated_text || text;
            }
            studio.finalText = polished;
            studio.interimText = '';
            renderTranscript();
            log('Polished punctuation.', 'success');
            polishBtn.disabled = false;
            polishBtn.innerHTML = originalLabel;
        } catch (e) {
            if (e instanceof RateLimitedError) {
                log(`Rate limited: ${e.message}`, 'error');
                startCountdown(polishBtn, e.retryAfter, originalLabel);
            } else {
                log(`Polish failed: ${e.message}`, 'error');
                polishBtn.disabled = false;
                polishBtn.innerHTML = originalLabel;
            }
        }
    });

    // ----------------------------------------------------------------
    // API helpers
    // ----------------------------------------------------------------
    class RateLimitedError extends Error {
        constructor(detail, retryAfter) {
            super(detail || 'Rate limited');
            this.name = 'RateLimitedError';
            this.retryAfter = retryAfter;
        }
    }
    async function apiPost(path, body) {
        const res = await fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {}),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            if (res.status === 429) {
                const retryAfter = parseInt(res.headers.get('Retry-After') || '30', 10);
                throw new RateLimitedError(err.detail || 'Rate limited', retryAfter);
            }
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return res.json();
    }
    function startCountdown(button, seconds, originalLabel) {
        let remaining = Math.max(1, Math.ceil(seconds));
        button.disabled = true;
        const update = () => {
            button.innerHTML = `⏳ wait ${remaining}s`;
            remaining -= 1;
        };
        update();
        const handle = setInterval(() => {
            if (remaining <= 0) {
                clearInterval(handle);
                button.disabled = false;
                button.innerHTML = originalLabel;
                return;
            }
            update();
        }, 1000);
    }

    // ----------------------------------------------------------------
    // Translation (ad-hoc + brief mirror)
    // ----------------------------------------------------------------
    function renderTranslation(data, opts = {}) {
        const { source = 'ad-hoc' } = opts;
        const original = escapeHtml(data.original_text || '');
        const translated = escapeHtml(data.translated_text || '');
        const srcLang = escapeHtml(data.source_language || 'unknown');
        const tgtLang = escapeHtml(data.target_language || 'en');
        const banner = data.needed_translation
            ? `<div class="text-xs text-zinc-500 mb-3">Source: <code>${source}</code> · ${srcLang} → ${tgtLang}</div>`
            : `<div class="text-xs text-zinc-500 mb-3">Source: <code>${source}</code> · already in <code>${tgtLang}</code> — no translation needed.</div>`;
        const block = data.needed_translation
            ? `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <div class="text-xs font-semibold text-zinc-500 mb-1 uppercase tracking-wide">Original (${srcLang})</div>
                        <div class="border border-zinc-800 rounded-lg p-3 text-sm bg-zinc-900/60 leading-relaxed whitespace-pre-wrap text-zinc-200">${original}</div>
                    </div>
                    <div>
                        <div class="text-xs font-semibold text-zinc-500 mb-1 uppercase tracking-wide">${tgtLang}</div>
                        <div class="border border-violet-700/40 rounded-lg p-3 text-sm bg-violet-500/5 leading-relaxed whitespace-pre-wrap text-zinc-100">${translated}</div>
                    </div>
                </div>
            `
            : `
                <div class="border border-zinc-800 rounded-lg p-3 text-sm bg-zinc-900/60 leading-relaxed whitespace-pre-wrap text-zinc-200">${original}</div>
            `;
        translateResult.innerHTML = banner + block;
    }
    translateBtn.addEventListener('click', async () => {
        const text = translateInput.value.trim();
        if (!text) {
            log('Translate input is empty', 'error');
            return;
        }
        const originalLabel = translateBtn.innerHTML;
        translateBtn.disabled = true;
        translateBtn.innerHTML = '<span class="spin"></span> Translating…';
        try {
            const data = await apiPost('/api/translate', {
                text,
                target_lang: translateTarget.value,
            });
            renderTranslation(data, { source: 'ad-hoc' });
            activateTab('translate');
            log(`Translated ${data.source_language} → ${data.target_language}`, 'success');
            translateBtn.disabled = false;
            translateBtn.innerHTML = originalLabel;
        } catch (e) {
            if (e instanceof RateLimitedError) {
                log(`Rate limited: ${e.message}`, 'error');
                startCountdown(translateBtn, e.retryAfter, originalLabel);
            } else {
                log(`Translate failed: ${e.message}`, 'error');
                translateBtn.disabled = false;
                translateBtn.innerHTML = originalLabel;
            }
        }
    });

    // ----------------------------------------------------------------
    // Compose Brief
    // ----------------------------------------------------------------
    composeBtn.addEventListener('click', async () => {
        const idea = ideaText.value.trim();
        if (!idea) {
            log('Idea is empty', 'error');
            return;
        }
        const originalLabel = '✨ Compose Brief';
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
            renderDraft();
            renderDetector(null);
            renderTranslation(
                {
                    original_text: data.original_text,
                    translated_text: data.translated_text,
                    source_language: data.source_language,
                    target_language: 'en',
                    needed_translation: data.needed_translation,
                },
                { source: `brief: ${data.post_id}` },
            );
            activateTab('brief');
            draftBtn.disabled = false;
            detectBtn.disabled = true;
            setStepStatus('draft', 'idle');
            setStepStatus('detect', 'idle');
            log(`Brief ready: ${data.working_title}`, 'success');
            composeBtn.disabled = false;
            composeBtn.innerHTML = originalLabel;
        } catch (e) {
            if (e instanceof RateLimitedError) {
                log(`Rate limited: ${e.message}`, 'error');
                startCountdown(composeBtn, e.retryAfter, originalLabel);
            } else {
                log(`Brief failed: ${e.message}`, 'error');
                composeBtn.disabled = false;
                composeBtn.innerHTML = originalLabel;
            }
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
        lines.push(``, `## Source Idea`);
        if (data.needed_translation) {
            lines.push(``, `**Original (${data.source_language}):**`);
            lines.push(``, blockquote(data.original_text));
            lines.push(``, `**Translated to ${data.target_language || 'en'}:**`);
            lines.push(``, blockquote(data.translated_text));
        } else {
            lines.push(``, `_Source language: ${data.source_language || 'unknown'} (no translation needed)._`);
            lines.push(``, blockquote(data.original_text));
        }
        panes.brief.innerHTML = marked.parse(lines.join('\n'));
    }
    function blockquote(text) {
        if (!text) return '';
        return text.split('\n').map((line) => (line.trim() ? `> ${line}` : '>')).join('\n');
    }

    // ----------------------------------------------------------------
    // Draft
    // ----------------------------------------------------------------
    draftBtn.addEventListener('click', async () => {
        if (!state.postId) return;
        const originalLabel = draftBtn.innerHTML;
        draftBtn.disabled = true;
        setStepStatus('draft', 'busy');
        log('Generating draft (this may take 20-60 seconds)…');
        try {
            const data = await apiPost(`/api/draft/${state.postId}`, {});
            state.draftText = data.text;
            state.draftPath = data.draft_path;
            state.wordCount = data.word_count;
            state.flags = [];
            renderDraft();
            renderDetector(null);
            activateTab('draft');
            setStepStatus('draft', 'ok');
            setStepStatus('detect', 'idle');
            detectBtn.disabled = false;
            log(`Draft ready: ${data.word_count} words`, 'success');
            draftBtn.disabled = false;
        } catch (e) {
            if (e instanceof RateLimitedError) {
                setStepStatus('draft', 'fail');
                log(`Rate limited: ${e.message}`, 'error');
                startCountdown(draftBtn, e.retryAfter, originalLabel);
            } else {
                setStepStatus('draft', 'fail');
                log(`Draft failed: ${e.message}`, 'error');
                draftBtn.disabled = false;
            }
        }
    });

    function renderDraft() {
        if (!state.draftText) {
            panes.draft.innerHTML = '<p class="text-zinc-600 italic">Generate a draft once a brief exists.</p>';
            return;
        }
        const meta = `<div class="text-xs text-zinc-500 mb-3">${state.wordCount} words · <code>${escapeHtml(state.draftPath)}</code></div>`;
        if (!state.flags.length) {
            panes.draft.innerHTML = meta + marked.parse(state.draftText);
            return;
        }
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
            const open = `<mark class="flag-highlight" id="flag-${flag.idx}" title="${safePattern} (~line ${flag.line_approx})">`;
            html = html
                .split(`__FLAGOPEN${flag.idx}__`).join(open)
                .split(`__FLAGCLOSE${flag.idx}__`).join('</mark>');
        });
        panes.draft.innerHTML = meta + html;
    }

    // ----------------------------------------------------------------
    // Detector
    // ----------------------------------------------------------------
    detectBtn.addEventListener('click', async () => {
        if (!state.postId) return;
        const originalLabel = detectBtn.innerHTML;
        detectBtn.disabled = true;
        setStepStatus('detect', 'busy');
        log('Running AI-tells detector…');
        try {
            const data = await apiPost(`/api/detect/${state.postId}`, {});
            state.flags = data.flags || [];
            renderDetector(data);
            renderDraft();
            activateTab('detect');
            setStepStatus('detect', data.passed ? 'ok' : 'fail');
            log(
                data.passed
                    ? `Detector PASS (${data.detector})`
                    : `Detector FAIL: ${data.flags.length} flags`,
                data.passed ? 'success' : 'error',
            );
            detectBtn.disabled = false;
        } catch (e) {
            if (e instanceof RateLimitedError) {
                setStepStatus('detect', 'fail');
                log(`Rate limited: ${e.message}`, 'error');
                startCountdown(detectBtn, e.retryAfter, originalLabel);
            } else {
                setStepStatus('detect', 'fail');
                log(`Detector failed: ${e.message}`, 'error');
                detectBtn.disabled = false;
            }
        }
    });

    function renderDetector(data) {
        if (!data) {
            panes.detect.innerHTML = '<p class="text-zinc-600 italic">Run the detector after generating a draft.</p>';
            return;
        }
        const head = `
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-semibold ${data.passed ? 'text-emerald-400' : 'text-red-400'}">
                    ${data.passed ? 'PASS' : 'FAIL'} — ${data.flags.length} flag${data.flags.length === 1 ? '' : 's'}
                </h3>
                <span class="text-xs text-zinc-500 font-mono">${data.detector}</span>
            </div>
        `;
        if (!data.flags.length) {
            panes.detect.innerHTML = head + '<p class="text-zinc-500 text-sm italic">No AI tells found. The draft is clear of the kill-list patterns.</p>';
            return;
        }
        const hint = '<p class="text-xs text-zinc-500 mb-3">Click a flag to jump to its highlighted location in the draft.</p>';
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
            log(`Flag #${idx} could not be located in the rendered draft.`, 'error');
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

    // ----------------------------------------------------------------
    // Boot
    // ----------------------------------------------------------------
    setStudioState('ready');
    if (!SR) {
        micStatus.textContent = 'Voice input requires Chrome/Safari. Type instead.';
    } else {
        micStatus.textContent = 'Click mic, then speak. Pause for punctuation.';
    }
    log('Studio ready. Click the mic and speak, or type your idea.', 'success');
})();
