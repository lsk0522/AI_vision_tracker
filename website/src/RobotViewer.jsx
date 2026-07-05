import React, { Suspense, useRef } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, useGLTF, Bounds, useBounds, Center, Environment, ContactShadows, Grid } from '@react-three/drei'

// 모델 로드 및 애니메이션
function Model({ url }) {
  const { scene } = useGLTF(url)
  const group = useRef()

  // 모델 질감(텍스처) 이쁘게 업그레이드 및 모서리 선명도(외곽선) 향상
  React.useEffect(() => {
    scene.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
        
        if (child.material) {
          // 공유 재질 문제를 방지하기 위해 복제해서 독립 적용
          child.material = child.material.clone();
          
          const r = Math.round(child.material.color.r * 255);
          const g = Math.round(child.material.color.g * 255);
          const b = Math.round(child.material.color.b * 255);
          
          // 아크릴/유리 패널 감지 (푸른빛이 도는 회색 또는 매우 밝은 회색)
          if ((r > 150 && g > 150 && b > 170) || (r > 170 && g > 170 && b > 170 && Math.abs(r-b) < 10)) {
            child.material.transparent = true;
            child.material.opacity = 0.25; // 투명하게
            child.material.roughness = 0.05; // 유리처럼 매끄럽게
            child.material.metalness = 0.2;
            child.material.depthWrite = false; // 렌더링 겹침 방지
          } 
          // 고무 발, 검정색 모터 등 감지 (어두운 색)
          else if (r < 80 && g < 80 && b < 80) {
            child.material.color.setHex(0x1a1a1a); // 확실한 검은색
            child.material.roughness = 0.9; // 고무 질감
            child.material.metalness = 0.0;
          } 
          // 나머지 금속 부품
          else {
            child.material.roughness = 0.5; 
            child.material.metalness = 0.4; 
          }
          
          child.material.needsUpdate = true;
        }

        // 모서리(Edge) 음영선 추가 (형태가 또렷하게 보이게)
        if (!child.userData.hasEdges) {
          const edges = new THREE.EdgesGeometry(child.geometry, 15);
          const line = new THREE.LineSegments(
            edges, 
            new THREE.LineBasicMaterial({ color: 0x111111, linewidth: 1 }) // 완전 선명한 검은색
          );
          child.add(line);
          child.userData.hasEdges = true;
        }
      }
    })
  }, [scene])

  useFrame((state) => {
    if (group.current) {
      const t = state.clock.getElapsedTime()
      group.current.rotation.y = Math.sin(t / 5) * 0.3
      group.current.position.y = Math.sin(t / 2) * 0.05
    }
  })

  return (
    <group ref={group} dispose={null}>
      <Center>
        <primitive object={scene} />
      </Center>
    </group>
  )
}

// Bounds 내부에서 자동 카메라 맞춤을 트리거하는 컴포넌트
function AutoFit() {
  const bounds = useBounds()
  React.useEffect(() => {
    // 모델 로드 후 카메라를 모델 전체가 보이도록 자동 조정
    bounds.refresh().fit()
  }, [bounds])
  return null
}

export default function RobotViewer() {
  return (
    <div className="viewer-container" style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        shadows
        gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }}
        camera={{ position: [8, 8, 8], fov: 45, near: 0.01, far: 1000 }}
        style={{ width: '100%', height: '100%', display: 'block', background: '#f0f2f5' }}
        dpr={window.devicePixelRatio ? Math.min(2, window.devicePixelRatio) : 2}
      >
        <ambientLight intensity={0.5} />
        <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} intensity={1} castShadow />
        <pointLight position={[-10, -10, -10]} intensity={0.5} />

        <Suspense fallback={null}>
          <Bounds fit clip observe margin={1.2}>
            <Model url={`${import.meta.env.BASE_URL}robot.glb`} />
            <AutoFit />
          </Bounds>

          {/* 스튜디오 환경 맵 (금속 재질의 광택과 반사를 현실감 있게 만들어줌) */}
          <Environment preset="city" />

          {/* 바닥 그림자 (공중에 떠있는 모델 아래에 자연스러운 그림자 생성) */}
          <ContactShadows position={[0, -1.5, 0]} opacity={0.4} scale={10} blur={2} far={4} />

          {/* 바닥 그리드 (허전한 느낌을 없애고 전문적인 엔지니어링 툴 느낌 추가) */}
          <Grid
            position={[0, -1.5, 0]}
            args={[20, 20]}
            cellSize={0.5}
            cellThickness={1}
            cellColor="#6f7a8b"
            sectionSize={2.5}
            sectionThickness={1.5}
            sectionColor="#3f4a5b"
            fadeDistance={25}
            fadeStrength={1}
          />
        </Suspense>

        <OrbitControls
          enablePan={false}
          enableZoom={true}
          autoRotate={true}
          autoRotateSpeed={0.5}
          minPolarAngle={Math.PI / 6}
          maxPolarAngle={Math.PI / 1.8}
        />
      </Canvas>
    </div>
  )
}

useGLTF.preload(`${import.meta.env.BASE_URL}robot.glb`)
