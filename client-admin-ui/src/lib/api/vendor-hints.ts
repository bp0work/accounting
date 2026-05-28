import { apiFetch } from './client';

export type VendorExtractionHint = {
  id: string;
  vendor_name: string;
  field_name: string;
  field_label: string;
  field_location?: string | null;
  example_value?: string | null;
  date_format?: string | null;
  is_active: boolean;
  updated_at: string;
};

export function listAllVendorHints() {
  return apiFetch<VendorExtractionHint[]>('/vendor-extraction-hints?all_vendors=true');
}

export function deleteVendorHint(hintId: string) {
  return apiFetch<void>(`/vendor-extraction-hints/${hintId}`, { method: 'DELETE' });
}
