import { extractedFieldLabel } from '$lib/case-labels';

/** "Document date label", "Vendor name label", … */
export function vendorHintFieldLabelInputLabel(fieldName: string): string {
  return `${extractedFieldLabel(fieldName)} label`;
}

/** "Document date", "Vendor name", … */
export function vendorHintExampleValueInputLabel(fieldName: string): string {
  return extractedFieldLabel(fieldName);
}

/** "Date format of document date", … — only shown for date fields. */
export function vendorHintDateFormatInputLabel(fieldName: string): string {
  return `Date format of ${extractedFieldLabel(fieldName).toLowerCase()}`;
}

export function vendorHintFieldLabelRequiredMessage(fieldName: string): string {
  return `${vendorHintFieldLabelInputLabel(fieldName)} is required.`;
}
