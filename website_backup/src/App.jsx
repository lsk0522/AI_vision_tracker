import React from 'react'
import { motion } from 'framer-motion'
import { Target, Shield, Cpu, ExternalLink } from 'lucide-react'
import RobotViewer from './RobotViewer'
import ErrorBoundary from './ErrorBoundary'

function App() {
  return (
    <div className="min-h-screen bg-brand-light text-brand-text font-sans selection:bg-brand-neon selection:text-white select-none">
      {/* Navigation */}
      <nav className="fixed w-full z-50 glass-panel border-b border-gray-100 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-brand-neon neon-glow flex items-center justify-center">
            <Target size={18} className="text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight">AI Vision Tracker</span>
        </div>
        <div className="flex items-center gap-4">
          <a href="https://github.com/lsk0522/AI_vision_tracker" target="_blank" rel="noreferrer" className="flex items-center gap-2 text-brand-muted hover:text-brand-neon transition-colors font-mono font-bold">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
              <path d="M9 18c-4.51 2-5-2-7-2" />
            </svg>
            GitHub
          </a>
        </div>
      </nav>

      {/* Hero Section with 3D Viewer */}
      <section className="pt-24 pb-12 px-4 md:px-8 max-w-7xl mx-auto flex flex-col md:flex-row items-center gap-12">
        <motion.div 
          className="flex-1 space-y-6 z-10 flex flex-col justify-center"
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8 }}
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-50 border border-brand-neon/30 text-brand-neon text-sm font-medium mb-4">
            <span className="w-2 h-2 rounded-full bg-brand-neon animate-pulse"></span>
            Physical AI Platform
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight leading-tight">
            완벽을 향한 추적,<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-neon to-emerald-400">
              AI Vision Tracker
            </span>
          </h1>
          <p className="text-lg md:text-xl text-brand-muted max-w-xl leading-relaxed">
            단순한 조이스틱 제어를 넘어선 차세대 스마트 트래킹 시스템.
            소프트웨어 안전 리밋과 실시간 인공지능 객체 인식으로 가장 안정적인 물리적 AI 검증 환경을 제공합니다.
          </p>
          <div className="pt-4 flex gap-4">
            <a href="#features" className="px-6 py-3 rounded-full bg-brand-text text-white font-medium hover:bg-gray-800 transition-colors shadow-lg shadow-gray-200">
              핵심 기능 보기
            </a>
            <a href="http://localhost:5000" target="_blank" rel="noreferrer" className="px-6 py-3 rounded-full bg-brand-surface text-brand-text font-medium hover:bg-gray-100 transition-colors border border-gray-200 flex items-center gap-2">
              대시보드 접속 <ExternalLink size={16} />
            </a>
          </div>
        </motion.div>

        <motion.div 
          className="flex-1 w-full self-stretch relative rounded-3xl overflow-hidden border border-gray-200 shadow-md"
          style={{background:'#f0f2f5'}}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, delay: 0.2 }}
        >
          {/* 3D Robot Viewer */}
          <div className="absolute top-4 left-4 z-10 px-3 py-1 rounded-full bg-white/70 backdrop-blur-md text-xs font-semibold text-brand-text border border-white shadow-sm pointer-events-none">
            Interactive 3D Model (마우스로 드래그해보세요)
          </div>
          <div style={{position:'absolute',inset:0,height:'100%',width:'100%'}}>
            <ErrorBoundary>
              <RobotViewer />
            </ErrorBoundary>
          </div>
        </motion.div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-brand-section border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-4 md:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">어떤 상황에서도 멈추지 않는 추적</h2>
            <p className="text-brand-muted max-w-2xl mx-auto">
              소프트웨어와 하드웨어의 완벽한 조화를 통해 극한의 상황에서도 안전하게 대상을 놓치지 않습니다.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<Shield size={24} className="text-brand-neon" />}
              title="Dynamic 2D Safe Zone"
              description="카메라가 아래를 향할 때 회전 반경을 자동으로 줄여 기둥과의 물리적 충돌을 완벽하게 방지합니다."
            />
            <FeatureCard 
              icon={<Cpu size={24} className="text-blue-500" />}
              title="Soft Braking System"
              description="목적지 도달 전 소프트웨어적으로 점진적 감속을 수행하여 하드웨어의 관성 밀림(오버슛)을 제거했습니다."
            />
            <FeatureCard 
              icon={<Target size={24} className="text-purple-500" />}
              title="AI CSRT Tracking"
              description="OpenCV 기반의 초고속 객체 인식 알고리즘으로, 카메라가 움직이는 중에도 타겟을 흔들림 없이 추적합니다."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 text-center text-brand-muted border-t border-gray-100 text-sm">
        <p>© 2026 AI Vision Tracker. All rights reserved.</p>
        <p className="mt-2 text-xs opacity-60">Designed with modern web technologies & Three.js</p>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }) {
  return (
    <motion.div 
      whileHover={{ y: -5 }}
      className="p-8 rounded-2xl glass-panel hover:shadow-xl hover:shadow-brand-neon/5 transition-all duration-300 group"
    >
      <div className="w-12 h-12 rounded-xl bg-white shadow-sm flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <h3 className="text-xl font-bold mb-3">{title}</h3>
      <p className="text-brand-muted leading-relaxed">{description}</p>
    </motion.div>
  )
}

export default App
