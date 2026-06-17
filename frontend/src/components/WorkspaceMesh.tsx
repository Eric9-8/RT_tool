import { useGLTF } from "@react-three/drei";
import { useEffect, useMemo } from "react";
import type { Material, Mesh } from "three";

type WorkspaceMeshProps = {
  assetUrl: string;
  opacity: number;
};

export function WorkspaceMesh(props: WorkspaceMeshProps) {
  const { assetUrl, opacity } = props;
  const gltf = useGLTF(assetUrl);
  const clonedScene = useMemo(() => gltf.scene.clone(true), [gltf.scene]);

  useEffect(() => {
    clonedScene.traverse((object) => {
      const maybeMesh = object as Mesh & { material?: Material | Material[] };
      if (!maybeMesh.material) {
        return;
      }
      const materials = Array.isArray(maybeMesh.material) ? maybeMesh.material : [maybeMesh.material];
      materials.forEach((material) => {
        material.transparent = true;
        material.opacity = opacity;
        material.depthWrite = opacity >= 1;
      });
    });
  }, [clonedScene, opacity]);

  return <primitive object={clonedScene} />;
}
