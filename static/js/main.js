/* ==========================================
   Apple Premium Script for AI Vision Tracker
   진입점 — 각 기능 모듈을 원본 script.js와 최대한 동일한 순서로 불러온다.

   참고: target-learning.js가 settings-panel.js를 import하는 것처럼
   모듈 사이에 실제 의존 관계가 있는 경우, ES 모듈 규격상 그 의존
   모듈이 먼저 평가된다 — 그래서 여기 적힌 순서와 실제 평가 순서가
   100% 같지는 않다. 그 영향을 받는 건 ESC 키 처리 등록 순서뿐인데,
   학습 모드 진입 버튼들이 이미 설정창을 먼저 닫아주기 때문에(둘이
   동시에 열려있는 상태가 나오지 않음) 실제 동작에는 차이가 없다.
   ========================================== */
import { initEscKey } from './ui-utils.js';
import './joystick.js';
import './tracking-view.js';
import { openSettings } from './settings-panel.js';
import './input-mode.js';
import './target-learning.js';
import { updateGallery } from './gallery.js';
import './device-settings.js';
import './motor-status.js';
import './motor-config.js';
import './arduino-control.js';
import './klipper.js';
import './firmware.js';
import './camera-settings.js';
import './misc-controls.js';

// ESC 키: 열려있는 모달/오버레이가 하나도 없으면 설정창을 연다 (원본의 마지막 else 분기)
initEscKey(openSettings);

// 최초 로드 시 스크롤 넛지 + 갤러리 리스트 불러오기
window.addEventListener("load", () => {
    setTimeout(() => {
        window.scrollTo(0, 1);
    }, 100);
    updateGallery();
});
