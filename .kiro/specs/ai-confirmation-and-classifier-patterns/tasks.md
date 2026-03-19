# 实施任务：AI 确认系统 + 文档分类器模式补全

## Part A: 后端 — 分类器模式补全

### Task 1: 分类器添加 10 个新文档类型的关键词模式
- [x] 在 `document_classifier.py` 的 `_load_patterns()` 中为以下类型添加 patterns：spendenbestaetigung, versicherungsbestaetigung, kinderbetreuungskosten, fortbildungskosten, pendlerpauschale, kirchenbeitrag, grundbuchauszug, betriebskostenabrechnung, gewerbeschein, kontoauszug
- [x] 每个类型包含 keywords、required_any、weight 配置
- [x] 确保 kontoauszug 与现有 bank_statement 不冲突

**涉及文件**: `backend/app/services/document_classifier.py`
**对应需求**: FR-1, FR-3

### Task 2: Pipeline 映射补全
- [x] 在 `document_pipeline_orchestrator.py` 的 `OCR_TO_DB_TYPE_MAP` 中添加 10 个新类型的映射

**涉及文件**: `backend/app/services/document_pipeline_orchestrator.py`
**对应需求**: FR-2

### Task 3: 后端测试
- [x] 编写分类器测试，验证每个新类型能被正确识别
- [x] 验证现有类型分类不受影响

**涉及文件**: `backend/tests/test_document_classifier_new_types.py`
**对应需求**: NFR-3

## Part B: 前端 — AI 确认系统

### Task 4: aiAdvisorStore 扩展
- [x] 添加 `pendingConfirmation` 状态
- [x] 添加 `requestConfirmation(message)` → `Promise<boolean>` action
- [x] 添加 `resolveConfirmation(confirmed: boolean)` action

**涉及文件**: `frontend/src/stores/aiAdvisorStore.ts`
**对应需求**: FR-4

### Task 5: 创建 useAIConfirmation hook
- [x] 新建 `frontend/src/hooks/useAIConfirmation.ts`
- [x] 导出 `confirm(message: string): Promise<boolean>` 方法

**涉及文件**: `frontend/src/hooks/useAIConfirmation.ts`
**对应需求**: FR-5

### Task 6: FloatingAIChat 确认消息渲染 + 遮罩层
- [x] 当 `pendingConfirmation` 存在时，渲染确认消息（AI 头像 + 文本 + 确认/取消按钮）
- [x] 桌面端自动展开面板，移动端自动打开 FAB
- [x] 添加全局遮罩层（背景变暗 + 禁用交互）
- [x] 遮罩 z-index < AI 面板 z-index

**涉及文件**: `frontend/src/components/ai/FloatingAIChat.tsx`, `frontend/src/components/ai/FloatingAIChat.css`
**对应需求**: FR-6, FR-7, NFR-1, NFR-2

### Task 7: TransactionsPage 替换 confirm/alert
- [x] 替换 `handleDeleteTransaction` 中的 `window.confirm()` 和 `window.alert()`
- [x] 替换 `handleBatchDelete` 中的 `window.confirm()` 和 `window.alert()`
- [x] 使用 `useAIConfirmation().confirm()` 替代

**涉及文件**: `frontend/src/pages/TransactionsPage.tsx`
**对应需求**: FR-8

### Task 8: i18n — AI 确认相关文案
- [x] 在三语文件中添加 `ai.confirmation.confirm`、`ai.confirmation.cancel`、`ai.confirmation.title` 等 key

**涉及文件**: `frontend/src/i18n/locales/en.json`, `de.json`, `zh.json`
**对应需求**: FR-9
