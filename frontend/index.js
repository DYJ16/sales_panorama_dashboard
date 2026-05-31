const API_HOST = window.location.hostname || "127.0.0.1";
const API_BASE = window.API_BASE || `${window.location.protocol}//${API_HOST}:8000`;
const DEFAULT_FILTERS = {
  start_date: "2013-01-01",
  end_date: "2014-12-31",
  product_line: "",
  country: "",
  channel: ""
};

const els = {
  form: document.getElementById("filterForm"),
  startDate: document.getElementById("startDate"),
  endDate: document.getElementById("endDate"),
  productLine: document.getElementById("productLine"),
  country: document.getElementById("country"),
  channel: document.getElementById("channel"),
  resetBtn: document.getElementById("resetBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  themeBtn: document.getElementById("themeBtn"),
  healthText: document.getElementById("healthText"),
  kpiSales: document.getElementById("kpiSales"),
  kpiOrders: document.getElementById("kpiOrders"),
  kpiCustomers: document.getElementById("kpiCustomers"),
  kpiHotProducts: document.getElementById("kpiHotProducts"),
  trendNote: document.getElementById("trendNote"),
  internetCard: document.getElementById("internetCard"),
  resellerCard: document.getElementById("resellerCard"),
  alertsList: document.getElementById("alertsList"),
  moreAlerts: document.getElementById("moreAlerts"),
  monthlyTitle: document.getElementById("monthlyTitle"),
  monthlyNote: document.getElementById("monthlyNote"),
  monthlyTable: document.getElementById("monthlyTable"),
  geoRank: document.getElementById("geoRank"),
  toast: document.getElementById("statusToast"),
  loadingMask: document.getElementById("loadingMask"),
  loadingBar: document.getElementById("loadingBar"),
  loadingPercent: document.getElementById("loadingPercent"),
  loadingStep: document.getElementById("loadingStep")
};

const state = {
  filters: { ...DEFAULT_FILTERS },
  products: [],
  selectedProduct: null,
  aborter: null,
  mockMode: false,
  themeMode: 0
};

const charts = {
  trend: echarts.init(document.getElementById("trendChart")),
  product: echarts.init(document.getElementById("productChart")),
  geo: echarts.init(document.getElementById("geoChart"))
};

const chartFont = {
  color: "#637064",
  fontFamily: "Inter, PingFang SC, Microsoft YaHei, Segoe UI, Arial"
};

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function toast(message, sticky = false) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  if (!sticky) {
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => els.toast.classList.remove("show"), 2800);
  }
}

function setLoading(percent, step) {
  els.loadingBar.style.width = `${percent}%`;
  els.loadingPercent.textContent = `${percent}%`;
  els.loadingStep.textContent = step;
}

function compact(value) {
  const n = Number(value || 0);
  if (Math.abs(n) >= 100000000) return `${(n / 100000000).toFixed(2)} 亿`;
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(2)} 万`;
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function money(value) {
  return `¥ ${compact(value)}`;
}

function moneyWan(value) {
  return (Number(value || 0) / 10000).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function percent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

function fillSelect(select, values, firstLabel) {
  const current = select.value;
  select.innerHTML = `<option value="">${firstLabel}</option>`;
  values.filter(Boolean).forEach(value => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value === "Internet" ? "网络销售" : value === "Reseller" ? "经销商" : value;
    select.appendChild(option);
  });
  select.value = current;
}

function readFilters() {
  return {
    start_date: els.startDate.value,
    end_date: els.endDate.value,
    product_line: els.productLine.value,
    country: els.country.value,
    channel: els.channel.value
  };
}

function buildParams(extra = {}) {
  const params = new URLSearchParams();
  Object.entries({ ...state.filters, ...extra }).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, value);
  });
  return params.toString();
}

async function getJson(path, signal) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(new Error("request timeout")), 4500);
  const abortFromParent = () => controller.abort(signal.reason);
  if (signal) {
    if (signal.aborted) controller.abort(signal.reason);
    else signal.addEventListener("abort", abortFromParent, { once: true });
  }
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`${path} 返回 ${response.status}`);
    return response.json();
  } finally {
    clearTimeout(timeout);
    if (signal) signal.removeEventListener("abort", abortFromParent);
  }
}

function animateNumber(element, from, to, formatter) {
  const start = Number(from || 0);
  const end = Number(to || 0);
  const duration = 760;
  let startTime = 0;

  function frame(ts) {
    if (!startTime) startTime = ts;
    const progress = Math.min((ts - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = formatter(start + (end - start) * eased);
    if (progress < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

const kpiValues = {
  sales: 0,
  orders: 0,
  customers: 0,
  products: 0
};

function renderKpis(data) {
  animateNumber(els.kpiSales, kpiValues.sales, data.total_sales, money);
  animateNumber(els.kpiOrders, kpiValues.orders, data.order_count, compact);
  animateNumber(els.kpiCustomers, kpiValues.customers, data.customer_count, compact);
  animateNumber(els.kpiHotProducts, kpiValues.products, data.hot_product_count, compact);
  kpiValues.sales = Number(data.total_sales || 0);
  kpiValues.orders = Number(data.order_count || 0);
  kpiValues.customers = Number(data.customer_count || 0);
  kpiValues.products = Number(data.hot_product_count || 0);
}

function growth(values) {
  return values.map((value, index) => {
    if (index === 0) return 0;
    const previous = values[index - 1] || 1;
    return Number((((value - previous) / previous) * 100).toFixed(1));
  });
}

function monthLabel(item) {
  return item.year_month || `${item.year}-${String(item.month).padStart(2, "0")}`;
}

function emptyChart(text) {
  return {
    title: {
      text,
      left: "center",
      top: "middle",
      textStyle: { color: "#637064", fontSize: 13, fontWeight: 400 }
    },
    xAxis: { show: false },
    yAxis: { show: false },
    series: []
  };
}

function renderTrend(items) {
  if (!items.length) {
    charts.trend.setOption(emptyChart("暂无趋势数据"), true);
    return;
  }

  const months = items.map(monthLabel);
  const sales = items.map(item => Number(item.sales_amount || 0));
  const orders = items.map(item => Number(item.order_count || 0));
  els.trendNote.textContent = `${months[0]} 至 ${months[months.length - 1]}`;

  charts.trend.setOption({
    animationDuration: 900,
    animationEasing: "cubicOut",
    color: ["#176bf2", "#d8a34c", "#47c3e8"],
    grid: { left: 56, right: 44, top: 46, bottom: 34 },
    legend: {
      top: 4,
      data: ["销售额（万元）", "订单数", "销售增长率"],
      textStyle: chartFont
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255,252,246,.96)",
      borderColor: "rgba(21,32,24,.12)",
      textStyle: chartFont,
      extraCssText: "box-shadow:0 18px 42px rgba(33,40,30,.14);border-radius:8px;"
    },
    xAxis: {
      type: "category",
      data: months,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "rgba(21,32,24,.12)" } },
      axisLabel: { color: "#637064" }
    },
    yAxis: [
      {
        type: "value",
        axisLabel: { color: "#637064", formatter: value => compact(value / 10000) },
        splitLine: { lineStyle: { color: "rgba(21,32,24,.08)", type: "dashed" } }
      },
      {
        type: "value",
        axisLabel: { color: "#637064", formatter: "{value}%" },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: "销售额（万元）",
        type: "line",
        smooth: true,
        symbolSize: 7,
        areaStyle: { color: "rgba(23,107,242,.13)" },
        data: sales
      },
      {
        name: "订单数",
        type: "bar",
        barWidth: 18,
        itemStyle: { borderRadius: [6, 6, 0, 0] },
        data: orders
      },
      {
        name: "销售增长率",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { type: "dashed" },
        data: growth(sales)
      }
    ]
  }, true);
}

function renderProducts(items) {
  state.products = items;
  if (!items.length) {
    charts.product.setOption(emptyChart("暂无产品数据"), true);
    return;
  }

  const names = items.map(item => item.product_name || `Product ${item.product_key}`);
  const values = items.map(item => Number(item.sales_amount || 0));

  charts.product.setOption({
    animationDuration: 820,
    grid: { left: 8, right: 18, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(255,252,246,.96)",
      borderColor: "rgba(21,32,24,.12)",
      textStyle: chartFont,
      formatter(params) {
        const p = params[0];
        return `${escapeHtml(p.name)}<br>销售额：${money(values[p.dataIndex])}`;
      }
    },
    xAxis: {
      type: "value",
      axisLabel: { color: "#637064", formatter: value => compact(value / 10000) },
      splitLine: { lineStyle: { color: "rgba(21,32,24,.08)", type: "dashed" } }
    },
    yAxis: {
      type: "category",
      data: names,
      inverse: true,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: "#152018", width: 145, overflow: "truncate" }
    },
    series: [{
      type: "bar",
      data: values,
      barWidth: 14,
      itemStyle: {
        borderRadius: [0, 8, 8, 0],
        color: params => {
          const palette = ["#176bf2", "#3b82f6", "#d8a34c", "#47c3e8", "#123d88"];
          return palette[params.dataIndex % palette.length];
        }
      }
    }]
  }, true);
}

function renderChannels(items) {
  const byChannel = Object.fromEntries(items.map(item => [item.sales_channel, item]));
  renderChannelTile(els.internetCard, byChannel.Internet || {}, "网络销售", "Internet");
  renderChannelTile(els.resellerCard, byChannel.Reseller || {}, "经销商", "Reseller");
}

function renderChannelTile(el, item, label, channel) {
  const isActive = state.filters.channel === channel;
  el.classList.toggle("active", isActive);
  el.innerHTML = `
    <div class="channel-name"><b>${label}</b><span>${isActive ? "已筛选" : "点击筛选"}</span></div>
    <div class="channel-value">${money(item.sales_amount || 0)}</div>
    <div class="channel-meta">订单 ${compact(item.order_count || 0)} · 销售占比 ${percent(item.sales_ratio || 0)}</div>
  `;
}

function renderAlerts(items, kpis = {}) {
  const fallback = [
    {
      level: "high",
      title: "月度销售波动",
      description: "最近窗口内高低峰差异明显，建议复核重点渠道和头部产品补货节奏。"
    },
    {
      level: "medium",
      title: "头部产品集中",
      description: "销售贡献集中在少数 SKU，适合继续观察库存、价格和区域需求。"
    },
    {
      level: "info",
      title: "筛选范围已同步",
      description: `当前销售额 ${money(kpis.total_sales || 0)}，图表已按最新条件刷新。`
    }
  ];
  const merged = [...items, ...fallback].slice(0, 5);
  els.alertsList.innerHTML = merged.map(item => `
    <div class="alert ${escapeHtml(item.level || "info")}">
      <i class="alert-mark"></i>
      <div>
        <strong>${escapeHtml(item.title || "经营提示")}</strong>
        <span>${escapeHtml(item.description || "当前指标存在需要关注的变化。")}</span>
      </div>
    </div>
  `).join("");
  els.moreAlerts.onclick = () => toast(`当前共展示 ${merged.length} 条预警，销售额 ${money(kpis.total_sales || 0)}`);
}

async function renderGeo(items) {
  const ranked = items.map((item, index) => ({
    name: item.country || item.region || item.territory || item.city || `区域 ${index + 1}`,
    value: Number(item.sales_amount || 0)
  })).sort((a, b) => b.value - a.value).slice(0, 8);

  if (!ranked.length) {
    charts.geo.setOption(emptyChart("暂无区域数据"), true);
    els.geoRank.innerHTML = "";
    return;
  }

  charts.geo.setOption({
    animationDuration: 900,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(255,252,246,.96)",
      borderColor: "rgba(21,32,24,.12)",
      textStyle: chartFont,
      formatter: params => `${escapeHtml(params.name)}<br>销售额：${money(params.value)}`
    },
    series: [{
      type: "pie",
      radius: ["42%", "76%"],
      center: ["50%", "52%"],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: "rgba(255,252,246,.88)", borderWidth: 3 },
      label: { color: "#637064", formatter: "{b}" },
      color: ["#176bf2", "#3b82f6", "#d8a34c", "#47c3e8", "#79b7ff", "#123d88"],
      data: ranked
    }]
  }, true);

  const max = ranked[0].value || 1;
  els.geoRank.innerHTML = ranked.map((item, index) => `
    <div class="rank-row">
      <b>${index + 1}</b>
      <span title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span>
      <div class="rank-track"><i style="width:${Math.max(8, (item.value / max) * 100)}%"></i></div>
    </div>
  `).join("");
}

function spark(values) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * 72;
    const y = 22 - ((value - min) / span) * 20;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="spark" viewBox="0 0 72 24" aria-hidden="true"><polyline points="${points}" fill="none" stroke="#176bf2" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function renderMonthlyTable(items) {
  if (!items.length) {
    els.monthlyTable.innerHTML = `<tbody><tr><td class="empty">暂无月度明细</td></tr></tbody>`;
    return;
  }
  const salesValues = items.map(item => Number(item.sales_amount || 0));
  els.monthlyTable.innerHTML = `
    <thead>
      <tr>
        <th>月份</th>
        <th>产品</th>
        <th>销售额</th>
        <th>订单</th>
        <th>趋势</th>
      </tr>
    </thead>
    <tbody>
      ${items.map((item, index) => `
        <tr>
          <td>${escapeHtml(monthLabel(item))}</td>
          <td>${escapeHtml(item.product_name || state.selectedProduct?.product_name || "-")}</td>
          <td>${money(item.sales_amount || 0)}</td>
          <td>${compact(item.order_count || 0)}</td>
          <td>${spark(salesValues.slice(Math.max(0, index - 5), index + 1))}</td>
        </tr>
      `).join("")}
    </tbody>
  `;
}

async function selectProduct(product, announce = true, signal) {
  if (!product) return;
  state.selectedProduct = product;
  els.monthlyTitle.textContent = product.product_name || "单品月度明细";
  els.monthlyNote.textContent = `ProductKey ${product.product_key} · ${product.product_line || "未分类"}`;
  if (state.mockMode) {
    renderMonthlyTable(mockMonthly(product));
    return;
  }
  const data = await getJson(`/api/products/${product.product_key}/monthly?${buildParams()}`, signal);
  renderMonthlyTable(data.items || []);
  if (announce) toast(`已下钻：${product.product_name}`);
}

function renderErrorState(message) {
  Object.values(charts).forEach(chart => chart.setOption(emptyChart(`无法加载数据：${message}`), true));
  els.alertsList.innerHTML = `<div class="empty">无法加载预警<br>${escapeHtml(message)}</div>`;
  els.monthlyTable.innerHTML = `<tbody><tr><td class="empty">无法加载明细</td></tr></tbody>`;
}

async function loadHealth() {
  const data = await getJson("/api/health");
  const time = data.server_time ? String(data.server_time).slice(0, 19).replace("T", " ") : "已连接";
  els.healthText.textContent = `数据源已连接 · ${time}`;
}

async function loadFilters() {
  const data = await getJson("/api/filters");
  fillSelect(els.productLine, data.product_line || [], "全部");
  fillSelect(els.country, data.country || [], "全部");
}

async function refreshDashboard(message) {
  if (state.aborter) state.aborter.abort();
  state.aborter = new AbortController();
  const signal = state.aborter.signal;
  state.filters = readFilters();
  els.loadingMask.classList.remove("hidden");

  if (state.mockMode) {
    setLoading(100, "已加载演示数据");
    renderMockDashboard();
    els.loadingMask.classList.add("hidden");
    if (message) toast(message);
    return;
  }

  try {
    setLoading(16, "读取核心指标...");
    const params = buildParams();
    const [kpis, trend, products, channels, geo, alerts] = await Promise.all([
      getJson(`/api/kpis?${params}`, signal),
      getJson(`/api/trend?${params}`, signal),
      getJson(`/api/products/top?${params}&limit=10`, signal),
      getJson(`/api/channels?${params}`, signal),
      getJson(`/api/geo/sales?${params}`, signal),
      getJson(`/api/alerts?${params}`, signal)
    ]);
    setLoading(72, "渲染图表...");
    renderKpis(kpis);
    renderTrend(trend.items || []);
    renderProducts(products.items || []);
    renderChannels(channels.items || []);
    renderAlerts(alerts.items || [], kpis);
    await renderGeo(geo.items || []);
    await selectProduct((products.items || [])[0], false, signal);
    setLoading(100, "完成");
    els.loadingMask.classList.add("hidden");
    if (message) toast(message);
  } catch (error) {
    if (error.name === "AbortError") return;
    els.loadingMask.classList.add("hidden");
    renderErrorState(error.message);
    toast(`数据加载失败：${error.message}`, true);
  }
}

function mockData() {
  const products = [
    ["Mountain-100 Silver, 38", 5400000, 1200, "M"],
    ["Road-150 Red, 56", 4200000, 980, "R"],
    ["Mountain-200 Black, 42", 3600000, 850, "M"],
    ["Road-250 Black, 44", 2900000, 710, "R"],
    ["Touring-1000 Yellow, 46", 2400000, 590, "T"],
    ["Mountain-200 Silver, 46", 2100000, 520, "M"],
    ["Road-350-W Yellow, 48", 1850000, 460, "R"],
    ["HL Mountain Frame - Silver", 1500000, 390, "M"],
    ["Road-550-W Yellow, 38", 1300000, 340, "R"],
    ["Sport-100 Helmet, Red", 1100000, 3100, "S"]
  ].map((item, index) => ({
    product_key: index + 1,
    product_name: item[0],
    sales_amount: item[1],
    order_count: item[2],
    product_line: item[3]
  }));
  return {
    kpis: { total_sales: 28350000, order_count: 58340, customer_count: 18520, hot_product_count: 124 },
    trend: Array.from({ length: 12 }, (_, index) => ({
      year_month: `2014-${String(index + 1).padStart(2, "0")}`,
      sales_amount: 1500000 + Math.sin(index * 0.88) * 360000 + index * 135000,
      order_count: 3600 + Math.cos(index * 0.7) * 540 + index * 260
    })),
    products,
    channels: [
      { sales_channel: "Internet", sales_amount: 16500000, order_count: 38000, sales_ratio: 0.582 },
      { sales_channel: "Reseller", sales_amount: 11850000, order_count: 20340, sales_ratio: 0.418 }
    ],
    geo: ["United States", "Australia", "Canada", "United Kingdom", "Germany", "France", "China"].map((name, index) => ({
      country: name,
      sales_amount: [6500000, 5200000, 4800000, 3900000, 3200000, 2800000, 1950000][index]
    })),
    alerts: [
      { level: "high", title: "区域销售回落", description: "部分区域销售额低于峰值月份，建议复核区域投放和渠道库存。" },
      { level: "medium", title: "大额订单集中", description: "头部产品贡献较高，建议跟踪交付和售后风险。" }
    ]
  };
}

function mockMonthly(product) {
  return Array.from({ length: 12 }, (_, index) => ({
    year_month: `2014-${String(index + 1).padStart(2, "0")}`,
    product_name: product.product_name,
    sales_amount: product.sales_amount * (0.055 + Math.sin(index * 0.9 + product.product_key) * 0.012 + index * 0.004),
    order_count: Math.round(product.order_count * (0.055 + index * 0.004))
  }));
}

function renderMockDashboard() {
  const data = mockData();
  renderKpis(data.kpis);
  renderTrend(data.trend);
  renderProducts(data.products);
  renderChannels(data.channels);
  renderAlerts(data.alerts, data.kpis);
  renderGeo(data.geo);
  selectProduct(data.products[0], false);
}

class RegiField {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.pointer = { x: 0.5, y: 0.35, tx: 0.5, ty: 0.35 };
    this.mode = 0;
    this.time = 0;
    this.resize();
    this.bind();
    this.draw();
  }

  bind() {
    window.addEventListener("resize", () => this.resize());
    window.addEventListener("pointermove", event => this.move(event.clientX, event.clientY));
    window.addEventListener("pointerdown", event => this.move(event.clientX, event.clientY));
  }

  move(x, y) {
    this.pointer.tx = x / window.innerWidth;
    this.pointer.ty = y / window.innerHeight;
    document.documentElement.style.setProperty("--cursor-x", `${Math.round(this.pointer.tx * 100)}%`);
    document.documentElement.style.setProperty("--cursor-y", `${Math.round(this.pointer.ty * 100)}%`);
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  setMode(mode) {
    this.mode = mode;
  }

  draw() {
    this.time += 0.008 + this.mode * 0.003;
    this.pointer.x += (this.pointer.tx - this.pointer.x) * 0.07;
    this.pointer.y += (this.pointer.ty - this.pointer.y) * 0.07;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    const colors = [
      ["rgba(23,107,242,.17)", "rgba(216,163,76,.16)", "rgba(71,195,232,.14)"],
      ["rgba(18,61,136,.16)", "rgba(23,107,242,.18)", "rgba(216,163,76,.16)"],
      ["rgba(23,107,242,.13)", "rgba(121,183,255,.18)", "rgba(255,255,255,.22)"]
    ][this.mode];

    for (let layer = 0; layer < 3; layer += 1) {
      ctx.beginPath();
      ctx.lineWidth = 1 + layer * 0.35;
      ctx.strokeStyle = colors[layer];
      const rows = 9 + layer * 4;
      const amplitude = 32 + layer * 21;
      for (let row = 0; row < rows; row += 1) {
        const baseY = this.height * (0.18 + row / (rows + 5)) + layer * 22;
        ctx.beginPath();
        for (let x = -40; x <= this.width + 40; x += 14) {
          const nx = x / this.width;
          const dist = Math.hypot(nx - this.pointer.x, baseY / this.height - this.pointer.y);
          const pull = Math.max(0, 1 - dist * 3.2);
          const wave = Math.sin(nx * 8 + this.time * (1 + layer * 0.35) + row * 0.5) * amplitude;
          const orbit = Math.cos(nx * 15 - this.time * 0.8 + row) * amplitude * 0.28;
          const y = baseY + wave + orbit - pull * (48 + layer * 12);
          if (x === -40) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
    }

    const gx = this.pointer.x * this.width;
    const gy = this.pointer.y * this.height;
    const gradient = ctx.createRadialGradient(gx, gy, 0, gx, gy, Math.min(this.width, this.height) * 0.34);
    gradient.addColorStop(0, "rgba(255,255,255,.42)");
    gradient.addColorStop(0.42, "rgba(255,255,255,.1)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, this.width, this.height);
    requestAnimationFrame(() => this.draw());
  }
}

function bindInteractions(field) {
  els.form.addEventListener("change", () => refreshDashboard("筛选条件已更新"));
  els.form.addEventListener("submit", event => {
    event.preventDefault();
    refreshDashboard("筛选条件已更新");
  });
  els.refreshBtn.addEventListener("click", () => refreshDashboard("数据已刷新"));
  els.resetBtn.addEventListener("click", () => {
    els.startDate.value = DEFAULT_FILTERS.start_date;
    els.endDate.value = DEFAULT_FILTERS.end_date;
    els.productLine.value = "";
    els.country.value = "";
    els.channel.value = "";
    refreshDashboard("筛选已重置");
  });
  els.themeBtn.addEventListener("click", () => {
    state.themeMode = (state.themeMode + 1) % 3;
    field.setMode(state.themeMode);
    els.themeBtn.textContent = ["光场模式", "霓彩模式", "深绿模式"][state.themeMode];
  });
  [els.internetCard, els.resellerCard].forEach(card => {
    card.addEventListener("click", () => {
      els.channel.value = els.channel.value === card.dataset.channel ? "" : card.dataset.channel;
      refreshDashboard(els.channel.value ? `已筛选渠道：${card.dataset.channel}` : "渠道筛选已取消");
    });
  });
  charts.product.on("click", params => {
    const product = state.products[params.dataIndex];
    selectProduct(product, true).catch(error => toast(`产品明细加载失败：${error.message}`, true));
  });
}

async function init() {
  const field = new RegiField(document.getElementById("regiField"));
  bindInteractions(field);
  setLoading(10, "初始化图表...");

  if (window.location.protocol === "file:") {
    state.mockMode = true;
    els.healthText.textContent = "本地演示模式 · 未连接后端";
    fillSelect(els.productLine, ["M", "R", "T", "S"], "全部");
    fillSelect(els.country, ["United States", "Australia", "Canada", "United Kingdom", "Germany", "France", "China"], "全部");
    renderMockDashboard();
    els.loadingMask.classList.add("hidden");
    toast("已加载本地演示数据");
    return;
  }

  try {
    await Promise.all([loadHealth(), loadFilters()]);
    await refreshDashboard("真实数据已加载");
  } catch (error) {
    state.mockMode = true;
    els.healthText.textContent = "后端未连接 · 已切换演示数据";
    fillSelect(els.productLine, ["M", "R", "T", "S"], "全部");
    fillSelect(els.country, ["United States", "Australia", "Canada", "United Kingdom", "Germany", "France", "China"], "全部");
    renderMockDashboard();
    els.loadingMask.classList.add("hidden");
    toast(`连接后端失败，已切换演示数据：${error.message}`, true);
  }
}

window.addEventListener("resize", debounce(() => {
  Object.values(charts).forEach(chart => chart.resize());
}, 180));

init();
