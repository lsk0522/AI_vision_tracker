import { state } from './state.js';
import { showToast, closeModalAnimate, registerEscHandler } from './ui-utils.js';

/* ==========================================
   애플 스타일 설정창 제어
   ========================================== */
const settingsBtn = document.getElementById("settings-btn");
const settingsModal = document.getElementById("settings-modal");
const closeSettings = document.getElementById("close-settings");

export function openSettings(){
    settingsModal.style.display = "flex";
}

export function closeSettingsModal(){
    closeModalAnimate(settingsModal);
}

settingsBtn.addEventListener("click", openSettings);
closeSettings.addEventListener("click", closeSettingsModal);

/* ==========================================
   소프트웨어 리밋 설정 버튼
   ========================================== */
function setLimit(axis, end) {
    fetch(`/set_limit?axis=${axis}&end=${end}`)
        .then(r => r.json())
        .then(d => {
            if (d.ok) {
                showToast(`리밋 저장: ${axis.toUpperCase()} ${end === 'max' ? '상단/우측' : '하단/좌측'} = ${d.value.toFixed(1)}`, 'success');
                updateLimitStatus();
            }
        })
        .catch(() => showToast('리밋 저장 실패', 'error'));
}

function updateLimitStatus() {
    fetch('/get_limits')
        .then(r => r.json())
        .then(d => {
            const m2el = document.getElementById('limit-m2-status');
            const m1el = document.getElementById('limit-m1-status');
            if (!m2el || !m1el) return;

            const fmt = v => v !== null ? v.toFixed(1) : '—';
            const hasM2 = d.m2_min !== null || d.m2_max !== null;
            const hasM1 = d.m1_min !== null || d.m1_max !== null;

            m2el.style.color = hasM2 ? 'rgba(48,209,88,0.9)' : 'rgba(255,255,255,0.35)';
            m2el.textContent = hasM2
                ? `하단: ${fmt(d.m2_min)} ~ 상단: ${fmt(d.m2_max)}  (현재: ${d.m2_now.toFixed(1)})`
                : '리밋 없음';

            m1el.style.color = hasM1 ? 'rgba(48,209,88,0.9)' : 'rgba(255,255,255,0.35)';
            m1el.textContent = hasM1
                ? `좌측: ${fmt(d.m1_min)} ~ 우측: ${fmt(d.m1_max)}  (현재: ${d.m1_now.toFixed(1)})`
                : '리밋 없음';
        });
}

document.getElementById('btn-limit-m2-max')?.addEventListener('click', () => setLimit('m2', 'max'));
document.getElementById('btn-limit-m2-min')?.addEventListener('click', () => setLimit('m2', 'min'));
document.getElementById('btn-limit-m1-max')?.addEventListener('click', () => setLimit('m1', 'max'));
document.getElementById('btn-limit-m1-min')?.addEventListener('click', () => setLimit('m1', 'min'));
document.getElementById('btn-clear-all-limits')?.addEventListener('click', () => {
    fetch('/clear_limit?axis=all&end=all')
        .then(() => { showToast('모든 리밋 제거됨', 'info'); updateLimitStatus(); })
        .catch(() => showToast('리밋 제거 실패', 'error'));
});

// 설정창 열릴 때 리밋 현황 새로고침
settingsBtn.addEventListener("click", updateLimitStatus);

settingsModal.addEventListener("click", function(e){
    if(e.target === settingsModal){
        closeSettingsModal();
    }
});

registerEscHandler(
    () => settingsModal.style.display === "flex",
    () => closeSettingsModal()
);

/* 속도 슬라이더 — debounce to avoid 60 HTTP requests/sec */
const speedSlider = document.getElementById("speed-slider");
const speedValue = document.getElementById("speed-value");

let _speedDebounce = null;
speedSlider.addEventListener("input", function(){
    state.maxSpeed = parseFloat(speedSlider.value);
    speedValue.textContent = speedSlider.value;
    clearTimeout(_speedDebounce);
    _speedDebounce = setTimeout(() => {
        fetch(`/set_speed?speed=${speedSlider.value}`).catch(() => {});
    }, 150);
});

// device-settings.js의 loadSettings()가 서버에서 받아온 초기 speed 값을 반영할 때 사용
export function setSpeedUI(speed) {
    speedSlider.value = speed;
    speedValue.textContent = speed;
}
