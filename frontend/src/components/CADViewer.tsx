import React, { useRef, useState, useCallback, Suspense } from 'react';
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
          color="#4DA6FF"
          metalness={0.3}
          roughness={0.4}
          side={THREE.DoubleSide}
          wireframe={wireframe}
        />
      </mesh>
      {wireframe && (
        <mesh geometry={geometry}>
          <meshBasicMaterial color="#88CCFF" wireframe transparent opacity={0.3} />
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
  const dist = Math.sqrt(
    (p1.x-p0.x)**2 + (p1.y-p0.y)**2 + (p1.z-p0.z)**2
  );
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
      {/* Distance label via sprite would go here in production */}
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
// Scene component (needs useThree)                                    //
// ------------------------------------------------------------------ //

interface SceneProps {
  meshData: MeshData | undefined;
  wireframe: boolean;
  measureMode: boolean;
  showGrid: boolean;
  onContextMenu: (e: ThreeEvent<MouseEvent>, worldPos: THREE.Vector3) => void;
  measurePoints: MeasurePoint[];
  onMeasureClick: (pos: MeasurePoint) => void;
}

function Scene({
  meshData, wireframe, measureMode, showGrid,
  onContextMenu, measurePoints, onMeasureClick
}: SceneProps) {
  const { camera } = useThree();

  const handleCanvasClick = useCallback((e: ThreeEvent<MouseEvent>) => {
    if (!measureMode) return;
    onMeasureClick({ x: e.point.x, y: e.point.y, z: e.point.z });
  }, [measureMode, onMeasureClick]);

  return (
    <>
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

      {/* Invisible ground plane for measure click detection */}
      {measureMode && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} onClick={handleCanvasClick} visible={false}>
          <planeGeometry args={[1000, 1000]} />
          <meshBasicMaterial />
        </mesh>
      )}

      <OrbitControls makeDefault enableDamping dampingFactor={0.05} />
      <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
        <GizmoViewport axisColors={['#FF4444', '#44FF44', '#4444FF']} labelColor="white" />
      </GizmoHelper>
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
  const { currentModel, wireframe, showGrid, measureMode, toggleWireframe, toggleGrid, toggleMeasureMode } = useCADStore();
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false, x: 0, y: 0, worldPos: new THREE.Vector3()
  });
  const [measurePoints, setMeasurePoints] = useState<MeasurePoint[]>([]);
  const [measureDist, setMeasureDist] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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
    <div ref={containerRef} className="relative w-full h-full bg-zinc-950 rounded-lg overflow-hidden"
      onClick={closeContextMenu}>

      {/* Toolbar */}
      <div className="absolute top-2 left-2 z-10 flex gap-2">
        <button onClick={toggleWireframe}
          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${wireframe ? 'bg-sky-600 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}>
          Wireframe
        </button>
        <button onClick={toggleGrid}
          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${showGrid ? 'bg-sky-600 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}>
          Grid
        </button>
        <button onClick={() => { toggleMeasureMode(); setMeasurePoints([]); setMeasureDist(null); }}
          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${measureMode ? 'bg-amber-600 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}>
          Measure
        </button>
      </div>

      {/* Measure distance display */}
      {measureDist !== null && (
        <div className="absolute top-2 right-2 z-10 bg-amber-900/80 border border-amber-600 rounded px-3 py-1 text-sm text-amber-300">
          Distance: <strong>{measureDist} mm</strong>
        </div>
      )}

      {/* Measure instructions */}
      {measureMode && !measureDist && (
        <div className="absolute top-2 right-2 z-10 bg-zinc-800/80 border border-zinc-600 rounded px-3 py-1 text-xs text-zinc-400">
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
            <p className="text-sm mt-1">Generate a model to view it here</p>
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
          />
        </Suspense>
      </Canvas>

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
  const { exportModel } = useCADStore();
  const items = [
    { label: 'Export STL', action: () => modelId && exportModel('stl', modelId) },
    { label: 'Export OBJ', action: () => modelId && exportModel('obj', modelId) },
    { label: 'Export STEP', action: () => modelId && exportModel('step', modelId) },
  ];
  return (
    <div
      className="fixed z-50 bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl py-1 min-w-[160px]"
      style={{ left: x, top: y }}
      onClick={(e) => e.stopPropagation()}
    >
      {items.map((item) => (
        <button
          key={item.label}
          onClick={() => { item.action(); onClose(); }}
          className="block w-full text-left px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors"
        >
          {item.label}
        </button>
      ))}
      <div className="border-t border-zinc-700 mt-1 pt-1">
        <button onClick={onClose}
          className="block w-full text-left px-4 py-2 text-sm text-zinc-500 hover:bg-zinc-700 hover:text-zinc-300 transition-colors">
          Close
        </button>
      </div>
    </div>
  );
}

export default CADViewer;
