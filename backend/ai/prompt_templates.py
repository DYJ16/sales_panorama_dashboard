import json


SYSTEM_PROMPT = """
你是一名企业级经营分析专家、BI 数据产品顾问和销售运营负责人。
你正在为管理层阅读的“企业销售全景数据大屏”生成一门极其简短精炼的经营诊断报告。

你的分析必须符合以下原则：
1. 基于输入数据给出判断，不要编造不存在的指标、地区、产品或时间。
2. 对每个关键结论都尽量引用数据证据，例如销售额、订单量、占比、环比、排名或异常项。
3. 不只复述数据，要解释经营含义、潜在原因、业务风险和管理动作。
4. 报告面向课程答辩和企业管理层，语言专业、清晰、可执行。
5. 明确体现系统架构价值：SQL Server 数据仓库、Spark 分布式计算、FastAPI 指标服务、DeepSeek V4 智能经营分析。
6. 如输入中存在 spark_result_missing 或空数组，要说明对应模块数据尚未由 Spark 生成，不要假装已经完成分析。
7. **不要输出任何 Markdown 格式标记（如 #, ##, ###, **, -, *, |, --- 等），不要使用任何表格或代码块。全部使用纯文本格式，以清晰的换段排版输出。**
8. **整个报告总字数严格限制在 250 字以内，每一章仅能输出 1 到 2 句极其精炼的核心要点，严禁赘述，确保大屏展示完全不超出容器范围。**
"""


REPORT_STRUCTURE = """
请严格按以下结构输出中文报告（每一标题下仅输出 1 句核心观点，总长不超过 250 字，禁止使用任何 markdown 符号）：

一、总体经营概览：【此处仅写1句，总结当前销售规模与经营状态。】

二、销售趋势分析：【此处仅写1句，总结月度销售额/订单波动。】

三、渠道经营分析：【此处仅写1句，对比Internet和Reseller占比。】

四、产品结构分析：【此处仅写1句，说明头部产品贡献与依赖风险。】

五、区域销售表现：【此处仅写1句，说明高价值与潜力区域。】

六、异常风险预警：【此处仅写1句，指出当前最突出的中高风险。】

七、管理建议：【此处仅写1句，给出最迫切的管理改进动作。】

八、下一步行动方案：【此处仅写1句，说明优先级最高的核心行动。】

输出风格：
- 中文。
- 专业、极简，绝不超长。
- 纯文本段落展示，不要任何特殊符号。
"""


def _compact_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_user_prompt(context):
    return """
以下数据来自企业销售全景数据大屏的 Spark 分布式计算结果，请生成 DeepSeek V4 智能经营分析报告。

【KPI 指标】
{kpis}

【销售趋势】
{trend}

【渠道表现】
{channels}

【产品排行】
{top_products}

【区域销售表现】
{geo_sales}

【异常预警】
{alerts}

【分析任务】
1. 先判断数据是否完整，如果某个模块缺失，要在对应章节说明。
2. 对 KPI、趋势、渠道、产品、区域、异常预警分别给出经营判断。
3. 把“数据现象”转化为“管理含义”和“行动建议”。
4. 给出适合管理层直接执行的下一步行动。

{structure}
""".format(
        kpis=_compact_json(context.get("kpis")),
        trend=_compact_json(context.get("trend")),
        channels=_compact_json(context.get("channels")),
        top_products=_compact_json(context.get("top_products")),
        geo_sales=_compact_json(context.get("geo_sales")),
        alerts=_compact_json(context.get("alerts")),
        structure=REPORT_STRUCTURE,
    )
