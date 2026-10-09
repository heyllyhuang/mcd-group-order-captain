# 麦当劳中国 MCP 工具参考

> **工具名以官方仓库为准**：<https://github.com/M-China/mcd-mcp-server>
> 价格、券、活动实时变化，参数与字段一律以 MCP 实际返回的 schema 为准，本文档只用于理解能力边界。

## 一、接入准备

### 1. 申请 MCP Token

1. 打开 <https://open.mcd.cn/mcp>（手机号验证登录）
2. 点右上角「控制台」→ 点「激活」申请 Token
3. 阅读并同意服务协议，一键复制 Token
4. **Token 等同账号凭据**：不要提交到 Git、不要贴到群里

### 2. MCP Server 连接信息

| 项 | 值 |
|---|---|
| 类型 | Streamable HTTP |
| URL | `https://mcp.mcd.cn` |
| 鉴权 | 请求头 `Authorization: Bearer <YOUR_MCP_TOKEN>` |
| 限流 | **600 次/分钟**，超出返回 429 |

WorkBuddy 接入路径：左侧【专家·技能·连接器】→【连接器】→ 右上角【自定义连接器】→【配置 MCP】→ 粘贴 JSON → 保存 → **回到列表把 mcd-mcp「启用」**。

配置见仓库根目录的 `mcp-config.example.json`（脱敏，仅含环境变量占位符）。

### 3. 错误码

| code | 原因 | 处理 |
|---|---|---|
| 401 | Token 无效/过期/未提供 | 检查 Authorization 头 |
| 429 | 超过 600 次/分钟 | 降低请求频率 |

## 二、工具清单

> ⭐ = 与「多人团餐」场景直接相关；★ = 本 Skill 主链路会用到

### 菜单与商品

| 工具 | 作用 | 团餐场景里的用法 |
|---|---|---|
| `query-meals` ★ | 查当前门店**可售菜单**（分类、餐品编码、标签） | 把每个人的口语翻译成具体餐品编码 |
| `query-meal-detail` ★ | 按餐品编码查**餐品详情**（套餐组成、可替换项） | 拆套餐、判断能不能把可乐换成无糖 |
| `list-nutrition-foods` ★ | 餐品**营养数据**（能量/蛋白/脂肪/碳水/钠/钙） | 有人提「减肥」「清淡」「热量」时必调 |
| **`query-meal-assistance`** ⭐ | **查询助餐服务**——仅企业团餐场景，查该门店支持的助餐服务 | **团餐专用**：确认这家店能不能承接企业团餐、有哪些助餐选项 |

### 门店与地址

| 工具 | 作用 | 团餐场景里的用法 |
|---|---|---|
| `delivery-query-addresses` ★ | 查用户可配送地址列表 | 确认送到办公室哪个地址 |
| `delivery-create-address` | 新增配送地址 | 第一次用新地址时 |
| `delivery-query-stores` | 按收货地址查**可配送门店** | 判断「哪家店能送我们这」 |
| `query-nearby-stores` | 查地址附近的门店 | 想自提时找最近的门店 |

### 优惠券（省钱的来源）

| 工具 | 作用 | 团餐场景里的用法 |
|---|---|---|
| `auto-bind-coupons` ★ | **麦麦省一键领券**（自动领完所有可领的） | 第一步，无脑先领，纯赚 |
| `available-coupons` ★ | 麦麦省**可领取**的券列表 | 看还有哪些羊毛没薅 |
| **`query-store-coupons`** ★ | 查**当前门店实际可用**的券 | 关键：**领了≠能用**，算价必须按门店查 |
| `query-my-coupons` | 查**我账户下**已有的全部券 | 看自己已经有什么券可用 |

### 算价与订单

| 工具 | 作用 | 团餐场景里的用法 |
|---|---|---|
| `calculate-price` ★ | 按商品列表（可带券）算**金额、配送费、优惠、应付** | 凑单试算 / 比价，可反复调 |
| `create-order` ★ | 创建订单，返回订单详情与**支付链接** | 下单（**务必先确认总额**） |
| `cancel-order` | 取消订单 | 下错单时 |
| `query-order` ★ | 查订单状态、内容、配送信息 | 下单后追踪 |
| `order-list` | 查近期到店/外送历史订单 | 回顾上次怎么点的 |

### 活动与营销

| 工具 | 作用 | 团餐场景里的用法 |
|---|---|---|
| `campaign-calendar` ★ | 查当月**营销活动日历**（进行中/往期/未来） | 判断「有没有更大的活动值得等」 |
| `query-party-city` / `query-party-store` / `query-partystore-date` / `query-partystore-session` / `party-order-create` | 主题活动（派对、品鉴会）的城市→门店→日期→场次→下单 | 团建场景可考虑 |

### 积分与商城（本 Skill 暂未使用，列出备查）

`query-my-account`（积分查询）、`mall-points-products`、`mall-product-detail`、`mall-create-order`、`mall-order-list`、`mall-order-detail`、`query-lottery-info`、`draw-lottery`、`query-my-prizes`

### 工具类

| 工具 | 作用 |
|---|---|
| `now-time-info` | 获取当前完整时间信息，便于判断活动是否在有效期内 |

## 三、调用顺序（团餐主链路）

```
now-time-info              # 0. 拿当前时间（判断活动有效期）
   ↓
campaign-calendar          # 1. 促销侦察：当月有哪些活动
auto-bind-coupons          # 2. 先领券（纯赚）
   ↓
query-meals                # 3. 拿菜单
query-meal-detail          # 4. 拆套餐
query-meal-assistance      # 5.（企业团餐）查助餐服务
   ↓
query-store-coupons        # 6. 查当前门店可用券
calculate-price            # 7. 试算（凑单/比价/拆单对比）
   ↓
delivery-query-addresses   # 8. 确认地址
create-order               # 9. 下单拿支付链接
```

## 四、踩坑记录

1. **领了券 ≠ 能用**。`available-coupons` 是可领取，**`query-store-coupons` 才是当前门店可用**，算价必须用后者。
2. **`calculate-price` 是幂等试算**，可放心反复调做凑单/拆单对比，不会产生订单。
3. **`create-order` 会真实产生订单和支付链接**，务必让团长确认总额后再调。
4. **餐品编码不要写死**。同一款餐品在不同门店的编码可能不同，一切以 `query-meals` 返回为准。
5. **外送费与免配送门槛因门店而异**，从 `calculate-price` 返回里读，不要预设「满 39 免运费」这类记忆中的规则。
6. **注意 600 次/分钟限流**，拆单枚举时不要对每个组合都打一次真实接口，优先本地用 `calculate-price` 的返回结果做离线测算。
7. **Token 失效**返回 401，重新到控制台激活即可；此时 Skill 自动降级为手动模式更稳妥。

## 五、限购与优惠规则怎么查

买单策略（模式 C）能不能成立，前提是搞清楚**优惠到底怎么限**：

1. `campaign-calendar` —— 查当月活动日历。**有时「等两天再点」比今天点更划算**，尤其月底大促前
2. `query-store-coupons` / `query-my-coupons` —— 看券的**门槛、面额、每单可用张数**
3. 活动细则（商品页 / 门店页）—— 确认限购是「**每单**限 N 份」还是「**每人**限 N 份」

**为什么必须分清这两种限购**

| 限购类型 | 拆单是否有效 |
|---|---|
| 每单限 N 份 | ✅ 有效——拆成 k 单就能吃 k 遍名额 |
| 每人限 N 份 | ❌ 无效——拆单只多付配送费 |

> ⚠️ **MCP 通常不返回限购数量与范围**，这两项属于「必须人工确认」字段，见 SKILL.md 的 Step 0。
> 拿不准时：按「每人限购」保守处理，并明确告诉团长「拆单收益存疑，建议先确认门店规则」。
