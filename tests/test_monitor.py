import unittest
import json
import sys
import os

# backend 경로를 sys.path에 추가하여 routes 패키지를 불러올 수 있도록 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from flask import Flask
from routes import setup_routes
import state

class TestMonitorAPI(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        setup_routes(self.app)
        self.client = self.app.test_client()
        
        # 각 테스트 수행 전 state 기본값 초기화
        state.active_limit_msg = ""
        state.point = [320, 240]

    def test_monitor_default_state(self):
        """1. 기본 상태 검증 (리밋 비활성화, 조준 편차 0)"""
        response = self.client.get('/api/status/monitor')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        
        self.assertFalse(data['limit_active'])
        self.assertEqual(data['limit_message'], "")
        self.assertEqual(data['target_error_x'], 0)
        self.assertEqual(data['target_error_y'], 0)
        self.assertEqual(data['current_point'], [320, 240])

    def test_monitor_limit_active(self):
        """2. 리밋 경고 활성화 상태 검증"""
        test_msg = "M2 upper limit reached! (-6.50 deg)"
        state.active_limit_msg = test_msg
        
        response = self.client.get('/api/status/monitor')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        
        self.assertTrue(data['limit_active'])
        self.assertEqual(data['limit_message'], test_msg)

    def test_monitor_error_calculation(self):
        """3. 조준점 오차 계산 검증"""
        state.point = [350, 200]  # X편차: +30, Y편차: -40
        
        response = self.client.get('/api/status/monitor')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        
        self.assertEqual(data['target_error_x'], 30)
        self.assertEqual(data['target_error_y'], -40)
        self.assertEqual(data['current_point'], [350, 200])

if __name__ == '__main__':
    unittest.main()
