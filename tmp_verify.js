delete require.cache[require.resolve('./frontend/src/i18n/locales/en.json')];
const en = require('./frontend/src/i18n/locales/en.json');
function hasKey(obj, path) {
  const parts = path.split('.');
  let cur = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object' || !(p in cur)) return false;
    cur = cur[p];
  }
  return true;
}
const keys = [
  'documents.review.contractRole.landlord','documents.review.contractRole.tenant','documents.review.contractRole.buyer','documents.review.contractRole.seller','documents.review.contractRole.borrower','documents.review.contractRole.policyHolder','documents.review.contractRole.unknown',
  'documents.review.contractRoleSource.manual','documents.review.contractRoleSource.context','documents.review.contractRoleSource.partyMatch','documents.review.contractRoleSource.text','documents.review.contractRoleSource.unknown',
  'documents.review.contractRoleTarget.recurringIncome','documents.review.contractRoleTarget.loan','documents.review.contractRoleTarget.insurance','documents.review.contractRoleTarget.asset','documents.review.contractRoleTarget.property',
  'documents.review.direction.expense','documents.review.direction.income','documents.review.direction.unknown',
  'documents.review.directionSource.manual','documents.review.directionSource.partyMatch','documents.review.directionSource.merchant','documents.review.directionSource.statement','documents.review.directionSource.unknown',
  'documents.review.semantic.receipt','documents.review.semantic.standardInvoice','documents.review.semantic.creditNote','documents.review.semantic.proforma','documents.review.semantic.deliveryNote','documents.review.semantic.unknown','documents.review.semantic.invoice',
  'documents.review.assetPurchaseContract','documents.review.readonlyMode','documents.review.templateSwitchAfterSave',
  'documents.review.fields.myRole','documents.review.fields.transactionDirection','documents.review.fields.documentSemantics',
  'documents.review.directionInsight','documents.review.directionSourceLabel','documents.review.directionConfidenceLabel','documents.review.directionReversal',
  'documents.review.fields.assetName','documents.review.fields.assetType','documents.review.fields.firstRegistrationDate','documents.review.fields.vehicleIdentificationNumber','documents.review.fields.licensePlate','documents.review.fields.mileageKm','documents.review.fields.previousOwners','documents.review.fields.isUsedAsset',
  'documents.review.assetPurchaseContractHint','documents.review.directionLabel','documents.review.semanticLabel','documents.review.reversal','documents.review.nonPostable','documents.review.nonPostableHint','documents.review.saveReferenceDocument',
  'documents.pipeline.processingPhase1Title','documents.pipeline.processingPhase1Body','documents.pipeline.firstResultTitle','documents.pipeline.firstResultBody','documents.pipeline.finalizingTitle','documents.pipeline.finalizingBody','documents.pipeline.phase2FailedTitle','documents.pipeline.phase2FailedBody',
  'documents.ocr.saveFailed','documents.ocr.assetName','documents.ocr.assetType','documents.ocr.firstRegistrationDate','documents.ocr.vehicleIdentificationNumber','documents.ocr.licensePlate','documents.ocr.mileageKm','documents.ocr.isUsedAsset','documents.ocr.documentType',
  'documents.receiptReview.mixedCategories','documents.receiptReview.noCategory','documents.receiptReview.applyCategoryToAll','documents.receiptReview.selectCategory','documents.receiptReview.incomeEditing','documents.receiptReview.incomeStatus','documents.receiptReview.incomeEditingHint','documents.receiptReview.incomeStatusHint','documents.receiptReview.incomeFooterEditing','documents.receiptReview.incomeFooterReadonly','documents.receiptReview.saveIncomeDocument',
  'documents.linkedTransaction.title','documents.linkedTransaction.hint','documents.linkedTransaction.open',
  'documents.linkedAsset.title','documents.linkedAsset.hint','documents.linkedAsset.gwg','documents.linkedAsset.degressive','documents.linkedAsset.linear','documents.linkedAsset.businessUse','documents.linkedAsset.ifbCandidate','documents.linkedAsset.annualDepreciation','documents.linkedAsset.remainingValue','documents.linkedAsset.open',
  'documents.linkedEntity.transaction','documents.linkedEntity.recurring','documents.linkedEntity.property','documents.linkedEntity.asset','documents.linkedEntity.open',
  'documents.processing','documents.failed','documents.actions',
  'documents.upload.captureSessionTitle','documents.upload.addPage','documents.upload.uploadGrouped','documents.upload.clearCaptureSession','documents.upload.duplicateReused',
  'documents.suggestion.keepLoanContract','documents.suggestion.createLoanRepayment','documents.suggestion.matchedProperty',
  'documents.suggestion.assetDecision.gwg','documents.suggestion.assetDecision.auto','documents.suggestion.assetDecision.asset',
  'documents.suggestion.assetVat.likelyYes','documents.suggestion.assetVat.likelyNo','documents.suggestion.assetVat.partial','documents.suggestion.assetVat.unclear',
  'documents.suggestion.assetErrors.putIntoUseRequired','documents.suggestion.assetErrors.businessUse','documents.suggestion.assetErrors.usefulLife',
  'documents.suggestion.assetConfirm','documents.suggestion.assetDecisionLabel','documents.suggestion.assetVatLabel','documents.suggestion.assetIfbLabel','documents.suggestion.assetIfbYes','documents.suggestion.assetIfbNo','documents.suggestion.assetBasis','documents.suggestion.assetConfidence','documents.suggestion.assetDuplicateWarning',
  'documents.suggestion.assetFields.putIntoUseDate','documents.suggestion.assetFields.businessUse','documents.suggestion.assetFields.condition','documents.suggestion.assetCondition.new','documents.suggestion.assetCondition.used','documents.suggestion.assetFields.firstRegistrationDate','documents.suggestion.assetFields.priorUsageYears','documents.suggestion.assetFields.gwgElection','documents.suggestion.assetGwg','documents.suggestion.assetCapitalize','documents.suggestion.assetFields.depreciationMethod','documents.suggestion.assetDepreciation.degressive','documents.suggestion.assetDepreciation.linear','documents.suggestion.assetFields.degressiveRate','documents.suggestion.assetFields.usefulLifeYears',
  'documents.employer.summarySaved','documents.employer.payrollConfirmed','documents.employer.noPayrollConfirmed','documents.employer.archiveUpdated','documents.employer.archiveSaved','documents.employer.title','documents.employer.loading','documents.employer.monthLabel','documents.employer.signalLabel','documents.employer.lastUpdate','documents.employer.summaryAmount','documents.employer.employeeCount','documents.employer.grossWages','documents.employer.netPaid','documents.employer.socialCost','documents.employer.lohnsteuer','documents.employer.db','documents.employer.dz','documents.employer.kommunalsteuer','documents.employer.specialPayments','documents.employer.notes','documents.employer.saving','documents.employer.saveSummary','documents.employer.confirming','documents.employer.confirmPayroll','documents.employer.confirmNoPayroll','documents.employer.taxYear','documents.employer.archiveSignal','documents.employer.employerName','documents.employer.grossIncome','documents.employer.withheldTax','documents.employer.updateArchive','documents.employer.archiveYear','documents.employer.workbenchEyebrow','documents.employer.workbenchTitle','documents.employer.workbenchSubtitle','documents.employer.pendingMonths','documents.employer.pendingMonthMeta','documents.employer.noPendingMonths','documents.employer.pendingArchives','documents.employer.noPendingArchives',
];
const missing = keys.filter(k => !hasKey(en, k));
console.log('Still missing:', missing.length);
missing.forEach(k => console.log(k));
