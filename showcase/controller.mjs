export const INTRO_MS = 8000;
export const HOLD_MS = 2400;
export const DURATION_MS = 24000;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
/** Visual time is independent of report selection and receipt state. */
export function createSceneController({ reducedMotion = false } = {}) {
    let phase = reducedMotion ? 'open' : 'entry';
    let introMs = reducedMotion ? INTRO_MS : 0;
    let holdMs = reducedMotion ? HOLD_MS : 0;
    let motionMs = 0;
    let scroll = 0;
    let paused = reducedMotion;
    let holding = false;
    function state() {
        return {
            phase, introProgress: introMs / INTRO_MS, holdProgress: holdMs / HOLD_MS,
            motionMs, scroll, paused, reducedMotion,
        };
    }
    function skip() {
        phase = 'open';
        introMs = INTRO_MS;
        holdMs = HOLD_MS;
        holding = false;
        return state();
    }
    return {
        state,
        start() {
            if (reducedMotion)
                return skip();
            phase = 'intro';
            introMs = 0;
            holdMs = 0;
            motionMs = 0;
            scroll = 0;
            holding = false;
            return state();
        },
        skip,
        beginHold() {
            if (phase === 'cage' && !paused)
                holding = true;
        },
        cancelHold() {
            if (reducedMotion)
                return;
            holding = false;
            if (phase === 'cage')
                holdMs = 0;
        },
        setReducedMotion(value) {
            reducedMotion = Boolean(value);
            if (reducedMotion) {
                paused = true;
                holding = false;
            }
            return state();
        },
        setPaused(value) {
            paused = reducedMotion || Boolean(value);
            if (paused)
                holding = false;
        },
        setScroll(value) {
            if (!paused && phase === 'open')
                scroll = clamp(Number(value) || 0, 0, 1600);
        },
        tick(delta) {
            if (paused || !Number.isFinite(delta) || delta < 0)
                return state();
            motionMs += delta;
            if (phase === 'intro') {
                introMs = clamp(introMs + delta, 0, INTRO_MS);
                if (introMs === INTRO_MS)
                    phase = 'cage';
            }
            if (holding && phase === 'cage') {
                holdMs = clamp(holdMs + delta, 0, HOLD_MS);
                if (holdMs === HOLD_MS)
                    skip();
            }
            return state();
        },
        frame(value) {
            if (!Number.isFinite(value))
                throw new TypeError('Timeline value must be finite');
            if (reducedMotion)
                return state();
            const ms = clamp(value, 0, DURATION_MS);
            motionMs = ms;
            introMs = clamp(ms, 0, INTRO_MS);
            holdMs = clamp(ms - INTRO_MS, 0, HOLD_MS);
            phase = ms < INTRO_MS ? 'intro' : ms < INTRO_MS + HOLD_MS ? 'cage' : 'open';
            holding = false;
            scroll = clamp((ms - 13000) / 5, 0, 1600);
            return state();
        },
    };
}
export function filterFindings(report, tool = '*', severity = '*') {
    return report.findings.filter(item => (tool === '*' || item.tool === tool) &&
        (severity === '*' || item.severity === severity));
}
export function selectStep(index, count) {
    if (!Number.isSafeInteger(count) || count < 1)
        throw new RangeError('No steps available');
    return clamp(Math.trunc(Number(index) || 0), 0, count - 1);
}
export function displayText(value) {
    return String(value).replace(/[\u0000-\u0008\u000b-\u001f\u007f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, char => `\\u${char.codePointAt(0).toString(16).padStart(4, '0')}`);
}
export function selectArtifact(artifacts, name) {
    if (!Object.hasOwn(artifacts, name) || typeof artifacts[name] !== 'string') {
        throw new TypeError('Unknown artifact');
    }
    return artifacts[name];
}
export function createBackdropPainter(paint) {
    let key = null;
    return {
        render(frame) {
            const next = `${frame.width},${frame.height},${frame.scroll},${frame.scale}`;
            if (key === next)
                return;
            key = next;
            paint(frame);
        },
        invalidate() {
            key = null;
        },
    };
}

export function renderResolution(width, deviceRatio) {
    return {
        pixelRatio: Math.min(deviceRatio, width < 700 ? 1 : 1.5),
        transmissionScale: width < 700 ? 0.5 : 0.8,
    };
}
