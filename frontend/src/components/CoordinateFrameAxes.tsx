import { Html, Line } from "@react-three/drei";

type CoordinateFrameAxesProps = {
  axisLabels: [string, string, string];
  axes: number[][];
  center: number[];
  colors: [string, string, string];
  label: string;
  length: number;
};

export function CoordinateFrameAxes(props: CoordinateFrameAxesProps) {
  const { axisLabels, axes, center, colors, label, length } = props;
  const anchor = tupleFrom(center);

  return (
    <group>
      {axes.map((axis, index) => (
        <group key={`${label}-${axisLabels[index]}`}>
          <Line color={colors[index]} lineWidth={2.8} points={[anchor, addScaledAxis(anchor, axis, length)]} />
          <Html distanceFactor={8} position={addScaledAxis(anchor, axis, length * 1.08)}>
            <div className="scene-tag">{axisLabels[index]}</div>
          </Html>
        </group>
      ))}
      <Html distanceFactor={8} position={[anchor[0], anchor[1], anchor[2] + length * 0.42]}>
        <div className="scene-tag active">{label}</div>
      </Html>
    </group>
  );
}

function addScaledAxis(anchor: [number, number, number], axis: number[], length: number): [number, number, number] {
  return [anchor[0] + axis[0] * length, anchor[1] + axis[1] * length, anchor[2] + axis[2] * length];
}

function tupleFrom(point: number[]): [number, number, number] {
  return [point[0], point[1], point[2] ?? 0];
}
