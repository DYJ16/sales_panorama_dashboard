# 企业销售全景数据大屏

基于codex开发的 `AdventureWorksDW` 数仓的企业销售全景仪表盘，面向销售管理、经营分析和课程答辩展示场景。项目采用 FastAPI 后端、SQL Server 查询接口、SQLite 本地产品管理库，以及原生 HTML/CSS/JavaScript + ECharts 前端大屏。

首页以 16:9 横屏大屏为主要展示形态，支持 KPI 总览、销售趋势、渠道对比、产品排行、产品月度明细、客户地理分布、异常预警和产品数据管理。

## 项目结构

```text
sales_panorama_dashboard/
  backend/
    app.py                 FastAPI 接口入口
    db.py                  SQL Server 连接与查询工具
    queries.py             核心经营分析 SQL 构造函数
    local_db.py            SQLite 产品管理本地库与 CRUD
    test_connection.py     SQL Server 连接检查脚本
    requirements.txt       Python 依赖
    .env.example           连接信息备份示例，运行时不依赖该文件
    sales_crud.db          产品管理本地 SQLite 数据库
  frontend/
    index.html             大屏首页，内嵌主要样式和交互逻辑
    index.css              备用/迭代样式文件
    index.js               备用/迭代脚本文件
    screenshot-*.png       页面验证截图
  run.py                   Python 一体化启动入口
  start.bat                Windows 一键启动脚本
  stop.bat                 Windows 一键停止脚本
  README.md                项目说明
```

## 技术架构

```text
浏览器首页
  ├─ frontend/index.html
  ├─ ECharts：折线图、柱状图、地图、排行图
  ├─ 原生 HTML/CSS/JavaScript，无前端构建依赖
  └─ Fetch API 调用 FastAPI 后端

FastAPI 服务
  ├─ backend/app.py
  ├─ /api/kpis、/api/trend、/api/products/top 等经营分析接口
  ├─ /api/crud/products 产品数据管理接口
  └─ backend/queries.py 统一封装 SQL 查询口径

数据层
  ├─ SQL Server：AdventureWorksDW
  ├─ 核心表：FactInternetSales、FactResellerSales、DimDate、DimProduct、DimCustomer、DimGeography
  └─ SQLite：backend/sales_crud.db，用于产品新增、编辑、删除和本地覆盖
```

## 核心功能

- 全局筛选：开始日期、结束日期、产品类别、国家/区域、销售渠道。
- KPI 指标：销售总额、订单总量、客户总数、热销产品数量。
- 销售趋势：近 12 个月销售额、订单量、销售同比和订单同比组合展示。
- 渠道对比：Internet 与 Reseller 销售额、订单量、占比和客单价对比。
- 异常预警：根据趋势波动和头部产品生成经营关注项。
- 产品排行：Top10 产品销售额横向柱状排行，支持点击下钻。
- 月度明细：选中产品后展示最近 12 个月销售额、订单量和迷你趋势线。
- 地理分布：基于客户地理信息展示地图热力/区域销售排行，地图资源不可用时自动降级为排行图。
- 销售工作台：支持产品搜索、新增、编辑、删除，本地 SQLite 覆盖远端产品信息。

## 数据来源与指标口径

数据库：`AdventureWorksDW`

核心数据表：

- `dbo.FactInternetSales`
- `dbo.FactResellerSales`
- `dbo.DimDate`
- `dbo.DimProduct`
- `dbo.DimCustomer`
- `dbo.DimGeography`

核心口径：

- 销售额：`FactInternetSales.SalesAmount` 与 `FactResellerSales.SalesAmount` 合并汇总。
- 订单量：按 `SalesOrderNumber` 去重。
- 客户数：基于互联网销售 `FactInternetSales.CustomerKey` 去重。
- 渠道：`Internet` 来源于 `FactInternetSales`，`Reseller` 来源于 `FactResellerSales`。
- 产品维度：通过 `ProductKey` 关联 `DimProduct`，支持 `ProductLine` 筛选。
- 时间维度：通过 `OrderDateKey` 关联 `DimDate`，支持日期范围筛选。
- 地理维度：通过 `FactInternetSales -> DimCustomer -> DimGeography` 获取客户国家、省份和城市。
- 近 12 月窗口：以当前筛选范围内最大销售日期或传入结束日期为终点，向前取 12 个月。

## API 接口

通用筛选参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `start_date` | string | 可选，格式 `YYYY-MM-DD` |
| `end_date` | string | 可选，格式 `YYYY-MM-DD` |
| `product_line` | string | 可选，对应 `DimProduct.ProductLine` |
| `country` | string | 可选，对应 `DimGeography.EnglishCountryRegionName` |
| `channel` | string | 可选，只允许 `Internet` 或 `Reseller` |

经营分析接口：

| 接口 | 说明 |
|---|---|
| `GET /api/health` | 数据库健康检查 |
| `GET /api/filters` | 产品类别、国家、年份、渠道筛选项 |
| `GET /api/kpis` | KPI 汇总 |
| `GET /api/trend` | 近 12 个月销售趋势 |
| `GET /api/products/top?limit=10` | 产品销售排行 |
| `GET /api/products/{product_key}/monthly` | 单产品月度明细 |
| `GET /api/geo/sales` | 客户地理销售分布 |
| `GET /api/channels` | 双渠道销售对比 |
| `GET /api/alerts` | 经营异常预警 |

产品管理接口：

| 接口 | 说明 |
|---|---|
| `GET /api/crud/products` | 查询本地产品列表，支持名称和产品线过滤 |
| `GET /api/crud/products/{product_key}` | 查询单个产品 |
| `POST /api/crud/products` | 新增产品 |
| `PUT /api/crud/products/{product_key}` | 编辑产品 |
| `DELETE /api/crud/products/{product_key}` | 删除产品并记录删除标记 |

## 环境要求

- Windows 环境
- Python 3.8+
- 可访问 SQL Server 数据库
- 浏览器可访问 `127.0.0.1:8088`

安装依赖：

```powershell
cd backend
pip install -r requirements.txt
```

`backend/requirements.txt` 当前包含：

```text
fastapi
uvicorn
pymssql
```

## 数据库配置

当前交付版本已按演示要求将数据库连接信息硬编码到 `backend/db.py`，运行时不再依赖系统环境变量或 `backend/.env`：

```text
DB_SERVER = ""
DB_DATABASE = ""
DB_USER = ""
DB_PASSWORD = ""
```

`backend/database.py` 作为兼容入口保留，内部复用 `backend/db.py` 的连接和查询函数。

## 启动方式

### 一键启动

在项目根目录运行：

```powershell
.\start.bat
```

脚本会检查 Python、释放 `8000` 和 `8088` 端口，然后执行 `run.py`。服务启动后访问：

```text
http://127.0.0.1:8088/index.html
```

后端地址：

```text
http://127.0.0.1:8000
```

### 一键停止

```powershell
.\stop.bat
```

该脚本会停止监听 `8000` 和 `8088` 的仪表盘进程。

### 手动启动

启动后端：

```powershell
cd backend
uvicorn app:app --host 127.0.0.1 --port 8000
```

启动前端：

```powershell
cd frontend
python -m http.server 8088 --bind 127.0.0.1
```

## 验证命令

后端语法检查：

```powershell
python -m compileall backend run.py
```

数据库连接检查：

```powershell
cd backend
python test_connection.py
```

浏览器访问检查：

```text
http://127.0.0.1:8088/index.html
```

## 可视化模块说明

| 模块 | 图表/组件类型 | 数据接口 | 展示逻辑 |
|---|---|---|---|
| KPI 总览 | 指标卡片 | `/api/kpis` | 展示销售额、订单量、客户数、热销产品数 |
| 销售趋势 | 柱状图 + 折线图 + 双轴 | `/api/trend` | 按月展示销售额、订单量及增长趋势 |
| 渠道对比 | 双渠道卡片 | `/api/channels` | 展示 Internet 和 Reseller 的销售额、订单量、占比、客单价 |
| 异常预警 | 列表卡片 | `/api/alerts` | 根据销售波动和头部产品生成管理关注项 |
| 产品排行 | 横向柱状图 | `/api/products/top` | 按销售额降序展示 Top10 产品 |
| 月度明细 | 表格 + 迷你趋势线 | `/api/products/{product_key}/monthly` | 点击产品排行后加载对应产品近 12 月明细 |
| 地理分布 | 地图/排行图 | `/api/geo/sales` | 优先渲染地图，失败时降级为区域排行 |
| 销售工作台 | 表格 + 抽屉表单 | `/api/crud/products` | 本地维护产品信息，覆盖/过滤远端排行结果 |

## 交付物

本项目可交付以下材料：

- 项目源码目录：`sales_panorama_dashboard/`
- 首页截图：`frontend/homepage-screenshot.png`
- 项目压缩包：`sales_panorama_dashboard.zip`
- 模块说明与核心 SQL Word 文档：`docs/企业销售全景数据大屏_模块与SQL说明.docx`

## 注意事项

- 前端使用 CDN 加载 ECharts；离线环境需要提前准备本地 ECharts 文件并修改引用。
- 如果 SQL Server 暂不可用，首页会切换到演示数据模式，便于界面展示。
- 地图模块依赖外部 GeoJSON 资源；资源不可用时会自动显示区域销售排行。
- SQLite 本地库用于产品管理演示，不替代正式主数据管理系统。
