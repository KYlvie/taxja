# 设计文档：AI 确认系统 + 文档分类器模式补全

## 1. 后端设计 — 分类器模式补全

### 1.1 关键词模式结构
每个新文档类型在 `_load_patterns()` 中添加条目，结构与现有类型一致：
```python
DocumentType.XXX: {
    "keywords": [...],        # 所有相关关键词
    "required_keywords": [],  # 必须全部匹配（通常为空）
    "required_any": [...],    # 至少一个必须匹配
    "weight": 1.0,            # 权重
}
```

### 1.2 OCR_TO_DB_TYPE_MAP 补全
在 `document_pipeline_orchestrator.py` 中添加映射：
```python
OCRDocumentType.SPENDENBESTAETIGUNG: DBDocumentType.SPENDENBESTAETIGUNG,
OCRDocumentType.VERSICHERUNGSBESTAETIGUNG: DBDocumentType.VERSICHERUNGSBESTAETIGUNG,
# ... 其余类型
```

### 1.3 KONTOAUSZUG vs BANK_STATEMENT
- `KONTOAUSZUG` 是详细的银行账户流水（多页、多笔交易）
- `BANK_STATEMENT` 是银行对账单（摘要性质）
- 两者关键词有重叠，通过 `required_any` 和 `weight` 区分
- `KONTOAUSZUG` 侧重：kontoauszug, kontobewegungen, buchungsdetails
- `BANK_STATEMENT` 保持现有模式不变

## 2. 前端设计 — AI 确认系统

### 2.1 状态管理（aiAdvisorStore 扩展）
```typescript
interface PendingConfirmation {
  id: string;
  message: string;
  resolve: (confirmed: boolean) => void;
}

// 新增 state
pendingConfirmation: PendingConfirmation | null;

// 新增 actions
requestConfirmation: (message: string) => Promise<boolean>;
resolveConfirmation: (confirmed: boolean) => void;
```

### 2.2 useAIConfirmation Hook
```typescript
function useAIConfirmation() {
  const { requestConfirmation } = useAIAdvisorStore();
  return { confirm: requestConfirmation };
}
```

调用方式：
```typescript
const { confirm } = useAIConfirmation();
const ok = await confirm(t('transactions.deleteCheck.confirmDelete'));
if (!ok) return;
```

### 2.3 FloatingAIChat 确认消息渲染
- 当 `pendingConfirmation` 不为 null 时，在聊天面板底部渲染确认消息
- 消息样式：AI 头像 + 消息文本 + 确认/取消按钮
- 桌面端：自动展开面板（如果折叠）
- 移动端：自动打开 FAB 面板

### 2.4 全局遮罩层
- 组件：`AIConfirmationOverlay`
- 位置：在 `FloatingAIChat` 内部渲染，条件为 `pendingConfirmation !== null`
- 样式：`position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 9998`
- AI 面板 z-index: `9999`（高于遮罩）
- 点击遮罩不关闭（强制用户通过按钮回复）

### 2.5 TransactionsPage 改造
替换所有 `window.confirm()` / `window.alert()` 为 `useAIConfirmation().confirm()`：
- `handleDeleteTransaction`: 4 处替换
- `handleBatchDelete`: 3 处替换

### 2.6 数据流
```
用户点击删除 → handleDeleteTransaction
  → deleteCheck API
  → confirm(message) → store.requestConfirmation(message)
    → 设置 pendingConfirmation + 显示遮罩
    → FloatingAIChat 渲染确认消息
    → 用户点击确认/取消
    → store.resolveConfirmation(true/false)
    → Promise resolve → 继续/中止删除
```

## 3. 文件变更清单

| 文件 | 变更 |
|------|------|
| `backend/app/services/document_classifier.py` | 添加 10 个新类型的 patterns |
| `backend/app/services/document_pipeline_orchestrator.py` | 添加 OCR_TO_DB_TYPE_MAP 映射 |
| `frontend/src/stores/aiAdvisorStore.ts` | 添加 pendingConfirmation 状态 |
| `frontend/src/hooks/useAIConfirmation.ts` | 新建 hook |
| `frontend/src/components/ai/FloatingAIChat.tsx` | 渲染确认消息 + 遮罩 |
| `frontend/src/components/ai/FloatingAIChat.css` | 遮罩 + 确认消息样式 |
| `frontend/src/pages/TransactionsPage.tsx` | 替换 confirm/alert |
| `frontend/src/i18n/locales/en.json` | AI 确认相关文案 |
| `frontend/src/i18n/locales/de.json` | AI 确认相关文案 |
| `frontend/src/i18n/locales/zh.json` | AI 确认相关文案 |
| `backend/tests/test_document_classifier_new_types.py` | 新类型分类测试 |
