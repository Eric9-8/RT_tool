import { useLoader } from "@react-three/fiber";
import { useMemo } from "react";
import type { BufferGeometry } from "three";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";

import { sceneMatrixFromPose } from "../math";
import type { PoseView } from "../types";

type GsPointCloudProps = {
  assetUrl: string;
  opacity: number;
  pose: PoseView;
  scale: number;
};

export function GsPointCloud(props: GsPointCloudProps) {
  const { assetUrl, opacity, pose, scale } = props;
  const geometry = useLoader(PLYLoader, assetUrl) as BufferGeometry;
  const matrix = useMemo(() => sceneMatrixFromPose(pose, scale), [pose, scale]);
  const hasVertexColors = Boolean(geometry.getAttribute("color"));

  return (
    <points geometry={geometry} matrix={matrix} matrixAutoUpdate={false}>
      <pointsMaterial
        color={hasVertexColors ? "#ffffff" : "#ffd166"}
        opacity={opacity}
        size={0.12}
        sizeAttenuation
        transparent
        vertexColors={hasVertexColors}
      />
    </points>
  );
}
