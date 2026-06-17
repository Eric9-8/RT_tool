# GS3D Map Alignment Editor

RT_tool 用于调试 `gs3d.json` 的 RT 矩阵，通过可视化地图和 GS 点云来评估 aiSim 中的对齐情况。

一个面向局域网共享的地图基准 GS3D 对齐工具。它会直接读取地图/GS3D 工作区目录，解析其中的 `GeoPackage/*.gpkg`、`gs3d.json`，并在存在 `map.json + Meshes/*.gltf` 时额外显示地图网格层；没有 `map.json` 时会进入轻量语义模式，只显示 GPKG 语义层、GS 点云和坐标系参考，并导出回标准 `gs3d.json`。

## 目录

- `backend/`: FastAPI API、地图工作区加载、GeoPackage 解析、坐标转换与导出逻辑
- `frontend/`: React + Three.js 对齐界面
- `shared/testdata/`: 前后端共享的数学一致性样例
- `tests/backend/`: 后端单元与接口测试

## 启动

首次安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PATH=/home/jialiang/.nvm/versions/node/v20.19.6/bin:$PATH npm --prefix frontend install
```

一键启动后端和前端：

```bash
./scripts/dev.sh
```

工作流：

```bash
1. 启动后端和前端
2. 在页面左侧输入地图/GS3D 工作区目录
3. 加载工作区后选择 block
4. 通过 yaw / pitch / roll / dx / dy / dz 微调
5. 导出对齐后的 gs3d.json
```

支持两种目录结构：

完整地图工作区：

```text
reconstruct_map_with_georef/
├── map.json
├── Meshes/
├── GeoPackage/
├── GS3D/
└── gs3d.json
```

轻量三件套工作区：

```text
some_gs3d_map/
├── GeoPackage/
├── GS3D/
│   └── full.ply
└── gs3d.json
```

`GeoPackage/*.gpkg` 里的 `MapInfo.ProjectionString` 始终是地图坐标系的权威来源。`map.json` 只用于完整模式下的可选 mesh 图层；如果 `gs3d.json.filename` 指向了其他地图名，但当前目录存在 `GS3D/full.ply`，工具会明确给出 warning 并使用本地资产。

默认访问：

- 前端 `http://127.0.0.1:5173`
- 后端 `http://127.0.0.1:8000`

启动约定：

- `scripts/dev.sh` 是本项目推荐的本地开发启动入口。
- 后端通过 `.venv/bin/python RT_tool.py` 启动 FastAPI。
- 前端通过 Node 18+ 启动 Vite；当前脚本会优先使用 `/home/jialiang/.nvm/versions/node/v20.19.6/bin`。
- 如需调整后端监听地址，可在启动前设置 `BACKEND_HOST` / `BACKEND_PORT`。
- 之后任何涉及端口、后端入口、前端启动方式或代理方式的改动，都要同步更新 `scripts/dev.sh` 和 `docs/architecture.md`。

## 测试

后端：

```bash
timeout 60s .venv/bin/python -m unittest discover -s tests/backend
```

前端：

```bash
PATH=/home/jialiang/.nvm/versions/node/v20.19.6/bin:$PATH npm --prefix frontend test
```
