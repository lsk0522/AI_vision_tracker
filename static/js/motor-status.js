import { state } from './state.js';
import { registerEscHandler } from './ui-utils.js';

/* ==========================================
   모터 상태창 (Motor Status Modal)
   ========================================== */
const motorStatusBtn   = document.getElementById("motor-status-btn");
const motorStatusModal = document.getElementById("motor-status-modal");
const closeMotorStatus = document.getElementById("close-motor-status");

function openMotorStatus()  { motorStatusModal.style.display = "flex"; loadAvailablePorts(); }
function closeMotorStatusModal() { motorStatusModal.style.display = "none"; }

motorStatusBtn.addEventListener("click", openMotorStatus);
closeMotorStatus.addEventListener("click", closeMotorStatusModal);
motorStatusModal.addEventListener("click", (e) => {
    if (e.target === motorStatusModal) closeMotorStatusModal();
});

registerEscHandler(
    () => motorStatusModal.style.display === "flex",
    () => closeMotorStatusModal()
);

// 연결 상태 dot (헤더)
const motorHeaderDot = document.getElementById("motor-status-dot");

// 상태창 내부 요소
const msConnBanner  = document.getElementById("ms-conn-banner");
const msConnLabel   = document.getElementById("ms-conn-label");
const msConnPort    = document.getElementById("ms-conn-port");
const msPortVal     = document.getElementById("ms-port-val");
const msStateDot    = document.getElementById("ms-state-dot");
const msStateText   = document.getElementById("ms-state-text");
const msTargetVal   = document.getElementById("ms-target-val");
const msExVal       = document.getElementById("ms-ex-val");
const msEyVal       = document.getElementById("ms-ey-val");
const msM1Steps     = document.getElementById("ms-m1-steps");
const msM2Steps     = document.getElementById("ms-m2-steps");
const msM1Bar       = document.getElementById("ms-m1-bar");
const msM2Bar       = document.getElementById("ms-m2-bar");

function _stateLabel(d) {
    if (!d.connected)  return ["disconnected", "연결 안됨"];
    if (d.stopped)     return ["stopped",  "정지됨"];
    if (d.timeout)     return ["timeout",  "타임아웃"];
    if (d.moving)      return ["moving",   "이동 중"];
    return ["idle", "대기"];
}

async function pollMotorStatus() {
    try {
        if (state.deviceType === "arduino") {
            // ── Arduino Uno 모드 ────────────────────────
            const res = await fetch("/arduino_motor_status");
            const d   = await res.json();

            motorHeaderDot.className = "motor-dot " +
                (d.connected ? "motor-dot-on" : "motor-dot-off");

            if (d.connected) {
                msConnBanner.className   = "ms-banner ms-banner-on";
                msConnLabel.textContent  = "연결됨";
                msConnPort.textContent   = d.port || "";
            } else {
                msConnBanner.className   = "ms-banner ms-banner-off";
                msConnLabel.textContent  = "연결 안됨";
                msConnPort.textContent   = "";
            }

            msPortVal.textContent   = d.port || "—";
            document.getElementById("ms-comm-val").textContent = "STEP / DIR (Arduino Uno)";
            msStateDot.className    = "ms-state-dot ms-state-idle";
            msStateText.textContent = d.connected ? "대기" : "연결 안됨";
            msTargetVal.textContent = `M1: ${d.pos_m1}  /  M2: ${d.pos_m2} step`;
            msExVal.textContent     = "—";
            msEyVal.textContent     = "—";
            msM1Steps.textContent   = `${d.pos_m1} step`;
            msM2Steps.textContent   = `${d.pos_m2} step`;
            msM1Bar.style.width     = "0%";
            msM2Bar.style.width     = "0%";

        } else {
            // ── ESP32 모드 ──────────────────────────────
            const res  = await fetch("/motor_status");
            const d    = await res.json();
            const [stKey, stLabel] = _stateLabel(d);

            motorHeaderDot.className = "motor-dot " +
                (d.connected ? "motor-dot-on" : "motor-dot-off");

            if (d.connected) {
                msConnBanner.className   = "ms-banner ms-banner-on";
                msConnLabel.textContent  = "연결됨";
                msConnPort.textContent   = d.port || "";
            } else {
                msConnBanner.className   = "ms-banner ms-banner-off";
                msConnLabel.textContent  = "연결 안됨";
                msConnPort.textContent   = "";
            }

            msPortVal.textContent   = d.port || "—";
            document.getElementById("ms-comm-val").textContent = "STEP / DIR (ESP32)";
            msStateDot.className    = "ms-state-dot ms-state-" + stKey;
            msStateText.textContent = stLabel;

            if (d.connected) {
                msTargetVal.textContent = `X ${d.target_x}  /  Y ${d.target_y}`;
                msExVal.textContent = `${d.error_x > 0 ? "+" : ""}${d.error_x} px`;
                msEyVal.textContent = `${d.error_y > 0 ? "+" : ""}${d.error_y} px`;
                msM1Steps.textContent = `${d.steps_m1} step`;
                msM2Steps.textContent = `${d.steps_m2} step`;
                const maxS = parseFloat(document.getElementById("cfg-max-steps")?.value || 25);
                msM1Bar.style.width = Math.min(100, (d.steps_m1 / maxS) * 100) + "%";
                msM2Bar.style.width = Math.min(100, (d.steps_m2 / maxS) * 100) + "%";
                msM1Bar.className = "ms-axis-fill " + (d.moving ? "ms-fill-moving" : "");
                msM2Bar.className = "ms-axis-fill " + (d.moving ? "ms-fill-moving" : "");
            } else {
                msTargetVal.textContent = "—";
                msExVal.textContent     = "—";
                msEyVal.textContent     = "—";
                msM1Steps.textContent   = "— step";
                msM2Steps.textContent   = "— step";
                msM1Bar.style.width     = "0%";
                msM2Bar.style.width     = "0%";
            }
        }
    } catch(e) {}
}

// 모달 열려 있을 때는 200ms, 닫혀 있을 때는 헤더 dot만 1초
let _lastMotorPoll = 0;
setInterval(() => {
    const now = Date.now();
    const interval = (motorStatusModal && motorStatusModal.style.display === "flex") ? 200 : 1000;
    if (now - _lastMotorPoll >= interval) {
        _lastMotorPoll = now;
        pollMotorStatus();
    }
}, 50);

/* ==========================================
   COM 포트 재연결 패널
   ========================================== */
const msPortSelect    = document.getElementById("ms-port-select");
const msReconnectBtn  = document.getElementById("ms-reconnect-btn");
const msReconnectMsg  = document.getElementById("ms-reconnect-msg");

async function loadAvailablePorts() {
    try {
        const res = await fetch("/available_ports");
        const d   = await res.json();

        if (!msPortSelect) return;
        // 기존 옵션 초기화 (자동 감지 유지)
        msPortSelect.innerHTML = '<option value="">자동 감지</option>';
        d.ports.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.device;
            opt.textContent = `${p.device} — ${p.description}`;
            // 현재 연결된 포트 선택 상태로
            if (p.device === d.current_port) opt.selected = true;
            msPortSelect.appendChild(opt);
        });
        if (msReconnectMsg) {
            msReconnectMsg.textContent = d.connected
                ? `✓ 현재 ${d.current_port} 연결됨`
                : "연결되지 않음 — 아래에서 포트를 선택하고 연결하세요";
            msReconnectMsg.style.color = d.connected ? "#30d158" : "rgba(235,235,245,0.5)";
        }
    } catch(e) {}
}

if (msReconnectBtn) {
    msReconnectBtn.addEventListener("click", async () => {
        const port = msPortSelect ? msPortSelect.value : "";
        msReconnectBtn.textContent = "연결 중…";
        msReconnectBtn.disabled = true;

        try {
            const url = port ? `/reconnect_esp32?port=${encodeURIComponent(port)}` : "/reconnect_esp32";
            const res = await fetch(url);
            const d   = await res.json();

            if (d.ok) {
                if (msReconnectMsg) {
                    msReconnectMsg.textContent = `✓ ${d.port} 연결 성공!`;
                    msReconnectMsg.style.color = "#30d158";
                }
                msReconnectBtn.textContent = "✓ 연결됨";
                msReconnectBtn.style.background = "rgba(48,209,88,0.20)";
                msReconnectBtn.style.borderColor = "rgba(48,209,88,0.40)";
                msReconnectBtn.style.color = "#30d158";
                // 포트 목록 새로고침
                setTimeout(loadAvailablePorts, 500);
            } else {
                if (msReconnectMsg) {
                    msReconnectMsg.textContent = "❌ 연결 실패 — 아두이노 IDE 시리얼 모니터를 닫고 다시 시도하세요";
                    msReconnectMsg.style.color = "#ff3b30";
                }
                msReconnectBtn.textContent = "🔌 연결";
                msReconnectBtn.disabled = false;
            }
        } catch(e) {
            if (msReconnectMsg) {
                msReconnectMsg.textContent = "❌ 서버 오류";
                msReconnectMsg.style.color = "#ff3b30";
            }
            msReconnectBtn.textContent = "🔌 연결";
            msReconnectBtn.disabled = false;
        }
        // 버튼 상태 복원 (3초 후)
        setTimeout(() => {
            msReconnectBtn.textContent = "🔌 연결";
            msReconnectBtn.disabled = false;
            msReconnectBtn.style.background = "";
            msReconnectBtn.style.borderColor = "";
            msReconnectBtn.style.color = "#007aff";
        }, 3000);
    });
}
