import { state } from './state.js';
import { registerEscHandler } from './ui-utils.js';
import { showDeviceCfgSection } from './device-settings.js';
import { stopKlipperPoll, loadEsp32MmSettings } from './klipper.js';
import { stopArduinoPosPoll } from './arduino-control.js';

/* ==========================================
   모터 설정창 (Motor Config Modal)
   ========================================== */
const btnOpenMotorCfg  = document.getElementById("btn-open-motor-settings");
const motorCfgModal    = document.getElementById("motor-cfg-modal");
const closeMotorCfg    = document.getElementById("close-motor-cfg");

function openMotorCfg() {
    document.getElementById("settings-modal").style.display = "none";
    showDeviceCfgSection(state.deviceType);
    motorCfgModal.style.display = "flex";
    loadMotorSettings();
    loadEsp32MmSettings();
}
function closeMotorCfgModal() {
    motorCfgModal.style.display = "none";
    stopArduinoPosPoll();
    if (state.esp32Mode === "pos") stopKlipperPoll();
}

btnOpenMotorCfg.addEventListener("click", openMotorCfg);
closeMotorCfg.addEventListener("click", closeMotorCfgModal);
motorCfgModal.addEventListener("click", (e) => {
    if (e.target === motorCfgModal) closeMotorCfgModal();
});

registerEscHandler(
    () => motorCfgModal.style.display === "flex",
    () => closeMotorCfgModal()
);

// 슬라이더 + 값 표시 헬퍼
// ── 모터 설정 (현재 HTML의 숫자 입력창 기반으로 참조) ──
// HTML에는 슬라이더가 아닌 number input + apply button 구조
// cfg-steps-per-px, cfg-max-steps, cfg-pulse-us 슬라이더는 제거됨
// → cfgDeadZone, cfgTimeout 슬라이더만 유지, 나머지는 klipper-param-apply 버튼으로 동작
const cfgDeadZone  = document.getElementById("cfg-dead-zone");
const cfgDeadZoneV = document.getElementById("cfg-dead-zone-val");
const cfgTimeout   = document.getElementById("cfg-timeout");
const cfgTimeoutV  = document.getElementById("cfg-timeout-val");
const cfgM1Btn     = document.getElementById("cfg-m1-invert");
const cfgM2Btn     = document.getElementById("cfg-m2-invert");
const cfgApplyMsg  = document.getElementById("cfg-apply-msg");

if (cfgDeadZone) cfgDeadZone.addEventListener("input", () => {
    if (cfgDeadZoneV) cfgDeadZoneV.textContent = cfgDeadZone.value;
});
if (cfgTimeout) cfgTimeout.addEventListener("input", () => {
    if (cfgTimeoutV) cfgTimeoutV.textContent = cfgTimeout.value;
});

function toggleInvertBtn(btn) {
    const active = btn.dataset.active === "true";
    btn.dataset.active = (!active).toString();
    btn.textContent = active ? "OFF" : "ON";
    btn.classList.toggle("cfg-toggle-active", !active);
}
if (cfgM1Btn) cfgM1Btn.addEventListener("click", () => toggleInvertBtn(cfgM1Btn));
if (cfgM2Btn) cfgM2Btn.addEventListener("click", () => toggleInvertBtn(cfgM2Btn));

// 설정값 불러오기
async function loadMotorSettings() {
    try {
        const res = await fetch("/motor_settings");
        const d   = await res.json();

        // 숫자 입력창에 현재 값 반영
        const stepsPxNum = document.getElementById("cfg-steps-per-px-num");
        if (stepsPxNum) stepsPxNum.value = d.steps_per_px;

        const maxSpeedEl = document.getElementById("cfg-max-speed-hz");
        if (maxSpeedEl) maxSpeedEl.value = d.max_speed_hz ?? 3000;

        const accelEl = document.getElementById("cfg-accel-rate");
        if (accelEl) accelEl.value = d.accel_rate ?? 8.0;

        if (cfgDeadZone) { cfgDeadZone.value = d.dead_zone; }
        if (cfgDeadZoneV) cfgDeadZoneV.textContent = d.dead_zone;

        if (cfgTimeout) { cfgTimeout.value = d.cmd_timeout_ms; }
        if (cfgTimeoutV) cfgTimeoutV.textContent = d.cmd_timeout_ms;

        if (cfgM1Btn) {
            cfgM1Btn.dataset.active = d.m1_invert.toString();
            cfgM1Btn.textContent    = d.m1_invert ? "ON" : "OFF";
            cfgM1Btn.classList.toggle("cfg-toggle-active", d.m1_invert);
        }
        if (cfgM2Btn) {
            cfgM2Btn.dataset.active = d.m2_invert.toString();
            cfgM2Btn.textContent    = d.m2_invert ? "ON" : "OFF";
            cfgM2Btn.classList.toggle("cfg-toggle-active", d.m2_invert);
        }
    } catch(e) { console.warn('[loadMotorSettings]', e); }
}

loadMotorSettings();

// 보드에 적용 (ESP32 / Arduino 공통 핸들러)
const cfgBtnApply = document.getElementById("cfg-btn-apply");
if (cfgBtnApply) cfgBtnApply.addEventListener("click", async () => {
    const params = [
        ["dead_zone",      cfgDeadZone ? cfgDeadZone.value : 8],
        ["cmd_timeout_ms", cfgTimeout  ? cfgTimeout.value  : 600],
        ["m1_invert",      cfgM1Btn ? cfgM1Btn.dataset.active : 'false'],
        ["m2_invert",      cfgM2Btn ? cfgM2Btn.dataset.active : 'false'],
    ];

    try {
        await Promise.all(params.map(([k, v]) =>
            fetch(`/set_motor_config?key=${k}&value=${v}`)
        ));

        if (state.deviceType === "arduino") {
            const res = await fetch("/apply_arduino_cfg");
            if (!res.ok) throw new Error("NOT_CONNECTED");
            if (cfgApplyMsg) cfgApplyMsg.textContent = "✓ Arduino에 적용 완료";
        } else {
            if (cfgApplyMsg) cfgApplyMsg.textContent = "✓ ESP32에 적용 완료";
        }
        if (cfgApplyMsg) cfgApplyMsg.style.color = "#30d158";
    } catch(e) {
        if (cfgApplyMsg) {
            cfgApplyMsg.textContent = (e.message === "NOT_CONNECTED") ? "✗ Arduino 연결 안됨" : "✗ 적용 실패";
            cfgApplyMsg.style.color = "#ff453a";
        }
    }
    setTimeout(() => { if (cfgApplyMsg) cfgApplyMsg.textContent = ""; }, 2500);
});

// 기본값 복원
const cfgBtnReset = document.getElementById("cfg-btn-reset");
if (cfgBtnReset) cfgBtnReset.addEventListener("click", () => {
    if (cfgDeadZone)  { cfgDeadZone.value  = 8;   }
    if (cfgDeadZoneV)   cfgDeadZoneV.textContent  = "8";
    if (cfgTimeout)   { cfgTimeout.value   = 600; }
    if (cfgTimeoutV)    cfgTimeoutV.textContent   = "600";
    if (cfgM1Btn) { cfgM1Btn.dataset.active = "false"; cfgM1Btn.textContent = "OFF"; cfgM1Btn.classList.remove("cfg-toggle-active"); }
    if (cfgM2Btn) { cfgM2Btn.dataset.active = "false"; cfgM2Btn.textContent = "OFF"; cfgM2Btn.classList.remove("cfg-toggle-active"); }
});
