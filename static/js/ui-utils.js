/* ==========================================
   공용 UI 유틸 — 토스트 알림, 모달 닫기 애니메이션, ESC 키 통합 처리
   ========================================== */

/* ==========================================
   Toast 알림 시스템 (alert() 대체)
   ========================================== */
export function showToast(msg, type = 'info', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-show'));
    setTimeout(() => {
        toast.classList.remove('toast-show');
        toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, duration);
}

/* ==========================================
   모달 열기/닫기 (Apple spring 애니메이션)
   ========================================== */
export function closeModalAnimate(modal) {
    const panel = modal.querySelector('.ios-modal-panel, .more-learn-panel, .gallery-panel, .motor-status-panel, .motor-cfg-panel, .camera-settings-panel');
    modal.classList.add('modal-closing');
    if (panel) {
        panel.style.animation = 'panelOut 0.22s cubic-bezier(0.55,0,1,0.45) forwards';
    }
    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('modal-closing');
        if (panel) panel.style.animation = '';
    }, 220);
}

/* ==========================================
   ESC 키 통합 처리

   원래 script.js는 하나의 keydown 리스너 안에 모든 모달을
   if/else-if 사슬로 나열했다. 모듈로 나누면서 각 모달 모듈이
   자기 자신을 registerEscHandler(check, run)으로 등록하도록
   바꿨다 — 등록 순서(= main.js의 import 순서)가 원래
   if/else-if 순서와 동일하면 동작은 100% 같다.
   ========================================== */
const _escHandlers = [];

export function registerEscHandler(check, run) {
    _escHandlers.push({ check, run });
}

export function initEscKey(fallback) {
    document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape") return;
        for (const h of _escHandlers) {
            if (h.check()) {
                h.run();
                return;
            }
        }
        fallback();
    });
}
