# 答辩说明

## 项目升级亮点

本项目从传统 FastAPI + SQL Server 实时查询大屏，升级为：

```text
SQL Server 数据仓库
  -> Spark Standalone 分布式计算
  -> FastAPI 轻量接口服务
  -> ECharts 可视化大屏
  -> DeepSeek V4 智能经营分析
```

## 可以重点讲解的模块

1. SQL Server 是唯一正式业务数据源，核心库为 `AdventureWorksDW`。
2. Spark 负责离线分布式聚合，输出 KPI、趋势、产品、渠道、区域和预警 JSON。
3. FastAPI 不再承担重计算，优先读取 Spark 结果，接口保持兼容。
4. ECharts 前端保持原大屏布局，只新增 DeepSeek V4 智能经营分析区域。
5. DeepSeek V4 读取 Spark 聚合结果，生成管理层可读的经营诊断报告。

## 演示顺序

1. 展示 Spark Master UI：`http://node1:8080`。
2. 执行 `scripts/check_spark_cluster.sh`，说明三节点集群状态。
3. 执行 `scripts/run_spark_job.sh`，生成 `output/spark_result/*.json`。
4. 启动 FastAPI 和前端，展示大屏图表。
5. 点击“生成 AI 报告”，展示 DeepSeek V4 智能经营诊断。

## AI 报告讲解口径

AI 报告不是简单复述数据，而是基于 Spark 结果完成：

- 总体经营判断
- 销售趋势分析
- 渠道结构分析
- 产品集中度分析
- 区域表现分析
- 异常风险识别
- 管理建议和下一步行动

## SQLite 说明

原项目存在 SQLite 产品 CRUD。改造后它只作为本地演示管理模块保留，不作为核心销售数据源，不影响 Spark 主指标口径。

## 风险与降级

- Spark 结果不存在：FastAPI 可回退到 SQL Server 查询，保证页面可展示。
- DeepSeek API Key 未配置：报告生成接口会提示配置真实 Key；答辩前应提前设置 `DEEPSEEK_API_KEY`。
- SQL Server 证书问题：JDBC 使用 `encrypt=true;trustServerCertificate=true`。
