# DeepSeek V4 智能经营分析指南

## 功能定位

DeepSeek V4 用于读取 Spark 分布式计算后的销售指标结果，生成中文企业经营分析报告，重点输出风险预警、管理建议和下一步行动方案。当前实现使用 `requests` 直接调用 DeepSeek 的兼容 HTTP 接口，不依赖额外大模型 SDK。

## 环境变量

```bash
export DEEPSEEK_API_KEY=你的_API_KEY
export DEEPSEEK_MODEL=deepseek-v4-flash
```

默认模型：

```text
deepseek-v4-flash
```

切换更强模型：

```bash
export DEEPSEEK_MODEL=deepseek-v4-pro
```

可选：

```bash
export DEEPSEEK_BASE_URL=https://api.deepseek.com
```

## 生成报告

```bash
cd /export/server/project/sales_panorama_dashboard
python backend/ai/deepseek_v4_report.py
```

或：

```bash
bash scripts/generate_ai_report.sh
```

输出：

```text
output/spark_result/ai_report.txt
```

## API Key 要求

当前版本只生成真实 DeepSeek V4 报告。如果未配置 `DEEPSEEK_API_KEY`，系统会返回明确错误，不会生成报告内容。

## 报告结构

报告包含：

1. 总体经营概览
2. 销售趋势分析
3. 渠道经营分析
4. 产品结构分析
5. 区域销售表现
6. 异常风险预警
7. 管理建议
8. 下一步行动方案

## 安全要求

- 不要把 API Key 写入代码。
- 不要在日志中打印 API Key。
- 前端不直接调用 DeepSeek API，统一通过 FastAPI 后端生成报告。
