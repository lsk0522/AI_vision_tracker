import { state } from './state.js';

/* ==========================================
   Klipper 스타일 ESP32 mm 위치 제어
   ========================================== */

// ── 상태 변수 ──────────────────────────────────────────────────────────────────────
let klipperAxis   = "M1";        // 현재 선택된 축

// ── 요소 참조 ──────────────────────────────────────────────────────────────────────
const esp32ModeSegment = document.getElementById("esp32-mode-segment");
const esp32TrackTab    = document.getElementById("esp32-track-tab");
const esp32PosTab      = document.getElementById("esp32-pos-tab");
const degAxisSegment    = document.getElementById("deg-axis-segment");
const kpAbsInput       = document.getElementById("kp-abs-input");
const kpAbsGo          = document.getElementById("kp-abs-go");
const kpSethomeBtn     = document.getElementById("kp-sethome-btn");
const kpEstopBtn       = document.getElementById("kp-estop-btn");
const kpApplyMsg       = document.getElementById("kp-apply-msg");

// ── 탭 전환 (추적 / 위치 제어) ────────────────────────────────────────────────────
if (esp32ModeSegment) {
    esp32ModeSegment.addEventListener("click", e => {
        const btn = e.target.closest(".segment-btn");
        if (!btn) return;

        // 슬라이더 이동
        const btns  = [...esp32ModeSegment.querySelectorAll(".segment-btn")];
        const idx   = btns.indexOf(btn);
        const slider = esp32ModeSegment.querySelector(".segment-slider");
        btns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        slider.style.transform = `translateX(${idx * 100}%)`;

        const mode = btn.dataset.value;
        state.esp32Mode = mode;

        if (mode === "track") {
            if (esp32TrackTab) esp32TrackTab.style.display = "";
            if (esp32PosTab)   esp32PosTab.style.display = "none";
            stopKlipperPoll();
            fetch("/esp32_set_mode?mode=track");
        } else {
            if (esp32TrackTab) esp32TrackTab.style.display = "none";
            if (esp32PosTab)   esp32PosTab.style.display = "";
            fetch("/esp32_set_mode?mode=pos");
            startKlipperPoll();
        }
    });
}

// ── 축 선택 세그먼트 ─────────────────────────────────────────────────────────────
if (degAxisSegment) {
    degAxisSegment.addEventListener("click", e => {
        const btn = e.target.closest(".segment-btn");
        if (!btn) return;
        const btns  = [...degAxisSegment.querySelectorAll(".segment-btn")];
        const idx   = btns.indexOf(btn);
        const slider = degAxisSegment.querySelector(".segment-slider");
        btns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        slider.style.transform = `translateX(${idx * 100}%)`;
        klipperAxis = btn.dataset.value;
    });
}

// ── Jog 버튼 (상대 이동) ─────────────────────────────────────────────────────────
document.querySelectorAll(".klipper-jog-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        const delta = parseFloat(btn.dataset.delta);
        if (isNaN(delta)) return;

        // 상대 이동(delta) 요청을 전송하여 백엔드 큐에서 순차 처리되도록 함
        await klipperMove(klipperAxis, null, delta);

        // UI 입력창에 예상 도달 위치 업데이트
        let curPos = (klipperAxis === "M1") ? state.klipperPosM1 : ((klipperAxis === "M2") ? state.klipperPosM2 : state.klipperPosM1);
        const targetMM = curPos + delta;
        if (kpAbsInput) kpAbsInput.value = targetMM.toFixed(2);
    });
});

// ── 절대 위치 이동 버튼 ───────────────────────────────────────────────────────────
if (kpAbsGo) {
    kpAbsGo.addEventListener("click", async () => {
        const mm = parseFloat(kpAbsInput?.value || 0);
        if (isNaN(mm)) return;
        await klipperMove(klipperAxis, mm);
    });
}

if (kpAbsInput) {
    kpAbsInput.addEventListener("keydown", async e => {
        if (e.key === "Enter") {
            e.preventDefault();
            const mm = parseFloat(kpAbsInput.value || 0);
            if (!isNaN(mm)) await klipperMove(klipperAxis, mm);
        }
    });
}

// ── SET HOME ─────────────────────────────────────────────────────────────────────
if (kpSethomeBtn) {
    kpSethomeBtn.addEventListener("click", async () => {
        try {
            await fetch("/esp32_sethome");
            state.klipperPosM1 = 0.0;
            state.klipperPosM2 = 0.0;
            updateKlipperGauge(0, 0, 0, 0);
            if (kpAbsInput) kpAbsInput.value = "0";
            showKlipperMsg("✓ 원점 설정 완료", "#30d158");
        } catch(e) {
            showKlipperMsg("❌ 연결 없음", "#ff3b30");
        }
    });
}

// ── E-STOP ────────────────────────────────────────────────────────────────────────
if (kpEstopBtn) {
    kpEstopBtn.addEventListener("click", async () => {
        try {
            await fetch("/esp32_stop");
            showKlipperMsg("⏹ 비상 정지 완료", "#ff9f0a");
        } catch(e) {}
    });
}

// ── 파라미터 카드 '적용' 버튼 ─────────────────────────────────────────────────────
document.querySelectorAll(".klipper-param-apply").forEach(btn => {
    btn.addEventListener("click", async () => {
        const key   = btn.dataset.key;
        const srcId = btn.dataset.src;
        const input = document.getElementById(srcId);
        if (!input) return;

        const value = input.value;
        try {
            const res = await fetch(`/set_esp32_deg_config?key=${key}&value=${encodeURIComponent(value)}`);
            if (res.ok) {
                // 부모 카드에 초록 플래시 효과
                const card = btn.closest(".klipper-param-card");
                if (card) {
                    card.classList.remove("flash-ok");
                    void card.offsetWidth; // reflow
                    card.classList.add("flash-ok");
                }
                showKlipperMsg(`✓ ${key} = ${value} 적용됨`, "#30d158");
            } else {
                showKlipperMsg("❌ 적용 실패", "#ff3b30");
            }
        } catch(e) {
            showKlipperMsg("❌ 서버 연결 오류", "#ff3b30");
        }
    });
});

// 방향 반전 토글 (위치 제어 탭)
const kpM1Inv = document.getElementById("kp-m1-invert");
const kpM2Inv = document.getElementById("kp-m2-invert");

function bindKlipperInvert(btn, key) {
    if (!btn) return;
    btn.addEventListener("click", async () => {
        const cur = btn.dataset.active === "true";
        const next = !cur;
        btn.dataset.active = next ? "true" : "false";
        btn.textContent    = next ? "ON" : "OFF";
        btn.style.background = next
            ? "rgba(48,209,88,0.25)"
            : "rgba(255,255,255,0.08)";
        btn.style.color = next ? "#30d158" : "";
        await fetch(`/set_esp32_deg_config?key=${key}&value=${next}`);
    });
}

bindKlipperInvert(kpM1Inv, "m1_invert");
bindKlipperInvert(kpM2Inv, "m2_invert");

// ── 핵심 이동 함수 ────────────────────────────────────────────────────────────────
async function klipperMove(axis, mm, delta = null) {
    try {
        let url;
        if (delta !== null) {
            url = `/esp32_move?target=${encodeURIComponent(axis)}&delta=${delta.toFixed(3)}`;
        } else {
            url = `/esp32_move?target=${encodeURIComponent(axis)}&mm=${mm.toFixed(3)}`;
        }
        const res = await fetch(url);
        if (!res.ok) {
            showKlipperMsg("❌ 연결 없음 (ESP32)", "#ff3b30");
        }
    } catch(e) {
        showKlipperMsg("❌ 서버 오류", "#ff3b30");
    }
}

// ── 실시간 위치 폴링 ──────────────────────────────────────────────────────────────
let klipperPollTimer = null;     // 위치 폴링 타이머

export function startKlipperPoll() {
    if (klipperPollTimer) return;
    klipperPollTimer = setInterval(pollKlipperPos, 200);
}

export function stopKlipperPoll() {
    if (klipperPollTimer) {
        clearInterval(klipperPollTimer);
        klipperPollTimer = null;
    }
}

async function pollKlipperPos() {
    try {
        const res = await fetch("/esp32_pos_status");
        if (!res.ok) return;
        const d = await res.json();
        state.klipperPosM1 = d.pos_m1_deg ?? 0;
        state.klipperPosM2 = d.pos_m2_deg ?? 0;
        updateKlipperGauge(state.klipperPosM1, state.klipperPosM2, d.speed_m1 ?? 0, d.speed_m2 ?? 0);
    } catch(e) {}
}

// ── 위치 게이지 업데이트 ──────────────────────────────────────────────────────────
const POS_RANGE = 200; // ±200mm 범위로 게이지 표시

function updateKlipperGauge(m1mm, m2mm, spd1, spd2) {
    const m1Val  = document.getElementById("kp-m1-val");
    const m2Val  = document.getElementById("kp-m2-val");
    const m1Fill = document.getElementById("kp-m1-fill");
    const m2Fill = document.getElementById("kp-m2-fill");
    const m1Spd  = document.getElementById("kp-m1-spd");
    const m2Spd  = document.getElementById("kp-m2-spd");

    if (m1Val) m1Val.textContent = m1mm.toFixed(2) + " mm";
    if (m2Val) m2Val.textContent = m2mm.toFixed(2) + " mm";

    if (m1Fill) {
        // 0mm = 50%, +POS_RANGE = 100%, -POS_RANGE = 0%
        const pct1 = Math.min(100, Math.max(0, 50 + (m1mm / POS_RANGE) * 50));
        m1Fill.style.width = pct1 + "%";
        m1Fill.classList.toggle("is-moving", spd1 > 10);
    }
    if (m2Fill) {
        const pct2 = Math.min(100, Math.max(0, 50 + (m2mm / POS_RANGE) * 50));
        m2Fill.style.width = pct2 + "%";
        m2Fill.classList.toggle("is-moving", spd2 > 10);
    }

    if (m1Spd) m1Spd.textContent = Math.round(spd1) + " Hz";
    if (m2Spd) m2Spd.textContent = Math.round(spd2) + " Hz";
}

// ── 메시지 표시 ──────────────────────────────────────────────────────────────────
function showKlipperMsg(text, color = "#fff") {
    if (!kpApplyMsg) return;
    kpApplyMsg.textContent  = text;
    kpApplyMsg.style.color  = color;
    kpApplyMsg.style.opacity = "1";
    setTimeout(() => { kpApplyMsg.style.opacity = "0"; }, 2500);
}

// ── 초기 파라미터 로드 ────────────────────────────────────────────────────────────
export async function loadEsp32MmSettings() {
    try {
        const res = await fetch("/esp32_deg_settings");
        if (!res.ok) return;
        const d = await res.json();

        // ── 위치 제어(mm) 탭 파라미터 ──
        const spm1El   = document.getElementById("kp-spm1");
        const spm2El   = document.getElementById("kp-spm2");
        const maxSpdEl = document.getElementById("kp-maxspd");
        const accelEl  = document.getElementById("kp-accel");
        const pulsEl   = document.getElementById("kp-pulseus");

        if (spm1El)   spm1El.value   = d.steps_per_deg_m1;
        if (spm2El)   spm2El.value   = d.steps_per_deg_m2;
        if (maxSpdEl) maxSpdEl.value = d.max_speed_hz;
        if (accelEl)  accelEl.value  = d.accel_rate;
        if (pulsEl)   pulsEl.value   = d.pulse_us;

        // ── 카메라 추적 탭 파라미터 (새로 추가된 필드) ──
        const spxEl      = document.getElementById("cfg-steps-per-px-num");
        const trackSpdEl = document.getElementById("cfg-max-speed-hz");
        const trackAccEl = document.getElementById("cfg-accel-rate");

        if (spxEl)      spxEl.value      = d.steps_per_px  ?? d.steps_per_px  ?? 3.5;
        if (trackSpdEl) trackSpdEl.value = d.max_speed_hz;
        if (trackAccEl) trackAccEl.value = d.accel_rate;

        // 방향 반전 상태 반영
        [kpM1Inv, kpM2Inv].forEach((btn, i) => {
            if (!btn) return;
            const active = i === 0 ? d.m1_invert : d.m2_invert;
            btn.dataset.active = active ? "true" : "false";
            btn.textContent    = active ? "ON" : "OFF";
            btn.style.background = active ? "rgba(48,209,88,0.25)" : "";
            btn.style.color      = active ? "#30d158" : "";
        });

        // 현재 ESP32 모드 반영
        if (d.control_mode === "pos") {
            // 탭을 위치 제어로 전환
            const btns = [...(esp32ModeSegment?.querySelectorAll(".segment-btn") || [])];
            btns.forEach(b => b.classList.remove("active"));
            const posBtn = btns.find(b => b.dataset.value === "pos");
            if (posBtn) posBtn.classList.add("active");
            const slider = esp32ModeSegment?.querySelector(".segment-slider");
            if (slider) slider.style.transform = "translateX(100%)";
            if (esp32TrackTab) esp32TrackTab.style.display = "none";
            if (esp32PosTab)   esp32PosTab.style.display = "";
            state.esp32Mode = "pos";
            startKlipperPoll();
        }
    } catch(e) {}
}
