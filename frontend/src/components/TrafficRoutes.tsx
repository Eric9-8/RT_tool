import { Line } from "@react-three/drei";

import type { TrafficRouteView } from "../types";

type TrafficRoutesProps = {
  routes: TrafficRouteView[];
};

const ROUTE_COLOR = "#ff6b35";
const MUTED_ROUTE_COLOR = "#9a5f48";
const ARROW_SPACING = 24;
const MAX_ARROWS_PER_ROUTE = 12;

export function TrafficRoutes(props: TrafficRoutesProps) {
  return (
    <group>
      {props.routes.map((route) => (
        <TrafficRoute key={route.name} route={route} />
      ))}
    </group>
  );
}

function TrafficRoute(props: { route: TrafficRouteView }) {
  const { route } = props;
  const color = route.drivable ? ROUTE_COLOR : MUTED_ROUTE_COLOR;
  return (
    <group>
      <Line color={color} lineWidth={route.drivable ? 2.4 : 1.4} points={route.coordinates.map(tupleFrom)} />
      {arrowPoints(route.coordinates).map((point, index) => (
        <RouteArrow color={color} key={`${route.name}-${index}`} point={point} />
      ))}
    </group>
  );
}

function RouteArrow(props: { point: ArrowPoint; color: string }) {
  const { point, color } = props;
  return (
    <group position={point.position} rotation={[0, 0, point.angle]}>
      <Line color={color} lineWidth={2} points={[[0, 0, 0], [-1.8, 0.8, 0], [-1.8, -0.8, 0], [0, 0, 0]]} />
    </group>
  );
}

type ArrowPoint = {
  position: [number, number, number];
  angle: number;
};

function arrowPoints(points: number[][]): ArrowPoint[] {
  if (points.length < 2) {
    return [];
  }
  const arrows: ArrowPoint[] = [];
  let travelled = 0;
  for (let index = 1; index < points.length; index += 1) {
    const current = points[index];
    const previous = points[index - 1];
    travelled += distance2d(previous, current);
    if (travelled < ARROW_SPACING && index < points.length - 1) {
      continue;
    }
    arrows.push(arrowAt(previous, current));
    travelled = 0;
  }
  return arrows.slice(0, MAX_ARROWS_PER_ROUTE);
}

function arrowAt(previous: number[], current: number[]): ArrowPoint {
  return {
    position: tupleFrom(current),
    angle: Math.atan2(current[1] - previous[1], current[0] - previous[0])
  };
}

function distance2d(left: number[], right: number[]): number {
  return Math.hypot(right[0] - left[0], right[1] - left[1]);
}

function tupleFrom(point: number[]): [number, number, number] {
  return [point[0], point[1], point[2] ?? 0];
}
