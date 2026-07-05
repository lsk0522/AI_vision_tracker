import React, { Suspense, useRef, useState } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, useGLTF, Center, Environment, ContactShadows } from '@react-three/drei'

// 2D 마우스 위치를 모터 회전 각도에 1:1로 직접 매핑합니다.

// 수학적으로 Pivot(중심축)을 강제로 맞춘 추적 모델
function TrackingModel({ axisZ, angleSign, panSign, panOffset, tiltOffset, showOrigins }) {
  const base = useGLTF(`${import.meta.env.BASE_URL}Base.glb`)
  const pan = useGLTF(`${import.meta.env.BASE_URL}Pan_Axis.glb`)
  const tilt = useGLTF(`${import.meta.env.BASE_URL}Tilt_Axis.glb`)

  const panRef = useRef()
  const tiltRef = useRef()

  // 1. 단일 진실 공급원(Single Source of Truth)으로 정확한 단위 벡터 직교 축 정의
  // Pan 축: 완벽한 수직축 (Y축)
  const panAxis = React.useMemo(() => new THREE.Vector3(0, 1, 0), []);
  // Tilt 축(회전 힌지): 사용자 요청에 따라 유지하는 2축 대각선 모터축 (1, 0, axisZ)
  const tiltAxis = React.useMemo(() => new THREE.Vector3(1, 0, axisZ).normalize(), [axisZ]);

  // 2. 축 검증 로직 (컴포넌트 마운트 시 브라우저 콘솔에 출력)
  React.useEffect(() => {
    console.log("=== 조인트 축 정렬 검증 ===");
    console.log(`Pan Axis: (${panAxis.x}, ${panAxis.y}, ${panAxis.z})`);
    console.log(`Tilt Axis: (${tiltAxis.x}, ${tiltAxis.y}, ${tiltAxis.z})`);
    const dotProduct = panAxis.dot(tiltAxis);
    console.log(`내적 (Dot Product): ${dotProduct} (0이면 완벽한 직교)`);
  }, [panAxis, tiltAxis]);

  const applyMaterial = React.useCallback((scene) => {
    scene.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
        if (child.material) {
          child.material = child.material.clone();
          const r = Math.round(child.material.color.r * 255);
          const g = Math.round(child.material.color.g * 255);
          const b = Math.round(child.material.color.b * 255);
          const isGlass = 
            (Math.abs(r - 170) <= 3 && Math.abs(g - 178) <= 3 && Math.abs(b - 196) <= 3) ||
            (Math.abs(r - 202) <= 3 && Math.abs(g - 209) <= 3 && Math.abs(b - 238) <= 3);

          if (isGlass) {
            child.material.transparent = true;
            child.material.opacity = 0.25;
            child.material.roughness = 0.05;
            child.material.metalness = 0.2;
            child.material.depthWrite = false;
          } else if (r < 80 && g < 80 && b < 80) {
            child.material.color.setHex(0x1a1a1a);
            child.material.roughness = 0.9;
            child.material.metalness = 0.0;
          } else {
            child.material.transparent = false;
            child.material.opacity = 1.0;
            child.material.roughness = 0.5; 
            child.material.metalness = 0.4; 
          }
          child.material.needsUpdate = true;
        }

        if (!child.userData.hasEdges) {
          const edges = new THREE.EdgesGeometry(child.geometry, 30);
          const line = new THREE.LineSegments(
            edges, 
            new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.25, depthWrite: false }) 
          );
          child.add(line);
          child.userData.hasEdges = true;
        }
      }
    })
  }, [])

  React.useEffect(() => {
    applyMaterial(base.scene)
    applyMaterial(pan.scene)
    applyMaterial(tilt.scene)
  }, [base.scene, pan.scene, tilt.scene, applyMaterial])

  useFrame((state) => {
    if (panRef.current && tiltRef.current) {
      // 1축(Pan) - 좌우 회전
      let targetPanAngle = state.pointer.x * (Math.PI / 2) * panSign + panOffset
      const targetPanQuat = new THREE.Quaternion().setFromAxisAngle(panAxis, targetPanAngle)
      panRef.current.quaternion.slerp(targetPanQuat, 0.08)

      // 2축(Tilt) - 상하 회전
      let targetTiltAngle = state.pointer.y * (Math.PI / 4) * angleSign + tiltOffset
      const targetQuat = new THREE.Quaternion().setFromAxisAngle(tiltAxis, targetTiltAngle)
      tiltRef.current.quaternion.slerp(targetQuat, 0.08)
    }
  })

  return (
    <group dispose={null}>
      {/* 1. Base - 원본 인벤터 위치(0,0,0)에서 180도 회전 고정 */}
      <group rotation={[0, Math.PI, 0]}>
        <primitive object={base.scene} />
        {showOrigins && <mesh><sphereGeometry args={[0.02]} /><meshBasicMaterial color="white" depthTest={false} transparent opacity={0.5} /></mesh>}
        {showOrigins && <axesHelper args={[0.5]} />}
      </group>
      
      {/* 2. Pan_Axis - 원본 위치(0,0,0)에서 좌우 회전 */}
      <group ref={panRef}>
        <primitive object={pan.scene} />
        {showOrigins && <mesh><sphereGeometry args={[0.03]} /><meshBasicMaterial color="red" depthTest={false} transparent opacity={0.8} /></mesh>}
        {/* 실제 회전에 사용되는 panAxis 변수를 직접 참조하여 녹색 화살표로 렌더링 */}
        {showOrigins && <arrowHelper args={[panAxis, new THREE.Vector3(0,0,0), 1.2, 0x00ff00, 0.2, 0.1]} />}
        
        {/* 3. Tilt_Axis - 사용자님이 찾아주신 정확한 모터축(Y=0.35) 피벗 적용 */}
        <group ref={tiltRef} position={[0, 0.35, 0]}>
          {/* 노란색 구와 큰 축 (회전 중심) */}
          {showOrigins && <mesh><sphereGeometry args={[0.04]} /><meshBasicMaterial color="yellow" depthTest={false} transparent opacity={0.9} /></mesh>}
          {/* 실제 회전에 사용되는 tiltAxis 변수를 직접 참조하여 파란색 화살표로 렌더링 */}
          {showOrigins && <arrowHelper args={[tiltAxis, new THREE.Vector3(0,0,0), 1.0, 0x0000ff, 0.2, 0.1]} />}
          
          <group position={[0, -0.35, 0]}>
            <primitive object={tilt.scene} />
          </group>
        </group>
      </group>
    </group>
  )
}

export default function SimulationViewer() {
  const [axisZ, setAxisZ] = useState(1); 
  const [angleSign, setAngleSign] = useState(1); // 1 (정방향), -1 (역방향)
  const [panSign, setPanSign] = useState(1); // 마우스 방향 일치
  const [panOffset, setPanOffset] = useState(-Math.PI * 0.75); // 1축 영점 -135도 교정
  const [tiltOffset, setTiltOffset] = useState(-20 * (Math.PI / 180)); // 2축 영점 -20도 교정
  const [showOrigins, setShowOrigins] = useState(false);
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  
  // 마우스 타겟 UI를 위한 좌표 상태
  const [mousePos, setMousePos] = useState({ x: -100, y: -100 });

  return (
    <div 
      className="viewer-container" 
      style={{ width: '100%', height: '100%', position: 'relative', cursor: 'none' }}
      onPointerMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
    >
      <Canvas
        camera={{ position: [0, 1.2, 2.5], fov: 45 }}
        shadows
        dpr={[1, 2]}
      >
        <color attach="background" args={['#0b0f19']} />
        
        <ambientLight intensity={0.6} />
        <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow shadow-mapSize={[1024, 1024]} />
        <spotLight position={[-5, 5, 5]} angle={0.3} penumbra={1} intensity={1} color="#00ffaa" />
        
        <Suspense fallback={null}>
          <TrackingModel 
            axisZ={axisZ}
            angleSign={angleSign} 
            panSign={panSign}
            panOffset={panOffset}
            tiltOffset={tiltOffset}
            showOrigins={showOrigins}
          />
          <Environment preset="city" />
          <ContactShadows position={[0, -1.5, 0]} opacity={0.5} scale={10} blur={2} far={4} color="#000000" />
        </Suspense>

        <OrbitControls 
          enablePan={true} 
          enableZoom={true}
          minDistance={2}
          maxDistance={8}
          mouseButtons={{
            LEFT: THREE.MOUSE.NONE, 
            MIDDLE: THREE.MOUSE.DOLLY, 
            RIGHT: THREE.MOUSE.ROTATE 
          }}
        />
      </Canvas>

      {/* 정밀 튜닝 UI 패널 */}
      <div className={`absolute top-20 right-6 bg-black/80 backdrop-blur-md rounded-2xl border border-brand-neon/50 text-white shadow-2xl pointer-events-auto transition-all duration-300 ${isPanelOpen ? 'w-80 p-4' : 'w-12 h-12 flex items-center justify-center cursor-pointer'}`}>
        {!isPanelOpen ? (
          <button onClick={() => setIsPanelOpen(true)} className="w-full h-full font-bold text-brand-neon hover:scale-110 transition-transform">⚙️</button>
        ) : (
          <>
            <div className="flex justify-between items-center mb-3 border-b border-brand-neon/30 pb-2">
              <h4 className="font-bold text-brand-neon text-sm flex items-center gap-2">
                시선 추적(Tracking) 정밀 튜닝
              </h4>
              <button onClick={() => setIsPanelOpen(false)} className="text-gray-400 hover:text-white transition-colors">✕</button>
            </div>
            
            <div className="flex flex-col gap-4">
              <button 
                onClick={() => setShowOrigins(!showOrigins)}
                className="w-full py-2 rounded-lg font-bold text-xs transition-colors bg-brand-surface border border-gray-500 hover:bg-gray-700"
              >
                {showOrigins ? '👀 원점(구슬/축) 숨기기' : '🔍 원점(구슬/축) 보이기'}
              </button>

              <div className="p-3 bg-white/5 rounded-lg border border-red-400/30">
                <h5 className="text-xs font-bold mb-3 text-red-400">1축 (Pan / 좌우) 튜닝</h5>
                <label className="text-[10px] flex justify-between mb-1 text-gray-300">
                  영점(정면) 교정 <span>{Math.round(panOffset * (180 / Math.PI))}도</span>
                </label>
                <input 
                  type="range" min={-Math.PI} max={Math.PI} step="0.01" 
                  value={panOffset} onChange={e => setPanOffset(parseFloat(e.target.value))} 
                  className="w-full accent-red-400 mb-3" 
                />
                <button 
                  onClick={() => setPanSign(panSign === 1 ? -1 : 1)}
                  className={`w-full py-1.5 rounded text-xs font-bold ${panSign === 1 ? 'bg-red-500/20 text-red-300 border border-red-500/50' : 'bg-red-500 text-white'}`}
                >
                  좌우 반전 (현재: {panSign === 1 ? '정방향' : '역방향'})
                </button>
              </div>

              <div className="p-3 bg-white/5 rounded-lg border border-blue-400/30">
                <h5 className="text-xs font-bold mb-3 text-blue-400">2축 (Tilt / 상하) 튜닝</h5>
                <label className="text-[10px] flex justify-between mb-1 text-gray-300">
                  영점(정면) 교정 <span>{Math.round(tiltOffset * (180 / Math.PI))}도</span>
                </label>
                <input 
                  type="range" min={-Math.PI} max={Math.PI} step="0.01" 
                  value={tiltOffset} onChange={e => setTiltOffset(parseFloat(e.target.value))} 
                  className="w-full accent-blue-400 mb-3" 
                />
                <button 
                  onClick={() => setAxisZ(axisZ === 1 ? -1 : 1)}
                  className="w-full py-1.5 rounded text-xs font-bold mb-2 bg-blue-500/20 text-blue-300 border border-blue-500/50 hover:bg-blue-500/40"
                >
                  대각선 축: {axisZ === 1 ? '(1, 0, 1)' : '(1, 0, -1)'}
                </button>
                <button 
                  onClick={() => setAngleSign(angleSign === 1 ? -1 : 1)}
                  className={`w-full py-1.5 rounded text-xs font-bold ${angleSign === 1 ? 'bg-blue-500/20 text-blue-300 border border-blue-500/50' : 'bg-blue-500 text-white'}`}
                >
                  상하 반전 (현재: {angleSign === 1 ? '정방향' : '역방향'})
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* 마우스 주변 타겟팅 시각 효과 (텍스트 없음) */}
      <div 
        className="pointer-events-none fixed z-50 flex items-center justify-center transition-opacity duration-200"
        style={{ 
          left: mousePos.x, top: mousePos.y, 
          transform: 'translate(-50%, -50%)',
          width: '60px', height: '60px',
          opacity: mousePos.x < 0 ? 0 : 1
        }}
      >
        <div className="absolute w-full h-full border-2 border-brand-neon rounded-full animate-ping opacity-30"></div>
        <div className="absolute w-full h-full border-[3px] border-brand-neon rounded-full opacity-60" style={{ borderStyle: 'dashed' }}></div>
        <div className="absolute w-2 h-2 bg-brand-neon rounded-full shadow-[0_0_10px_#00ffaa]"></div>
        {/* 과녁 십자선 */}
        <div className="absolute w-full h-[2px] bg-brand-neon/60"></div>
        <div className="absolute h-full w-[2px] bg-brand-neon/60"></div>
      </div>
    </div>
  )
}
