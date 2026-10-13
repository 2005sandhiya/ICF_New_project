import { API_BASE_URL } from '../config.js';

export function validateTemplateFile(file) {
  if (!file || !file.name.toLowerCase().endsWith('.docx')) return 'Choose a DOCX template (.docx).';
  if (!file.size || file.size > 10 * 1024 * 1024) return 'Choose a non-empty DOCX template no larger than 10 MB.';
  return null;
}

export async function templateRequest(studyId, method = 'GET', file = null, signal) {
  try {
    const body = file ? new FormData() : undefined;
    if (file) body.append('file', file);
    const response = await fetch(`${API_BASE_URL}/api/icf/template/${encodeURIComponent(studyId)}`, {method, body, signal});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Template request failed.');
    return {success: true, data};
  } catch (error) {
    return {success: false, error: error.message};
  }
}

export const templateDownloadUrl = studyId => `${API_BASE_URL}/api/icf/template/${encodeURIComponent(studyId)}/file`;

export async function exportICFDocument(studyId, revision, exportType = 'patient_facing', format = 'pdf') {
  try {
    const response = await fetch(`${API_BASE_URL}/api/icf/export/${encodeURIComponent(studyId)}?export_type=${encodeURIComponent(exportType)}&format=${format}&revision=${revision}`, {
      method: 'POST', headers: {Accept: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === 'string' ? error.detail : `${format.toUpperCase()} export failed (${response.status}).`);
    }
    const blob = await response.blob();
    if (!blob.size) throw new Error('The server returned an empty document.');
    const expected = format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    if (!response.headers.get('content-type')?.startsWith(expected)) throw new Error('The server returned an unexpected document format.');
    const filename = response.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1];
    return {success: true, blob, filename};
  } catch (error) {
    return {success: false, error: error.message || 'Document export failed.'};
  }
}
