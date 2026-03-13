#!/usr/bin/env python3
"""
Rebuild zh.json with proper UTF-8 encoding
This script creates a complete Chinese translation file
"""
import json

# Complete Chinese translations
zh_translations = {
  "common": {
    "appName": "Taxja",
    "slogan": "税务，轻松搞定！",
    "loading": "加载中...",
    "save": "保存",
    "cancel": "取消",
    "delete": "删除",
    "edit": "编辑",
    "close": "关闭",
    "confirm": "确认",
    "back": "返回",
    "next": "下一步",
    "previous": "上一步",
    "search": "搜索",
    "filter": "筛选",
    "export": "导出",
    "import": "导入",
    "upload": "上传",
    "download": "下载",
    "yes": "是",
    "no": "否",
    "actions": "操作",
    "saving": "保存中...",
    "error": "错误",
    "success": "成功",
    "warning": "警告",
    "info": "信息",
    "enabled": "已启用",
    "disabled": "已禁用",
    "page": "页",
    "of": "共",
    "done": "完成",
    "loadingPreview": "加载预览中...",
    "comingSoon": "即将推出"
  },
  "auth": {
    "login": "登录",
    "logout": "登出",
    "register": "注册",
    "email": "邮箱",
    "password": "密码",
    "confirmPassword": "确认密码",
    "forgotPassword": "忘记密码？",
    "twoFactorCode": "双因素验证码",
    "rememberMe": "记住我",
    "enter2FACode": "请输入您的双因素验证码",
    "invalid2FACode": "无效的双因素验证码",
    "twoFactorAuth": "双因素认证",
    "setup2FA": "设置双因素认证",
    "scan2FACode": "使用您的认证应用扫描此二维码",
    "enter2FAManually": "或手动输入此密钥",
    "verify2FACode": "输入验证码以完成设置",
    "enable2FA": "启用双因素认证",
    "disable2FA": "禁用双因素认证",
    "twoFactorEnabled": "双因素认证已启用",
    "twoFactorDisabled": "双因素认证已禁用"
  },
  "nav": {
    "dashboard": "仪表板",
    "transactions": "交易记录",
    "documents": "文档",
    "properties": "房产",
    "reports": "报告",
    "settings": "设置",
    "profile": "个人资料",
    "help": "帮助",
    "aiAssistant": "AI 助手"
  },
  "dashboard": {
    "title": "仪表板",
    "welcome": "欢迎回来",
    "overview": "概览",
    "recentTransactions": "最近交易",
    "upcomingDeadlines": "即将到期",
    "taxSummary": "税务摘要",
    "quickActions": "快捷操作",
    "addTransaction": "添加交易",
    "uploadDocument": "上传文档",
    "viewReports": "查看报告"
  },
  "transactions": {
    "title": "交易记录",
    "addTransaction": "添加交易",
    "editTransaction": "编辑交易",
    "deleteTransaction": "删除交易",
    "type": "类型",
    "amount": "金额",
    "date": "日期",
    "description": "描述",
    "category": "类别",
    "deductible": "可抵扣",
    "nonDeductible": "不可抵扣",
    "income": "收入",
    "expense": "支出",
    "noTransactions": "暂无交易记录",
    "filterByType": "按类型筛选",
    "filterByCategory": "按类别筛选",
    "filterByDate": "按日期筛选",
    "totalIncome": "总收入",
    "totalExpense": "总支出",
    "netIncome": "净收入"
  },
  "documents": {
    "title": "文档",
    "uploadDocument": "上传文档",
    "documentType": "文档类型",
    "uploadDate": "上传日期",
    "status": "状态",
    "actions": "操作",
    "view": "查看",
    "download": "下载",
    "delete": "删除",
    "noDocuments": "暂无文档",
    "processing": "处理中",
    "completed": "已完成",
    "failed": "失败",
    "ocrResults": "OCR 识别结果",
    "extractedData": "提取的数据",
    "confidence": "置信度",
    "documentTypes": {
      "receipt": "收据",
      "invoice": "发票",
      "contract": "合同",
      "statement": "对账单",
      "purchase_contract": "购房合同",
      "rental_contract": "租赁合同",
      "loan_contract": "贷款合同",
      "bank_statement": "银行对账单",
      "property_tax": "房产税",
      "svs_notice": "SVS 通知",
      "lohnzettel": "Lohnzettel",
      "einkommensteuerbescheid": "年度所得税评估报告",
      "e1_form": "所得税申报表 (E1)",
      "other": "其他",
      "unknown": "未知"
    },
    "upload": {
      "title": "上传文档",
      "dragDrop": "拖放文件到此处，或点击选择",
      "formats": "支持格式：JPG、PNG、PDF（最大 10MB）",
      "uploading": "上传中...",
      "success": "上传成功",
      "error": "上传失败"
    },
    "ocr": {
      "processing": "正在识别文档...",
      "completed": "识别完成",
      "failed": "识别失败",
      "noResults": "未识别到内容",
      "fields": {
        "document_date": "文档日期",
        "total_amount": "总金额",
        "seller_name": "卖方名称",
        "buyer_name": "买方名称",
        "property_address": "房产地址",
        "purchase_price": "购买价格",
        "building_value": "建筑价值",
        "land_value": "土地价值",
        "notary_fees": "公证费",
        "registry_fees": "登记费",
        "property_tax": "房产税",
        "monthly_rent": "月租金",
        "deposit": "押金",
        "lease_start": "租赁开始日期",
        "lease_end": "租赁结束日期",
        "landlord_name": "房东姓名",
        "tenant_name": "租户姓名",
        "loan_amount": "贷款金额",
        "interest_rate": "利率",
        "loan_term": "贷款期限",
        "monthly_payment": "月供",
        "lender_name": "贷款机构",
        "borrower_name": "借款人",
        "account_number": "账号",
        "bank_name": "银行名称",
        "transaction_date": "交易日期",
        "transaction_amount": "交易金额",
        "balance": "余额"
      }
    },
    "suggestions": {
      "title": "导入建议",
      "property": "检测到房产信息",
      "recurring": "检测到定期交易",
      "confirmImport": "确认导入",
      "dismiss": "忽略",
      "propertyDetails": "房产详情",
      "recurringDetails": "定期交易详情"
    },
    "deleteDialog": {
      "title": "删除文档",
      "message": "您确定要删除此文档吗？",
      "documentOnly": "仅删除文档",
      "withData": "删除文档及相关数据",
      "relatedData": "相关数据",
      "property": "房产",
      "transactions": "交易记录",
      "recurringTransactions": "定期交易",
      "warning": "此操作无法撤销"
    }
  },
  "properties": {
    "title": "房产",
    "addProperty": "添加房产",
    "editProperty": "编辑房产",
    "deleteProperty": "删除房产",
    "address": "地址",
    "purchaseDate": "购买日期",
    "purchasePrice": "购买价格",
    "buildingValue": "建筑价值",
    "landValue": "土地价值",
    "depreciationRate": "折旧率",
    "status": "状态",
    "active": "活跃",
    "sold": "已售出",
    "archived": "已归档",
    "noProperties": "暂无房产",
    "metrics": {
      "title": "财务指标",
      "accumulatedDepreciation": "累计折旧",
      "remainingValue": "剩余价值",
      "annualDepreciation": "年度折旧",
      "rentalIncome": "租金收入",
      "expenses": "支出",
      "netIncome": "净收入",
      "yearsRemaining": "剩余年限"
    },
    "warnings": {
      "title": "税务警告",
      "noRentalIncome": "无租金收入",
      "longVacancy": "长期空置",
      "info": "信息",
      "warning": "警告",
      "error": "错误"
    }
  },
  "reports": {
    "title": "报告",
    "generateReport": "生成报告",
    "reportType": "报告类型",
    "year": "年份",
    "quarter": "季度",
    "month": "月份",
    "download": "下载",
    "preview": "预览",
    "noReports": "暂无报告"
  },
  "settings": {
    "title": "设置",
    "profile": "个人资料",
    "security": "安全",
    "notifications": "通知",
    "language": "语言",
    "theme": "主题",
    "saveChanges": "保存更改",
    "changesSaved": "更改已保存"
  },
  "aiAssistant": {
    "title": "AI 税务助手",
    "placeholder": "询问关于奥地利税务的问题...",
    "send": "发送",
    "thinking": "思考中...",
    "error": "抱歉，出现了错误",
    "examples": {
      "title": "示例问题",
      "q1": "什么费用可以抵扣？",
      "q2": "如何计算房产折旧？",
      "q3": "SVS 缴费标准是什么？"
    }
  },
  "recurring": {
    "title": "定期交易",
    "addRecurring": "添加定期交易",
    "editRecurring": "编辑定期交易",
    "frequency": "频率",
    "startDate": "开始日期",
    "endDate": "结束日期",
    "nextOccurrence": "下次发生",
    "active": "活跃",
    "paused": "已暂停",
    "completed": "已完成",
    "frequencies": {
      "daily": "每日",
      "weekly": "每周",
      "monthly": "每月",
      "quarterly": "每季度",
      "yearly": "每年"
    }
  }
}

# Write to file with proper UTF-8 encoding
output_file = 'src/i18n/locales/zh.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(zh_translations, f, ensure_ascii=False, indent=2)

print(f"✅ Successfully created {output_file} with UTF-8 encoding")
print(f"   Total keys: {sum(len(v) if isinstance(v, dict) else 1 for v in zh_translations.values())}")
