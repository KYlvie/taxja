# 文档删除功能集成指南

## 已完成的工作

### 后端实现 ✅

1. **修改删除API** (`backend/app/api/v1/endpoints/documents.py`)
   - 添加 `delete_mode` 参数：`document_only` (默认) 或 `with_data`
   - `document_only`: 只删除文档文件，保留所有数据
   - `with_data`: 删除文档和所有关联数据（房产、交易、定期交易）

2. **新增关联数据查询API** (`backend/app/api/v1/endpoints/documents.py`)
   - `GET /api/v1/documents/{id}/related-data`
   - 返回文档关联的房产、交易、定期交易信息

### 前端实现 ✅

1. **更新documentService** (`frontend/src/services/documentService.ts`)
   - `deleteDocument(id, deleteMode)` - 支持删除模式参数
   - `getDocumentRelatedData(id)` - 获取关联数据

2. **创建删除对话框组件** (`frontend/src/components/documents/DeleteDocumentDialog.tsx`)
   - 显示关联数据
   - 两种删除选项（单选）
   - 警告和建议提示

3. **添加样式** (`frontend/src/components/documents/DeleteDocumentDialog.css`)
   - 响应式设计
   - 清晰的视觉层次

4. **添加i18n翻译**
   - `frontend/src/i18n/locales/de.json`
   - `frontend/src/i18n/locales/en.json`
   - `frontend/src/i18n/locales/zh.json`

## 需要集成的地方

### DocumentList组件

在 `frontend/src/components/documents/DocumentList.tsx` 中：

```typescript
import DeleteDocumentDialog from './DeleteDocumentDialog';

const DocumentList = () => {
  const [deletingDocumentId, setDeletingDocumentId] = useState<number | null>(null);

  const handleDeleteClick = (documentId: number) => {
    setDeletingDocumentId(documentId);
  };

  const handleDeleteConfirm = async (deleteMode: 'document_only' | 'with_data') => {
    try {
      await documentService.deleteDocument(deletingDocumentId!, deleteMode);
      setDeletingDocumentId(null);
      // Refresh document list
      loadDocuments();
      // Show success message
      alert(t('documents.deleteSuccess'));
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert(t('documents.deleteError'));
    }
  };

  const handleDeleteCancel = () => {
    setDeletingDocumentId(null);
  };

  return (
    <div>
      {/* Document list UI */}
      <button onClick={() => handleDeleteClick(document.id)}>
        🗑️ {t('common.delete')}
      </button>

      {/* Delete confirmation dialog */}
      {deletingDocumentId && (
        <DeleteDocumentDialog
          documentId={deletingDocumentId}
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
        />
      )}
    </div>
  );
};
```

### DocumentsPage组件

如果DocumentsPage直接处理删除，也需要类似的集成。

## 用户体验流程

1. **用户点击删除按钮**
   - 触发 `handleDeleteClick(documentId)`

2. **显示删除对话框**
   - 自动加载关联数据
   - 显示加载状态

3. **用户看到关联数据**
   - 如果有关联数据，显示警告和详情
   - 如果没有关联数据，直接显示删除选项

4. **用户选择删除模式**
   - **仅删除文档**（推荐）：绿色，默认选中
   - **删除全部数据**：红色，显示警告

5. **用户确认删除**
   - 调用API with选定的模式
   - 显示成功/失败消息
   - 刷新文档列表

## 测试场景

### 场景1：删除Kaufvertrag（有关联房产）
- 显示房产信息（地址、购买价格）
- 显示关联交易
- 推荐"仅删除文档"
- 如果选择"删除全部"，显示红色警告

### 场景2：删除Mietvertrag（有定期交易）
- 显示定期租金收入信息
- 推荐"仅删除文档"

### 场景3：删除普通Receipt（无关联数据）
- 不显示关联数据警告
- 两种选项都可用
- 默认"仅删除文档"

## 后续改进建议

1. **批量删除**
   - 支持选择多个文档一次性删除
   - 显示所有关联数据的汇总

2. **孤儿数据清理**
   - 添加"查找孤儿数据"功能
   - 列出没有关联文档的房产/交易
   - 批量清理选项

3. **删除历史**
   - 记录删除操作日志
   - 支持查看删除历史
   - 审计追踪

4. **软删除**
   - 考虑实现软删除（标记为已删除）
   - 30天内可恢复
   - 自动清理过期的软删除记录

## 相关文件

### 后端
- `backend/app/api/v1/endpoints/documents.py` - API endpoints
- `backend/app/services/property_service.py` - 房产删除逻辑
- `backend/app/models/document.py` - 文档模型

### 前端
- `frontend/src/components/documents/DeleteDocumentDialog.tsx` - 删除对话框
- `frontend/src/components/documents/DeleteDocumentDialog.css` - 样式
- `frontend/src/components/documents/DocumentList.tsx` - 需要集成
- `frontend/src/services/documentService.ts` - API服务
- `frontend/src/i18n/locales/*.json` - 翻译文件

## 注意事项

1. **数据安全**
   - 默认模式是"仅删除文档"，保护用户数据
   - "删除全部"需要明确的用户确认

2. **用户教育**
   - 清晰的说明和建议
   - 视觉上区分安全和危险操作

3. **错误处理**
   - 如果房产删除失败，继续删除文档
   - 显示详细的错误信息

4. **性能**
   - 关联数据查询应该快速
   - 考虑缓存常用查询

---

**实施状态**: 后端和前端组件已完成，需要在DocumentList中集成
**测试状态**: 待测试
**文档更新**: 2026-03-09
