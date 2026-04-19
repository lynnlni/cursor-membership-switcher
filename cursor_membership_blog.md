# 逆向分析 Cursor 编辑器会员等级判定机制

> 环境：macOS Sequoia 15.4 / Cursor 最新版 / IDA Pro + ida-pro-mcp / Proxyman

---

## 一、背景

Cursor 是一款基于 VS Code 的 AI 编辑器，其 Pro/Pro+/Ultra 等付费等级决定了 AI 补全次数、模型访问权限等功能。本文从网络请求入手，逆向追踪会员等级在客户端的完整生命周期：**网络获取 → 数据解析 → 本地存储 → UI 判断**。

---

## 二、入口：网络请求

通过 Proxyman 抓包，发现 Cursor 登录后会请求：

```
GET https://api2.cursor.sh/auth/full_stripe_profile
Authorization: Bearer <access_token>
```

返回 JSON：

```json
{
  "membershipType": "free",
  "subscriptionStatus": "canceled",
  "paymentId": "xxxxx",
  "lastPaymentFailed": false,
  "isOnStudentPlan": false,
  "isTeamMember": false,
  ...
}
```

关键字段是 `membershipType`，可能的值为：`free`、`pro`、`pro_plus`、`ultra`、`enterprise`、`free_trial`。

---

## 三、客户端代码定位

Cursor 是 Electron 应用，核心逻辑在打包后的 JS 文件中：

```
/Applications/Cursor.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js
```

该文件约 50MB（minified），通过 `grep` 定位关键字符串：

```bash
grep -n "membershipType" workbench.desktop.main.js
grep -n "full_stripe_profile" workbench.desktop.main.js
```

### 3.1 MembershipType 枚举定义

在 minified JS 中找到枚举定义：

```js
(function(Pa) {
  Pa.FREE       = "free"
  Pa.PRO        = "pro"
  Pa.PRO_PLUS   = "pro_plus"
  Pa.ENTERPRISE = "enterprise"
  Pa.FREE_TRIAL = "free_trial"
  Pa.ULTRA      = "ultra"
})(Pa || (Pa = {}))
```

### 3.2 网络请求发起

`getStripeProfile` 函数：

```js
this.getStripeProfile = async () => {
  const U = await this.getAccessToken();
  if (U) try {
    return await (await fetch(
      `${this.cursorCredsService.getBackendUrl()}/auth/full_stripe_profile`,
      {
        headers: {
          Authorization: `Bearer ${U}`,
          // ... 其他 header
        }
      }
    )).json();
  } catch (q) {
    console.error("Failed to fetch stripe profile:", q);
  }
};
```

### 3.3 响应解析与存储

`refreshMembership()` 是核心函数，负责获取 profile 并写入本地存储：

```js
this.refreshMembership = async () => {
  // 1. 无 token → 设为 FREE
  if (!U) {
    this.storeMembershipType(Pa.FREE);
    return;
  }

  // 2. 先查 team 信息
  const q = await this.getTeams();
  const J = q.some(z => z.hasBilling && z.seats > 0);

  // 3. 如果是付费 team 成员 → ENTERPRISE
  if (J) {
    this.storeMembershipType(Pa.ENTERPRISE);
    // ... 处理 bedrock 等
  } else {
    // 4. 否则请求 full_stripe_profile
    const Y = await fetch(`/auth/full_stripe_profile`, { ... });
    G = await Y.json();
    
    // 5. 直接取 JSON 中的 membershipType 写入本地
    this.storeMembershipType(G.membershipType);
    this.storeSubscriptionStatus(G.subscriptionStatus);
  }
};
```

### 3.4 本地存储

`storeMembershipType` 将值写入 Electron 的 SQLite 数据库：

```js
this.storeMembershipType = r => {
  const s = this.membershipType();
  r = r ?? Pa.FREE;
  this.storageService.store("cursorAuth/stripeMembershipType", r, -1, 1);
  // 同时触发内存中的 reactive storage 更新
  if (s !== r) {
    this.notifySubscriptionChangedListeners(r, s, o);
    this._onDidChangeSubscription.fire(r);
  }
};
```

数据库文件位置：

```
~/Library/Application Support/Cursor/User/globalStorage/state.vscdb
```

通过 sqlite3 直接查询：

```bash
sqlite3 ~/Library/Application\ Support/Cursor/User/globalStorage/state.vscdb \
  "SELECT key, value FROM ItemTable WHERE key LIKE '%cursorAuth%'"
```

输出示例：

```
cursorAuth/stripeMembershipType|pro
cursorAuth/stripeSubscriptionStatus|active
cursorAuth/cachedEmail|user@example.com
```

### 3.5 读取时的 switch 判断

```js
this.membershipType = () => {
  switch (this._membershipType()) {  // 从 storage 读取
    case Pa.ENTERPRISE:  return Pa.ENTERPRISE   // "enterprise"
    case Pa.PRO:         return Pa.PRO           // "pro"
    case Pa.PRO_PLUS:    return Pa.PRO_PLUS      // "pro_plus"
    case Pa.FREE_TRIAL:  return Pa.FREE_TRIAL    // "free_trial"
    case Pa.ULTRA:       return Pa.ULTRA         // "ultra"
    default:             return Pa.FREE          // "free"
  }
};
```

### 3.6 UI 层面的 Pro 判断

```js
// 是否有付费权限
function isPaidUser(n) {
  return n === Pa.ULTRA || n === Pa.PRO || n === Pa.PRO_PLUS
      || n === Pa.ENTERPRISE || n === Pa.FREE_TRIAL;
}

// 登录后触发 Pro UI 解锁
if (membershipType() === Pa.PRO || membershipType() === Pa.PRO_PLUS 
    || membershipType() === Pa.ULTRA) {
  this.setUsageBar(); // 显示用量条等 Pro 功能
}

// 分享功能限制
if (membershipType === Pa.FREE || membershipType === Pa.FREE_TRIAL) {
  return { success: false, reason: "Share feature is only available for Pro users." };
}
```

---

## 四、数据流全貌

```
                    ┌──────────────────┐
                    │ Cursor 启动/登录  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  getTeams()      │
                    │  查询团队信息      │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │ 是付费团队     │              │ 否
              ▼                             ▼
    storeMembershipType          GET /auth/full_stripe_profile
    ("enterprise")                        │
                                         ▼
                               解析 JSON: membershipType
                                         │
                                         ▼
                              storeMembershipType(G.membershipType)
                                         │
                          ┌──────────────┼──────────────┐
                          ▼                             ▼
                 SQLite (state.vscdb)         内存 (reactive storage)
                 key: cursorAuth/             同时更新，驱动 UI
                 stripeMembershipType
                          │
                          ▼
                  membershipType() 读取
                  → switch 判断返回枚举值
                          │
                          ▼
                  UI 层 isPaidUser() 等
                  → 决定功能开关
```

---

## 五、方案探索与演进

### 方案 A：直接写 SQLite（失败）

最初尝试直接修改 `state.vscdb` 中的 `cursorAuth/stripeMembershipType` 值。

**问题：** `refreshMembership()` 会在启动、定时刷新、登录等时机重新请求网络，覆盖本地值。修改后几秒即失效。

### 方案 B：SQLite Trigger 锁定（失败）

在数据库上创建 `BEFORE UPDATE` trigger 拦截写入：

```sql
CREATE TRIGGER lock_membership
BEFORE UPDATE ON ItemTable
WHEN NEW.key = 'cursorAuth/stripeMembershipType'
BEGIN
    SELECT RAISE(IGNORE);
END;
```

**问题：** trigger 只拦截了 SQLite 写入，但 `storeMembershipType()` 同时更新了内存中的 reactive storage。内存值被修改后直接驱动 UI 刷新，虽然重启后 SQLite 保留旧值，但很快又被网络刷新覆盖。本质上内存和数据库是双写的。

### 方案 C：Patch JS 文件（最终方案）

分析 `storeMembershipType` 的函数体：

```js
// 原始代码
this.storeMembershipType = r => {
  const s = this.membershipType(), o = this.subscriptionStatus();
  r = r ?? Pa.FREE;           // ← patch 注入点
  this.storageService.store(MDt, r, -1, 1);
  // ...
};
```

在 `r=r??Pa.FREE` 前插入一行赋值：

```js
/*__cursor_membership_patch__*/r="pro";  // 强制覆盖
r=r??Pa.FREE,
```

**原理：** 无论网络返回什么值，在写入 SQLite 和更新内存之前，`r` 被强制赋值为目标值。这样两层存储都拿到的是正确的值，不需要拦截网络、不需要锁定数据库。

**优势：**
- 改动极小（插入一行代码）
- 不需要额外服务（mitmproxy/Proxyman）
- 内存和 SQLite 同时正确
- 支持一键还原

---

## 六、工具实现

基于方案 C 开发了 Python 命令行工具，核心逻辑：

```python
# 定位 patch 点
ORIGINAL_SNIPPET = "r=r??Pa.FREE,"
PATCH_MARKER = "/*__cursor_membership_patch__*/"

def apply_patch(value):
    content = read_js()
    
    if current_patch(content) is not None:
        # 已有 patch，替换值
        content = re.sub(
            PATCH_MARKER + r'r="\w+";',
            f'{PATCH_MARKER}r="{value}";',
            content
        )
    else:
        # 首次 patch，备份并插入
        shutil.copy2(JS_PATH, BACKUP_PATH)
        content = content.replace(
            ORIGINAL_SNIPPET,
            f'{PATCH_MARKER}r="{value}";' + ORIGINAL_SNIPPET,
            1
        )
    write_js(content)
```

运行效果：

```
$ python3 cursor_membership.py

==============================================
  Cursor Membership Switcher (macOS)
==============================================
  JS patch : not patched (original)
----------------------------------------------
  [1] Free         (free)
  [2] Free Trial   (free_trial)
  [3] Pro          (pro)
  [4] Pro+         (pro_plus)
  [5] Ultra        (ultra)
  [6] Enterprise   (enterprise)
  [r] Restore original (remove patch)
  [q] Quit
----------------------------------------------
  Select: 3

  Patched: storeMembershipType will always use "pro"
  Restart Cursor to apply.
```

---

## 七、总结

| 方案 | 原理 | 结果 |
|------|------|------|
| 写 SQLite | 修改本地存储值 | 失败，网络刷新覆盖 |
| SQLite Trigger | 拦截数据库写入 | 失败，内存双写绕过 |
| JS Patch | 修改函数逻辑，拦截赋值 | 成功，源头阻断 |

**核心教训：** Electron 应用的状态管理往往涉及多层存储（SQLite + 内存 reactive state），单一层面拦截无法解决问题。最可靠的方案是在数据流的源头——即 JS 逻辑内部——进行拦截。

**注意事项：** Cursor 更新后会覆盖 JS 文件，需要重新执行 patch。工具已内置备份与还原功能。
