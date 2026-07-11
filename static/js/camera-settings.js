import { registerEscHandler } from './ui-utils.js';

/* ==========================================
   카메라 설정 모달
   ========================================== */

const cameraCfgModal    = document.getElementById("camera-cfg-modal");
const closeCameraCfgBtn = document.getElementById("close-camera-cfg");
const btnOpenCameraSettings = document.getElementById("btn-open-camera-settings");
const camIndexSelect    = document.getElementById("cam-index-select");
const camRefreshBtn     = document.getElementById("cam-refresh-btn");
const camConnectBtn     = document.getElementById("cam-connect-btn");
const camConnectMsg     = document.getElementById("cam-connect-msg");
const camStatusBanner   = document.getElementById("cam-status-banner");
const camStatusDot      = document.getElementById("cam-status-dot");
const camStatusLabel    = document.getElementById("cam-status-label");
const camFlipToggle     = document.getElementById("cam-flip-toggle");
const camResSelect      = document.getElementById("cam-res-select");
const camFpsSelect      = document.getElementById("cam-fps-select");

function openCameraSettings() {
    document.getElementById("settings-modal").style.display = "none";
    cameraCfgModal.style.display = "flex";
    loadCameraSettings();
}

function closeCameraSettings() {
    cameraCfgModal.style.display = "none";
}

if (btnOpenCameraSettings) {
    btnOpenCameraSettings.addEventListener("click", openCameraSettings);
}
if (closeCameraCfgBtn) {
    closeCameraCfgBtn.addEventListener("click", closeCameraSettings);
}
if (cameraCfgModal) {
    cameraCfgModal.addEventListener("click", (e) => {
        if (e.target === cameraCfgModal) closeCameraSettings();
    });
}

registerEscHandler(
    () => !!(cameraCfgModal && cameraCfgModal.style.display === "flex"),
    () => closeCameraSettings()
);

// Load current camera info from server
async function loadCameraSettings() {
    try {
        const res  = await fetch("/camera_settings");
        const data = await res.json();

        // Update info card
        const idxEl    = document.getElementById("cam-info-index");
        const resEl    = document.getElementById("cam-info-res");
        const fpsEl    = document.getElementById("cam-info-fps");
        const statEl   = document.getElementById("cam-info-status");

        if (idxEl)  idxEl.textContent  = `Camera ${data.index}`;
        if (resEl)  resEl.textContent  = `${data.width} × ${data.height}`;
        if (fpsEl)  fpsEl.textContent  = `${data.fps} fps`;
        if (statEl) statEl.textContent = data.is_dummy ? "더미 (카메라 없음)" : "정상 연결됨";

        // Status banner
        if (camStatusBanner && camStatusDot && camStatusLabel) {
            if (data.is_dummy) {
                camStatusBanner.className = "ms-banner ms-banner-off";
                camStatusDot.style.background = "#ff3b30";
                camStatusDot.style.boxShadow  = "0 0 5px #ff3b30";
                camStatusLabel.textContent = "카메라가 감지되지 않았습니다";
            } else {
                camStatusBanner.className = "ms-banner ms-banner-on";
                camStatusDot.style.background = "#30d158";
                camStatusDot.style.boxShadow  = "0 0 5px #30d158";
                camStatusLabel.textContent = `Camera ${data.index} 연결됨`;
            }
        }

        // Flip toggle sync
        if (camFlipToggle) {
            camFlipToggle.dataset.active = data.flip ? "true" : "false";
            camFlipToggle.textContent    = data.flip ? "ON" : "OFF";
            camFlipToggle.style.background = data.flip
                ? "rgba(48,209,88,0.25)" : "rgba(255,255,255,0.08)";
            camFlipToggle.style.color = data.flip ? "#30d158" : "";
        }

        // Set select to current index
        if (camIndexSelect) {
            camIndexSelect.value = String(data.index);
        }

        // Populate and set Resolution select
        if (camResSelect && data.res_presets) {
            camResSelect.innerHTML = "";
            data.res_presets.forEach(res => {
                const opt = document.createElement("option");
                const val = `${res[0]},${res[1]}`;
                opt.value = val;
                opt.textContent = `${res[0]} × ${res[1]}`;
                if (res[0] === data.width && res[1] === data.height) {
                    opt.selected = true;
                }
                camResSelect.appendChild(opt);
            });
            // If current resolution is not in presets, add it
            if (!data.res_presets.some(res => res[0] === data.width && res[1] === data.height)) {
                const opt = document.createElement("option");
                const val = `${data.width},${data.height}`;
                opt.value = val;
                opt.textContent = `${data.width} × ${data.height} (Custom)`;
                opt.selected = true;
                camResSelect.appendChild(opt);
            }
        }

        // Populate and set FPS select
        if (camFpsSelect && data.fps_presets) {
            camFpsSelect.innerHTML = "";
            const currentFps = Math.round(data.fps); // round to handle 30.00003
            data.fps_presets.forEach(fps => {
                const opt = document.createElement("option");
                opt.value = String(fps);
                opt.textContent = `${fps} fps`;
                if (fps === currentFps) {
                    opt.selected = true;
                }
                camFpsSelect.appendChild(opt);
            });
            if (!data.fps_presets.includes(currentFps)) {
                const opt = document.createElement("option");
                opt.value = String(currentFps);
                opt.textContent = `${currentFps} fps (Custom)`;
                opt.selected = true;
                camFpsSelect.appendChild(opt);
            }
        }

    } catch(e) {
        console.warn("Failed to load camera settings:", e);
    }
}

// Probe available cameras
if (camRefreshBtn) {
    camRefreshBtn.addEventListener("click", async () => {
        camRefreshBtn.textContent = "탐색 중...";
        camRefreshBtn.disabled = true;
        try {
            const res  = await fetch("/list_cameras");
            const data = await res.json();

            if (!camIndexSelect) return;
            const currentVal = camIndexSelect.value;
            camIndexSelect.innerHTML = "";

            if (data.cameras.length === 0) {
                const opt = document.createElement("option");
                opt.value = "0";
                opt.textContent = "감지된 카메라 없음";
                camIndexSelect.appendChild(opt);
            } else {
                data.cameras.forEach(idx => {
                    const opt = document.createElement("option");
                    opt.value = String(idx);
                    opt.textContent = `Camera ${idx}`;
                    if (String(idx) === currentVal) opt.selected = true;
                    camIndexSelect.appendChild(opt);
                });
            }
            if (camConnectMsg) {
                camConnectMsg.textContent = `${data.cameras.length}개 카메라 감지됨`;
                camConnectMsg.style.color = "#30d158";
            }
        } catch(e) {
            if (camConnectMsg) {
                camConnectMsg.textContent = "탐색 실패";
                camConnectMsg.style.color = "#ff3b30";
            }
        }
        camRefreshBtn.textContent = "🔍 탐색";
        camRefreshBtn.disabled = false;
    });
}

// Switch camera
if (camConnectBtn) {
    camConnectBtn.addEventListener("click", async () => {
        const index = parseInt(camIndexSelect?.value || "0");
        camConnectBtn.textContent = "전환 중...";
        camConnectBtn.disabled = true;
        try {
            const res  = await fetch(`/set_camera?index=${index}`);
            const data = await res.json();
            if (data.ok) {
                if (camConnectMsg) {
                    camConnectMsg.textContent = `✓ Camera ${index} 전환 완료`;
                    camConnectMsg.style.color = "#30d158";
                }
                setTimeout(loadCameraSettings, 800);
            } else {
                if (camConnectMsg) {
                    camConnectMsg.textContent = `❌ Camera ${index} 열기 실패`;
                    camConnectMsg.style.color = "#ff3b30";
                }
            }
        } catch(e) {
            if (camConnectMsg) {
                camConnectMsg.textContent = "서버 오류";
                camConnectMsg.style.color = "#ff3b30";
            }
        }
        camConnectBtn.textContent = "📷 적용";
        camConnectBtn.disabled = false;
        setTimeout(() => { if (camConnectMsg) camConnectMsg.textContent = ""; }, 3000);
    });
}

// Flip toggle
if (camFlipToggle) {
    camFlipToggle.addEventListener("click", async () => {
        const cur  = camFlipToggle.dataset.active === "true";
        const next = !cur;
        camFlipToggle.dataset.active = next ? "true" : "false";
        camFlipToggle.textContent    = next ? "ON" : "OFF";
        camFlipToggle.style.background = next
            ? "rgba(48,209,88,0.25)" : "rgba(255,255,255,0.08)";
        camFlipToggle.style.color = next ? "#30d158" : "";
        await fetch("/flip");
    });
}

// Resolution change
if (camResSelect) {
    camResSelect.addEventListener("change", async (e) => {
        const [w, h] = e.target.value.split(",");
        try {
            await fetch(`/set_camera_resolution?w=${w}&h=${h}`);
            setTimeout(loadCameraSettings, 500); // refresh UI to reflect actual applied values
        } catch(err) {
            console.error("Failed to change resolution:", err);
        }
    });
}

// FPS change
if (camFpsSelect) {
    camFpsSelect.addEventListener("change", async (e) => {
        const fps = e.target.value;
        try {
            await fetch(`/set_camera_fps?fps=${fps}`);
            setTimeout(loadCameraSettings, 500);
        } catch(err) {
            console.error("Failed to change fps:", err);
        }
    });
}
