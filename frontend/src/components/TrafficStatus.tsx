import type { TrafficDataSummary } from "../types";

export function TrafficStatus(props: { trafficSummary: TrafficDataSummary | null }) {
  const { trafficSummary } = props;
  if (!trafficSummary?.exists) {
    return <p className="status">未发现 traffic_data.json。</p>;
  }
  return (
    <p className={trafficSummary.referenceStatus === "preferred" ? "status" : "status status-warning"}>
      traffic routes：{trafficSummary.routeCount}；GPKG 参考层：
      {trafficSummary.referenceLayer ?? "无"}
      {trafficSummary.referenceStatus === "fallback" ? "（缺少 Paths，使用可用参考层）" : ""}
      {trafficSummary.referenceStatus === "missing" ? "（缺少可对比几何层）" : ""}
    </p>
  );
}
