# 需求文档：AI 确认系统 + 文档分类器模式补全

## 1. 概述

本功能包含两个子系统：
1. **后端**：为 11 个新增文档类型添加 OCR 关键词模式规则，并补全 pipeline 映射
2. **前端**：用 AI 聊天面板内的确认消息替代浏览器原生 `confirm()`/`alert()` 弹框，实现统一的 AI 交互体验

## 2. 用户故事

### 2.1 文档分类器模式补全
- 作为用户，当我上传捐赠确认（Spendenbestätigung）、保险确认、儿童看护费用、继续教育费用、通勤补贴确认、教会税确认、土地登记摘录、物业管理费结算单、营业执照、银行账户流水等文档时，系统应能自动识别并正确分类
- 作为用户，分类结果应通过完整的 pipeline 链路（OCR → 分类 → 提取 → 建议）正确传递到前端

### 2.2 AI 确认系统
- 作为用户，当系统需要我确认操作（如删除交易）时，确认提示应出现在 AI 聊天面板中，而非浏览器原生弹框
- 作为用户，当 AI 面板显示确认请求时，页面背景应变暗/禁用，强制我立即回复
- 作为用户，确认消息应包含"确认"和"取消"按钮，点击后立即恢复正常状态
- 作为用户，整个交互应感觉像在和 AI 助手对话，而非与系统弹框交互

## 3. 功能需求

### 3.1 后端 — 分类器模式规则
- FR-1: 为以下 11 个文档类型在 `document_classifier.py` 的 `self.patterns` 中添加关键词模式：
  - `spendenbestaetigung`（捐赠确认）
  - `versicherungsbestaetigung`（保险确认）
  - `kinderbetreuungskosten`（儿童看护费用）
  - `fortbildungskosten`（继续教育费用）
  - `pendlerpauschale`（通勤补贴确认）
  - `kirchenbeitrag`（教会税确认）
  - `grundbuchauszug`（土地登记摘录）
  - `betriebskostenabrechnung`（物业管理费结算单）
  - `gewerbeschein`（营业执照）
  - `kontoauszug`（银行账户流水）
- FR-2: 在 `OCR_TO_DB_TYPE_MAP` 中添加新类型的映射
- FR-3: 每个类型应包含 `keywords`、`required_any`（至少一个必须匹配）、`weight` 配置

### 3.2 前端 — AI 确认系统
- FR-4: 在 `aiAdvisorStore` 中添加确认请求状态管理（`pendingConfirmation`）
- FR-5: 创建 `useAIConfirmation` hook，提供 `requestConfirmation(message)` → `Promise<boolean>` 接口
- FR-6: 在 `FloatingAIChat` 中渲染确认消息，包含确认/取消按钮
- FR-7: 确认请求激活时，显示全局遮罩层（背景变暗 + 禁用交互）
- FR-8: 替换 `TransactionsPage.tsx` 中所有 `window.confirm()` 和 `window.alert()` 调用
- FR-9: 三语 i18n 支持（德语、英语、中文）

## 4. 非功能需求
- NFR-1: 确认弹出响应时间 < 100ms
- NFR-2: 遮罩层应覆盖整个视口，z-index 高于所有其他元素（AI 面板除外）
- NFR-3: 分类器新模式不应影响现有类型的分类准确性
