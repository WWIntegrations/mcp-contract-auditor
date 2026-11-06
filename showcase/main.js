import { createSceneController, filterFindings, selectStep, displayText, selectArtifact, INTRO_MS, HOLD_MS, DURATION_MS } from './controller.mjs';
import { createArtwork } from './scene.js';
const $ = selector => document.querySelector(selector);
const data = JSON.parse($('#showcase-data').textContent);
const artifacts = JSON.parse($('#showcase-artifacts').textContent);
const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
const scene = createSceneController({
    reducedMotion: motionPreference.matches
});
let artwork = null;
let manualFrame = false;
let ready = false;
let stepIndex = 0;
let lastTime = performance.now();
let artworkError = null;
let renderedFindings = [];
function text(element, value) {
    element.textContent = displayText(value ?? 'Not declared');
}
function element(tag, content, className) {
    const node = document.createElement(tag);
    if (content !== undefined)
        text(node, content);
    if (className)
        node.className = className;
    return node;
}
function pretty(value) {
    return displayText(JSON.stringify(value, null, 2));
}
function download(content, name, type = 'application/json') {
    const url = URL.createObjectURL(new Blob([content], {
        type
    }));
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function showFallback(error) {
    artworkError = error instanceof Error ? error.message : String(error);
    $('#scene-canvas').hidden = true;
    $('#art-fallback').hidden = false;
    text($('#fallback-note'), 'Static artwork. WebGL is unavailable; the full inspector remains usable.');
    scene.skip();
    document.querySelectorAll('[data-color],#material-toggle').forEach(button => button.disabled = true);
    artwork = null;
}
function paint() {
    const state = scene.state();
    try {
        artwork?.render(state);
    }
    catch (error) {
        showFallback(error);
    }
    const current = scene.state();
    $('#entry-controls').hidden = current.phase !== 'entry';
    $('#hold-open').hidden = current.phase !== 'cage';
    $('#hold-help').hidden = current.phase !== 'cage';
    $('#hold-progress').value = current.holdProgress;
    $('#hold-open').style.transform = `scale(${1 - current.holdProgress * 0.25})`;
    $('#skip-intro').hidden = current.phase === 'open';
    $('#scene-open-copy').hidden = current.phase !== 'open';
    $('.material-panel').hidden = current.phase !== 'open';
    $('#motion-toggle').setAttribute('aria-pressed', String(current.paused));
    $('#motion-toggle').lastChild.textContent = current.reducedMotion ? ' STILL' : current.paused ? ' RESUME' : ' PAUSE';
    $('#motion-toggle').setAttribute('aria-label', current.reducedMotion ? 'Reduced motion enabled' : current.paused ? 'Resume artwork motion' : 'Pause artwork motion');
    $('#motion-toggle').disabled = current.reducedMotion;
    document.body.dataset.scenePhase = current.phase;
    window.showcaseMeta = {
        ready, step: stepIndex, stepCount: data.steps.length, state: current.phase,
        introMs: INTRO_MS, holdMs: HOLD_MS, durationMs: DURATION_MS,
        motionMs: current.motionMs, motionPaused: current.paused,
        reducedMotion: current.reducedMotion, playing: !manualFrame && !current.paused,
        decorativeScroll: current.scroll, holdProgress: current.holdProgress,
        renderer: artwork ? 'WebGL' : 'static', artworkError,
        graphics: artwork?.stats() ?? null,
        findingCount: renderedFindings.length,
        displayedFindingRules: renderedFindings.map(item => item.rule_id),
        receiptValid: data.receipt_valid,
        staleReceiptValid: data.stale_receipt_valid,
        auditDigest: data.report.audit_digest,
    };
}
function renderTranscript(target, transcript) {
    const fragment = document.createDocumentFragment();
    transcript.exchanges.forEach((exchange, index) => {
        const row = element('div', undefined, 'trace-row');
        row.dataset.method = exchange.request.method;
        row.dataset.page = String(index + 1);
        row.append(element('span', String(index + 1).padStart(2, '0')));
        const body = element('div');
        body.append(element('p', exchange.request.method));
        const requestCursor = Object.hasOwn(exchange.request.params, 'cursor') ? JSON.stringify(exchange.request.params.cursor) : '(first page)';
        body.append(element('small', `request id ${JSON.stringify(exchange.request.id)} / cursor ${requestCursor}`));
        const result = exchange.response.result;
        body.append(element('p', result.tools.map(tool => tool.name).join(', ') || 'Empty page'));
        const next = Object.hasOwn(result, 'nextCursor') ? JSON.stringify(result.nextCursor) : '(catalog end)';
        body.append(element('small', `${result.tools.length} declarations / next cursor ${next}`));
        row.append(body);
        fragment.append(row);
    });
    target.replaceChildren(fragment);
}
function renderDiff() {
    const tool = $('#tool-select').value;
    const severity = $('#severity-select').value;
    renderedFindings = filterFindings(data.report, tool, severity);
    const findings = document.createDocumentFragment();
    for (const item of renderedFindings) {
        const row = element('article', undefined, 'finding-row');
        row.dataset.ruleId = item.rule_id;
        row.dataset.severity = item.severity;
        row.dataset.tool = item.tool ?? '';
        row.append(element('span', item.severity.toUpperCase(), 'severity'));
        const identity = element('div');
        identity.append(element('h4', item.tool || 'Catalog'), element('code', item.pointer || '(root)'));
        const reason = element('div');
        reason.append(element('p', item.rule_id), element('p', item.reason_code));
        row.append(identity, reason);
        findings.append(row);
    }
    if (!renderedFindings.length)
        findings.append(element('p', 'No findings match these filters. This is not a safety conclusion.'));
    $('#finding-list').replaceChildren(findings);
    text($('#filter-count'), `${renderedFindings.length} of ${data.report.findings.length} findings shown`);
    const relations = document.createDocumentFragment();
    for (const item of data.report.schema_relations.filter(item => tool === '*' || item.tool === tool)) {
        const row = element('div', undefined, 'relation-row');
        row.dataset.tool = item.tool;
        row.dataset.compatibility = item.compatibility;
        row.append(element('span', item.tool), element('span', item.side), element('span', item.relation ?? 'not_declared'), element('span', item.compatibility));
        relations.append(row);
    }
    $('#relation-list').replaceChildren(relations);
    const changes = document.createDocumentFragment();
    for (const item of data.report.changes.filter(item => tool === '*' || item.tool === tool)) {
        const row = element('article', undefined, 'change-row');
        row.dataset.pointer = item.pointer;
        row.dataset.tool = item.tool;
        row.append(element('h4', `${item.tool} / ${item.kind} / ${item.pointer || '(root)'}`));
        const values = element('div', undefined, 'change-values');
        for (const side of ['before', 'after']) {
            const column = element('div');
            column.append(element('p', side.toUpperCase()));
            column.append(element('pre', item[side].present ? pretty(item[side].value) : 'ABSENT'));
            values.append(column);
        }
        row.append(values);
        changes.append(row);
    }
    if (!changes.childNodes.length)
        changes.append(element('p', 'No structural changes for the selected tool.'));
    $('#change-list').replaceChildren(changes);
    if (ready)
        paint();
}
function renderReceipt() {
    const stale = $('#receipt-check').value === 'stale';
    const valid = stale ? data.stale_receipt_valid : data.receipt_valid;
    $('#receipt-status').dataset.valid = String(valid);
    text($('#receipt-status'), valid ? 'DIGEST MATCHES.' : 'DIGEST DOES NOT MATCH.');
    text($('#receipt-description'), stale ? 'Recorded core check after changing the candidate description. The old receipt no longer matches that comparison.' : 'Recorded core check against the original snapshots and audit ruleset. This browser is displaying the result, not authenticating the reviewer.');
}
const stepHelp = {
    'capture-baseline': 'Inspect the baseline fixture process capture. Page cursors are shown literally, including an empty string cursor.',
    'capture-candidate': 'Inspect the candidate fixture process capture. These are declarations; no tools/call request was sent.',
    'input-contract': 'A required input changed. Read the exact before/after values and the bounded schema relation.',
    description: 'A description changed. Treat the text as untrusted data, not an instruction to this viewer.',
    hints: 'Declared hints changed. They are metadata, not permissions or proof of implementation behavior.',
    'opaque-schema': 'The unsupported schema stays visible. Unknown remains unknown even when its text has not changed.',
    receipt: 'The fixture created a local unsigned acknowledgement bound to this audit digest. Findings are unchanged.',
    'stale-receipt': 'The fixture changed the candidate after acknowledgement and checked the old receipt again.',
};
function chooseStep(index) {
    stepIndex = selectStep(index, data.steps.length);
    const step = data.steps[stepIndex];
    $('#step-select').value = String(stepIndex);
    $('#previous-step').disabled = stepIndex === 0;
    $('#next-step').disabled = stepIndex === data.steps.length - 1;
    text($('#step-number'), `${String(stepIndex + 1).padStart(2, '0')} / ${String(data.steps.length).padStart(2, '0')}`);
    text($('#step-label'), step.label);
    text($('#step-description'), stepHelp[step.step_id] || 'Inspect the captured artifact below.');
    const hasTool = [...$('#tool-select').options].some(option => option.value === step.tool);
    $('#tool-select').value = hasTool ? step.tool : '*';
    $('#severity-select').value = '*';
    $('#receipt-check').value = step.step_id === 'stale-receipt' ? 'stale' : 'current';
    renderReceipt();
    renderDiff();
}
function initializeData() {
    const stepOptions = data.steps.map((step, index) => {
        const option = element('option', `${String(index + 1).padStart(2, '0')} / ${step.label}`);
        option.value = String(index);
        return option;
    });
    $('#step-select').replaceChildren(...stepOptions);
    const all = element('option', 'All tools');
    all.value = '*';
    const names = [...new Set([...data.baseline_snapshot.tools, ...data.candidate_snapshot.tools].map(tool => tool.name))].sort();
    $('#tool-select').replaceChildren(all, ...names.map(name => {
        const option = element('option', name);
        option.value = name;
        return option;
    }));
    text($('#context-label'), `${data.report.origin_id} / ${data.report.scope_id}`);
    text($('#protocol-profile'), data.report.protocol_version);
    text($('#ruleset'), data.report.ruleset_version);
    text($('#tool-count'), `${data.report.tool_count.baseline} / ${data.report.tool_count.candidate}`);
    renderTranscript($('#baseline-trace'), data.baseline_transcript);
    renderTranscript($('#candidate-trace'), data.candidate_transcript);
    for (const key of ['baseline_transcript', 'candidate_transcript', 'baseline_snapshot', 'candidate_snapshot']) {
        text($(`#${key.replaceAll('_', '-')}`), selectArtifact(artifacts, key));
    }
    text($('#baseline-digest'), data.baseline_snapshot.contract_digest);
    text($('#candidate-digest'), data.candidate_snapshot.contract_digest);
    const coverage = document.createDocumentFragment();
    for (const side of ['input', 'output']) {
        const column = element('div');
        column.append(element('h3', side.toUpperCase()));
        const list = element('dl');
        for (const [key, value] of Object.entries(data.report.schema_coverage[side])) {
            const row = element('div');
            row.append(element('dt', key), element('dd', value));
            list.append(row);
        }
        column.append(list);
        coverage.append(column);
    }
    $('#coverage').replaceChildren(coverage);
    text($('#receipt-reviewer'), `Declared reviewer: ${data.receipt.reviewer}`);
    text($('#receipt-digest'), data.report.audit_digest);
    text($('#receipt-json'), selectArtifact(artifacts, 'receipt'));
    chooseStep(0);
}
$('#start-view').addEventListener('click', () => {
    manualFrame = false;
    scene.start();
    paint();
});
$('#skip-intro').addEventListener('click', () => {
    manualFrame = false;
    scene.skip();
    paint();
});
$('#hold-open').addEventListener('pointerdown', event => {
    if (event.button !== 0)
        return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    manualFrame = false;
    scene.beginHold();
});
for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    $('#hold-open').addEventListener(name, () => {
        scene.cancelHold();
        paint();
    });
}
$('#hold-open').addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        scene.skip();
        paint();
    }
});
window.addEventListener('blur', () => scene.cancelHold());
$('#motion-toggle').addEventListener('click', () => {
    scene.setPaused(!scene.state().paused);
    manualFrame = false;
    lastTime = performance.now();
    paint();
});
for (const button of document.querySelectorAll('[data-color]'))
    button.addEventListener('click', () => {
        artwork?.setColor(button.dataset.color);
        document.querySelectorAll('[data-color]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
        paint();
    });
$('#material-toggle').addEventListener('click', event => {
    const button = event.currentTarget;
    const enabled = button.getAttribute('aria-pressed') !== 'true';
    button.setAttribute('aria-pressed', String(enabled));
    artwork?.setMaterial(enabled ? 'wire' : 'glass');
    paint();
});
$('#step-select').addEventListener('change', event => chooseStep(Number(event.target.value)));
$('#previous-step').addEventListener('click', () => chooseStep(stepIndex - 1));
$('#next-step').addEventListener('click', () => chooseStep(stepIndex + 1));
$('#tool-select').addEventListener('change', renderDiff);
$('#severity-select').addEventListener('change', renderDiff);
$('#reset-filters').addEventListener('click', () => {
    $('#tool-select').value = '*';
    $('#severity-select').value = '*';
    renderDiff();
});
$('#receipt-check').addEventListener('change', renderReceipt);
$('#export-artifact').addEventListener('click', () => {
    const kind = $('#export-kind').value;
    const raw = selectArtifact(artifacts, kind);
    download(raw, `contract-lab-${kind}.json`);
    text($('#export-status'), `Downloaded ${kind}. Original core serializer text preserved.`);
});
$('#export-licenses').addEventListener('click', () => download($('#font-license').textContent, 'contract-lab-licenses.json'));
window.addEventListener('resize', () => {
    if (!ready)
        return;
    try {
        artwork?.resize();
    }
    catch (error) {
        showFallback(error);
    }
    paint();
});
window.addEventListener('scroll', () => {
    if (!ready || manualFrame)
        return;
    scene.setScroll(window.scrollY);
    paint();
}, {
    passive: true
});
$('#scene-canvas').addEventListener('webglcontextlost', event => {
    event.preventDefault();
    showFallback(new Error('WebGL context lost'));
    paint();
});
window.showcaseFrame = ms => {
    if (!ready)
        throw new Error('Wait for showcaseReady');
    manualFrame = true;
    scene.frame(ms);
    paint();
    return window.showcaseMeta;
};
motionPreference.addEventListener('change', event => {
    scene.setReducedMotion(event.matches);
    lastTime = performance.now();
    if (ready)
        paint();
});
window.showcaseReady = (async () => {
    await Promise.all([document.fonts.load('32px Anton'), document.fonts.load('13px Departure')]);
    await document.fonts.ready;
    initializeData();
    try {
        artwork = createArtwork($('#scene-canvas'));
    }
    catch (error) {
        showFallback(error);
    }
    document.querySelectorAll('button:disabled,select:disabled').forEach(control => control.disabled = false);
    if (!artwork)
        document.querySelectorAll('[data-color],#material-toggle').forEach(control => control.disabled = true);
    $('#motion-toggle').disabled = scene.state().reducedMotion;
    ready = true;
    chooseStep(0);
    paint();
    lastTime = performance.now();
    return window.showcaseMeta;
})();
function animate(now) {
    const delta = Math.min(100, Math.max(0, now - lastTime));
    lastTime = now;
    if (ready && !manualFrame && !document.hidden && !scene.state().paused) {
        scene.tick(delta);
        paint();
    }
    requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
