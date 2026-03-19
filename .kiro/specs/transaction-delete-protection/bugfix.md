# Bugfix Requirements Document

## Introduction

交易删除功能存在两个缺陷：（1）删除交易时缺乏保护机制，不检查交易是否绑定了文档（`document_id`）或来自定期交易（`source_recurring_id`），导致关联文档的 line items 变成孤立状态，用户也无法感知关联关系；（2）文档详情页的 line items 表格不显示交易创建状态，用户无法区分哪些 line items 已创建交易、哪些尚未创建。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 用户删除一笔绑定了文档（`document_id` 不为空）且该文档仅关联这一笔交易的交易 THEN 系统直接删除该交易，不给出任何警告，导致文档的 line items 变成孤立状态

1.2 WHEN 用户删除一笔绑定了文档（`document_id` 不为空）且该文档还关联了其他交易的交易 THEN 系统直接删除该交易，不提示用户该交易来自某文档以及该文档共有多少笔交易

1.3 WHEN 用户删除一笔来自定期交易（`source_recurring_id` 不为空）的交易 THEN 系统直接删除该交易，不提示用户下次定期交易仍会自动生成

1.4 WHEN 用户通过批量删除（batch-delete）删除包含上述关联关系的交易 THEN 系统直接批量删除所有交易，不进行任何关联检查或提示

1.5 WHEN 用户查看文档详情页中包含多个 line items 的文档 THEN 系统不显示每个 line item 的交易创建状态，用户无法区分哪些已创建交易、哪些未创建

### Expected Behavior (Correct)

2.1 WHEN 用户删除一笔绑定了文档且该文档仅关联这一笔交易的交易 THEN 系统 SHALL 阻止删除并返回错误信息，提示"此交易关联了文档 {document_name}，请从文档管理中修改"

2.2 WHEN 用户删除一笔绑定了文档且该文档还关联了其他交易的交易 THEN 系统 SHALL 返回需要确认的提示信息，包含文档名称和该文档关联的交易总数（如"此交易来自文档 {document_name}（共 N 笔），仅删除这一笔，确定？"），用户确认后才执行删除

2.3 WHEN 用户删除一笔来自定期交易的交易 THEN 系统 SHALL 返回需要确认的提示信息（如"这笔来自定期交易，删除后下次仍会自动生成，确定删除？"），用户确认后才执行删除

2.4 WHEN 用户通过批量删除删除包含关联关系的交易 THEN 系统 SHALL 先进行预检查（pre-check），返回每笔交易的关联信息摘要（包含被阻止的交易列表和需要确认的交易列表），用户确认后才执行可删除的交易

2.5 WHEN 用户查看文档详情页中包含多个 line items 的文档 THEN 系统 SHALL 在每个 line item 行显示交易创建状态：✅ 已创建交易（可点击跳转到对应交易）或 ⭕ 未创建交易

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 用户删除一笔没有绑定文档且不来自定期交易的普通交易 THEN 系统 SHALL CONTINUE TO 直接删除该交易，无需额外确认

3.2 WHEN 用户通过批量删除删除全部为无关联关系的普通交易 THEN 系统 SHALL CONTINUE TO 直接批量删除所有交易

3.3 WHEN 用户查看不包含 line items 的文档详情 THEN 系统 SHALL CONTINUE TO 正常显示文档详情，不受交易状态显示功能影响

3.4 WHEN 用户在交易页面进行创建、编辑、筛选、导出等非删除操作 THEN 系统 SHALL CONTINUE TO 正常执行这些操作，不受删除保护机制影响

3.5 WHEN 用户从文档管理页面删除文档 THEN 系统 SHALL CONTINUE TO 按现有逻辑处理文档删除，不受交易删除保护机制影响
