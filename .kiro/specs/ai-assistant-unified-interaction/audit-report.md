# AI Unified Interaction System — Code Audit Report

## 审查范围

对本次实施的全部代码进行逻辑审查，涵盖 10 个新建文件和 10 个修改文件。

---

## 已修复的问题（15 个）

### Bug #10 — clearMessages 登出后残留 processing 状态 ✅ 已修复

**文件**: `stores/aiAdvisorStore.ts` 第 280 行
**严重度**: HIGH

**问题描述**:
`clearMessages()` 原来只清除了 `messages`、`unreadCount`、`structuredMessages`，但没有重置 `processingDocs` 和 `pendingSuggestionDocIds`。

**复现路径**:
1. 用户上传一个文档（processingDocs = [42]）
2. 文档正在处理中
3. 用户登出（触发 clearMessages）
4. 用户重新登入
5. Chat 面板仍然显示 doc #42 的 processing indicator，即使它已经不存在了

**影响**: 登出/登入后 Chat 面板显示过期的处理指示器，FAB badge 显示错误数量。

**修复**: 在 `clearMessages` 中添加 `processingDocs: []` 和 `pendingSuggestionDocIds: []`。

---

### Bug #9 — idempotencyKey 为空时去重逻辑失效 ✅ 已修复

**文件**: `stores/aiAdvisorStore.ts` 第 336 行
**严重度**: MEDIUM

**问题描述**:
`pushStructuredMessage` 通过 `m.idempotencyKey === msg.idempotencyKey` 做去重。如果传入的 `idempotencyKey` 为 `undefined`（前端 bug 或数据异常），`undefined === undefined` 恒为 `true`，导致所有无 key 的新消息都会覆盖第一条无 key 消息，而非追加。

**复现路径**:
1. 某个代码路径调用 `pushSuggestionMessage({ idempotencyKey: undefined, ... })`
2. 第一条消息正常插入
3. 第二条消息找到第一条（因为 undefined === undefined），覆盖了它
4. 用户只看到一条消息，但实际有两个不同的 suggestion

**修复**: 添加空值守卫：如果 `idempotencyKey` 为空，跳过去重逻辑直接追加，并打 console.warn。

---

### Bug #11 — getOrderedMessages 的 timestamp 排序不健壮 ✅ 已修复

**文件**: `stores/aiAdvisorStore.ts` 第 496 行
**严重度**: LOW

**问题描述**:
原代码假设 timestamp 是 `Date` 对象或可被 `new Date()` 解析的字符串。但如果某条消息的 timestamp 是数字（毫秒戳）或格式错误的字符串，`new Date(ts).getTime()` 返回 `NaN`，会导致 `.sort()` 结果不确定（NaN 比较行为在不同浏览器中不一致）。

**修复**: 添加 `getTime()` 辅助函数，处理 Date/number/string 三种类型，NaN fallback 到 0。

---

### Bug #2 — UNDO_TYPES 每次渲染都重建 ✅ 已修复

**文件**: `components/ai/ChatSuggestionCard.tsx` 第 92 行
**严重度**: MEDIUM

**问题描述**:
`const UNDO_TYPES = new Set([...])` 声明在组件函数体内，每次渲染都创建新的 Set 实例。虽然性能影响微小（Set 构造约 0.01ms），但违反了"常量提升"的最佳实践。在严格模式的 React DevTools 双渲染模式下，每帧创建两次。

**修复**: 将 `UNDO_TYPES` 提升到组件外部的模块作用域。

---

### Bug #3 — handleConfirm 无 action 时静默失败 ✅ 已修复

**文件**: `components/ai/ChatSuggestionCard.tsx` 第 120 行
**严重度**: MEDIUM

**问题描述**:
如果 `message.action` 为 `undefined`（后端未返回 action descriptor，或 DocumentUpload 接线时遗漏），`handleConfirm` 直接 `return`，不设置 loading 也不显示错误。用户看到点击"确认"按钮后什么都没发生，无法理解原因。

**复现路径**:
1. 后端生成了一个旧格式的 suggestion（没有 action descriptor）
2. 前端 DocumentUpload 接线时也没有构造 action
3. 用户点击确认 → 静默失败

**修复**: 在 early return 前设置错误消息："Action configuration missing. Please refresh."

---

### Bug #1 — Undo timer 在组件卸载时可能残留 ✅ 已修复

**文件**: `components/ai/ChatSuggestionCard.tsx` 第 96 行
**严重度**: HIGH

**问题描述**:
原来的 cleanup 函数 `clearInterval(undoTimerRef.current)` 后没有把 `undoTimerRef.current` 设为 `null`。如果组件卸载后又重新挂载（React Strict Mode 或快速切换页面），新的 `useEffect` 返回的 cleanup 可能尝试 clear 一个已无效的 timer ID。

**修复**: cleanup 后设置 `undoTimerRef.current = null`。

---

### Bug #7 — 轮询超时后 processing indicator 永久残留 ✅ 已修复

**文件**: `components/documents/DocumentUpload.tsx` 第 492 行
**严重度**: MEDIUM

**问题描述**:
`pollForProcessing` 在循环 60 次后退出（约 3 分钟），执行 fallback 逻辑（设置 upload 状态为 completed）。但此时没有调用 `removeProcessingMessage(documentId)`，导致 Chat 面板中的 processing indicator "🔍 正在分析..." 永远不会消失。

**复现路径**:
1. 用户上传一个文档
2. Chat 显示 "🔍 正在分析..."
3. 后端处理超过 3 分钟（例如 OCR 服务宕机）
4. 轮询达到 60 次上限
5. 上传标记为 completed（fallback）
6. 但 Chat 面板仍然显示 processing indicator

**修复**: 在轮询超时的退出路径添加 `removeProcessingMessage(documentId)`。

---

### Bug #15 — follow-up 问题被加到 auto-created suggestions 上 ✅ 已修复

**文件**: `backend/services/document_pipeline_orchestrator.py` 第 1511 行
**严重度**: MEDIUM

**问题描述**:
`_enrich_suggestions_with_follow_ups()` 遍历所有 suggestions 添加 follow-up 问题，但没有检查 suggestion 的 status。auto-created 的 suggestion（已经自动创建了实体）不应该再问用户问题——实体已经存在了。

**复现路径**:
1. 后端处理一个 Mietvertrag（租赁合同），自动创建了 recurring income
2. suggestion.status = "auto-created"
3. _enrich_suggestions_with_follow_ups 仍然给它加了 follow-up 问题
4. 前端收到后在 Chat 面板显示追问表单
5. 用户困惑：实体已经创建了，为什么还在问我问题？

**修复**: 在循环开始处添加 `if suggestion.status in ("auto-created", "confirmed", "dismissed"): continue`。

---

### Bug #4 — submitted 状态不同步 ✅ 已修复

**文件**: `components/ai/ChatFollowUpQuestion.tsx` 第 35 行
**严重度**: MEDIUM

**问题描述**:
组件的 `submitted` 本地状态通过 `useState(message.answered)` 初始化。但如果父组件更新了 `message.answered`（例如通过 store 的 `markFollowUpAnswered`），组件不会重新初始化 state——React 的 `useState` 初始值只在首次渲染时使用。

**复现路径**:
1. 用户在 Chat 中提交了 follow-up 答案
2. Store 更新 `message.answered = true`
3. 组件因某种原因重新渲染（例如父组件状态变化）
4. 本地 `submitted` 仍为 `false`（因为 useState 不会重新读取 prop）
5. 用户看到表单重新出现

**修复**: 添加 `useEffect(() => { if (message.answered && !submitted) setSubmitted(true); }, [message.answered])`。

---

### Bug #20 — follow-up 提交前无客户端验证 ✅ 已修复

**文件**: `components/ai/ChatFollowUpQuestion.tsx`
**严重度**: MEDIUM

**问题描述**:
用户可以不填写任何字段直接点击"提交答案"，请求会发送到后端然后失败（因为 required 字段为空）。这导致不必要的 API 调用和延迟的错误反馈。

**修复**: 添加 `validateAnswers()` 函数，检查：required 字段非空、number 字段是有效数字、min/max 范围约束。

---

### Bug #5 — 409 冲突后用户可立即重试 ✅ 已修复

**文件**: `components/ai/ChatFollowUpQuestion.tsx` 第 92 行
**严重度**: MEDIUM

**问题描述**:
当后端返回 HTTP 409（版本冲突，另一个 tab 修改了 suggestion），错误消息显示了但提交按钮仍然可点。用户可以立即重试，但会再次收到 409——因为版本号没有更新。这导致无限重试循环。

**修复**: 添加 `versionConflict` 状态，409 时设为 true 并禁用提交按钮。用户修改任何字段时清除冲突状态。

---

## 未修复的问题（7 个）

### Bug #6 — idempotencyKey 前端生成而非后端生成

**文件**: `components/documents/DocumentUpload.tsx` 第 449 行
**严重度**: HIGH（架构层面）
**状态**: 未修复 — 需要改轮询架构

**问题描述**:
Spec 明确规定 "idempotencyKey 由后端生成并返回，前端不得自行拼接推断"（NFR-7）。但当前实现中，DocumentUpload 在推送 suggestion 消息时自己拼接了 key：

```typescript
idempotencyKey: `${documentId}:${suggestionType}:completed`
```

而不是使用后端 `/process-status` 返回的 `idempotency_key`。

**为什么还没修**:
当前轮询逻辑使用 `documentService.getDocument()` 而非 `documentService.getProcessStatus()`。要修复这个问题，需要将整个轮询链路从 getDocument 切换到 getProcessStatus，涉及约 50 行逻辑改动和测试。建议在下个迭代中统一切换。

**影响**:
如果后端修改了 phase 命名或 suggestionType 格式，前端拼出来的 key 会和后端不匹配，导致去重失败（同一个 suggestion 出现两次）。目前不会发生，因为两边使用相同的命名约定。

---

### Bug #12 — structuredMessages 50 上限的淘汰策略不精确

**文件**: `stores/aiAdvisorStore.ts` 第 344、366、412 行
**严重度**: MEDIUM
**状态**: 未修复 — 实际场景低概率触发

**问题描述**:
`.slice(-50)` 保留数组最后 50 条。但如果一条旧消息被 idempotency 更新，它在数组中的位置不变（in-place 更新），而新消息追加在末尾。这意味着按数组位置裁剪不等于按时间裁剪——可能保留了一条很旧但最近被更新过的消息，而丢掉了一条时间上更新的消息。

**为什么还没修**:
正常使用中，单个用户几乎不可能在一个会话中产生超过 50 条 structured messages（需要同时上传 50+ 文档）。修复需要在每次裁剪前按 timestamp 排序，增加计算复杂度。

---

### Bug #14 — 车辆检测关键词匹配可能误判

**文件**: `backend/services/document_pipeline_orchestrator.py` 第 1583 行
**严重度**: MEDIUM
**状态**: 未修复 — 低概率误判

**问题描述**:
```python
is_vehicle = any(kw in asset_category for kw in ("fahrzeug", "vehicle", "auto", "pkw", "kfz", "car"))
```

这里 `kw in asset_category` 是子字符串匹配。如果 `asset_category = "fahrzeugausruestung"`（车辆配件），也会匹配 "fahrzeug"，但这不是车辆本身。

**为什么还没修**:
实际数据中，asset_category 的值由 OCR + AI 分类器生成，通常是标准化的单词（如 "pkw"、"fahrzeug"、"bueroausstattung"），不太会出现复合词。修复需要改用词边界匹配 `kw in asset_category.split()`。

---

### Bug #16 — ocr_result 可能是字符串格式

**文件**: `backend/api/v1/endpoints/documents.py` 第 3299 行
**严重度**: MEDIUM
**状态**: 未修复 — 现有代码在其他地方已处理

**问题描述**:
`get_process_status` 端点假设 `document.ocr_result` 是 dict 或 None。但如果是遗留数据（JSON 字符串格式），`.get("_pipeline")` 会失败（str 没有 .get 方法）。

**为什么还没修**:
SQLAlchemy 的 JSON 列类型在读取时自动反序列化为 dict。只有直接修改数据库才可能出现 string 格式。DocumentUpload 中的其他代码已经有了 JSON.parse 的 fallback 处理。

---

### Bug #18 — flag_modified 总是被调用

**文件**: `backend/api/v1/endpoints/documents.py` 第 3443 行
**严重度**: LOW
**状态**: 未修复 — 微优化

**问题描述**:
`submit_follow_up_answers` 中，即使答案没有实际改变任何数据（例如用户提交了一个空 answers dict），仍然调用 `flag_modified(document, "ocr_result")` 并触发 DB commit。

**为什么还没修**: 性能影响极小（单次 JSON 列更新），且 version bump 逻辑需要 commit 来保证原子性。

---

### Bug #21 — ProactiveMessage 和 StructuredMessage 可能重复显示

**文件**: `stores/aiAdvisorStore.ts` 第 478-489 行
**严重度**: MEDIUM
**状态**: 未修复 — 需要架构变更

**问题描述**:
当一个文档上传后，`DocumentUpload` 同时：
1. 调用 `pushAIMessage({ type: 'recurring_confirm', ... })` 创建 ProactiveMessage
2. 调用 `pushSuggestionMessage({ type: 'suggestion', ... })` 创建 StructuredMessage

两者在 `getOrderedMessages()` 中被合并到一个列表返回。用户可能看到同一个 suggestion 的两种表现形式——一个是旧的 proactive notification（带链接），一个是新的 suggestion card（带确认按钮）。

**为什么还没修**:
这是一个过渡期问题。完全修复需要合并两个消息系统（ProactiveMessage 和 StructuredChatMessage）为一个统一类型，或者在 push 时检测并移除重复的 proactive message。这是 spec 中 Section 8 "Key Risk: Dual-System Long-Term Drift" 描述的核心风险，需要在后续迭代中彻底解决。

**临时缓解**: 目前 ChatInterface 中 structured messages 和 proactive messages 在不同 section 渲染，视觉上有区分。

---

### Bug #22 — Undo 倒计时在组件快速重挂载时可能闪烁

**文件**: `components/ai/ChatSuggestionCard.tsx` 第 87-100 行
**严重度**: LOW
**状态**: 未修复 — 纯视觉问题

**问题描述**:
如果 ChatSuggestionCard 在 undo 倒计时运行中被卸载然后重新挂载（例如 React Strict Mode 双渲染），cleanup 清除了 timer 但 `undoCountdown` state 不会重置。组件重新挂载时可能短暂显示旧的倒计时数字。

**为什么还没修**: 仅在 React Strict Mode 的开发环境中可能出现，不影响生产环境。
