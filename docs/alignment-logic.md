# 地图与 GS 点云对齐逻辑

本文记录当前工具中地图、GPKG 语义层、GS 点云和 `gs3d.json` 之间的坐标对齐逻辑。这里描述的是当前代码实现，不是历史方案。

## 核心原则

工具以地图坐标系为编辑基准，以 aiSim/GS3D 的 `gs3d.json` row-vector RT 约定为导出基准。

也就是说，用户在前端看到和调整的是“地图系姿态”，但最终导出的仍是 aiSim 可接受的 geocent/ECEF 姿态。

## 工作区模式

当前支持两种工作区：

`full_map`：目录中存在 `map.json`。工具会解析 `map.json` 中的 mesh 清单，并显示 `Meshes/*.gltf` 地图网格层。

`semantic_only`：目录中没有 `map.json`，但存在 `GeoPackage/*.gpkg` 和 `gs3d.json`。工具不会伪造 mesh 层，只显示 GPKG 语义层、GS 点云和坐标系参考。

两种模式下，地图坐标系的权威来源都是 `GeoPackage/*.gpkg` 中 `MapInfo.ProjectionString`。`map.json` 只影响是否有地图网格可视化，不决定坐标转换。

## 坐标系

地图坐标系来自 `MapInfo.ProjectionString`，通常是本地投影坐标系。前端场景中按 `X/East`、`Y/North`、`Z/Up` 解释。

GS 原始坐标系来自 `gs3d.json`，当前假设其 `proj-string` 为 `+proj=geocent`，也就是 ECEF/geocent 坐标。`center` 和 `RT` 的平移行都存储 ECEF 坐标。

前端编辑统一发生在地图坐标系中。用户输入的 `yaw / pitch / roll / dx / dy / dz` 都被解释为地图系下对当前 block 的编辑量。

## aiSim RT 约定

`gs3d.json` 中的 `RT` 是长度 16 的扁平数组，按 4x4 行主序理解：

```text
[ r00, r01, r02, 0,
  r10, r11, r12, 0,
  r20, r21, r22, 0,
  tx,  ty,  tz,  1 ]
```

当前工具按 aiSim/GS3D 的 row-vector 语义解释它：

`RT` 前三行前三列表示局部 `X/Y/Z` 轴在目标坐标系中的方向。

`RT` 最后一行前三个值是平移。

`center` 必须等于 `RT[3][0:3]`。

这点非常关键：它不是常见 Three.js column-vector 的“平移在最后一列”矩阵。前端渲染到 Three.js 时会显式转换，不把 Three.js 矩阵约定反向污染导出逻辑。

## 导入时的自动定位

加载工作区时，后端对每个 GS block 做一次 `geocent -> map` 转换。

平移转换：

```text
ECEF center -> lon/lat/height -> map easting/northing + height
```

旋转转换：

```text
R_map = R_geocent @ ECEF_TO_ENU.T
```

其中 `ECEF_TO_ENU` 的三行分别是当前位置的 `East / North / Up` 基向量在 ECEF 中的方向。

如果一个 `gs3d.json` 本身已经符合 aiSim geocent 姿态约定，那么它转换到地图系后通常会接近单位姿态：局部 X 指向 East，局部 Y 指向 North，局部 Z 指向 Up。

## 前端预览编辑

前端不会直接修改原始 `gs3d.json`。每个 block 都保存一组基于导入姿态的累计 delta：

```text
BlockDelta = { yaw, pitch, roll, dx, dy, dz }
```

旋转顺序为：

```text
yaw(Z) -> pitch(Y) -> roll(X)
R_delta = Rz @ Ry @ Rx
```

在 row-vector 语义下，编辑后的地图系姿态为：

```text
R_new = R_delta @ R_base
T_new = T_base + [dx, dy, dz] @ R_new
center_new = T_new
```

这里的 `dx / dy / dz` 是沿编辑后 GS 局部轴移动，而不是沿世界固定轴移动。这样前端预览和后端导出使用同一套数学语义。

## 导出时的权威计算

导出时，前端只提交每个 block 的 `BlockDelta`。后端重新计算最终结果，后端结果是权威结果。

导出链路为：

```text
导入时 mapPose
  -> apply BlockDelta 得到编辑后的 map RT
  -> map RT 转回 geocent RT
  -> 写回 gs3d.json 的 RT 和 center
```

地图系转回 geocent 时：

```text
R_geocent = R_map @ ECEF_TO_ENU
map center -> lon/lat/height -> ECEF center
```

导出会保留未编辑 block 和其他非姿态字段。被编辑 block 的 `RT` 和 `center` 会同步更新，且仍保持标准 `gs3d.json` 结构。

## 资产加载与显示

GS 点云资产优先按 `gs3d.json.filename` 解析。如果 `filename` 中的 map 名和当前工作区目录名不一致，但当前目录存在 `GS3D/full.ply`，后端会返回 warning，并明确使用本地 `GS3D/full.ply`。

如果既解析不到 `filename`，也找不到本地 `GS3D/full.ply`，则 `assetUrl` 为 `null`。这种情况下仍可编辑姿态和导出，只是不显示 GS 点云资产。

## 显示锚定不影响导出

前端有观察模式，例如“跟随当前 block”和“地图固定到原点并贴地”。这些模式只改变 Three.js 场景中的显示 offset、相机 target 和地面网格位置。

显示锚定不会修改地图坐标、GS 姿态、delta，也不会影响导出的 `RT/center`。它只是为了让用户更容易观察地图和 GS 点云的相对关系。

## 代码位置

后端投影转换：`backend/app/projection.py`

后端 delta 应用：`backend/app/transform.py`

后端工作区加载与导出：`backend/app/workspace.py`

前端预览数学：`frontend/src/math.ts`

前端场景显示：`frontend/src/components/ScenePanel.tsx`
