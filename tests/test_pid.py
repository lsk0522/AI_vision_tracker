import unittest
import json
import sys
import os
import time

# backend 경로를 sys.path에 추가하여 routes 패키지를 불러올 수 있도록 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from flask import Flask
from routes import setup_routes
import state

class TestPIDTracking(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        setup_routes(self.app)
        self.client = self.app.test_client()
        
        # state 초기화 및 제어 모드 auto 세팅
        state.control_mode = "auto"
        state.active_limit_msg = ""
        state.point = [320, 240]
        
        # 가상 PID 내부 변수들 초기화
        if hasattr(state, '_smooth_tx'): delattr(state, '_smooth_tx')
        if hasattr(state, '_smooth_ty'): delattr(state, '_smooth_ty')
        if hasattr(state, '_integral_x'): delattr(state, '_integral_x')
        if hasattr(state, '_integral_y'): delattr(state, '_integral_y')
        state.remote_tracking_last_time = 0.0

    def test_scenario_1_static_target(self):
        """시나리오 1: 타겟이 중심점에 정지해 있을 때 제어 신호가 0으로 안정되는가?"""
        # 1초 간격으로 갭을 해제하기 위해 초기화성 호출
        self.client.get('/set_target?tx=320&ty=240')
        
        # 지속적으로 중앙 좌표 호출
        for _ in range(5):
            time.sleep(0.01) # dt 간격을 만들어 줌
            response = self.client.get('/set_target?tx=320&ty=240')
            self.assertEqual(response.status_code, 200)
            
        # 조준점이 320, 240에 정지해 있는지 검증
        self.assertEqual(state.point, [320, 240])
        self.assertAlmostEqual(state._smooth_tx, 320.0)
        self.assertAlmostEqual(state._smooth_ty, 240.0)

    def test_scenario_2_differential_damping(self):
        """시나리오 2: 타겟이 급격하게 이동할 때, 미분(D) 제동력에 의해 오버슈트(흔들림)가 억제되는가?"""
        # 초기 위치 320 -> 320
        self.client.get('/set_target?tx=320&ty=240')
        
        # 1단계: 타겟이 320에서 400으로 급격히 이동
        # 첫 번째 이동 호출 (이때 가상위치 _smooth_tx는 아직 320 근처에서 400 쪽으로 출발)
        self.client.get('/set_target?tx=400&ty=240')
        
        # 가상 위치가 빠르게 400을 향해 다가가고 있을 때 (예: _smooth_tx가 390 정도에 도달했다고 가정하고 시뮬레이션)
        state._smooth_tx = 390.0
        state._prev_err_x = 400.0 - 380.0  # 이전 오차: 20
        # 이번 오차: 400.0 - 390.0 = 10
        # 오차가 20에서 10으로 감소했으므로 (타겟에 급격히 다가가는 제동 시점)
        
        # API 재호출하여 미분 감속 댐핑 작동 검증
        # 10ms 후 호출 모사
        state.remote_tracking_last_time = time.time() - 0.01
        
        response = self.client.get('/set_target?tx=400&ty=240')
        self.assertEqual(response.status_code, 200)
        
        # 이번 오차(10)와 이전 오차(20)의 차이: (10 - 20) / 0.01 = -1000
        # 미분 계수 Kd = 0.05 이므로 D항 제어량 = 0.05 * -1000 = -50.0 (강력한 음수 제동력 작동!)
        # 비례항 P항 제어량 = Kp * err_x = 0.15 * 10 = +1.5
        # 즉, 비례항은 타겟 방향인 양수(+1.5)를 가리키지만, 미분항의 브레이크 제동량(-50.0)이 훨씬 커서
        # 오버슈트 방지를 위해 제어 출력이 음수가 되어 속도를 감속하게 됨을 검증.
        
        # D항 제동량이 제어 출력의 속도를 늦추도록 기여했는지 확인
        # (만약 LFP 형태였다면 단순 오차에 비례해 계속 + 방향으로 빠르게 달려갔을 것임)
        # 미분 제동력이 잘 걸려서 제어 변화량이 억제(감속 브레이크 작동)되었는지 검증
        self.assertTrue(state._prev_err_x < 20.0) # 오차가 10으로 감소되었음
        # 미분 댐핑량(-50)이 비례 제어량(+1.5)보다 압도적으로 강해 실제 _smooth_tx 가 390.0보다 감소하였음을 검증
        self.assertTrue(state._smooth_tx < 390.0)

    def test_scenario_3_anti_windup(self):
        """시나리오 3: 미세한 오차가 지속될 때, Anti-Windup 임계치 안에서 적분(I) 제어가 안전하게 상한선에 도달하는가?"""
        # 초기화
        self.client.get('/set_target?tx=320&ty=240')
        
        # 350에 타겟을 둠으로써 지속적인 오차(tx=350, 가상위치=320) 발생
        # 이로 인해 적분 누적이 지속적으로 쌓이게 됨
        # dt = 0.1s 로 고정하고 50번 누적 시뮬레이션
        for _ in range(50):
            state.remote_tracking_last_time = time.time() - 0.1
            self.client.get('/set_target?tx=350&ty=240')
            # 강제로 가상 위치를 320에 묶어놓아 오차가 계속 30으로 누적되도록 함
            state._smooth_tx = 320.0
            
        # 적분 누적항이 100.0 (windup_limit)을 초과하지 않고 100.0에 걸려 있는지 검증
        self.assertEqual(state._integral_x, 100.0)
        self.assertTrue(state._integral_x <= 100.0)

if __name__ == '__main__':
    unittest.main()
