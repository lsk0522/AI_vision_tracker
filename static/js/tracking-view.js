import { state } from './state.js';

/* ==========================================
   조준점 렌더링 캔버스 + 서버 위치 동기화 + 메인 루프
   ========================================== */
const img    = document.getElementById("video");
const canvas = document.getElementById("overlay");
const ctx    = canvas.getContext("2d");

canvas.width  = 640;
canvas.height = 480;

/* ==========================================
   Apple 시네마틱 크로스헤어 — 코너 브래킷 + 중심 도트
   ========================================== */
function drawCrosshair(){
    ctx.clearRect(0, 0, 640, 480);

    // 수동: Apple Red, 자동: Apple Green
    const color = (state.controlMode === "auto") ? "#30D158" : "#FF3B30";

    ctx.save();

    // 학습 모드 중이거나 ROI 영역을 선택하고 있을 때는 조준점(도트·링·브래킷) 전부 숨김
    const roiOverlayEl = document.getElementById("roi-select-overlay");
    const isROIOpen = roiOverlayEl && (roiOverlayEl.style.display === "block");
    if (!state.learningMode && !isROIOpen && state.controlMode !== "auto") {

        // ── 중심 도트 ──────────────────────────
        ctx.shadowBlur  = 10;
        ctx.shadowColor = color;
        ctx.fillStyle   = color;
        ctx.beginPath();
        ctx.arc(state.px, state.py, 2, 0, Math.PI * 2);
        ctx.fill();

        // ── 바깥 링 (얇고 반투명) ───────────────
        ctx.strokeStyle = (state.controlMode === "auto")
            ? "rgba(48, 209, 88, 0.28)"
            : "rgba(255, 59, 48, 0.28)";
        ctx.lineWidth   = 1;
        ctx.shadowBlur  = 0;
        ctx.beginPath();
        ctx.arc(state.px, state.py, 22, 0, Math.PI * 2);
        ctx.stroke();

        // ── 코너 브래킷 (L자 4개) ──────────────
        const gap = 28;
        const len = 10;
        const corners = [
            { ox: state.px - gap, oy: state.py - gap, dx:  len, dy:    0, ex:   0, ey:  len },
            { ox: state.px + gap, oy: state.py - gap, dx: -len, dy:    0, ex:   0, ey:  len },
            { ox: state.px - gap, oy: state.py + gap, dx:  len, dy:    0, ex:   0, ey: -len },
            { ox: state.px + gap, oy: state.py + gap, dx: -len, dy:    0, ex:   0, ey: -len },
        ];

        ctx.strokeStyle = color;
        ctx.lineWidth   = 1.8;
        ctx.lineCap     = "round";
        ctx.shadowBlur  = 8;
        ctx.shadowColor = color;

        corners.forEach(({ ox, oy, dx, dy, ex, ey }) => {
            ctx.beginPath();
            ctx.moveTo(ox + dx, oy + dy);
            ctx.lineTo(ox, oy);
            ctx.lineTo(ox + ex, oy + ey);
            ctx.stroke();
        });

    } // end if (!learningMode)

    // 학습 모드: 고정 학습 존 애니메이션
    if (state.learningMode) {
        ctx.save();
        const zx = state.currentLearnZone.x;
        const zy = state.currentLearnZone.y;
        const zw = state.currentLearnZone.w;
        const zh = state.currentLearnZone.h;

        // 반투명 외부 어둠
        ctx.fillStyle = "rgba(0,0,0,0.35)";
        ctx.fillRect(0, 0, 640, zy);
        ctx.fillRect(0, zy + zh, 640, 480 - zy - zh);
        ctx.fillRect(0, zy, zx, zh);
        ctx.fillRect(zx + zw, zy, 640 - zx - zw, zh);

        // 애니메이션 점선 테두리
        const dash = (Date.now() / 25) % 20;
        ctx.setLineDash([10, 5]);
        ctx.lineDashOffset = -dash;
        ctx.strokeStyle = "#30d158";
        ctx.lineWidth = 2;
        ctx.shadowBlur = 12;
        ctx.shadowColor = "#30d158";
        ctx.strokeRect(zx, zy, zw, zh);

        // 코너 L자 핸들
        ctx.setLineDash([]);
        ctx.lineWidth = 3.5;
        const hl = 16;
        [
            [zx,      zy,       hl,  0,  0,  hl],
            [zx + zw, zy,      -hl,  0,  0,  hl],
            [zx,      zy + zh,  hl,  0,  0, -hl],
            [zx + zw, zy + zh, -hl,  0,  0, -hl],
        ].forEach(([ox, oy, dx1, dy1, dx2, dy2]) => {
            ctx.beginPath();
            ctx.moveTo(ox + dx1, oy); ctx.lineTo(ox, oy); ctx.lineTo(ox, oy + dy2);
            ctx.stroke();
        });

        // 진행률 텍스트 (박스 상단에 그려서 하단 게이지바와의 중복/겹침 차단)
        ctx.setLineDash([]);
        ctx.shadowBlur = 0;
        ctx.font = "bold 13px -apple-system, sans-serif";
        ctx.fillStyle = "#30d158";
        ctx.textAlign = "center";
        let textY = zy - 10;
        if (textY < 15) {
            textY = zy + 20; // 상단 한계 경계선일 경우 박스 안쪽에 표기
        }
        ctx.fillText(`${state.learningProgress}%`, zx + zw / 2, textY);

        ctx.restore();
    }

    // 자동 모드: 야구공 검출 박스 + 예측 위치 표시
    if (state.controlMode === "auto" && state.ballState && state.ballState.detected) {
        const lost = state.ballState.lost;
        const boxColor = lost ? "rgba(255,159,10,0.7)" : "#30d158";

        ctx.save();
        ctx.strokeStyle = boxColor;
        ctx.shadowBlur = 6;
        ctx.shadowColor = boxColor;
        ctx.lineWidth = 2;

        if (!lost && state.ballState.x !== undefined) {
            // 실제 검출 박스
            ctx.strokeRect(state.ballState.x, state.ballState.y, state.ballState.w, state.ballState.h);
        }

        // 칼만 예측 위치 (작은 십자선)
        const pcx = state.ballState.predicted_cx ?? state.ballState.cx;
        const pcy = state.ballState.predicted_cy ?? state.ballState.cy;
        if (pcx !== undefined) {
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(pcx - 10, pcy); ctx.lineTo(pcx + 10, pcy);
            ctx.moveTo(pcx, pcy - 10); ctx.lineTo(pcx, pcy + 10);
            ctx.stroke();
        }

        ctx.restore();
    }

    ctx.restore();
}

/* ==========================================
   야구공 검출 상태 (자동 모드)
   ========================================== */
setInterval(async () => {
    if (state.controlMode !== "auto") {
        state.ballState = null;
        return;
    }
    try {
        const res = await fetch("/ball");
        state.ballState = await res.json();
        if (state.ballState && state.ballState.detected && state.ballState.cx !== undefined) {
            // 자동 모드: 실제 추적 대상의 위치를 조준점 타겟(tPx, tPy)으로 설정하여,
            // 십자선이 모터 각도가 아닌 실제 물체를 부드럽게 따라가게 함
            state.tPx = state.ballState.cx;
            state.tPy = state.ballState.cy;
        }
    } catch(e) {}
}, 50);

let _isFetchingClick = false;
let _pendingClickX = null;
let _pendingClickY = null;

export function sendClick(x, y) {
    if (_isFetchingClick) {
        _pendingClickX = Math.round(x);
        _pendingClickY = Math.round(y);
        return;
    }
    _isFetchingClick = true;
    _pendingClickX = null;
    _pendingClickY = null;

    fetch(`/click?x=${Math.round(x)}&y=${Math.round(y)}`)
        .catch(()=>{})
        .finally(() => {
            _isFetchingClick = false;
            if (_pendingClickX !== null) {
                setTimeout(() => sendClick(_pendingClickX, _pendingClickY), 5);
            }
        });
}

function syncServer(){
    const now = Date.now();
    if(now - state.lastSync < 50) return;
    state.lastSync = now;
    sendClick(state.tPx, state.tPy);
}


async function syncPos(){
    // 자동 모드일 때는 모터 위치(/pos)로 크로스헤어를 옮기지 않음
    if (state.controlMode === "auto") return;

    // 조이스틱을 사용 중이거나 최근에 사용했다면 아예 서버에 요청조차 하지 않음 (네트워크 트래픽 낭비 방지)
    if (state.joystickTouchId !== null || (Date.now() - state.lastSync < 300)) return;

    try {
        const res  = await fetch("/pos");
        const data = await res.json();

        // 비동기 네트워크 응답을 기다리는 동안 사용자가 조이스틱을 조작하기 시작했을 수 있으므로 재확인
        if (state.controlMode === "auto" || state.joystickTouchId !== null || (Date.now() - state.lastSync < 300)) return;

        state.tPx = data.x;   // 목표값만 갱신 — 렌더링은 loop()에서 lerp
        state.tPy = data.y;
    } catch(e) {}
}

// 자동 모드: 50ms마다 위치 동기화 (추적 반응성)
// 수동 포인터 모드에서만 모터의 물리적 위치 표시를 위해 /pos를 호출하고,
// 조이스틱 및 자동 모드일 때는 네트워크 낭비를 방지하기 위해 호출하지 않습니다.
setInterval(() => {
    if (state.inputMode === "pointer") {
        syncPos();
    }
}, 200);

/* ==========================================
   메인 드로잉 및 조준점 갱신 루프 (delta-time lerp)
   ========================================== */
let _lastFrameTime = 0;

function loop(timestamp){
    const dt = _lastFrameTime === 0 ? 1 : Math.min((timestamp - _lastFrameTime) / (1000 / 60), 3);
    _lastFrameTime = timestamp;

    if (state.controlMode === "manual") {
        // 수동 조이스틱 모드: 십자선은 항상 중앙(320, 240)에 렌더링
        state.px = 320;
        state.py = 240;

        if (state.inputMode === "joystick") {
            const now = Date.now();
            if (now - state.lastSync > 80) {
                const shapeJoy = (v) => {
                    const dead = 0.06;
                    const a = Math.abs(v);
                    if (a <= dead) return 0;
                    const n = (a - dead) / (1 - dead);
                    return Math.sign(v) * Math.pow(n, 1.35);
                };
                const targetJoyX = shapeJoy(state.joyVx);
                const targetJoyY = shapeJoy(state.joyVy);

                // 조준점 반응 속도(maxSpeed: 1~20)에 비례한 가속도 제한 (급발진 방지)
                const maxDelta = 0.04 + (state.maxSpeed * 0.005);

                if (targetJoyX === 0 && targetJoyY === 0) {
                    state.joySendX = 0;
                    state.joySendY = 0;
                } else {
                    if (targetJoyX > state.joySendX + maxDelta) state.joySendX += maxDelta;
                    else if (targetJoyX < state.joySendX - maxDelta) state.joySendX -= maxDelta;
                    else state.joySendX = targetJoyX;

                    if (targetJoyY > state.joySendY + maxDelta) state.joySendY += maxDelta;
                    else if (targetJoyY < state.joySendY - maxDelta) state.joySendY -= maxDelta;
                    else state.joySendY = targetJoyY;
                }

                if (targetJoyX === 0 && targetJoyY === 0 && Math.abs(state.joySendX) < 0.001 && Math.abs(state.joySendY) < 0.001) {
                    state.joySendX = 0;
                    state.joySendY = 0;
                    if (state._joySent) {
                        state.joySeq++;
                        fetch(`/joystick_dir?x=0&y=0&seq=${state.joySeq}`).catch(()=>{});
                        state.lastSync = now;
                        state._joySent = false;
                    }
                    requestAnimationFrame(loop);
                    return;
                }

                if (Math.abs(state.joySendX) > 0.01 || Math.abs(state.joySendY) > 0.01) {
                    const speedMult = state.maxSpeed / 5.0;
                    state.joySeq++;
                    fetch(`/joystick_dir?x=${(state.joySendX * speedMult).toFixed(3)}&y=${(state.joySendY * speedMult).toFixed(3)}&seq=${state.joySeq}`).catch(()=>{});
                    state.lastSync = now;
                    state._joySent = true;
                } else if (state._joySent) {
                    state.joySendX = 0;
                    state.joySendY = 0;
                    state.joySeq++;
                    fetch(`/joystick_dir?x=0&y=0&seq=${state.joySeq}`).catch(()=>{});
                    state.lastSync = now;
                    state._joySent = false;
                }
            }
        }
    } else {
        // 자동 모드: 서버 갱신(80ms)을 lerp로 보간 → 끊김 없음
        state.px += (state.tPx - state.px) * 0.20;
        state.py += (state.tPy - state.py) * 0.20;
    }
    drawCrosshair();
    requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
