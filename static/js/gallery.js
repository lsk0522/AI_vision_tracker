import { showToast, closeModalAnimate, registerEscHandler } from './ui-utils.js';

/* ==========================================
   미디어 라이브러리 (갤러리 및 라이트박스) 제어
   ========================================= */
let captures = [];
let activeCaptureIndex = -1;

const galleryBtn = document.getElementById("gallery-btn");
const galleryModal = document.getElementById("gallery-modal");
const closeGallery = document.getElementById("close-gallery");
const galleryThumb = document.getElementById("gallery-thumb");
const galleryEmptyIcon = document.getElementById("gallery-empty-icon");

export async function updateGallery() {
    try {
        const res = await fetch("/captures?_t=" + Date.now());
        captures = await res.json();

        if (captures && captures.length > 0) {
            galleryThumb.src = `/picture/${captures[0]}?_t=${Date.now()}`;
            galleryThumb.style.display = "block";
            galleryEmptyIcon.style.display = "none";
        } else {
            galleryThumb.style.display = "none";
            galleryEmptyIcon.style.display = "flex";
        }
    } catch(e) {
        console.error("Failed to update gallery:", e);
    }
}

function openGalleryModal(index = 0) {
    galleryModal.style.display = "flex";
    if (captures.length === 0) {
        document.getElementById("gallery-active-img").src = "";
        document.getElementById("gallery-img-info").textContent = "사진이 없습니다";
        document.getElementById("gallery-thumbnails-list").innerHTML = "";
        return;
    }
    activeCaptureIndex = index;
    renderActiveImage();
    renderGalleryThumbnails();
}

function closeGalleryModal() {
    closeModalAnimate(galleryModal);
}

galleryBtn.addEventListener("click", async () => {
    await updateGallery();
    openGalleryModal(0);
});

const galleryDeleteBtn = document.getElementById("gallery-delete");
if (galleryDeleteBtn) {
    galleryDeleteBtn.addEventListener("click", async () => {
        if (activeCaptureIndex < 0 || activeCaptureIndex >= captures.length) return;
        const filename = captures[activeCaptureIndex];

        // Confirmation is optional, let's just delete for fast UX or add a small confirm
        if (!confirm("정말 이 사진을 삭제하시겠습니까?")) return;

        try {
            const res = await fetch(`/delete/${filename}`);
            if (res.ok) {
                showToast("사진이 삭제되었습니다.", "success");
                await updateGallery();
                // If there are still pictures, show the previous or first one
                if (captures.length > 0) {
                    let nextIdx = activeCaptureIndex;
                    if (nextIdx >= captures.length) nextIdx = captures.length - 1;
                    openGalleryModal(nextIdx);
                } else {
                    closeGalleryModal();
                }
            } else {
                showToast("삭제 실패", "error");
            }
        } catch(e) {
            showToast("삭제 중 오류 발생", "error");
        }
    });
}

closeGallery.addEventListener("click", closeGalleryModal);
galleryModal.addEventListener("click", (e) => {
    if (e.target === galleryModal) {
        closeGalleryModal();
    }
});

registerEscHandler(
    () => galleryModal.style.display === "flex",
    () => closeGalleryModal()
);

function renderActiveImage() {
    if (activeCaptureIndex < 0 || activeCaptureIndex >= captures.length) return;
    const filename = captures[activeCaptureIndex];
    const activeImg = document.getElementById("gallery-active-img");
    const imgInfo = document.getElementById("gallery-img-info");
    const downloadBtn = document.getElementById("gallery-download");

    // Skeleton loading: add .loading class until image loads
    activeImg.classList.add('loading');
    activeImg.onload = () => activeImg.classList.remove('loading');
    activeImg.onerror = () => activeImg.classList.remove('loading');
    activeImg.src = `/picture/${filename}`;

    // 이미지 정보 파싱 (예: 320_240_1623456789.jpg -> 날짜 및 조준 좌표)
    let label = filename;
    try {
        const temp = filename.replace(".jpg", "");
        const parts = temp.split("_");
        if (parts.length >= 3) {
            const x = parts[0];
            const y = parts[1];
            const ts = parseInt(parts[2]);
            const date = new Date(ts * 1000).toLocaleString("ko-KR", {
                timeStyle: "medium",
                dateStyle: "short"
            });
            label = `${date} (${x}, ${y})`;
        }
    } catch(e) {}

    imgInfo.textContent = `${label} [${activeCaptureIndex + 1} / ${captures.length}]`;
    downloadBtn.href = `/picture/${filename}`;
}

function renderGalleryThumbnails() {
    const thumbList = document.getElementById("gallery-thumbnails-list");
    thumbList.innerHTML = "";

    captures.forEach((filename, idx) => {
        const item = document.createElement("img");
        item.className = `gallery-thumb-item ${idx === activeCaptureIndex ? 'active' : ''}`;
        item.src = `/picture/${filename}`;
        item.alt = "Thumbnail";

        item.addEventListener("click", () => {
            activeCaptureIndex = idx;
            renderActiveImage();
            updateThumbnailsHighlight();
        });
        thumbList.appendChild(item);
    });
}

function updateThumbnailsHighlight() {
    const thumbs = document.querySelectorAll(".gallery-thumb-item");
    thumbs.forEach((thumb, i) => {
        if (i === activeCaptureIndex) {
            thumb.classList.add("active");
            thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        } else {
            thumb.classList.remove("active");
        }
    });
}

document.getElementById("gallery-prev").addEventListener("click", () => {
    if (captures.length <= 1) return;
    activeCaptureIndex = (activeCaptureIndex - 1 + captures.length) % captures.length;
    renderActiveImage();
    updateThumbnailsHighlight();
});

document.getElementById("gallery-next").addEventListener("click", () => {
    if (captures.length <= 1) return;
    activeCaptureIndex = (activeCaptureIndex + 1) % captures.length;
    renderActiveImage();
    updateThumbnailsHighlight();
});
