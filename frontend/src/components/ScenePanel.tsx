import { useEffect, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";

import { Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

import { gridSpec, mapSceneBounds, previewPose, sceneDisplayTransform } from "../math";
import type {
  BlockDelta,
  GsAlignmentView,
  LayerVisibilityState,
  MapFeatureView,
  MapLayerView,
  SceneAnchorMode,
  WorkspaceSceneResponse
} from "../types";
import { ZERO_DELTA } from "../types";
import { CoordinateFrameAxes } from "./CoordinateFrameAxes";
import { GsPointCloud } from "./GsPointCloud";
import { TrafficRoutes } from "./TrafficRoutes";
import { WorkspaceMesh } from "./WorkspaceMesh";

type ScenePanelProps = {
  blocks: GsAlignmentView[];
  deltas: Record<string, BlockDelta>;
  layerState: LayerVisibilityState;
  scene: WorkspaceSceneResponse | null;
  sceneAnchorMode: SceneAnchorMode;
  selectedBlockId: string | null;
};

const AXIS_LENGTH = 16;
const MAP_AXIS_LENGTH = 24;
const CAMERA_OFFSET: [number, number, number] = [42, -42, 32];
const IDENTITY_AXES = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
type SceneControlsRef = MutableRefObject<OrbitControlsImpl | null>;

export function ScenePanel(props: ScenePanelProps) {
  const { blocks, deltas, layerState, scene, sceneAnchorMode, selectedBlockId } = props;
  const selectedBlock = blocks.find((block) => block.blockId === selectedBlockId) ?? null;
  const selectedPreview = selectedBlock
    ? previewPose(selectedBlock.mapPose, deltas[selectedBlock.blockId] ?? ZERO_DELTA)
    : null;
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const bounds = useMemo(() => mapSceneBounds(scene), [scene]);
  const displayTransform = useMemo(
    () => sceneDisplayTransform(bounds, selectedBlock?.mapPose.center ?? null, sceneAnchorMode),
    [bounds, sceneAnchorMode, selectedBlock]
  );
  const grid = useMemo(() => gridSpec(bounds), [bounds]);
  const modeLabel = sceneAnchorMode === "map_origin_grounded" ? "地图固定到原点并贴地" : "跟随当前 block";

  return (
    <section className="panel scene-panel">
      <div className="panel-header">
        <span className="eyebrow">Spatial Console</span>
        <h2>地图基准对齐场景</h2>
        <p className="status">当前观察模式：{modeLabel}。仅影响显示参考，不影响导出结果。</p>
      </div>
      <div className="scene-shell">
        <Canvas camera={{ position: CAMERA_OFFSET, fov: 42 }}>
          <color attach="background" args={["#08131f"]} />
          <SceneViewController controlsRef={controlsRef} orbitTarget={displayTransform.orbitTarget} />
          <ambientLight intensity={0.8} />
          <directionalLight intensity={2.2} position={[40, 30, 18]} />
          <gridHelper
            args={[grid.size, grid.divisions, "#4b5d75", "#1d2b3c"]}
            position={[0, 0, displayTransform.groundZ]}
            rotation={[Math.PI / 2, 0, 0]}
          />
          <OrbitControls enableDamping makeDefault ref={controlsRef} />
          <group position={displayTransform.offset}>
            {layerState.showMeshes ? scene?.meshes.map((mesh) => <WorkspaceMesh assetUrl={mesh.assetUrl} key={mesh.assetUrl} opacity={layerState.meshOpacity} />) : null}
            {scene?.layers.map((layer) =>
              layerState.visibleLayers[layer.name] ? <LayerGeometry key={layer.name} layer={layer} /> : null
            )}
            {layerState.showTrafficRoutes && scene?.trafficRoutes.length ? (
              <TrafficRoutes routes={scene.trafficRoutes} />
            ) : null}
            {blocks.map((block) => (
              <BlockMarker key={block.blockId} block={block} selected={block.blockId === selectedBlockId} />
            ))}
            <CoordinateFrameAxes
              axes={IDENTITY_AXES}
              axisLabels={["East/X", "North/Y", "Up/Z"]}
              center={[0, 0, 0]}
              colors={["#ef476f", "#06d6a0", "#4cc9f0"]}
              label="Map ENU"
              length={MAP_AXIS_LENGTH}
            />
            {selectedBlock ? (
              <CoordinateFrameAxes
                axes={axesFromPose(selectedBlock.mapPose)}
                axisLabels={["GS X", "GS Y", "GS Z"]}
                center={selectedBlock.mapPose.center}
                colors={["#ef476f", "#06d6a0", "#118ab2"]}
                label="GS INIT"
                length={AXIS_LENGTH}
              />
            ) : null}
            {selectedPreview ? (
              <CoordinateFrameAxes
                axes={axesFromPose(selectedPreview)}
                axisLabels={["Edit X", "Edit Y", "Edit Z"]}
                center={selectedPreview.center}
                colors={["#ffd166", "#8ac926", "#4cc9f0"]}
                label="GS EDIT"
                length={AXIS_LENGTH}
              />
            ) : null}
            {selectedBlock && selectedPreview ? (
              <Line
                color="#f4b942"
                lineWidth={1.5}
                points={[selectedBlock.mapPose.center, selectedPreview.center].map((point) => tupleFrom(point))}
              />
            ) : null}
            {selectedBlock && selectedPreview && selectedBlock.assetUrl && layerState.showGsAsset ? (
              <GsPointCloud
                assetUrl={selectedBlock.assetUrl}
                opacity={layerState.gsOpacity}
                pose={selectedPreview}
                scale={selectedBlock.scale}
              />
            ) : null}
          </group>
        </Canvas>
      </div>
    </section>
  );
}

function SceneViewController(props: { controlsRef: SceneControlsRef; orbitTarget: [number, number, number] }) {
  const { controlsRef, orbitTarget } = props;
  const { camera } = useThree();

  useEffect(() => {
    camera.up.set(0, 0, 1);
    camera.position.set(
      orbitTarget[0] + CAMERA_OFFSET[0],
      orbitTarget[1] + CAMERA_OFFSET[1],
      orbitTarget[2] + CAMERA_OFFSET[2]
    );
    camera.lookAt(orbitTarget[0], orbitTarget[1], orbitTarget[2]);
    controlsRef.current?.target.set(orbitTarget[0], orbitTarget[1], orbitTarget[2]);
    controlsRef.current?.update();
  }, [camera, controlsRef, orbitTarget]);

  return null;
}

function LayerGeometry(props: { layer: MapLayerView }) {
  const { layer } = props;
  const color = colorForLayer(layer.name);
  return (
    <group>
      {layer.features.map((feature, index) => (
        <FeatureGeometry color={color} feature={feature} key={`${layer.name}-${index}`} />
      ))}
    </group>
  );
}

function FeatureGeometry(props: { feature: MapFeatureView; color: string }) {
  const { feature, color } = props;
  if (feature.geometryType === "Point" || feature.geometryType === "MultiPoint") {
    return (
      <group>
        {(feature.coordinates as number[][]).map((point, index) => (
          <mesh key={index} position={tupleFrom(point)}>
            <sphereGeometry args={[0.35, 12, 12]} />
            <meshStandardMaterial color={color} />
          </mesh>
        ))}
      </group>
    );
  }
  if (feature.geometryType === "LineString") {
    return <Line color={color} lineWidth={1.6} points={(feature.coordinates as number[][]).map((point) => tupleFrom(point))} />;
  }
  return (
    <group>
      {(feature.coordinates as number[][][]).map((line, index) => (
        <Line color={color} key={index} lineWidth={1.4} points={line.map((point) => tupleFrom(point))} />
      ))}
    </group>
  );
}

function BlockMarker(props: { block: GsAlignmentView; selected: boolean }) {
  const { block, selected } = props;

  return (
    <group position={tupleFrom(block.mapPose.center)}>
      <mesh>
        <sphereGeometry args={[selected ? 1.3 : 0.7, 24, 24]} />
        <meshStandardMaterial color={selected ? "#ffe28a" : "#5ea6ff"} emissive="#1f2a39" />
      </mesh>
      <Html distanceFactor={8} position={[0, 2.2, 0] as [number, number, number]}>
        <div className={selected ? "scene-tag active" : "scene-tag"}>B{block.blockId}</div>
      </Html>
    </group>
  );
}

function tupleFrom(point: number[]): [number, number, number] {
  return [point[0], point[1], point[2] ?? 0];
}

function axesFromPose(pose: { rtMatrix: number[][] }): number[][] {
  return pose.rtMatrix.slice(0, 3).map((row) => row.slice(0, 3));
}

function colorForLayer(layerName: string): string {
  if (layerName === "RoadReferenceLines") {
    return "#f4b942";
  }
  if (layerName === "RoadMarks") {
    return "#b8f2e6";
  }
  if (layerName === "Paths") {
    return "#4cc9f0";
  }
  if (layerName === "StopLines") {
    return "#ffd166";
  }
  if (layerName === "RoadShapes") {
    return "#ff7c7c";
  }
  return "#8fa7c2";
}
