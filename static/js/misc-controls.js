import { state } from './state.js';
import { showToast } from './ui-utils.js';
import { setInputModeUI, onInputModeChange } from './input-mode.js';

// ═══════════════════════════════════════════════════════════════
//  퀵 바텀 키 핸들러 (Quick Bottom Bar Buttons)
// ═══════════════════════════════════════════════════════════════

// Quick SET HOME 버튼
const quickSethomeBtn = document.getElementById('quick-sethome-btn');
if (quickSethomeBtn) {
    quickSethomeBtn.addEventListener('click', async () => {
        try {
            await fetch('/esp32_sethome');
            showToast('🏠 원점 설정 완료', 'success');
            // 계기판 가우지도 수동 동기화
            state.klipperPosM1 = 0.0;
            state.klipperPosM2 = 0.0;
        } catch(e) {
            showToast('❌ 연결 없음', 'error');
        }
    });
}

// Quick AI 토글 버튼
const quickAiBtn = document.getElementById('quick-ai-btn');
const quickAiLabel = document.getElementById('quick-ai-label');

function _updateQuickAiBtn(mode) {
    if (!quickAiBtn || !quickAiLabel) return;
    const isAuto = (mode === 'auto');
    quickAiBtn.classList.toggle('ai-active', isAuto);
    quickAiLabel.textContent = isAuto ? 'AI 추적' : '수동';
    quickAiLabel.classList.toggle('ai-active', isAuto);
}

if (quickAiBtn) {
    quickAiBtn.addEventListener('click', () => {
        const newMode = (state.inputMode === 'auto') ? 'joystick' : 'auto';
        setInputModeUI(newMode);
        fetch('/set_input_mode?mode=' + newMode).catch(() => {});
        _updateQuickAiBtn(newMode);
    });
}

/* 원래 script.js는 window.setInputModeUI를 몽키패치해서 모든
   setInputModeUI() 호출 후 퀵 버튼이 동기화되도록 했다. 모듈에서는
   input-mode.js가 제공하는 구독 함수로 같은 효과를 낸다. */
onInputModeChange(_updateQuickAiBtn);

// 조이스틱 비활성 시적 피드백 강화
// AI 모드일 때 조이스틱 브레이스를 더 선명하게 흐릿하게 표시
(function() {
    const joystickBase = document.getElementById('joystick-base');
    if (!joystickBase) return;
    const observer = new MutationObserver(() => {
        const isAuto = joystickBase.style.opacity === '0';
        joystickBase.style.transition = 'opacity 0.3s ease, filter 0.3s ease';
        joystickBase.style.filter = isAuto ? 'blur(2px) brightness(0.4)' : '';
    });
    observer.observe(joystickBase, { attributes: true, attributeFilter: ['style'] });
})();

// 실행 시 퀵 버튼 초기 상태 동기화
_updateQuickAiBtn(state.inputMode || 'joystick');

// ── Fullscreen Toggle ──────────────────────────────────────────────────
const fullscreenBtn = document.getElementById("fullscreen-btn");
if (fullscreenBtn) {
    fullscreenBtn.addEventListener("click", () => {
        if (!document.fullscreenElement) {
            if (document.documentElement.requestFullscreen) {
                document.documentElement.requestFullscreen();
            } else if (document.documentElement.webkitRequestFullscreen) { // Safari
                document.documentElement.webkitRequestFullscreen();
            } else if (document.documentElement.msRequestFullscreen) { // IE11
                document.documentElement.msRequestFullscreen();
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) { // Safari
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) { // IE11
                document.msExitFullscreen();
            }
        }
    });
}
