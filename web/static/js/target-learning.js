import { state } from './state.js';
import { showToast, registerEscHandler } from './ui-utils.js';
import { setInputModeUI } from './input-mode.js';
import { closeSettingsModal, openSettings } from './settings-panel.js';

/* ── 물건 선택 버튼 ──────────────────────────────────── */
let hasTarget = false;

const btnSelectTarget  = document.getElementById("btn-select-target");
const targetPreviewRow = document.getElementById("target-preview-row");
const targetThumb      = document.getElementById("target-thumb");
const btnAddLearning   = document.getElementById("btn-add-learning");
const btnClearTarget   = document.getElementById("btn-clear-target");

/* 버그 수정: 현재 index.html에는 이 섹션(물건 선택 / ROI / 다각도 학습)의
   HTML 요소가 전부 빠져 있다(YOLO 자동 추적으로 전환되며 UI가 제거된 것으로
   보임). 그런데 원래 코드는 형제 버튼들(btnAddLearning, btnClearTarget)과
   달리 이 줄만 if 가드 없이 .addEventListener를 호출하고 있었어서, 여기서
   던져진 예외가 스크립트 전체(갤러리·모터상태·카메라설정·펌웨어업로드 등
   이후의 모든 최상위 코드)의 실행을 막고 있었다. 아래 이 섹션의 나머지
   .addEventListener 호출들도 같은 이유로 옵셔널 체이닝(?.)을 붙였다 —
   파일 내 다른 곳(예: btn-limit-* 버튼)에서 이미 쓰이던 것과 같은 패턴. */
btnSelectTarget?.addEventListener("click", () => {
    closeSettingsModal();
    openROISelect();
});

if (btnAddLearning) {
    btnAddLearning.addEventListener("click", async () => {
        closeSettingsModal();
        try {
            await fetch("/add_learning?n=20");
            _startLearningSession();
        } catch (e) {
            console.error("추가 학습 실패", e);
        }
    });
}

if (btnClearTarget) {
    btnClearTarget.addEventListener("click", async () => {
        try {
            await fetch("/clear_target");
            hasTarget = false;
            targetPreviewRow.style.display = "none";
            if (btnSelectTarget) btnSelectTarget.textContent = "물건 새로 학습하기";
            _sessionCount = 0;
            // Fix: use setInputModeUI (correct function name, was setControlModeUI)
            state.controlMode = 'manual';
            setInputModeUI('joystick');
            await fetch("/set_mode?mode=manual");
        } catch (e) {
            console.error("타겟 초기화 실패", e);
            showToast('타겟 초기화 실패', 'error');
        }
    });
}

export function setTargetUI(thumbSrc) {
    hasTarget = true;
    if (thumbSrc) targetThumb.src = thumbSrc;
    targetPreviewRow.style.display = "flex";
    if (btnSelectTarget) btnSelectTarget.textContent = "다시 학습";
}

/* ══════════════════════════════════════════
   ROI 드래그 선택
   ══════════════════════════════════════════ */
const roiOverlay    = document.getElementById("roi-select-overlay");
const roiCanvas     = document.getElementById("roi-canvas");
const roiConfirmBtns = document.getElementById("roi-confirm-btns");
const btnRoiCancel  = document.getElementById("btn-roi-cancel");
const btnRoiConfirm = document.getElementById("btn-roi-confirm");

let _roiDrag = false, _roiSx = 0, _roiSy = 0, _roiRect = null;

function _vidCoords(cx, cy) {
    const r = document.getElementById("video").getBoundingClientRect();
    return { x: Math.round((cx - r.left) * 640 / r.width),
             y: Math.round((cy - r.top)  * 480 / r.height) };
}

function _drawROI(x1, y1, x2, y2) {
    const c = roiCanvas;
    c.width = c.offsetWidth; c.height = c.offsetHeight;
    const ctx = c.getContext("2d");
    const vr = document.getElementById("video").getBoundingClientRect();
    const sx = Math.min(x1,x2) * vr.width/640,  sy = Math.min(y1,y2) * vr.height/480;
    const sw = Math.abs(x2-x1) * vr.width/640,  sh = Math.abs(y2-y1) * vr.height/480;
    ctx.clearRect(0,0,c.width,c.height);
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0,0,c.width,c.height);
    ctx.clearRect(sx,sy,sw,sh);
    ctx.strokeStyle = "#007aff"; ctx.lineWidth = 2.5;
    ctx.shadowColor = "rgba(0,122,255,0.8)"; ctx.shadowBlur = 8;
    ctx.strokeRect(sx,sy,sw,sh);
    // 코너 핸들
    const L=14; ctx.strokeStyle="#fff"; ctx.lineWidth=3; ctx.shadowBlur=0;
    [[sx,sy],[sx+sw,sy],[sx,sy+sh],[sx+sw,sy+sh]].forEach(([cx,cy]) => {
        const dx = cx<sx+sw/2?1:-1, dy = cy<sy+sh/2?1:-1;
        ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+dx*L,cy);
        ctx.moveTo(cx,cy); ctx.lineTo(cx,cy+dy*L); ctx.stroke();
    });
    const wP=Math.abs(x2-x1), hP=Math.abs(y2-y1);
    if(wP>30 && hP>30) {
        const label=`${wP} × ${hP}`;
        ctx.font="bold 12px Inter,sans-serif";
        const tw=ctx.measureText(label).width;
        ctx.fillStyle="rgba(0,0,0,0.6)";
        ctx.fillRect(sx+sw/2-tw/2-6, sy+sh/2-10, tw+12, 20);
        ctx.fillStyle="#fff"; ctx.textAlign="center";
        ctx.fillText(label, sx+sw/2, sy+sh/2+4);
    }
}

function openROISelect() {
    roiOverlay.style.display = "block";
    roiConfirmBtns.style.display = "none";
    _roiRect = null;
    const c = roiCanvas;
    c.width = c.offsetWidth; c.height = c.offsetHeight;
    const ctx = c.getContext("2d");
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0,0,c.width,c.height);
}
function closeROISelect() { roiOverlay.style.display = "none"; _roiRect = null; }

function _roiPointerDown(cx, cy, target) {
    if (target && target.closest("#roi-confirm-btns")) return;
    const p = _vidCoords(cx,cy);
    _roiDrag=true; _roiSx=p.x; _roiSy=p.y;
    roiConfirmBtns.style.display="none";
}
function _roiPointerMove(cx, cy) {
    if(!_roiDrag) return;
    const p = _vidCoords(cx,cy);
    _drawROI(_roiSx,_roiSy,p.x,p.y);
}
function _roiPointerUp(cx, cy) {
    if(!_roiDrag) return; _roiDrag=false;
    const p = _vidCoords(cx,cy);
    const x=Math.min(_roiSx,p.x), y=Math.min(_roiSy,p.y);
    const w=Math.abs(p.x-_roiSx), h=Math.abs(p.y-_roiSy);
    if(w>20 && h>20) { _roiRect={x,y,w,h}; roiConfirmBtns.style.display="flex"; }
}

roiOverlay?.addEventListener("mousedown", e => _roiPointerDown(e.clientX, e.clientY, e.target));
roiOverlay?.addEventListener("mousemove", e => _roiPointerMove(e.clientX, e.clientY));
roiOverlay?.addEventListener("mouseup",   e => _roiPointerUp(e.clientX, e.clientY));
roiOverlay?.addEventListener("touchstart", e => { e.preventDefault(); const t=e.touches[0]; _roiPointerDown(t.clientX,t.clientY,e.target); }, {passive:false});
roiOverlay?.addEventListener("touchmove",  e => { e.preventDefault(); const t=e.touches[0]; _roiPointerMove(t.clientX,t.clientY); }, {passive:false});
roiOverlay?.addEventListener("touchend",   e => { const t=e.changedTouches[0]; _roiPointerUp(t.clientX,t.clientY); });

btnRoiCancel?.addEventListener("click", closeROISelect);
btnRoiConfirm?.addEventListener("click", async () => {
    if(!_roiRect) return;
    const {x,y,w,h} = _roiRect;
    await fetch(`/set_learn_zone?x=${x}&y=${y}&w=${w}&h=${h}`).catch(()=>{});
    state.currentLearnZone = { x, y, w, h };
    closeROISelect();
    _startLearningSession();
});

/* ══════════════════════════════════════════
   지문인식 스타일 반복 학습 모달
   ══════════════════════════════════════════ */
const moreLearnModal    = document.getElementById("more-learn-modal");
const moreLearnThumb    = document.getElementById("more-learn-thumb");
const moreLearnThumbIcon = document.getElementById("more-learn-thumb-icon");
const moreLearnCount    = document.getElementById("more-learn-count");
const moreLearnDots     = document.getElementById("more-learn-dots");
const btnMoreLearn      = document.getElementById("btn-more-learn");
const btnFinishLearn    = document.getElementById("btn-finish-learn");

let _sessionCount = 0;

function _renderDots(n) {
    if(!moreLearnDots) return;
    moreLearnDots.innerHTML = "";
    for(let i=0;i<5;i++) {
        const d = document.createElement("div");
        d.className = "ml-dot" + (i<n ? " ml-dot-on" : "");
        moreLearnDots.appendChild(d);
    }
}

function _showMoreLearnModal(thumbnail) {
    _sessionCount++;
    if(thumbnail) { moreLearnThumb.src=thumbnail; moreLearnThumb.style.display="block"; moreLearnThumbIcon.style.display="none"; }
    else          { moreLearnThumb.style.display="none"; moreLearnThumbIcon.style.display="block"; }
    moreLearnCount.textContent = `${_sessionCount}회 학습 완료`;
    _renderDots(_sessionCount);

    // 지문인식 스타일 다각도 모션 가이드
    const descEl = document.querySelector(".more-learn-desc");
    if (descEl) {
        if (_sessionCount === 1) {
            descEl.innerHTML = "1단계 스캔 완료!<br>이번에는 물체를 <b>옆으로 살짝 돌려 측면</b>을 학습해 보세요.";
        } else if (_sessionCount === 2) {
            descEl.innerHTML = "2단계 스캔 완료!<br>이번에는 물체를 <b>조금 더 멀리서(크기 변화)</b> 학습해 보세요.";
        } else if (_sessionCount === 3) {
            descEl.innerHTML = "3단계 스캔 완료!<br>이번에는 물체를 <b>위/아래로 비스듬히 기울여서</b> 학습해 보세요.";
        } else if (_sessionCount === 4) {
            descEl.innerHTML = "4단계 스캔 완료!<br>마지막으로 <b>뒷면 또는 불규칙한 각도</b>를 한번 더 학습하세요.";
        } else {
            descEl.innerHTML = "5단계 스캔 완료! 다각도 학습이 모두 끝났습니다.<br>완료 버튼을 누르면 고정밀 자동 추적이 가능합니다.";
        }
    }
    moreLearnModal.style.display = "flex";
}

btnMoreLearn && btnMoreLearn.addEventListener("click", () => {
    moreLearnModal.style.display = "none";
    fetch("/add_learning?n=20").catch(()=>{});
    _startLearnPoll();
});
btnFinishLearn && btnFinishLearn.addEventListener("click", () => {
    moreLearnModal.style.display = "none";
    _sessionCount = 0;
});

/* ══════════════════════════════════════════
   학습 모드 오버레이
   ══════════════════════════════════════════ */
const learnOverlay   = document.getElementById("learn-overlay");
const btnCancelLearn = document.getElementById("btn-cancel-learn");
const learnFill      = document.getElementById("learn-progress-fill");
const learnPct       = document.getElementById("learn-progress-pct");
const learnBannerTxt = document.getElementById("learn-banner-text");

let _learnPollTimer = null;

function _startLearningSession() {
    fetch("/start_learning").catch(()=>{});
    _startLearnPoll();
}

function _startLearnPoll() {
    state.learningMode = true;
    state.learningProgress = 0;
    learnFill.style.width = "0%";
    learnPct.textContent  = "0%";
    learnBannerTxt.textContent = "AI 트래커 대상을 지정했습니다!";
    learnBannerTxt.style.color = ""; // 색상 초기화
    learnOverlay.classList.add("active");
    document.getElementById("joystick-base").style.pointerEvents = "none";
    document.body.classList.add("is-learning");

    // Force live indicator visible and update to LEARNING state
    const liveIndicator     = document.getElementById("live-indicator");
    const trackingIndicator = document.getElementById("tracking-indicator");
    if (liveIndicator)     liveIndicator.style.display    = "flex";
    if (trackingIndicator) trackingIndicator.style.display = "none";
    const statusLabel = document.querySelector(".status-label");
    const statusDot   = document.querySelector(".status-dot");
    if (statusLabel && statusDot) {
        statusLabel.textContent    = "LEARNING";
        statusLabel.style.color    = "#30d158";
        statusDot.style.background = "#30d158";
        statusDot.style.boxShadow  = "0 0 7px #30d158";
    }

    if(_learnPollTimer) clearInterval(_learnPollTimer);
    _learnPollTimer = setInterval(_pollLearning, 120);
}

function exitLearningMode() {
    state.learningMode = false;
    learnOverlay.classList.remove("active");
    document.getElementById("joystick-base").style.pointerEvents = "";
    document.body.classList.remove("is-learning");

    // Restore header indicators to current input mode
    const statusLabel = document.querySelector(".status-label");
    const statusDot   = document.querySelector(".status-dot");
    if (statusLabel && statusDot) {
        statusLabel.textContent    = "LIVE";
        statusLabel.style.color    = "";
        statusDot.style.background = "";
        statusDot.style.boxShadow  = "";
    }
    // Re-apply the correct header indicator for the current mode
    if (typeof setInputModeUI === "function") setInputModeUI(state.inputMode);

    if(_learnPollTimer) { clearInterval(_learnPollTimer); _learnPollTimer = null; }
}



async function _pollLearning() {
    try {
        const res  = await fetch("/learning_progress");
        const data = await res.json();
        state.learningProgress = data.progress;
        /* % 중복 방지: fill 너비만, 숫자는 span 하나만 */
        learnFill.style.width = data.progress + "%";
        learnPct.textContent  = data.progress + "%";
        if(data.done) {
            clearInterval(_learnPollTimer); _learnPollTimer = null;
            learnFill.style.width = "100%";
            learnPct.textContent  = "100%";

            if (data.failed) {
                learnBannerTxt.textContent = "✗ 학습 실패: 특징점 부족";
                learnBannerTxt.style.color = "#ff453a";
                setTimeout(() => {
                    exitLearningMode();
                    // Replace alert() with styled toast
                    showToast('인식된 특징점이 부족합니다. 밝은 곳에서 다시 시도해 주세요.', 'error', 5000);
                }, 1000);
            } else {
                learnBannerTxt.textContent = "✓ 추적 대상을 고정했습니다!";
                learnBannerTxt.style.color = "#30d158";
                setTimeout(() => {
                    exitLearningMode();
                    setTargetUI(data.thumbnail);
                    /* 연속 3회전 학습이므로 추가 모달 표시 안 함 */
                }, 800);
            }
        } else {
            // 진행도에 따라 안내 텍스트 자동 변경 (3회전 안내)
            if (data.progress < 33) {
                learnBannerTxt.textContent = "제자리에서 360도 천천히 돌려주세요 (1/3 회전)";
            } else if (data.progress < 66) {
                learnBannerTxt.textContent = "살짝 기울여서 한 번 더 돌려주세요 (2/3 회전)";
            } else {
                learnBannerTxt.textContent = "마지막으로 반대쪽 측면을 돌려주세요 (3/3 회전)";
            }
        }
    } catch(e) {}
}

btnCancelLearn?.addEventListener("click", () => {
    exitLearningMode();
    moreLearnModal.style.display = "none";
    _sessionCount = 0;
    fetch("/clear_target");
});

/* ── ESC 키 처리 (원래 script.js의 if/else-if 순서와 동일하게 등록) ── */
registerEscHandler(
    () => state.learningMode,
    () => {
        exitLearningMode();
        moreLearnModal.style.display = "none";
        _sessionCount = 0;
        fetch("/clear_target");
    }
);
registerEscHandler(
    () => roiOverlay && roiOverlay.style.display === "block",
    () => { closeROISelect(); openSettings(); }
);
registerEscHandler(
    () => moreLearnModal && moreLearnModal.style.display === "flex",
    () => {
        moreLearnModal.style.display = "none";
        _sessionCount = 0;
        openSettings();
    }
);
