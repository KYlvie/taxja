# Requirements Document

## Introduction

扩展现有的房产管理系统，使其支持通用资产管理（Allgemeine Anlagenverwaltung）。系统需要支持添加和管理各类可折旧资产（如车辆、电脑、机械、办公家具、软件许可等），并根据奥地利税法正确计算折旧（AfA）。后端已有基础的资产模型和 API 端点，但缺少关键的税法计算逻辑（半年规则、豪华车上限、低值资产）；前端完全缺少资产管理界面。

## Glossary

- **Asset_Management_System**: 通用资产管理系统，管理非房地产类可折旧资产的前后端模块
- **AfA_Calculator**: 折旧计算服务（Absetzung für Abnutzung），负责计算年度折旧金额
- **Asset_Form**: 前端资产创建/编辑表单组件
- **Assets_Page**: 前端资产列表和管理页面
- **Halbjahresregel**: 半年规则——购入年和处置年只能计提半年折旧
- **Luxustangente**: 豪华车上限——乘用车（PKW）仅前 €40,000 可折旧，电动车豁免
- **GWG**: 低值资产（Geringwertige Wirtschaftsgüter）——购入价 ≤ €1,000（不含增值税）的资产可在购入年一次性全额扣除
- **IFB**: 投资免税额（Investitionsfreibetrag）——电动车和环保设备可额外扣除 15%
- **Lineare_AfA**: 直线折旧法——奥地利税法对动产唯一允许的折旧方法
- **Business_Use_Percentage**: 营业使用比例——资产用于业务的百分比，仅该比例部分可折旧

## Requirements

### Requirement 1: 半年规则折旧计算（Halbjahresregel）

**User Story:** 作为纳税人，我希望系统在购入年和处置年自动按半年计提折旧，以符合奥地利税法对动产的半年规则要求。

#### Acceptance Criteria

1. WHEN a movable asset is purchased in a given year, THE AfA_Calculator SHALL calculate depreciation for that year as exactly half of the full annual depreciation amount, regardless of the actual purchase month
2. WHEN a movable asset is disposed of in a given year, THE AfA_Calculator SHALL calculate depreciation for that year as exactly half of the full annual depreciation amount, regardless of the actual disposal month
3. WHILE an asset has asset_type other than "real_estate", THE AfA_Calculator SHALL apply the Halbjahresregel instead of month-based pro-rating
4. THE AfA_Calculator SHALL continue to use month-based pro-rating for real_estate assets without applying the Halbjahresregel

### Requirement 2: 豪华车上限（Luxustangente）

**User Story:** 作为纳税人，我希望系统在计算乘用车折旧时自动应用 €40,000 的豪华车上限，以确保折旧金额符合奥地利税法。

#### Acceptance Criteria

1. WHEN an asset with asset_type "vehicle" has a purchase_price exceeding €40,000, THE AfA_Calculator SHALL use €40,000 as the depreciable base instead of the actual purchase_price
2. WHEN an asset with asset_type "electric_vehicle" has a purchase_price exceeding €40,000, THE AfA_Calculator SHALL use the full purchase_price as the depreciable base without applying the Luxustangente cap
3. THE AfA_Calculator SHALL apply the Luxustangente cap before applying the business_use_percentage reduction
4. WHEN the Luxustangente cap is applied, THE Asset_Management_System SHALL store the non-deductible amount (purchase_price minus €40,000) for reporting purposes

### Requirement 3: 低值资产处理（GWG）

**User Story:** 作为纳税人，我希望系统能识别低值资产并提供一次性全额扣除的选项，以简化小额资产的税务处理。

#### Acceptance Criteria

1. WHEN an asset is created with a purchase_price of €1,000 or less (excluding VAT), THE Asset_Management_System SHALL flag the asset as GWG-eligible
2. WHERE the GWG option is selected by the user, THE AfA_Calculator SHALL expense the full depreciable amount in the purchase year instead of spreading depreciation over the useful life
3. WHERE the GWG option is not selected by the user, THE AfA_Calculator SHALL depreciate the asset normally over the standard useful life using Lineare_AfA
4. THE Asset_Form SHALL display a GWG indicator and allow the user to choose between immediate expensing and normal depreciation when the asset qualifies as GWG

### Requirement 4: 直线折旧计算（Lineare AfA）

**User Story:** 作为纳税人，我希望系统对所有动产资产使用直线折旧法，并根据资产类型自动确定使用年限和折旧率。

#### Acceptance Criteria

1. THE AfA_Calculator SHALL calculate annual depreciation for movable assets using the formula: depreciable_base × (1 / useful_life_years)
2. WHEN an asset is created, THE Asset_Management_System SHALL auto-determine the useful_life_years based on the asset_type from the ASSET_USEFUL_LIFE table
3. THE AfA_Calculator SHALL apply the business_use_percentage to the depreciable base, so that only the business-use portion is deductible
4. THE AfA_Calculator SHALL stop depreciation when accumulated_depreciation reaches the depreciable base
5. WHEN the user provides a custom useful_life_years value, THE Asset_Management_System SHALL use the user-provided value instead of the default from ASSET_USEFUL_LIFE

### Requirement 5: 前端资产创建表单（Asset Form）

**User Story:** 作为用户，我希望有一个专用的资产创建表单，以便我能方便地添加各类可折旧资产。

#### Acceptance Criteria

1. THE Asset_Form SHALL provide a dropdown for selecting asset_type from the following options: vehicle, electric_vehicle, computer, phone, office_furniture, machinery, tools, software, other_equipment
2. THE Asset_Form SHALL include input fields for: name, purchase_date, purchase_price, supplier, business_use_percentage, and optional sub_category
3. WHEN the user selects an asset_type, THE Asset_Form SHALL auto-fill the useful_life_years field with the default value from ASSET_USEFUL_LIFE, while allowing the user to override the value
4. THE Asset_Form SHALL validate that purchase_price is greater than zero and purchase_date is not in the future
5. WHEN the user selects asset_type "vehicle", THE Asset_Form SHALL display a warning if purchase_price exceeds €40,000, explaining the Luxustangente cap
6. WHEN the purchase_price is €1,000 or less, THE Asset_Form SHALL display a GWG option allowing the user to choose immediate expensing
7. THE Asset_Form SHALL submit data to the existing POST /api/v1/properties/assets endpoint

### Requirement 6: 前端资产列表和管理页面（Assets Page）

**User Story:** 作为用户，我希望在资产管理页面中能看到所有非房地产资产的列表，并能查看每个资产的折旧状态。

#### Acceptance Criteria

1. THE Assets_Page SHALL display a list of all non-real-estate assets retrieved from the GET /api/v1/properties/assets endpoint
2. THE Assets_Page SHALL show for each asset: name, asset_type (with localized label), purchase_date, purchase_price, annual_depreciation, accumulated_depreciation, and remaining_value
3. THE Assets_Page SHALL provide a button to open the Asset_Form for creating new assets
4. WHEN an asset is a GWG that was fully expensed, THE Assets_Page SHALL display a "GWG" badge next to the asset
5. WHEN an asset is a vehicle with Luxustangente applied, THE Assets_Page SHALL display the non-deductible amount
6. THE Assets_Page SHALL be accessible from the main navigation, separate from the real estate properties page

### Requirement 7: 投资免税额提示（IFB）

**User Story:** 作为纳税人，我希望系统在添加电动车或环保设备时提示我可以申请 15% 的投资免税额。

#### Acceptance Criteria

1. WHEN an asset with asset_type "electric_vehicle" is created, THE Asset_Management_System SHALL display an informational notice that the asset is eligible for a 15% Investitionsfreibetrag (IFB)
2. THE Asset_Management_System SHALL calculate and display the IFB amount as: purchase_price × 15%
3. THE Asset_Management_System SHALL indicate that the IFB is an additional deduction on top of regular depreciation, for the user to claim in the tax return

### Requirement 8: 资产处置（Asset Disposal）

**User Story:** 作为用户，我希望能记录资产的处置（出售或报废），以便系统正确计算处置年的折旧并停止后续折旧。

#### Acceptance Criteria

1. THE Assets_Page SHALL provide an action to mark an asset as disposed, requiring the user to enter a disposal date
2. WHEN an asset is marked as disposed, THE AfA_Calculator SHALL calculate half-year depreciation for the disposal year per the Halbjahresregel
3. WHEN an asset is marked as disposed, THE Asset_Management_System SHALL set the asset status to "sold" and record the sale_date
4. THE AfA_Calculator SHALL return zero depreciation for any year after the disposal year

### Requirement 9: 资产类型本地化显示（i18n）

**User Story:** 作为用户，我希望资产类型名称以我选择的语言显示（德语、英语、中文），以便我能理解每种资产类型。

#### Acceptance Criteria

1. THE Asset_Management_System SHALL provide localized labels for all asset_type values in German, English, and Chinese
2. THE Asset_Form SHALL display asset_type options using localized labels from the i18n translation files
3. THE Assets_Page SHALL display asset_type using localized labels from the i18n translation files

### Requirement 10: 折旧计算的往返一致性（Round-Trip Property）

**User Story:** 作为开发者，我希望折旧计算在序列化和反序列化后保持一致，以确保数据完整性。

#### Acceptance Criteria

1. FOR ALL valid Asset objects, THE AfA_Calculator SHALL produce identical annual_depreciation results when calculated from the stored database fields as when calculated from the original input parameters
2. FOR ALL assets with accumulated_depreciation records, THE AfA_Calculator SHALL ensure that the sum of all yearly depreciation amounts equals the stored accumulated_depreciation value
3. FOR ALL GWG assets with immediate expensing, THE AfA_Calculator SHALL ensure that accumulated_depreciation equals the depreciable base after the purchase year calculation
