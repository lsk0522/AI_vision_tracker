/* ==========================================
   Arduino Uno 스텝모터 (DM542) 제어창
   ========================================== */
const ardEstopBtn  = document.getElementById("ard-estop-btn");
const ardStepsRev  = document.getElementById("ard-steps-rev");
const ardStepsRevV = document.getElementById("ard-steps-rev-val");
const ardM1Deg     = document.getElementById("ard-m1-deg");
const ardM1DegV    = document.getElementById("ard-m1-deg-val");
const ardM1Spd     = document.getElementById("ard-m1-spd");
const ardM1SpdV    = document.getElementById("ard-m1-spd-val");
const ardM1Acc     = document.getElementById("ard-m1-acc");
const ardM1AccV    = document.getElementById("ard-m1-acc-val");
const ardM1RunBtn  = document.getElementById("ard-m1-run-btn");
const ardM1HomeBtn = document.getElementById("ard-m1-home-btn");
const ardM2Deg     = document.getElementById("ard-m2-deg");
const ardM2DegV    = document.getElementById("ard-m2-deg-val");
const ardM2Spd     = document.getElementById("ard-m2-spd");
const ardM2SpdV    = document.getElementById("ard-m2-spd-val");
const ardM2Acc     = document.getElementById("ard-m2-acc");
const ardM2AccV    = document.getElementById("ard-m2-acc-val");
const ardM2RunBtn  = document.getElementById("ard-m2-run-btn");
const ardM2HomeBtn = document.getElementById("ard-m2-home-btn");
const ardPosM1     = document.getElementById("ard-pos-m1");
const ardPosM2     = document.getElementById("ard-pos-m2");
const ardSaveBtn   = document.getElementById("ard-save-btn");
const ardApplyMsg  = document.getElementById("ard-apply-msg");

ardStepsRev.addEventListener("input", () => { ardStepsRevV.textContent = ardStepsRev.value; });
ardM1Deg.addEventListener("input",    () => { ardM1DegV.textContent = ardM1Deg.value + "°"; });
ardM1Spd.addEventListener("input",    () => { ardM1SpdV.textContent = ardM1Spd.value; });
ardM1Acc.addEventListener("input",    () => { ardM1AccV.textContent = ardM1Acc.value; });
ardM2Deg.addEventListener("input",    () => { ardM2DegV.textContent = ardM2Deg.value + "°"; });
ardM2Spd.addEventListener("input",    () => { ardM2SpdV.textContent = ardM2Spd.value; });
ardM2Acc.addEventListener("input",    () => { ardM2AccV.textContent = ardM2Acc.value; });

function _ardMsg(text, color, ms = 2500) {
    ardApplyMsg.textContent = text;
    ardApplyMsg.style.color = color;
    setTimeout(() => { ardApplyMsg.textContent = ""; }, ms);
}

/* 비상 정지 */
ardEstopBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/arduino_estop");
        if (res.ok) _ardMsg("⏹ 비상 정지 전송 완료", "#ff453a");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M1 RUN — Apply 시 단 1회 JSON 전송 */
ardM1RunBtn.addEventListener("click", async () => {
    try {
        const p = new URLSearchParams({
            id: 1, deg: ardM1Deg.value,
            spd: ardM1Spd.value, acc: ardM1Acc.value,
        });
        const res = await fetch(`/arduino_run?${p}`);
        if (res.ok) _ardMsg("✓ M1 RUN 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M1 HOME */
ardM1HomeBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/arduino_home?id=1");
        if (res.ok) _ardMsg("✓ M1 HOME 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M2 RUN */
ardM2RunBtn.addEventListener("click", async () => {
    try {
        const p = new URLSearchParams({
            id: 2, deg: ardM2Deg.value,
            spd: ardM2Spd.value, acc: ardM2Acc.value,
        });
        const res = await fetch(`/arduino_run?${p}`);
        if (res.ok) _ardMsg("✓ M2 RUN 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M2 HOME */
ardM2HomeBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/arduino_home?id=2");
        if (res.ok) _ardMsg("✓ M2 HOME 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* 파라미터 저장 (서버 state에만 기록, Arduino로는 전송 안 함) */
ardSaveBtn.addEventListener("click", async () => {
    try {
        await Promise.all([
            fetch(`/set_arduino_motor_config?key=steps_per_rev&value=${ardStepsRev.value}`),
            fetch(`/set_arduino_motor_config?key=m1_max_speed&value=${ardM1Spd.value}`),
            fetch(`/set_arduino_motor_config?key=m1_accel&value=${ardM1Acc.value}`),
            fetch(`/set_arduino_motor_config?key=m2_max_speed&value=${ardM2Spd.value}`),
            fetch(`/set_arduino_motor_config?key=m2_accel&value=${ardM2Acc.value}`),
        ]);
        _ardMsg("✓ 파라미터 저장 완료", "#30d158");
    } catch(e) { _ardMsg("✗ 저장 실패", "#ff453a"); }
});

/* 설정값 불러오기 (참고: 원본 script.js에서도 호출부가 없는 미사용 함수였음 — 그대로 보존) */
async function loadArduinoSettings() {
    try {
        const res = await fetch("/arduino_motor_settings");
        const d   = await res.json();
        ardStepsRev.value = d.steps_per_rev; ardStepsRevV.textContent = d.steps_per_rev;
        ardM1Spd.value = d.m1_max_speed;     ardM1SpdV.textContent    = d.m1_max_speed;
        ardM1Acc.value = d.m1_accel;         ardM1AccV.textContent    = d.m1_accel;
        ardM2Spd.value = d.m2_max_speed;     ardM2SpdV.textContent    = d.m2_max_speed;
        ardM2Acc.value = d.m2_accel;         ardM2AccV.textContent    = d.m2_accel;
    } catch(e) {}
}

/* 위치 폴링 — 모달 열려 있을 때만 실행 (참고: 원본에서도 시작 지점이 없어
   실제로는 한 번도 동작하지 않던 폴링이었음 — 그대로 보존) */
let _ardPosPollTimer = null;

async function _pollArduinoPos() {
    try {
        const res = await fetch("/arduino_motor_status");
        const d   = await res.json();
        ardPosM1.textContent = `${d.pos_m1} step`;
        ardPosM2.textContent = `${d.pos_m2} step`;
    } catch(e) {}
}

// motor-config.js의 closeMotorCfgModal()에서 호출 — 원본의 직접 변수 접근을
// 모듈 경계를 넘지 않도록 함수 호출로 대체 (동작은 동일)
export function stopArduinoPosPoll() {
    if (_ardPosPollTimer) { clearInterval(_ardPosPollTimer); _ardPosPollTimer = null; }
}
