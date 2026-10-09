# MCP 集成说明

本文档说明「麦麦拼单团长」实际使用的麦当劳 MCP Server、Tool、调用流程与业务价值。

## 一、使用的 MCP Server

| 项 | 值 |
|---|---|
| Server 名称 | `mcd-mcp`（麦当劳中国 MCP 服务） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权方式 | 请求头 `Authorization: Bearer <MCD_MCP_TOKEN>` |
| Token 获取 | <https://open.mcd.cn/mcp> 手机号登录 → 控制台 → 激活 |
| Token 配置 | 见 `mcp-config.example.json`（仅环境变量占位符，不含真实凭据） |

官方文档：<https://github.com/M-China/mcd-mcp-server>

## 二、使用的 Tool 清单

本 Skill 主链路使用 **8 个** MCP Tool：

| # | Tool | 用途 | 在哪个环节 |
|---|---|---|---|
| 1 | `now-time-info` | 获取当前时间，判断活动是否在有效期内 | Step 0 促销侦察 |
| 2 | `campaign-calendar` | 查当月营销活动日历（进行中/往期/未来） | Step 0 促销侦察 |
| 3 | `auto-bind-coupons` | 麦麦省一键领取当前可领的全部券 | Step A3 领券 |
| 4 | `query-store-coupons` | 查**当前门店实际可用**的券 | Step A3 领券 |
| 5 | `query-meals` | 查当前门店可售菜单（分类、餐品编码、标签） | Step A2 对齐菜单 |
| 6 | `query-meal-detail` | 按编码查餐品详情（套餐组成、可替换项） | Step A2 对齐菜单 |
| 7 | `list-nutrition-foods` | 餐品营养数据 | Step A2 / 模式 B 特殊人群 |
| 8 | `calculate-price` | 商品价格计算（金额、配送费、优惠、应付） | Step A3 试算 / 模式 C 拆单 |

**下单环节（可选，需用户明确同意）追加 2 个：**

| # | Tool | 用途 |
|---|---|---|
| 9 | `delivery-query-addresses` | 确认配送地址 |
| 10 | `delivery-create-address` | 新增配送地址（首次使用时） |
| 11 | `create-order` | 创建订单，返回订单详情与支付链接 |

**企业团餐场景额外使用：**

| # | Tool | 用途 |
|---|---|---|
| 12 | `query-meal-assistance` | 查询门店支持的**助餐服务**（仅企业团餐场景） |

## 三、调用流程

```
                        ┌─ now-time-info        （拿当前时间）
  Step 0 促销侦察 ───────┤
                        └─ campaign-calendar    （当月活动日历）
                                  │
                                  ▼
  Step A3 领券 ──── auto-bind-coupons  →  query-store-coupons
                       （先全领）            （再按门店筛可用）
                                  │
                                  ▼
  Step A2 对齐菜单 ── query-meals  →  query-meal-detail
                       （拿菜单）      （拆套餐/换无糖）
                       query-meal-assistance（企业团餐查助餐）
                       list-nutrition-foods （有人提热量/减肥）
                                  │
                                  ▼
  Step A3/C 算价 ──── calculate-price  （试算 · 幂等 · 可反复调）
                       ├─ 凑单对比
                       ├─ 套餐 vs 单点比价
                       └─ 拆单策略枚举
                                  │
                                  ▼
  Step A6 下单（可选，需确认）── delivery-query-addresses
                                  →  create-order  →  支付链接
```

**关键设计**：

- `calculate-price` 是**幂等试算**，拆单枚举（k=1..N）全部在本地反复调用它得出对比，**不产生订单**
- `create-order` 只在用户明确说「下单」且确认总额后才调用
- 促销侦察（`campaign-calendar`）前置到所有模式之前，确保方案围绕**当天真实活动**构建

## 四、业务价值

这个项目解决的是一个**真实存在、但长期被忽略**的场景：**为十几个人点麦当劳**。

它不是把「点一份餐」自动化，而是把**团长这个角色的完整工作流**自动化：

| 环节 | 原来怎么做 | 用本 Skill | 价值 |
|---|---|---|---|
| 收单 | 群里刷屏，拿纸记 | 口语直接进，自动结构化 | 免去转录与漏单 |
| 翻译菜单 | 凭记忆翻菜单找商品 | `query-meals` 实时对齐 | 不会点错、不会报错价 |
| 省钱 | 靠经验，容易漏券 | 先领券再算价，四层优化 | **可量化省钱**（实测示例省 11.5%） |
| 配餐 | 拍脑袋估份数 | 按人数 × 场景系数配餐，三档对比 | **减少浪费**——小食饮料按比例配 |
| 买单 | 直接下单 | 算出最优买法（吃满限购 + 拆单） | 实测示例 10 份套餐从 ¥331 降到 ¥260 |
| 拆账 | 计算器手按，怕算错 | 三种分摊模式 + 强制自检 | 各人应付之和**严格等于**整单实付 |

**特别说明**：本项目坚持「**吃得刚好，不是吃得最多**」——配餐环节把「不浪费」做成可计算的规则（小食按人数 60%~80% 配、饮料按 80% 配），而不是靠感觉。

## 五、降级方案

未配置 MCP Token 时，Skill 自动进入**手动模式**：由用户输入菜名与价格，配餐、买单、拆账逻辑照常运行，结算单标注「手动录入模式」。

这保证了项目在**任何环境**下都可演示与使用。

## 六、数据与隐私

- 本项目**不收集、不上传、不存储**任何用户数据
- MCP Token 仅由用户本地配置，仓库内只提供环境变量占位符（`${MCD_MCP_TOKEN}`）
- 所有计算在本地完成（Python 标准库，无网络请求）
- 餐品信息、价格、活动以麦当劳官方接口实时返回为准
