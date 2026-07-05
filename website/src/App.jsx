import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Target, Shield, Cpu, ExternalLink, Activity, Server, Zap, Layers, Lock, X, Terminal } from 'lucide-react'
import RobotViewer from './RobotViewer'
import ErrorBoundary from './ErrorBoundary'

function App() {
  const [showDashboardModal, setShowDashboardModal] = useState(false);
  const [currentHash, setCurrentHash] = useState(window.location.hash);

  React.useEffect(() => {
    const handleHashChange = () => setCurrentHash(window.location.hash);
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleDashboardClick = (e) => {
    e.preventDefault();
    setShowDashboardModal(true);
  };

  if (currentHash === '#controlweb') {
    return (
      <div className="w-screen h-screen bg-brand-light flex flex-col overflow-hidden font-sans selection:bg-brand-neon selection:text-brand-light">
        {/* Navbar specifically for the iframe view */}
        <nav className="w-full z-50 glass-panel border-b border-brand-border/30 px-6 py-4 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-brand-neon/20 border border-brand-neon/50 flex items-center justify-center neon-glow">
              <Zap size={18} className="text-brand-neon" />
            </div>
            <span className="font-bold text-lg tracking-tight text-white">Dashboard Connect</span>
          </div>
          <button 
            onClick={() => window.location.hash = ''} 
            className="px-6 py-2 rounded-full glass-panel text-white font-medium hover:bg-white/10 transition-colors border border-brand-border flex items-center gap-2"
          >
            ← 메인 화면으로 돌아가기
          </button>
        </nav>
        
        {/* Iframe */}
        <div className="flex-1 w-full relative bg-[#0b0f19] flex items-center justify-center">
          <div className="absolute flex flex-col items-center justify-center text-brand-muted z-0">
            <div className="w-12 h-12 border-4 border-brand-border border-t-brand-neon rounded-full animate-spin mb-4"></div>
            <p>로컬 서버(localhost:5000) 연결 대기 중...</p>
            <p className="text-sm mt-2">연결을 거부할 경우, 혼합 콘텐츠(Mixed Content) 차단을 해제해 주세요.</p>
          </div>
          <iframe 
            src="http://localhost:5000" 
            className="w-full h-full border-none relative z-10 bg-transparent"
            title="AI Vision Tracker Dashboard"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-brand-light text-brand-text font-sans selection:bg-brand-neon selection:text-brand-light select-none overflow-x-hidden relative">
      
      {/* Dashboard Connection Modal */}
      <AnimatePresence>
        {showDashboardModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              exit={{ opacity: 0 }}
              onClick={() => setShowDashboardModal(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-lg glass-panel bg-brand-surface/90 border border-brand-border/50 rounded-3xl p-8 shadow-2xl"
            >
              <button 
                onClick={() => setShowDashboardModal(false)}
                className="absolute top-6 right-6 text-brand-muted hover:text-white transition-colors"
              >
                <X size={24} />
              </button>
              
              <div className="w-12 h-12 rounded-full bg-brand-neon/20 flex items-center justify-center text-brand-neon mb-6">
                <Zap size={24} />
              </div>
              
              <h3 className="text-2xl font-bold text-white mb-2">로컬 대시보드 연결 안내</h3>
              <p className="text-brand-muted mb-6 leading-relaxed">
                대시보드는 AI Vision Tracker 소프트웨어가 <strong className="text-white">사용자의 PC(로컬)에서 실행 중일 때만</strong> 접속할 수 있습니다. 
              </p>

              <div className="bg-brand-light rounded-xl p-5 mb-8 border border-brand-border/50">
                <h4 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                  <Terminal size={16} /> 실행 방법
                </h4>
                <ol className="text-sm text-brand-muted space-y-3 list-decimal list-inside">
                  <li>GitHub에서 소스 코드를 다운로드합니다.</li>
                  <li>파이썬 필수 패키지를 설치합니다 <code className="bg-black/30 px-2 py-0.5 rounded text-brand-neon mx-1">pip install -r requirements.txt</code></li>
                  <li>메인 스크립트를 실행합니다 <code className="bg-black/30 px-2 py-0.5 rounded text-brand-neon mx-1">python app.py</code></li>
                  <li>서버가 켜지면 아래 버튼을 눌러 접속하세요.</li>
                </ol>
              </div>

              <div className="flex gap-4">
                <button 
                  onClick={() => {
                    setShowDashboardModal(false);
                    window.location.hash = '#controlweb';
                  }}
                  className="flex-1 py-3 rounded-xl bg-brand-neon text-brand-light font-bold text-center hover:bg-[#00ffaa] transition-colors"
                >
                  강제 접속 시도 (내장 대시보드 열기)
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Navigation */}
      <nav className="fixed w-full z-50 glass-panel border-b border-brand-border/30 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-brand-neon/20 border border-brand-neon/50 flex items-center justify-center neon-glow">
            <Target size={18} className="text-brand-neon" />
          </div>
          <span className="font-bold text-lg tracking-tight text-white">AI Vision Tracker</span>
        </div>
        <div className="flex items-center gap-4">
          <a href="https://github.com/lsk0522/AI_vision_tracker" target="_blank" rel="noreferrer" className="flex items-center gap-2 text-brand-muted hover:text-white transition-colors font-mono font-medium">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
              <path d="M9 18c-4.51 2-5-2-7-2" />
            </svg>
            GitHub
          </a>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-4 md:px-8 max-w-7xl mx-auto flex flex-col md:flex-row items-center gap-12 min-h-screen">
        {/* Aurora Background Effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
          <div className="absolute -top-[10%] -left-[10%] w-[50%] h-[50%] rounded-full bg-brand-neon/15 blur-[120px] mix-blend-screen animate-pulse"></div>
          <div className="absolute top-[30%] right-[0%] w-[40%] h-[40%] rounded-full bg-blue-500/10 blur-[100px] mix-blend-screen"></div>
        </div>

        <motion.div 
          className="flex-1 space-y-8 z-10 flex flex-col justify-center"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-panel border border-brand-neon/30 text-brand-neon text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-brand-neon animate-pulse neon-glow"></span>
            Physical AI Platform
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight leading-[1.1]">
            완벽을 향한 추적,<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-neon to-blue-400">
              AI Vision Tracker
            </span>
          </h1>
          <p className="text-lg md:text-xl text-brand-muted max-w-xl leading-relaxed">
            단순한 조이스틱 제어를 넘어선 차세대 스마트 트래킹 시스템.
            소프트웨어 안전 리밋과 실시간 인공지능 객체 인식으로 가장 안정적인 물리적 AI 검증 환경을 제공합니다.
          </p>
          <div className="pt-4 flex flex-wrap gap-4">
            <a href="#features" className="px-8 py-4 rounded-full bg-white text-brand-light font-bold hover:bg-gray-200 transition-colors shadow-lg">
              기능 둘러보기
            </a>
            <a href="http://localhost:5000" target="_blank" rel="noreferrer" onClick={handleDashboardClick} className="px-8 py-4 rounded-full glass-panel text-white font-medium hover:bg-white/10 transition-colors flex items-center gap-2 group border border-brand-border">
              대시보드 접속 <ExternalLink size={18} className="group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
            </a>
          </div>
        </motion.div>

        <motion.div 
          className="flex-1 w-full self-stretch relative rounded-3xl overflow-hidden glass-panel border border-brand-border/50 shadow-2xl z-10 min-h-[500px]"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, delay: 0.2 }}
        >
          <div className="absolute top-4 left-4 z-20 px-4 py-1.5 rounded-full bg-brand-surface/80 backdrop-blur-md text-xs font-semibold text-brand-muted border border-brand-border shadow-sm pointer-events-none flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-brand-neon"></div>
            Interactive 3D Model
          </div>
          <div style={{position:'absolute',inset:0,height:'100%',width:'100%'}}>
            <ErrorBoundary>
              <RobotViewer />
            </ErrorBoundary>
          </div>
        </motion.div>
      </section>

      {/* Architecture & Tech Stack (Bento Box) */}
      <section className="py-24 max-w-7xl mx-auto px-4 md:px-8 relative z-10">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-5xl font-extrabold mb-6">강력한 하드웨어와 소프트웨어의 결합</h2>
          <p className="text-brand-muted text-lg max-w-2xl mx-auto">
            단순한 카메라 트래커를 넘어선, 완벽한 AI Vision 추적 플랫폼을 위한 핵심 기반 기술
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 auto-rows-[220px]">
          {/* Large Card 2x2 */}
          <div className="md:col-span-2 md:row-span-2 glass-panel rounded-3xl p-10 flex flex-col justify-end relative overflow-hidden group transition-transform duration-300 hover:-translate-y-1 hover:border-brand-neon/30">
            <div className="absolute -top-10 -right-10 p-8 opacity-10 group-hover:opacity-20 group-hover:rotate-12 transition-all duration-500 text-brand-neon">
              <Server size={250} />
            </div>
            <div className="relative z-10">
              <div className="w-12 h-12 rounded-xl bg-brand-surface border border-brand-border flex items-center justify-center mb-6">
                <Cpu className="text-brand-neon" size={24} />
              </div>
              <h3 className="text-3xl font-bold mb-4 text-white">Raspberry Pi 4 & ESP32</h3>
              <p className="text-brand-muted text-lg leading-relaxed">강력한 연산 능력의 라즈베리파이가 AI 비전 처리를 전담하고, 실시간 모터 제어는 ESP32 하드웨어 인터럽트로 완벽하게 분산 처리하여 지연(Latency) 없는 추적을 보장합니다.</p>
            </div>
          </div>
          
          {/* Medium Card 2x1 */}
          <div className="md:col-span-2 md:row-span-1 glass-panel rounded-3xl p-8 flex flex-col justify-center relative overflow-hidden group transition-transform duration-300 hover:-translate-y-1 hover:border-blue-400/30">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-full bg-brand-surface border border-brand-border flex items-center justify-center text-blue-400 group-hover:scale-110 transition-transform">
                <Activity size={24} />
              </div>
              <h3 className="text-2xl font-bold text-white">OpenCV CSRT Algorithm</h3>
            </div>
            <p className="text-brand-muted leading-relaxed">기존 단순 색상 추적과 달리 다각도의 형태 변화와 가려짐(Occlusion)에도 강인한 CSRT 객체 추적 알고리즘 탑재</p>
          </div>
          
          {/* Small Cards 1x1 */}
          <div className="md:col-span-1 md:row-span-1 glass-panel rounded-3xl p-6 flex flex-col justify-center items-center text-center group transition-transform duration-300 hover:-translate-y-1 hover:border-brand-neon/50">
            <Layers size={40} className="text-brand-neon mb-4 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg mb-2 text-white">React + Three.js</h3>
            <p className="text-brand-muted text-sm">실시간 3D 모니터링</p>
          </div>
          <div className="md:col-span-1 md:row-span-1 glass-panel rounded-3xl p-6 flex flex-col justify-center items-center text-center group transition-transform duration-300 hover:-translate-y-1 hover:border-purple-400/50">
            <Lock size={40} className="text-purple-400 mb-4 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg mb-2 text-white">Safe Zone API</h3>
            <p className="text-brand-muted text-sm">물리 충돌 방지 소프트웨어 제동</p>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 bg-brand-section border-y border-brand-border/50 relative z-10">
        <div className="max-w-7xl mx-auto px-4 md:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-extrabold mb-6 text-white">어떤 상황에서도 멈추지 않는 추적</h2>
            <p className="text-brand-muted text-lg max-w-2xl mx-auto">
              소프트웨어와 하드웨어의 완벽한 조화를 통해 극한의 상황에서도 안전하게 대상을 놓치지 않습니다.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<Shield size={28} className="text-brand-neon" />}
              title="Dynamic 2D Safe Zone"
              description="카메라가 아래를 향할 때 회전 반경을 자동으로 줄여 기둥과의 물리적 충돌을 완벽하게 방지합니다."
            />
            <FeatureCard 
              icon={<Cpu size={28} className="text-blue-400" />}
              title="Soft Braking System"
              description="목적지 도달 전 소프트웨어적으로 점진적 감속을 수행하여 하드웨어의 관성 밀림(오버슛)을 제거했습니다."
            />
            <FeatureCard 
              icon={<Target size={28} className="text-purple-400" />}
              title="AI CSRT Tracking"
              description="OpenCV 기반의 초고속 객체 인식 알고리즘으로, 카메라가 움직이는 중에도 타겟을 흔들림 없이 추적합니다."
            />
          </div>
        </div>
      </section>

      {/* How it Works (Timeline) */}
      <section className="py-24 relative z-10 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 md:px-8">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-5xl font-extrabold mb-6">단 0.1초 만에 이루어지는 프로세스</h2>
            <p className="text-brand-muted text-lg">목표물을 감지하고 모터가 구동되기까지의 완벽한 파이프라인</p>
          </div>
          
          <div className="flex flex-col md:flex-row justify-between items-start gap-12 md:gap-8 relative">
            {/* 데스크탑 가로 연결선 */}
            <div className="hidden md:block absolute top-10 left-[15%] right-[15%] h-[2px] bg-gradient-to-r from-transparent via-brand-border to-transparent z-0"></div>
            {/* 모바일 세로 연결선 */}
            <div className="md:hidden absolute top-[5%] bottom-[5%] left-10 w-[2px] bg-gradient-to-b from-transparent via-brand-border to-transparent z-0"></div>
            
            {[
              { step: '01', title: 'Target Acquisition', desc: '카메라 모듈이 초당 60프레임으로 이미지를 수집하고 사용자가 지정한 타겟을 인식합니다.' },
              { step: '02', title: 'AI Processing', desc: '라즈베리파이 내부의 OpenCV엔진이 타겟의 예상 이동 경로와 현재 오차를 계산합니다.' },
              { step: '03', title: 'Hardware Actuation', desc: '계산된 좌표를 ESP32가 넘겨받아 초정밀 PID 제어로 서보모터를 부드럽게 구동시킵니다.' }
            ].map((item, i) => (
              <div key={i} className="relative z-10 flex flex-row md:flex-col items-center md:items-center gap-6 md:gap-6 md:text-center w-full md:w-1/3 group">
                <div className="w-20 h-20 shrink-0 rounded-full bg-[#1f2937] flex items-center justify-center text-2xl font-black text-[#00ffaa] border-2 border-[#00ffaa] shadow-[0_0_20px_rgba(0,255,170,0.4)] group-hover:scale-110 group-hover:shadow-[0_0_30px_rgba(0,255,170,0.8)] transition-all duration-300 relative z-20">
                  {item.step}
                </div>
                <div>
                  <h3 className="text-2xl font-bold mb-3 text-white group-hover:text-brand-neon transition-colors">{item.title}</h3>
                  <p className="text-brand-muted leading-relaxed">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Banner */}
      <section className="py-32 relative overflow-hidden bg-brand-section border-t border-brand-border/50">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[600px] h-[600px] bg-brand-neon/5 blur-[120px] rounded-full"></div>
        </div>
        <div className="max-w-4xl mx-auto px-4 relative z-10 text-center">
          <h2 className="text-4xl md:text-6xl font-black mb-8 text-white">지금 바로 시작해보세요</h2>
          <p className="text-xl text-brand-muted mb-12 max-w-2xl mx-auto leading-relaxed">
            오픈소스로 공개된 프로젝트 코드를 확인하거나, 로컬 대시보드에 접속하여 직접 AI Vision Tracker를 조종해볼 수 있습니다.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-6">
            <a href="http://localhost:5000" onClick={handleDashboardClick} className="px-8 py-4 rounded-full bg-brand-neon text-brand-light font-extrabold text-lg hover:scale-105 hover:bg-[#00ffaa] transition-all duration-300 shadow-[0_0_30px_rgba(0,255,170,0.3)] flex items-center justify-center gap-3 group">
              <Zap size={22} className="group-hover:scale-110 group-hover:rotate-12 transition-transform duration-300" /> 대시보드 접속하기
            </a>
            <a href="https://github.com/lsk0522/AI_vision_tracker" className="px-8 py-4 rounded-full glass-panel text-white font-bold text-lg hover:scale-105 hover:bg-white/5 transition-all duration-300 border border-brand-border flex items-center justify-center gap-3">
              GitHub 코드 보기 <ExternalLink size={20} />
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 text-center text-brand-muted/60 border-t border-brand-border/30 text-sm bg-brand-light relative z-10">
        <p className="mb-2">© 2026 AI Vision Tracker. All rights reserved.</p>
        <p className="text-xs">Designed with modern web technologies & Three.js</p>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="p-8 rounded-3xl glass-panel group transition-transform duration-300 hover:-translate-y-2 hover:shadow-[0_10px_30px_rgba(0,255,170,0.1)] border border-brand-border hover:border-brand-neon/40">
      <div className="w-14 h-14 rounded-2xl bg-brand-surface border border-brand-border flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 shadow-inner">
        {icon}
      </div>
      <h3 className="text-xl font-bold mb-3 text-white">{title}</h3>
      <p className="text-brand-muted leading-relaxed">{description}</p>
    </div>
  )
}

export default App
