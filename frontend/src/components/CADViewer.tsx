import React, { useRef, useState, useCallback, Suspense, useMemo, useEffect } from 'react';
import { Canvas, ThreeEvent, useThree } from '@react-three/fiber';
import { OrbitControls, Grid, GizmoHelper, GizmoViewport } from '@react-three/drei';
import * as THREE from 'three';
import useCADStore from '../store/cadStore';
import type { MeshData } from '../types/cad';

// ------------------------------------------------------------------ //
// CAD Mesh component                                                   //
// ------------------------------------------------------------------ //

interface CADMeshProps {
  meshData: MeshData;
  wireframe: boolean;
  onContextMenu: (e: ThreeEvent<MouseEvent>) => void;
}

function CADMesh({ meshData, wireframe, onContextMenu }: CADMeshProps) {
  const geometry = React.useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const verts = new Float32Array(meshData.vertices.flat());
    geo.setAttribute('position', new THREE.BufferAttribute(verts, 3));
    const faces = new Uint32Array(meshData.faces.flat());
    geo.setIndex(new THREE.BufferAttribute(faces, 1));
    if (meshData.normals.length > 0) {
      const norms = new Float32Array(meshData.normals.flat());
      geo.setAttribute('normal', new THREE.BufferAttribute(norms, 3));
    } else {
      geo.computeVertexNormals();
    }
    geo.computeBoundingBox();
    return geo;
  }, [meshData]);

  return (
    <group>
      <mesh
        geometry={geometry}
        castShadow
        receiveShadow
        onContextMenu={onContextMenu}
      >
        <meshStandardMaterial
          color="#5AAED8"
          metalness={0.25}
          roughness={0.45}
          side={THREE.DoubleSide}
          wireframe={wireframe}
        />
      </mesh>
      {wireframe && (
        <mesh geometry={geometry}>
          <meshBasicMaterial color="#7BBBD8" wireframe transparent opacity={0.3} />
        </mesh>
      )}
    </group>
  );
}

// ------------------------------------------------------------------ //
// Axis lines (X=red, Y=green, Z=blue)                                 //
// ------------------------------------------------------------------ //

function AxisLines() {
  const len = 50;
  return (
    <group>
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[new Float32Array([0,0,0, len,0,0]), 3]}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#FF4444" />
      </line>
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[new Float32Array([0,0,0, 0,len,0]), 3]}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#44FF44" />
      </line>
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[new Float32Array([0,0,0, 0,0,len]), 3]}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#4444FF" />
      </line>
    </group>
  );
}

// ------------------------------------------------------------------ //
// Measurement tool                                                     //
// ------------------------------------------------------------------ //

interface MeasurePoint {
  x: number; y: number; z: number;
}

interface MeasurementOverlayProps {
  points: MeasurePoint[];
}

function MeasurementLine({ points }: MeasurementOverlayProps) {
  if (points.length < 2) return null;
  const p0 = points[0];
  const p1 = points[1];
  const verts = new Float32Array([p0.x,p0.y,p0.z, p1.x,p1.y,p1.z]);
  const mid = { x:(p0.x+p1.x)/2, y:(p0.y+p1.y)/2, z:(p0.z+p1.z)/2 };
  return (
    <group>
      <line>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[verts, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#FFFF00" linewidth={2} />
      </line>
      <mesh position={[mid.x, mid.y, mid.z]}>
        <sphereGeometry args={[0.5]} />
        <meshBasicMaterial color="#FFFF00" />
      </mesh>
      <group position={[p0.x, p0.y, p0.z]}>
        <mesh><sphereGeometry args={[1]}/><meshBasicMaterial color="#FF8C00"/></mesh>
      </group>
      <group position={[p1.x, p1.y, p1.z]}>
        <mesh><sphereGeometry args={[1]}/><meshBasicMaterial color="#FF8C00"/></mesh>
      </group>
    </group>
  );
}

// ------------------------------------------------------------------ //
// Camera controller — handles fit-to-view inside canvas              //
// ------------------------------------------------------------------ //

interface CameraControllerProps {
  fitTrigger: number;
  modelBounds: ModelBounds | null;
  orbitRef: React.MutableRefObject<any>;
}

// Distance multiplier used to position the camera relative to the model's
// largest dimension when fitting the view.
const CAMERA_DISTANCE_MULTIPLIER = 1.8;

function CameraController({ fitTrigger, modelBounds, orbitRef }: CameraControllerProps) {
  const { camera } = useThree();

  useEffect(() => {
    if (!fitTrigger || !modelBounds) return;
    const { center, size } = modelBounds;
    const maxDim = Math.max(...size);
    const dist = maxDim * CAMERA_DISTANCE_MULTIPLIER;
    camera.position.set(center[0] + dist, center[1] - dist, center[2] + dist);
    camera.lookAt(center[0], center[1], center[2]);
    if (orbitRef.current) {
      orbitRef.current.target.set(center[0], center[1], center[2]);
      orbitRef.current.update();
    }
  // fitTrigger is the only value that should trigger re-runs;
  // camera and orbitRef are stable refs and modelBounds is passed in
  // only to be read within the effect — not to trigger it again.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitTrigger]);

  return null;
}

// ------------------------------------------------------------------ //
// Scene component (needs useThree)                                    //
// ------------------------------------------------------------------ //

interface ModelBounds {
  min: number[];
  max: number[];
  center: number[];
  size: number[];
}

interface SceneProps {
  meshData: MeshData | undefined;
  wireframe: boolean;
  measureMode: boolean;
  showGrid: boolean;
  onContextMenu: (e: ThreeEvent<MouseEvent>, worldPos: THREE.Vector3) => void;
  measurePoints: MeasurePoint[];
  onMeasureClick: (pos: MeasurePoint) => void;
  fitTrigger: number;
  modelBounds: ModelBounds | null;
  orbitRef: React.MutableRefObject<any>;
}

function Scene({
  meshData, wireframe, measureMode, showGrid,
  onContextMenu, measurePoints, onMeasureClick,
  fitTrigger, modelBounds, orbitRef,
}: SceneProps) {
  const handleCanvasClick = useCallback((e: ThreeEvent<MouseEvent>) => {
    if (!measureMode) return;
    onMeasureClick({ x: e.point.x, y: e.point.y, z: e.point.z });
  }, [measureMode, onMeasureClick]);

  return (
    <>
      {/* SW dark-mode viewport background */}
      <color attach="background" args={['#0F1820']} />

      <ambientLight intensity={0.5} />
      <directionalLight position={[50, 50, 80]} intensity={1} castShadow />
      <directionalLight position={[-30, -30, 40]} intensity={0.3} />

      {showGrid && (
        <Grid
          args={[200, 200]}
          cellSize={10}
          cellThickness={0.5}
          cellColor="#555"
          sectionSize={50}
          sectionThickness={1}
          sectionColor="#888"
          fadeDistance={300}
          position={[0, 0, 0]}
        />
      )}

      <AxisLines />

      {meshData && (
        <CADMesh
          meshData={meshData}
          wireframe={wireframe}
          onContextMenu={(e) => {
            e.stopPropagation();
            onContextMenu(e, e.point);
          }}
        />
      )}

      {measureMode && <MeasurementLine points={measurePoints} />}

      {measureMode && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} onClick={handleCanvasClick} visible={false}>
          <planeGeometry args={[1000, 1000]} />
          <meshBasicMaterial />
        </mesh>
      )}

      <OrbitControls ref={orbitRef} makeDefault enableDamping dampingFactor={0.05} />
      <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
        <GizmoViewport axisColors={['#FF4444', '#44FF44', '#4444FF']} labelColor="white" />
      </GizmoHelper>

      <CameraController fitTrigger={fitTrigger} modelBounds={modelBounds} orbitRef={orbitRef} />
    </>
  );
}

// ------------------------------------------------------------------ //
// Main CADViewer                                                       //
// ------------------------------------------------------------------ //

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  worldPos: THREE.Vector3;
}

export const CADViewer: React.FC = () => {
  const { currentModel, wireframe, showGrid, measureMode, toggleWireframe, toggleGrid, toggleMeasureMode, exportModel } = useCADStore();
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false, x: 0, y: 0, worldPos: new THREE.Vector3()
  });
  const [measurePoints, setMeasurePoints] = useState<MeasurePoint[]>([]);
  const [measureDist, setMeasureDist] = useState<number | null>(null);
  const [fitTrigger, setFitTrigger] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const orbitRef = useRef<any>(null);

  // Compute bounding box from mesh vertices
  const modelBounds = useMemo<ModelBounds | null>(() => {
    const verts = currentModel?.mesh_data?.vertices;
    if (!verts?.length) return null;
    const mn = [Infinity, Infinity, Infinity];
    const mx = [-Infinity, -Infinity, -Infinity];
    for (const v of verts) {
      for (let i = 0; i < 3; i++) {
        if (v[i] < mn[i]) mn[i] = v[i];
        if (v[i] > mx[i]) mx[i] = v[i];
      }
    }
    const center = mn.map((v, i) => (v + mx[i]) / 2);
    const size = mn.map((v, i) => mx[i] - v);
    return { min: mn, max: mx, center, size };
  }, [currentModel?.mesh_data]);

  // Auto fit when a new model loads
  useEffect(() => {
    if (modelBounds) setFitTrigger((n) => n + 1);
  }, [modelBounds]);

  const handleContextMenu = useCallback((e: ThreeEvent<MouseEvent>, worldPos: THREE.Vector3) => {
    const nativeEvent = e.nativeEvent as MouseEvent;
    setContextMenu({ visible: true, x: nativeEvent.clientX, y: nativeEvent.clientY, worldPos });
  }, []);

  const handleMeasureClick = useCallback((pos: MeasurePoint) => {
    setMeasurePoints((prev) => {
      if (prev.length >= 2) {
        setMeasureDist(null);
        return [pos];
      }
      const next = [...prev, pos];
      if (next.length === 2) {
        const d = Math.sqrt((next[1].x-next[0].x)**2+(next[1].y-next[0].y)**2+(next[1].z-next[0].z)**2);
        setMeasureDist(Math.round(d * 100) / 100);
      }
      return next;
    });
  }, []);

  const closeContextMenu = () => setContextMenu((s) => ({ ...s, visible: false }));

  return (
    <div ref={containerRef} className="relative w-full h-full bg-zinc-950 overflow-hidden"
      onClick={closeContextMenu}>

      {/* Toolbar */}
      <div className="absolute top-2 left-2 z-10 flex gap-1 flex-wrap">
        <button onClick={toggleWireframe}
          className={wireframe ? 'toolbar-btn-active' : 'toolbar-btn'}>
          Wireframe
        </button>
        <button onClick={toggleGrid}
          className={showGrid ? 'toolbar-btn-active' : 'toolbar-btn'}>
          Grid
        </button>
        <button onClick={() => { toggleMeasureMode(); setMeasurePoints([]); setMeasureDist(null); }}
          className={measureMode ? 'toolbar-btn-warn' : 'toolbar-btn'}>
          Measure
        </button>
        <button
          onClick={() => setFitTrigger((n) => n + 1)}
          disabled={!modelBounds}
          title="Fit model to view"
          className="toolbar-btn disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Fit View
        </button>
      </div>

      {/* Quick export buttons */}
      {currentModel && (
        <div className="absolute top-2 right-2 z-10 flex gap-1">
          {(['stl', 'obj', 'step'] as const).map((fmt) => (
            <button
              key={fmt}
              onClick={() => exportModel(fmt, currentModel.id)}
              title={`Export ${fmt.toUpperCase()}`}
              className="toolbar-btn"
            >
              ↓ {fmt.toUpperCase()}
            </button>
          ))}
        </div>
      )}

      {/* Measure distance display */}
      {measureDist !== null && (
        <div className="absolute top-10 right-2 z-10 bg-mc-900/90 border border-mc-600 rounded-sm px-3 py-1 text-sm text-mc-300">
          Distance: <strong>{measureDist} mm</strong>
        </div>
      )}

      {/* Measure instructions */}
      {measureMode && !measureDist && (
        <div className="absolute top-10 right-2 z-10 bg-zinc-800/90 border border-zinc-600 rounded-sm px-3 py-1 text-xs text-zinc-400">
          {measurePoints.length === 0 ? 'Click first point' : 'Click second point'}
        </div>
      )}

      {/* No model placeholder */}
      {!currentModel?.mesh_data && (
        <div className="absolute inset-0 flex items-center justify-center text-zinc-600 pointer-events-none">
          <div className="text-center">
            <svg className="w-16 h-16 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            <p className="text-lg">No model loaded</p>
            <p className="text-sm mt-1">Describe a part and click Generate</p>
          </div>
        </div>
      )}

      <Canvas
        shadows
        camera={{ position: [80, -80, 80], fov: 45, near: 0.1, far: 10000 }}
        gl={{ antialias: true }}
      >
        <Suspense fallback={null}>
          <Scene
            meshData={currentModel?.mesh_data}
            wireframe={wireframe}
            measureMode={measureMode}
            showGrid={showGrid}
            onContextMenu={handleContextMenu}
            measurePoints={measurePoints}
            onMeasureClick={handleMeasureClick}
            fitTrigger={fitTrigger}
            modelBounds={modelBounds}
            orbitRef={orbitRef}
          />
        </Suspense>
      </Canvas>

      {/* Model info overlay — SW-style info panel */}
      {currentModel?.mesh_data && (
        <div className="absolute bottom-8 left-2 z-10 bg-zinc-800/90 border border-zinc-600 rounded-sm px-3 py-2 text-xs text-zinc-400 backdrop-blur-sm max-w-[220px]">
          <p className="text-zinc-200 font-semibold truncate">{currentModel.name}</p>
          <p className="mt-0.5 text-zinc-400">
            {currentModel.mesh_data.vertex_count.toLocaleString()} verts &middot;{' '}
            {currentModel.mesh_data.face_count.toLocaleString()} faces
          </p>
          {modelBounds && (
            <p className="mt-0.5 font-mono text-zinc-500">
              {modelBounds.size[0].toFixed(1)} &times; {modelBounds.size[1].toFixed(1)} &times; {modelBounds.size[2].toFixed(1)} mm
            </p>
          )}
        </div>
      )}

      {/* Context Menu */}
      {contextMenu.visible && (
        <ContextMenuOverlay
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={closeContextMenu}
          modelId={currentModel?.id}
        />
      )}
    </div>
  );
};

// Inline context menu to avoid circular import
interface ContextMenuOverlayProps {
  x: number; y: number;
  onClose: () => void;
  modelId?: string;
}

function ContextMenuOverlay({ x, y, onClose, modelId }: ContextMenuOverlayProps) {
  const { exportModel, exportGCode } = useCADStore();
  const items = [
    { label: '↓ Export STL', action: () => modelId && exportModel('stl', modelId) },
    { label: '↓ Export OBJ', action: () => modelId && exportModel('obj', modelId) },
    { label: '↓ Export STEP', action: () => modelId && exportModel('step', modelId) },
    { label: '⚙ CNC G-code', action: () => modelId && exportGCode('cnc', modelId) },
    { label: '🖨 3D Print G-code', action: () => modelId && exportGCode('3dprint', modelId) },
    { label: '🔴 Laser G-code', action: () => modelId && exportGCode('laser', modelId) },
  ];
  return (
    <div
      className="fixed z-50 bg-zinc-800 border border-zinc-600 rounded-sm shadow-2xl py-1 min-w-[180px]"
      style={{ left: x, top: y }}
      onClick={(e) => e.stopPropagation()}
    >
      {items.map((item) => (
        <button
          key={item.label}
          onClick={() => { item.action(); onClose(); }}
          className="block w-full text-left px-4 py-1.5 text-xs text-zinc-300 hover:bg-sky-600 hover:text-white transition-colors"
        >
          {item.label}
        </button>
      ))}
      <div className="border-t border-zinc-600 mt-1 pt-1">
        <button onClick={onClose}
          className="block w-full text-left px-4 py-1.5 text-xs text-zinc-500 hover:bg-zinc-700 hover:text-zinc-300 transition-colors">
          Close
        </button>
      </div>
    </div>
  );
}

export default CADViewer;

