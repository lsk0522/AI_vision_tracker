import { showToast, closeModalAnimate, registerEscHandler } from './ui-utils.js';

// ══════════════════════════════════════════
// ESP32 펌웨어 업로드 로직
// ══════════════════════════════════════════
const btnUploadFirmware = document.getElementById("btn-upload-firmware");
const firmwareModal = document.getElementById("firmware-modal");
const closeFirmware = document.getElementById("close-firmware");
const btnStartUpload = document.getElementById("btn-start-upload");
const firmwareProgress = document.getElementById("firmware-progress");

const btnReleaseMotors = document.getElementById("btn-release-motors");
const btnEnableMotors = document.getElementById("btn-enable-motors");
if (btnEnableMotors) {
    btnEnableMotors.addEventListener("click", async () => {
        try {
            await fetch("/enable_motors");
            showToast("모터 전원이 활성화되었습니다.", "success");
        } catch(e) {
            console.error(e);
        }
    });
}

if (btnReleaseMotors) {
    btnReleaseMotors.addEventListener("click", async () => {
        try {
            await fetch("/release_motors");
            showToast("⚠️ 모터 전원이 강제 차단되었습니다 (힘 풀림).", "info");
        } catch(e) {
            console.error(e);
        }
    });
}

if (btnUploadFirmware) {
    btnUploadFirmware.addEventListener("click", () => {
        document.getElementById("settings-modal").style.display = "none";
        firmwareModal.style.display = "flex";
        btnStartUpload.style.display = "block";
        firmwareProgress.style.display = "none";
    });
}

if (closeFirmware) {
    closeFirmware.addEventListener("click", () => {
        closeModalAnimate(firmwareModal);
    });
}

registerEscHandler(
    () => !!(firmwareModal && firmwareModal.style.display === "flex"),
    () => { firmwareModal.style.display = "none"; }
);

if (btnStartUpload) {
    btnStartUpload.addEventListener("click", async () => {
        btnStartUpload.style.display = "none";
        firmwareProgress.style.display = "flex";
        try {
            showToast("업로드를 시작합니다...", "info");
            const res = await fetch("/upload_firmware", { method: "POST" });
            const data = await res.json();
            if (data.ok) {
                showToast("펌웨어 업로드 완료!", "success");
                setTimeout(() => closeModalAnimate(firmwareModal), 1500);
            } else {
                showToast("업로드 실패. 백엔드 콘솔을 확인하세요.", "error");
                console.error("Upload failed:\n", data.log);
                btnStartUpload.style.display = "block";
                firmwareProgress.style.display = "none";
            }
        } catch(e) {
            showToast("업로드 중 네트워크 오류가 발생했습니다.", "error");
            btnStartUpload.style.display = "block";
            firmwareProgress.style.display = "none";
        }
    });
}

/* ═══════════════════════════════════════════════════════════════
   펌웨어 버전 불일치 감지 & 경고 모달
   ═══════════════════════════════════════════════════════════════ */
(function initFirmwareMismatchWatcher() {
    const overlay   = document.getElementById("firmware-mismatch-overlay");
    const modal     = document.getElementById("firmware-mismatch-modal");
    const elExp     = document.getElementById("fw-expected");
    const elAct     = document.getElementById("fw-actual");
    const btnUpload = document.getElementById("fw-upload-btn");
    const btnDismiss= document.getElementById("fw-dismiss-btn");

    if (!overlay || !modal) return;

    let dismissed        = false;   // 사용자가 '나중에 하기' 누른 경우
    let uploadInProgress = false;

    /* ── 모달 표시 ── */
    function showMismatchModal(expected, actual) {
        elExp.textContent = expected || "—";
        elAct.textContent = actual   || "(없음)";
        overlay.style.display = "flex";
    }

    /* ── 모달 숨김 ── */
    function hideMismatchModal() {
        overlay.style.display = "none";
        modal.classList.remove("fw-uploading");
    }

    /* ── 5초마다 /firmware_status 폴링 ── */
    async function pollFirmwareStatus() {
        if (uploadInProgress) return;
        try {
            const res  = await fetch("/firmware_status");
            if (!res.ok) return;
            const data = await res.json();

            if (data.mismatch && !dismissed) {
                showMismatchModal(data.expected, data.actual);
            } else if (!data.mismatch) {
                // 버전이 맞으면 모달 숨기고 dismissed 초기화
                hideMismatchModal();
                dismissed = false;
            }
        } catch (_) {
            /* 서버 미응답 시 무시 */
        }
    }

    setInterval(pollFirmwareStatus, 5000);
    // 페이지 로드 후 3초 뒤 첫 번째 체크 (ESP32 부팅 대기)
    setTimeout(pollFirmwareStatus, 3000);

    /* ── '나중에 하기' 버튼 ── */
    btnDismiss.addEventListener("click", () => {
        dismissed = true;
        hideMismatchModal();
        showToast("⚠️ 펌웨어가 맞지 않습니다. 문제가 생길 수 있습니다.", "warn");
    });

    /* ── '펌웨어 업로드' 버튼 → 기존 /upload_firmware API 재활용 ── */
    btnUpload.addEventListener("click", async () => {
        if (uploadInProgress) return;
        uploadInProgress = true;
        modal.classList.add("fw-uploading");

        // 버튼 텍스트를 업로드 중 상태로 변경
        btnUpload.innerHTML = `
            <div class="spinner" style="width:18px;height:18px;border-width:2.5px;"></div>
            업로드 중…
        `;

        showToast("펌웨어 업로드를 시작합니다…", "info");

        try {
            const res  = await fetch("/upload_firmware", { method: "POST" });
            const data = await res.json();

            if (data.ok) {
                showToast("✅ 펌웨어 업로드 완료! ESP32가 재부팅됩니다.", "success");
                dismissed = false;
                // 재부팅 후 VER: 재수신까지 8초 대기 후 재폴링
                setTimeout(() => {
                    uploadInProgress = false;
                    modal.classList.remove("fw-uploading");
                    btnUpload.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                            <polyline points="16 16 12 12 8 16"></polyline>
                            <line x1="12" y1="12" x2="12" y2="21"></line>
                            <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
                        </svg>
                        펌웨어 업로드
                    `;
                    pollFirmwareStatus();
                }, 8000);
            } else {
                showToast("❌ 업로드 실패. 백엔드 콘솔을 확인하세요.", "error");
                console.error("[firmware] 업로드 실패 로그:\n", data.log);
                uploadInProgress = false;
                modal.classList.remove("fw-uploading");
                btnUpload.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                        <polyline points="16 16 12 12 8 16"></polyline>
                        <line x1="12" y1="12" x2="12" y2="21"></line>
                        <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
                    </svg>
                    펌웨어 업로드
                `;
            }
        } catch (e) {
            showToast("❌ 업로드 중 네트워크 오류가 발생했습니다.", "error");
            uploadInProgress = false;
            modal.classList.remove("fw-uploading");
            btnUpload.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                    <polyline points="16 16 12 12 8 16"></polyline>
                    <line x1="12" y1="12" x2="12" y2="21"></line>
                    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
                </svg>
                펌웨어 업로드
            `;
        }
    });
})();
