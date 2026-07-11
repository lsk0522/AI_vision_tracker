import { state } from './state.js';
import { sendClick } from './tracking-view.js';

/* ==========================================
   화면 크기에 맞춘 조이스틱/컨트롤 레이아웃
   ========================================== */
let BASE_R;
let STICK_R;

export function resize(){
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const wrap = document.getElementById("wrap");

    let w;
    let h;

    /* 원래 4:3 비율 유지 */
    if (vw / vh > 4 / 3) {
        h = vh;
        w = vh * 4 / 3;
    } else {
        w = vw;
        h = vw * 3 / 4;
    }

    wrap.style.width  = w + "px";
    wrap.style.height = h + "px";

    const s = Math.min(w, h);

    // 조이스틱 및 컨트롤 버튼 크기 동적 조절
    BASE_R  = Math.round(s * 0.12);
    STICK_R = Math.round(s * 0.05);

    const base  = document.getElementById("joystick-base");
    const stick = document.getElementById("joystick-stick");

    base.style.width  = BASE_R * 2 + "px";
    base.style.height = BASE_R * 2 + "px";

    stick.style.width  = STICK_R * 2 + "px";
    stick.style.height = STICK_R * 2 + "px";

    stick.style.left = BASE_R + "px";
    stick.style.top  = BASE_R + "px";
}

resize();
window.addEventListener("resize", resize);

/* ==========================================
   조이스틱 드래그 제어 로직 (마우스 & 터치)
   ========================================== */
const base  = document.getElementById("joystick-base");
const stick = document.getElementById("joystick-stick");

function getBaseCenter(){
    const rect = base.getBoundingClientRect();
    return {
        x: rect.left + BASE_R,
        y: rect.top  + BASE_R
    };
}

let joyDirX = 0;
let joyDirY = 0;

let _joyLastSend = 0;

function checkJoystickDir() {
    // Deprecated: Joystick directly mapped to /click in loop() for zero-delay velocity control
}

function updateStick(tx, ty){
    const center = getBaseCenter();
    let dx = tx - center.x;
    let dy = ty - center.y;

    const dist = Math.sqrt(dx*dx + dy*dy);
    const maxDist = BASE_R * 0.75;

    if(dist > maxDist){
        dx = dx / dist * maxDist;
        dy = dy / dist * maxDist;
    }

    stick.style.left = BASE_R + dx + "px";
    stick.style.top  = BASE_R + dy + "px";

    state.joyVx = dx / maxDist;
    state.joyVy = dy / maxDist;

    // checkJoystickDir(); // removed to prevent overlap with syncServer
    checkJoystickDir(); // Re-enabled for proper velocity control
}

let joyAbortController = null;

function resetStick(){
    // Spring-back animation: restore transition then snap to center with physics
    stick.style.transition = 'left 0.45s cubic-bezier(0.34,1.56,0.64,1.0), top 0.45s cubic-bezier(0.34,1.56,0.64,1.0), background 0.15s';
    stick.style.left = BASE_R + "px";
    stick.style.top  = BASE_R + "px";
    setTimeout(() => { stick.style.transition = ''; }, 460);

    state.joyVx = 0;
    state.joyVy = 0;
    state.joySendX = 0;
    state.joySendY = 0;
    state.joystickTouchId = null;

    if (state.inputMode === "joystick") {
        state.tPx = 320;
        state.tPy = 240;
        sendClick(320, 240);
        // 조이스틱 릴리즈 즉시 stop 명령 전송 (이전 요청 취소)
        if (state._joySent) {
            state.joySeq++;
            if (joyAbortController) joyAbortController.abort();
            joyAbortController = new AbortController();
            fetch(`/joystick_dir?x=0&y=0&seq=${state.joySeq}`, { signal: joyAbortController.signal }).catch(()=>{});
            state._joySent = false;
        }
    }
    state.lastSync = Date.now();
}

/* 터치 제어 */
base.addEventListener("touchstart", (e)=>{
    e.preventDefault();
    const t = e.changedTouches[0];
    state.joystickTouchId = t.identifier;
    updateStick(t.clientX, t.clientY);
},{passive:false});

base.addEventListener("touchmove", (e)=>{
    e.preventDefault();
    for(const t of e.changedTouches){
        if(t.identifier === state.joystickTouchId){
            updateStick(t.clientX, t.clientY);
        }
    }
},{passive:false});

base.addEventListener("touchend", (e) => {
    resetStick();
});
base.addEventListener("touchcancel", (e) => {
    resetStick();
});

/* 마우스 제어 */
base.addEventListener("mousedown", (e)=>{
    e.preventDefault();
    updateStick(e.clientX, e.clientY);

    function move(ev){
        updateStick(ev.clientX, ev.clientY);
    }

    function up(){
        resetStick();
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
        document.removeEventListener("mouseleave", up);
    }

    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    document.addEventListener("mouseleave", up);
});
