import test from 'node:test';
import assert from 'node:assert/strict';
import { createSceneController, filterFindings, selectStep, displayText, selectArtifact, createBackdropPainter, renderResolution } from './controller.mjs';
test('opening the scene does not require or create an audit decision', () => {
    const scene = createSceneController();
    scene.skip();
    assert.equal(scene.state().phase, 'open');
    assert.equal('receipt' in scene.state(), false);
});
test('a cancelled hold does not unlock the scene', () => {
    const scene = createSceneController();
    scene.start();
    scene.tick(8000);
    scene.beginHold();
    scene.tick(900);
    assert.ok(scene.state().holdProgress > 0);
    scene.cancelHold();
    assert.equal(scene.state().holdProgress, 0);
    assert.equal(scene.state().phase, 'cage');
});
test('hold can finish and release cannot relock it', () => {
    const scene = createSceneController();
    scene.start();
    scene.tick(8000);
    scene.beginHold();
    scene.tick(2400);
    scene.cancelHold();
    assert.equal(scene.state().phase, 'open');
});
test('motion pause freezes elapsed phase, hold and scroll decoration', () => {
    const scene = createSceneController();
    scene.frame(15000);
    scene.setPaused(true);
    const before = scene.state();
    scene.tick(800);
    scene.setScroll(1400);
    assert.deepEqual(scene.state(), before);
    scene.setPaused(false);
    scene.tick(100);
    assert.ok(scene.state().motionMs > before.motionMs);
});
test('reduced motion is static in both timeline and manual scroll APIs', () => {
    const scene = createSceneController({
        reducedMotion: true
    });
    scene.frame(0);
    const before = scene.state();
    scene.frame(18000);
    scene.setScroll(1600);
    scene.tick(1000);
    assert.deepEqual(scene.state(), before);
    assert.equal(before.phase, 'open');
});
test('deterministic sampling is independent of prior frames', () => {
    const scene = createSceneController();
    const first = scene.frame(9500);
    scene.frame(20000);
    assert.deepEqual(scene.frame(9500), first);
});
test('nonfinite timeline input is rejected without corrupting state', () => {
    const scene = createSceneController();
    const before = scene.state();
    assert.throws(() => scene.frame(NaN), /finite/);
    assert.deepEqual(scene.state(), before);
});
test('finding filters retain unknown and do not change report', () => {
    const report = {
        findings: [{
                tool: 'a', severity: 'high'
            }, {
                tool: 'b', severity: 'unknown'
            }, {
                tool: 'a', severity: 'unknown'
            }]
    };
    const original = JSON.stringify(report);
    assert.equal(filterFindings(report, 'a', 'unknown').length, 1);
    assert.equal(filterFindings(report, '*', '*').length, 3);
    assert.equal(JSON.stringify(report), original);
});
test('step selection clamps at real bounds', () => {
    assert.equal(selectStep(-1, 8), 0);
    assert.equal(selectStep(8, 8), 7);
    assert.throws(() => selectStep(0, 0), /steps/);
});
test('control and bidi characters remain visible as escaped data', () => {
    assert.equal(displayText('x\u202ey\u001bz'), 'x\\u202ey\\u001bz');
    assert.equal(displayText('</script>'), '</script>');
});
test('artifact export returns exact bytes as text without Number roundtrip', () => {
    const original = '{"n":123456789012345678901234567890,"d":1.2300}\n';
    assert.equal(selectArtifact({
        report: original
    }, 'report'), original);
    assert.throws(() => selectArtifact({
        report: original
    }, '__proto__'), /artifact/);
});
test('backdrop at 15002 ms is identical after nearby or distant preceding frame', () => {
    function sample(previous) {
        let painted;
        const painter = createBackdropPainter(frame => {
            painted = frame;
        });
        const scene = createSceneController();
        for (const ms of [previous, 15002]) {
            const state = scene.frame(ms);
            painter.render({
                width: 1440, height: 900, scroll: state.scroll, scale: 1
            });
        }
        return painted;
    }
    assert.deepEqual(sample(15000), sample(0));
    assert.equal(sample(15000).scroll, 400.4);
});
test('a changed intro scale redraws even inside the old quantization bucket', () => {
    let calls = 0;
    const painter = createBackdropPainter(() => {
        calls++;
    });
    painter.render({
        width: 1440, height: 900, scroll: 0, scale: 0.5
    });
    painter.render({
        width: 1440, height: 900, scroll: 0, scale: 0.5001
    });
    assert.equal(calls, 2);
    painter.render({
        width: 1440, height: 900, scroll: 0, scale: 0.5001
    });
    assert.equal(calls, 2);
    painter.invalidate();
    painter.render({
        width: 1440, height: 900, scroll: 0, scale: 0.5001
    });
    assert.equal(calls, 3);
});
test('changing reduced motion freezes an active intro and manual frames', () => {
    const scene = createSceneController();
    scene.start();
    scene.tick(4000);
    scene.setReducedMotion(true);
    const frozen = scene.state();
    scene.tick(5000);
    scene.frame(18000);
    scene.setScroll(1200);
    assert.deepEqual(scene.state(), frozen);
    scene.setReducedMotion(false);
    const restored = scene.state();
    assert.equal(restored.paused, true);
    scene.tick(1000);
    assert.deepEqual(scene.state(), restored);
    scene.setPaused(false);
    scene.tick(100);
    assert.ok(scene.state().motionMs > restored.motionMs);
});
test('changing reduced motion during hold neither completes nor resets the gesture', () => {
    const scene = createSceneController();
    scene.start();
    scene.tick(8000);
    scene.beginHold();
    scene.tick(900);
    scene.setReducedMotion(true);
    const frozen = scene.state();
    scene.tick(3000);
    scene.frame(20000);
    scene.beginHold();
    assert.deepEqual(scene.state(), frozen);
    assert.equal(frozen.phase, 'cage');
});

test('render resolution follows desktop to mobile to desktop resize', () => {
    assert.deepEqual([1440,390,1440].map(width => renderResolution(width,2)), [
        {pixelRatio:1.5,transmissionScale:0.8},
        {pixelRatio:1,transmissionScale:0.5},
        {pixelRatio:1.5,transmissionScale:0.8},
    ]);
    assert.equal(renderResolution(390,0.75).pixelRatio,0.75);
});
