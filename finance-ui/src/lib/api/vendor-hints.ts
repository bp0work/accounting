import { apiFetch } from './client';

export type VendorExtractionHint = {
  id: string;
  tenant_id: string;
  vendor_name: string;
  field_name: string;
  field_label: string;
  field_location?: string | null;
  example_value?: string | null;
  date_format?: string | null;
  is_active: boolean;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
};

export type VendorExtractionHintCreate = {
  vendor_name: string;
  field_name: string;
  field_label: string;
  field_location?: string | null;
  example_value?: string | null;
  date_format?: string | null;
};

export function saveVendorExtractionHint(body: VendorExtractionHintCreate) {
  return apiFetch<VendorExtractionHint>('/vendor-extraction-hints', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function listVendorExtractionHints(vendorName: string) {
  const q = new URLSearchParams({ vendor_name: vendorName });
  return apiFetch<VendorExtractionHint[]>(`/vendor-extraction-hints?${q}`);
}
