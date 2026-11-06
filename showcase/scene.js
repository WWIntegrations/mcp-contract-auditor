import * as THREE from 'three';
import { createBackdropPainter, renderResolution } from './controller.mjs';
const smooth = t => t * t * (3 - 2 * t);
const clamp = value => Math.min(1, Math.max(0, value));
/** Procedural artwork. Mesh counts and colors do not encode audit results. */
export function createArtwork(canvas) {
    const mobile = matchMedia('(max-width: 700px)').matches;
    const renderer = new THREE.WebGLRenderer({
        canvas, antialias: !mobile, alpha: false, preserveDrawingBuffer: true
    });
    renderer.setPixelRatio(Math.min(devicePixelRatio, mobile ? 1 : 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.18;
    renderer.transmissionResolutionScale = mobile ? 0.5 : 0.8;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#e5e5eb');
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.z = 12;
    // All environment lighting is generated here, with no HDRI or network resource.
    const studio = new THREE.Scene();
    studio.background = new THREE.Color('#b7b9cb');
    const room = new THREE.Mesh(new THREE.BoxGeometry(30, 25, 30), new THREE.MeshBasicMaterial({
        color: '#a2a5b7', side: THREE.BackSide
    }));
    studio.add(room);
    const lights = [
        {
            p: [-5, 7, 5], s: [4, 8, 1], c: 0xffffff
        },
        {
            p: [7, 2, 3], s: [2, 11, 1], c: 0xffffff
        },
        {
            p: [0, 10, -4], s: [11, 2, 1], c: 0xe8d8ff
        },
        {
            p: [-7, -3, -4], s: [2, 7, 1], c: 0x719bff
        },
    ];
    for (const light of lights) {
        const panel = new THREE.Mesh(new THREE.BoxGeometry(...light.s), new THREE.MeshBasicMaterial({
            color: light.c
        }));
        panel.position.set(...light.p);
        panel.lookAt(0, 0, 0);
        studio.add(panel);
    }
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTarget = pmrem.fromScene(studio, 0.06);
    scene.environment = envTarget.texture;
    pmrem.dispose();
    studio.traverse(object => {
        object.geometry?.dispose();
        object.material?.dispose();
    });
    scene.add(new THREE.HemisphereLight(0xffffff, 0x606080, 2));
    const key = new THREE.DirectionalLight(0xffffff, 3);
    key.position.set(-3, 6, 5);
    scene.add(key);
    const backdropCanvas = document.createElement('canvas');
    const ctx = backdropCanvas.getContext('2d');
    if (!ctx) {
        renderer.dispose();
        envTarget.dispose();
        throw new Error('A 2D canvas is unavailable for the scene typography');
    }
    const backdropTexture = new THREE.CanvasTexture(backdropCanvas);
    backdropTexture.colorSpace = THREE.SRGBColorSpace;
    const backdrop = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({
        map: backdropTexture, toneMapped: false
    }));
    backdrop.position.z = -4;
    scene.add(backdrop);
    let width = 1440;
    let height = 900;
    const tileMaterial = new THREE.MeshPhysicalMaterial({
        color: 0xffffff, transmission: 1, opacity: 1, roughness: 0.045,
        thickness: 0.21, ior: 1.48, metalness: 0, clearcoat: 1,
        clearcoatRoughness: 0.08, dispersion: 0.8, envMapIntensity: 1.3,
    });
    const tileShape = new THREE.Shape();
    const w = 0.53, h = 0.63, r = 0.035;
    tileShape.moveTo(-w / 2 + r, -h / 2);
    tileShape.lineTo(w / 2 - r, -h / 2);
    tileShape.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
    tileShape.lineTo(w / 2, h / 2 - r);
    tileShape.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
    tileShape.lineTo(-w / 2 + r, h / 2);
    tileShape.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
    tileShape.lineTo(-w / 2, -h / 2 + r);
    tileShape.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
    const tileGeometry = new THREE.ExtrudeGeometry(tileShape, {
        depth: 0.065, bevelEnabled: true, bevelThickness: 0.018, bevelSize: 0.018, bevelSegments: 2, steps: 1, curveSegments: 3
    });
    tileGeometry.center();
    const rows = mobile ? 6 : 7;
    const columns = mobile ? 12 : 16;
    const tiles = new THREE.InstancedMesh(tileGeometry, tileMaterial, rows * columns);
    tiles.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    tiles.frustumCulled = false;
    scene.add(tiles);
    const tileTransform = new THREE.Object3D();
    const core = new THREE.Group();
    scene.add(core);
    const coreMaterial = new THREE.MeshPhysicalMaterial({
        color: '#d790f1', transmission: 0.95, opacity: 1, roughness: 0.08,
        thickness: 0.8, ior: 1.44, clearcoat: 1, iridescence: 0.7,
        iridescenceIOR: 1.32, dispersion: 0.65, envMapIntensity: 1.55,
        attenuationColor: '#e7a9ff', attenuationDistance: 3,
    });
    const arch = new THREE.Shape();
    arch.moveTo(-1.48, 0.68);
    arch.bezierCurveTo(-1.62, 2.35, 1.62, 2.35, 1.48, 0.68);
    arch.lineTo(1.04, 0.68);
    arch.bezierCurveTo(1.1, 1.72, -1.1, 1.72, -1.04, 0.68);
    arch.closePath();
    const archGeometry = new THREE.ExtrudeGeometry(arch, {
        depth: 0.34, bevelEnabled: true, bevelThickness: 0.11, bevelSize: 0.09, bevelSegments: mobile ? 3 : 5, curveSegments: mobile ? 20 : 36, steps: 1
    });
    const brackets = [];
    for (let i = 0; i < 2; i++) {
        const mesh = new THREE.Mesh(archGeometry, coreMaterial);
        mesh.position.set(i === 0 ? -0.1 : 0.1, i === 0 ? 0 : -0.12, i === 0 ? 0.14 : -0.5);
        mesh.rotation.y = i === 0 ? 0.16 : -0.16;
        core.add(mesh);
        brackets.push(mesh);
    }
    const strands = [];
    const strandCount = mobile ? 8 : 12;
    const segments = mobile ? 36 : 60;
    for (let i = 0; i < strandCount; i++) {
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array((segments + 1) * 6);
        const indices = [];
        for (let j = 0; j < segments; j++)
            indices.push(j * 2, j * 2 + 1, j * 2 + 2, j * 2 + 1, j * 2 + 3, j * 2 + 2);
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage));
        geometry.setIndex(indices);
        const material = coreMaterial.clone();
        material.side = THREE.DoubleSide;
        material.thickness = i % 3 === 0 ? 0.12 : 0.035;
        const mesh = new THREE.Mesh(geometry, material);
        mesh.frustumCulled = false;
        core.add(mesh);
        strands.push({
            mesh, positions, index: i
        });
    }
    const pearl = new THREE.Mesh(new THREE.SphereGeometry(0.13, 20, 12), new THREE.MeshPhysicalMaterial({
        color: 0xffffff, roughness: 0.2, clearcoat: 1
    }));
    pearl.position.y = -0.05;
    core.add(pearl);
    const openingSphere = new THREE.Mesh(new THREE.SphereGeometry(3.05, mobile ? 32 : 64, mobile ? 24 : 48), new THREE.MeshPhysicalMaterial({
        color: '#cdd1dd', metalness: 0.08, roughness: 0.5, transmission: 0.85, thickness: 3, ior: 1.12
    }));
    scene.add(openingSphere);
    let materialMode = 'glass';
    let colorMode = 'scroll';
    const backdropPainter = createBackdropPainter(({ width, height, scroll, scale }) => {
        const bw = backdropCanvas.width, bh = backdropCanvas.height;
        ctx.fillStyle = '#e5e5eb';
        ctx.fillRect(0, 0, bw, bh);
        ctx.fillStyle = 'rgba(255,255,255,.2)';
        const pitch = Math.max(5, bw / 180);
        for (let y = 0; y < bh; y += pitch)
            for (let x = 0; x < bw; x += pitch) {
                ctx.beginPath();
                ctx.arc(x, y, pitch * 0.23, 0, Math.PI * 2);
                ctx.fill();
            }
        ctx.fillStyle = '#000000';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const small = width < 700;
        const text = 'CONTRACT LAB';
        let fontSize = bh * 0.37;
        ctx.font = `${fontSize}px Anton`;
        fontSize *= Math.min(1, bw * 0.81 / ctx.measureText(text).width);
        if (small)
            fontSize = bw * 0.24;
        ctx.font = `${fontSize}px Anton`;
        ctx.save();
        ctx.translate(bw / 2, bh * (small ? 0.465 : 411 / 900));
        ctx.scale(scale, scale);
        if (small) {
            ctx.fillText('CONTRACT', 0, -fontSize * 0.53);
            ctx.fillText('LAB', 0, fontSize * 0.53);
        }
        else {
            // Fit the substitute font's visible ink, not its em box.
            ctx.textBaseline = 'alphabetic';
            const ink = ctx.measureText(text);
            const xScale = bw * (1163 / 1440) / (ink.actualBoundingBoxLeft + ink.actualBoundingBoxRight);
            const yScale = bh * (274 / 900) / (ink.actualBoundingBoxAscent + ink.actualBoundingBoxDescent);
            const baseline = (ink.actualBoundingBoxAscent - ink.actualBoundingBoxDescent) / 2;
            const centeredX = (ink.actualBoundingBoxLeft - ink.actualBoundingBoxRight) / 2;
            const shift = scroll / 1600 * bw * 1.55;
            ctx.scale(xScale, yScale);
            ctx.fillText(text, centeredX - shift / xScale, baseline);
            ctx.fillText('READ THE CONTRACT', (bw * 1.55 - shift) / xScale, baseline);
        }
        ctx.restore();
        backdropTexture.needsUpdate = true;
    });
    function resize() {
        const rect = canvas.parentElement.getBoundingClientRect();
        width = Math.max(1, Math.round(rect.width));
        height = Math.max(1, Math.round(rect.height));
        const quality = renderResolution(width, devicePixelRatio);
        renderer.setPixelRatio(quality.pixelRatio);
        renderer.transmissionResolutionScale = quality.transmissionScale;
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.position.z = width < 700 ? 15.8 : 12;
        camera.updateProjectionMatrix();
        const planeHeight = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * (camera.position.z + 4);
        backdrop.scale.set(planeHeight * camera.aspect, planeHeight, 1);
        const resolution = Math.min(1, 1600 / width);
        backdropCanvas.width = Math.round(width * resolution);
        backdropCanvas.height = Math.round(height * resolution);
        backdropPainter.invalidate();
    }
    function render(state) {
        const time = state.motionMs / 1000;
        const intro = state.phase === 'entry' ? 0 : state.introProgress;
        const reveal = smooth(clamp((intro - 0.12) / 0.25));
        const open = smooth(state.holdProgress);
        const compact = width < 700 ? 0.72 : 1;
        const pulse = Math.sin(time * 1.3) * 0.022;
        const coreScale = (0.16 + 0.84 * reveal) * compact;
        core.scale.setScalar(coreScale);
        core.position.y = (width < 700 ? 0 : 0.34) + state.scroll / 1600 * 0.35;
        brackets[0].scale.set(1 + pulse, 1 - pulse, 1);
        brackets[1].rotation.y = -0.16 + Math.sin(time * 0.7) * 0.07;
        openingSphere.visible = intro < 0.26;
        openingSphere.scale.setScalar(compact * (1 - smooth(clamp((intro - 0.16) / 0.1))));
        tiles.visible = open < 0.999 && intro > 0.14;
        let index = 0;
        const spreadIntro = (1 - smooth(clamp((intro - 0.22) / 0.36))) * 2.4;
        for (let row = 0; row < rows; row++) {
            const phi = -1.17 + row / (rows - 1) * 2.34;
            for (let col = 0; col < columns; col++) {
                const theta = col / columns * Math.PI * 2 + row * 0.09 + Math.sin(time * 0.22) * 0.035;
                const direction = new THREE.Vector3(Math.cos(phi) * Math.sin(theta), Math.sin(phi), Math.cos(phi) * Math.cos(theta));
                const radius = (2.95 + spreadIntro + open * (5.2 + (index % 5) * 0.4)) * compact * 0.97;
                tileTransform.position.copy(direction).multiplyScalar(radius);
                tileTransform.lookAt(tileTransform.position.clone().multiplyScalar(2));
                tileTransform.rotateZ(open * Math.sin(index * 2.1) * 1.6);
                tileTransform.rotateY(open * Math.cos(index) * 1.3);
                tileTransform.scale.setScalar(compact * (1 - open * 0.65) * 0.97);
                tileTransform.updateMatrix();
                tiles.setMatrixAt(index++, tileTransform.matrix);
            }
        }
        tiles.instanceMatrix.needsUpdate = true;
        const tint = colorMode === 'violet' ? 0 : colorMode === 'blue' ? 1 : clamp(state.scroll / 650);
        const color = new THREE.Color('#d790f1').lerp(new THREE.Color('#77c7ef'), tint);
        coreMaterial.color.copy(color);
        for (const { mesh, positions, index: i } of strands) {
            mesh.material.color.copy(color);
            const side = i % 2 === 0 ? -1 : 1;
            const anchor = side * (0.5 + (i % 6) * 0.17);
            for (let j = 0; j <= segments; j++) {
                const u = j / segments;
                const phase = u * 7 + time * (0.55 + i * 0.03) + i * 1.7;
                const x = anchor * (1 - u * 0.6) + Math.sin(phase) * 0.32 * Math.sin(u * Math.PI);
                const y = 0.72 - u * (3.3 + (i % 4) * 0.28);
                const z = Math.cos(phase * 0.7) * 0.32 + Math.sin(i) * 0.22;
                const half = (i % 3 === 0 ? 0.1 : 0.02) * (1 - u * 0.75);
                const twist = phase * 0.8;
                const offset = j * 6;
                positions[offset] = x - Math.cos(twist) * half;
                positions[offset + 1] = y;
                positions[offset + 2] = z - Math.sin(twist) * half;
                positions[offset + 3] = x + Math.cos(twist) * half;
                positions[offset + 4] = y;
                positions[offset + 5] = z + Math.sin(twist) * half;
            }
            mesh.geometry.attributes.position.needsUpdate = true;
            mesh.geometry.computeVertexNormals();
        }
        backdropPainter.render({
            width, height, scroll: state.scroll, scale: 0.12 + 0.88 * reveal
        });
        renderer.render(scene, camera);
    }
    resize();
    return {
        render, resize,
        setColor(value) {
            colorMode = value;
        },
        setMaterial(value) {
            materialMode = value;
            coreMaterial.wireframe = value === 'wire';
            for (const { mesh } of strands)
                mesh.material.wireframe = value === 'wire';
        },
        stats() {
            return {
                renderer: 'WebGL', transmission: coreMaterial.transmission, materialMode, triangles: renderer.info.render.triangles, tileCount: rows * columns, lod: mobile ? 'mobile' : 'desktop', geometryLod: mobile ? 'mobile' : 'desktop', composition: width < 700 ? 'mobile' : 'desktop', pixelRatio: renderer.getPixelRatio()
            };
        },
        dispose() {
            scene.traverse(object => {
                object.geometry?.dispose();
                if (Array.isArray(object.material))
                    object.material.forEach(material => material.dispose());
                else
                    object.material?.dispose();
            });
            backdropTexture.dispose();
            envTarget.dispose();
            renderer.dispose();
        },
    };
}
