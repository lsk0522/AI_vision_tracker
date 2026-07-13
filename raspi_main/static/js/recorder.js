import { showToast } from './ui-utils.js';

/* ==========================================
   화면 녹화 (Screen Record)
   MJPEG <img> 스트림을 캔버스에 복사 → captureStream → MediaRecorder
   버튼 한 번 = 녹화 시작, 다시 누르면 정지 + .webm 자동 다운로드
   ========================================== */
const recordBtn  = document.getElementById("record-btn");
const recordTime = document.getElementById("record-time");
const videoImg   = document.getElementById("video");

let _recorder   = null;
let _chunks     = [];
let _canvas     = null;
let _ctx        = null;
let _rafId      = null;
let _timerId    = null;
let _startedAt  = 0;

function _fmtElapsed(ms) {
    const s = Math.floor(ms / 1000);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function _fmtFilename(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `AIVT_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}.webm`;
}

function _drawLoop() {
    // MJPEG <img>는 프레임 이벤트가 없으므로 rAF 주기로 캔버스에 복사
    try {
        _ctx.drawImage(videoImg, 0, 0, _canvas.width, _canvas.height);
    } catch (e) { /* 스트림 끊김 프레임은 건너뜀 */ }
    _rafId = requestAnimationFrame(_drawLoop);
}

function startRecording() {
    if (!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) {
        showToast("이 브라우저는 화면 녹화를 지원하지 않습니다", "error");
        return;
    }
    const w = videoImg.naturalWidth  || 640;
    const h = videoImg.naturalHeight || 480;

    _canvas = document.createElement("canvas");
    _canvas.width = w; _canvas.height = h;
    _ctx = _canvas.getContext("2d");
    _drawLoop();

    const stream = _canvas.captureStream(30);
    const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
        ? "video/webm;codecs=vp9" : "video/webm";
    _chunks = [];
    _recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 4_000_000 });
    _recorder.ondataavailable = (e) => { if (e.data.size > 0) _chunks.push(e.data); };
    _recorder.onstop = _saveRecording;
    _recorder.start(1000);  // 1초 단위로 chunk 수집 (탭 닫힘 등에도 데이터 보존)

    _startedAt = Date.now();
    recordTime.textContent = "0:00";
    _timerId = setInterval(() => {
        recordTime.textContent = _fmtElapsed(Date.now() - _startedAt);
    }, 1000);

    recordBtn.classList.add("recording");
    showToast("● 녹화 시작", "info", 1500);
}

function stopRecording() {
    if (_recorder && _recorder.state !== "inactive") _recorder.stop();
    if (_rafId)   cancelAnimationFrame(_rafId);
    if (_timerId) clearInterval(_timerId);
    _rafId = null; _timerId = null;
    recordBtn.classList.remove("recording");
}

function _saveRecording() {
    const blob = new Blob(_chunks, { type: "video/webm" });
    _chunks = [];
    _recorder = null;
    if (blob.size === 0) {
        showToast("녹화된 프레임이 없습니다", "error");
        return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = _fmtFilename(new Date());
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    showToast("✓ 녹화 저장됨 (" + (blob.size / 1048576).toFixed(1) + " MB)", "success");
}

if (recordBtn && videoImg) {
    recordBtn.addEventListener("click", () => {
        if (_recorder) stopRecording();
        else startRecording();
    });
}
