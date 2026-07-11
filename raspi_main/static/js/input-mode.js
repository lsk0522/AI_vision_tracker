import { state } from './state.js';

/* ── Input Mode: "pointer" | "joystick" | "auto" ──────────────── */
const controlSegmentBtns = document.querySelectorAll("#control-mode-segment .segment-btn");
const segmentSlider      = document.querySelector("#control-mode-segment .segment-slider");
const hiddenSelect       = document.getElementById("control-mode");

// Header indicator elements
const liveIndicator     = document.getElementById("live-indicator");
const trackingIndicator = document.getElementById("tracking-indicator");
const trackingDot       = document.getElementById("tracking-dot");
const trackingLabel     = document.getElementById("tracking-label");

// Click handler for 3-way segment buttons
controlSegmentBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
        const val = btn.dataset.value;
        setInputModeUI(val);
        fetch(`/set_input_mode?mode=${val}`);
    });
});

/* 원래 script.js는 misc-controls의 퀵 AI 버튼이 setInputModeUI를
   window.setInputModeUI = function(...) {...} 로 몽키패치해서, 이후
   모든(이 파일 안에서든 다른 곳에서든) setInputModeUI(...) 호출이
   퀵 버튼 동기화까지 함께 실행되도록 만들어져 있었다(클래식 스크립트의
   전역 함수 선언 = window 프로퍼티라서 가능했던 트릭). ES 모듈에는 이런
   암묵적 전역 재바인딩이 없으므로, 같은 효과를 구독자 목록으로 재현한다:
   misc-controls.js가 onInputModeChange(cb)로 자신을 등록해둔다. */
const _listeners = [];
export function onInputModeChange(fn) {
    _listeners.push(fn);
}

export function setInputModeUI(mode) {
    state.inputMode = mode;
    if (hiddenSelect) hiddenSelect.value = mode;

    // Update active button and slider position
    const btns = [...controlSegmentBtns];
    btns.forEach(b => b.classList.toggle("active", b.dataset.value === mode));
    const idx = btns.findIndex(b => b.dataset.value === mode);
    segmentSlider.style.transform = `translateX(${idx * 100}%)`;

    // Sync legacy controlMode for crosshair color etc.
    state.controlMode = (mode === "auto") ? "auto" : "manual";

    // Update header indicators
    if (liveIndicator)     liveIndicator.style.display    = (mode === "joystick") ? "flex" : "none";
    if (trackingIndicator) trackingIndicator.style.display = (mode === "auto")    ? "flex" : "none";

    // Toggle joystick visibility
    const joystickBase = document.getElementById("joystick-base");
    if (joystickBase) {
        joystickBase.style.opacity      = (mode === "joystick") ? "1" : "0";
        joystickBase.style.pointerEvents = (mode === "joystick") ? "" : "none";
    }

    // Reset joystick when leaving joystick mode
    if (mode !== "joystick") {
        state.joyVx = 0; state.joyVy = 0;
    }

    // Start or stop AI tracking poll
    if (mode === "auto") {
        startTrackingPoll();
    } else {
        stopTrackingPoll();
        // Reset tracking indicator on non-auto modes
        updateTrackingUI(false);
    }

    _listeners.forEach(fn => fn(mode));
}

/* ── AI Tracking Status Polling ──────────────────────────────── */
let trackingPollTimer = null;

function startTrackingPoll() {
    if (trackingPollTimer) return;
    trackingPollTimer = setInterval(pollTrackingStatus, 200);
}

function stopTrackingPoll() {
    if (trackingPollTimer) {
        clearInterval(trackingPollTimer);
        trackingPollTimer = null;
    }
}

async function pollTrackingStatus() {
    if (state.inputMode !== "auto") return;
    try {
        const res  = await fetch("/tracking_status");
        const data = await res.json();
        updateTrackingUI(data.locked);
    } catch(e) {}
}

function updateTrackingUI(locked) {
    if (!trackingDot || !trackingLabel) return;
    if (locked) {
        trackingDot.className   = "tracking-dot tracking-locked";
        trackingLabel.textContent = "LOCKED";
        trackingLabel.style.color = "#30d158";
    } else {
        trackingDot.className   = "tracking-dot tracking-searching";
        trackingLabel.textContent = "SEARCHING";
        trackingLabel.style.color = "#ff9f0a";
    }
}
