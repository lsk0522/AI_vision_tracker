import React, { Suspense, useRef } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, useGLTF, Bounds, useBounds, Center } from '@react-three/drei'

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
          // 원래 색상 유지 및 선명도만 살짝 조정
          child.material.roughness = 0.4; 
          child.material.metalness = 0.4; 
          child.material.needsUpdate = true;
        }

        // 모서리(Edge) 음영선 추가 (형태가 또렷하게 보이게)
        if (!child.userData.hasEdges) {
          const edges = new THREE.EdgesGeometry(child.geometry, 15);
          const line = new THREE.LineSegments(
            edges, 
            new THREE.LineBasicMaterial({ color: 0x222222, linewidth: 1, transparent: true, opacity: 0.5 })
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
        {/* 부드러운 주변광 */}
        <ambientLight intensity={0.5} color="#ffffff" />
        
        {/* 주 조명 (따뜻한 톤, 그림자 생성) */}
        <directionalLight 
          castShadow 
          position={[10, 15, 10]} 
          intensity={1.8} 
          color="#fff8eb" 
          shadow-mapSize={[2048, 2048]} 
        />
        
        {/* 보조 조명 (차가운 톤, 반대편에서 모델 음영 완화) */}
        <directionalLight position={[-10, 10, 10]} intensity={0.8} color="#e0f2fe" />
        
        {/* 림 라이트 (모델 뒤쪽에서 윤곽선 강조) */}
        <directionalLight position={[0, 10, -10]} intensity={1.2} color="#ffffff" />

        <Suspense fallback={null}>
          {/*
            Bounds: 자식 객체의 바운딩 박스를 계산해서
            카메라가 모델 전체를 화면에 꽉 맞게(margin=1.2배 여유) 자동 배치
            clip=true: 카메라 near/far도 자동 조정 → clipping 문제 원천 차단
          */}
          <Bounds fit clip observe margin={1.4}>
            <Model url={`${import.meta.env.BASE_URL}robot.glb`} />
            <AutoFit />
          </Bounds>
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
