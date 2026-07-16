import { state } from './state.js';
import { setInputModeUI } from './input-mode.js';
import { setTargetUI } from './target-learning.js';
import { setSpeedUI } from './settings-panel.js';

/* ==========================================
   설정 데이터 로드 및 초기화
   ========================================== */
/* ── 기기 타입 (ESP32 / Arduino) ────────────────────────── */
const deviceSegmentBtns = document.querySelectorAll("#device-type-segment .segment-btn");
const deviceSlider      = document.querySelector("#device-type-segment .segment-slider");
const motorLinkLabel    = document.getElementById("motor-link-label");
const esp32CfgSection   = document.getElementById("esp32-cfg-section");
const arduinoCfgSection = document.getElementById("arduino-cfg-section");

export function setDeviceTypeUI(type) {
    state.deviceType = type;
    deviceSegmentBtns.forEach(btn => {
        btn.classList.toggle("active", btn.dataset.value === type);
    });
    deviceSlider.style.transform = (type === "esp32") ? "translateX(0)" : "translateX(100%)";
    motorLinkLabel.textContent = "모터 파라미터 설정";
    document.getElementById("motor-cfg-title").textContent = "모터 파라미터 설정";
    const applyBtn = document.getElementById("cfg-btn-apply");
    if (applyBtn) applyBtn.textContent = (type === "esp32") ? "ESP32에 적용" : "Arduino에 적용";
}

deviceSegmentBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        const val = btn.dataset.value;
        setDeviceTypeUI(val);
        fetch(`/set_device_type?type=${val}`);
    });
});

export function showDeviceCfgSection(_type) {
    esp32CfgSection.style.display   = "";      // ESP32·Arduino 공통 UI
    arduinoCfgSection.style.display = "none";  // 사용 안 함
}

async function loadSettings(){
    try {
        const res  = await fetch("/settings");
        const data = await res.json();

        state.maxSpeed = data.speed;
        setSpeedUI(data.speed);

        // Apply 3-way input mode (pointer/joystick/auto)
        const savedMode = data.input_mode || "joystick";
        setInputModeUI(savedMode);

        setDeviceTypeUI(data.device_type || "esp32");

        // Restore tracking thumbnail if target was learned
        if (data.tracking_mode === "custom") {
            setTargetUI("/target_thumbnail?t=" + Date.now());
        }

        // Restore learned ROI zone coordinates
        const lzRes = await fetch("/get_learn_zone");
        const lzData = await lzRes.json();
        state.currentLearnZone = { x: lzData.x, y: lzData.y, w: lzData.w, h: lzData.h };
    } catch(e) {
        console.log("Failed to load settings:", e);
    }
}


loadSettings();
