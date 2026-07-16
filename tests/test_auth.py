import unittest
import json
import sys
import os

# backend 경로를 sys.path에 추가하여 routes 패키지를 불러올 수 있도록 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from flask import Flask
from routes import setup_routes
from routes.auth_routes import USERS_DB
from werkzeug.security import check_password_hash

class TestAuthAPI(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        setup_routes(self.app)
        self.client = self.app.test_client()
        # 매 테스트 수행 전에 In-Memory DB 초기화
        USERS_DB.clear()

    def test_signup_success(self):
        """1. 정상 가입 (Success) 검증"""
        response = self.client.post('/signup', 
                                    data=json.dumps({
                                        'email': 'test@example.com',
                                        'password': 'StrongPass123!'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['message'], '회원가입이 완료되었습니다.')

    def test_signup_duplicate_email(self):
        """2. 이메일 중복 (Duplicate Email) 검증"""
        # 첫 번째 가입
        self.client.post('/signup', 
                         data=json.dumps({
                             'email': 'test@example.com',
                             'password': 'StrongPass123!'
                         }),
                         content_type='application/json')
        
        # 두 번째 동일 이메일 가입
        response = self.client.post('/signup', 
                                    data=json.dumps({
                                        'email': 'test@example.com',
                                        'password': 'AnotherPass1!'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], '이미 존재하는 이메일입니다.')

    def test_signup_short_password(self):
        """3. 길이 미달 (Short Password) 검증 (5자)"""
        response = self.client.post('/signup', 
                                    data=json.dumps({
                                        'email': 'new@example.com',
                                        'password': 'Str1!'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertIn('최소 8자 이상', data['message'])

    def test_signup_missing_symbol(self):
        """4. 특수문자 누락 (Missing Symbol) 검증"""
        response = self.client.post('/signup', 
                                    data=json.dumps({
                                        'email': 'new2@example.com',
                                        'password': 'StrongPass123'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertIn('특수문자', data['message'])

    def test_signup_missing_uppercase(self):
        """5. 대문자 누락 (Missing Uppercase) 검증"""
        response = self.client.post('/signup', 
                                    data=json.dumps({
                                        'email': 'new3@example.com',
                                        'password': 'weakpass123!'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertIn('대문자', data['message'])

    def test_signup_password_hashed(self):
        """6. 회원가입 시 비밀번호 암호화 저장 검증"""
        raw_password = 'StrongPass123!'
        self.client.post('/signup', 
                         data=json.dumps({
                             'email': 'hashed@example.com',
                             'password': raw_password
                         }),
                         content_type='application/json')
        
        user = USERS_DB.get('hashed@example.com')
        self.assertIsNotNone(user)
        # 평문으로 저장되지 않았는지 검증
        self.assertNotEqual(user['password'], raw_password)
        # 해시 값이 올바른지 검증
        self.assertTrue(check_password_hash(user['password'], raw_password))

    def test_login_success(self):
        """7. 로그인 성공 검증"""
        # 회원가입 진행
        self.client.post('/signup', 
                         data=json.dumps({
                             'email': 'login_ok@example.com',
                             'password': 'StrongPass123!'
                         }),
                         content_type='application/json')
        
        # 로그인 요청
        response = self.client.post('/login',
                                    data=json.dumps({
                                        'email': 'login_ok@example.com',
                                        'password': 'StrongPass123!'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['message'], '로그인에 성공했습니다.')

    def test_login_nonexistent_email(self):
        """8. 존재하지 않는 이메일 로그인 시도 검증"""
        response = self.client.post('/login',
                                    data=json.dumps({
                                        'email': 'nobody@example.com',
                                        'password': 'StrongPass123!'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], '이메일 또는 비밀번호가 올바르지 않습니다.')

    def test_login_wrong_password(self):
        """9. 비밀번호 불일치 로그인 시도 검증"""
        # 회원가입 진행
        self.client.post('/signup', 
                         data=json.dumps({
                             'email': 'login_fail@example.com',
                             'password': 'StrongPass123!'
                         }),
                         content_type='application/json')
        
        # 잘못된 비밀번호로 로그인 요청
        response = self.client.post('/login',
                                    data=json.dumps({
                                        'email': 'login_fail@example.com',
                                        'password': 'WrongPass123!'
                                    }),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], '이메일 또는 비밀번호가 올바르지 않습니다.')

if __name__ == '__main__':
    unittest.main()
