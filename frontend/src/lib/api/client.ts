import { sidecarFetch, getSidecarPort } from '$lib/sidecar';
import type {
	FileRecord,
	ImportResponse,
	SaveResponse,
	BatchSaveResponse,
	ApplyMetadataResponse,
	BatchUpdateResponse,
	MetadataUpdate,
	UCSCategory,
	AppSettings,
	ModelsStatus
} from '$lib/types';

export class ApiError extends Error {
	code?: string;

	constructor(
		public status: number,
		message: string,
		code?: string
	) {
		super(message);
		this.name = 'ApiError';
		this.code = code;
	}
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await sidecarFetch(path, init);
	if (!res.ok) {
		const body = await res.text();
		let code: string | undefined;
		let message = body || res.statusText;
		try {
			const parsed = JSON.parse(body);
			if (parsed.code) code = parsed.code;
			if (parsed.error) message = parsed.error;
		} catch {
			// Not JSON — use raw body as message
		}
		throw new ApiError(res.status, message, code);
	}
	return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

export function importDirectory(directory: string, recursive = true): Promise<ImportResponse> {
	return json('/files/import', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ directory, recursive })
	});
}

// ---------------------------------------------------------------------------
// Files CRUD
// ---------------------------------------------------------------------------

export async function fetchFiles(params?: {
	status?: string;
	category?: string;
	search?: string;
}): Promise<FileRecord[]> {
	const query = new URLSearchParams();
	if (params?.status) query.set('status', params.status);
	if (params?.category) query.set('category', params.category);
	if (params?.search) query.set('search', params.search);
	const qs = query.toString();
	const data = await json<{ files: FileRecord[]; count: number }>(`/files${qs ? `?${qs}` : ''}`);
	return data.files;
}

export function fetchFile(id: string): Promise<FileRecord> {
	return json(`/files/${id}`);
}

export function updateMetadata(id: string, updates: MetadataUpdate): Promise<FileRecord> {
	return json(`/files/${id}/metadata`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(updates)
	});
}

// ---------------------------------------------------------------------------
// Save / Revert
// ---------------------------------------------------------------------------

export function saveFile(
	id: string,
	rename = true,
	saveCopy = false,
	copyPath?: string
): Promise<SaveResponse> {
	return json(`/files/${id}/save`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ rename, save_copy: saveCopy, copy_path: copyPath })
	});
}

export function saveBatch(fileIds: string[], rename = true): Promise<BatchSaveResponse> {
	return json('/files/save-batch', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ file_ids: fileIds, rename })
	});
}

export function revertFile(id: string): Promise<FileRecord> {
	return json(`/files/${id}/revert`, { method: 'POST' });
}

// ---------------------------------------------------------------------------
// Apply Metadata
// ---------------------------------------------------------------------------

export function applyMetadata(
	sourceId: string,
	targetIds: string[],
	fields: string[]
): Promise<ApplyMetadataResponse> {
	return json('/files/apply-metadata', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ source_id: sourceId, target_ids: targetIds, fields })
	});
}

// ---------------------------------------------------------------------------
// Batch Update
// ---------------------------------------------------------------------------

export function batchUpdate(
	fileIds: string[],
	updates: Record<string, string>
): Promise<BatchUpdateResponse> {
	return json('/files/batch-update', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ file_ids: fileIds, updates })
	});
}

// ---------------------------------------------------------------------------
// UCS
// ---------------------------------------------------------------------------

export async function fetchUcsCategories(): Promise<UCSCategory[]> {
	const data = await json<{ categories: UCSCategory[] }>('/ucs/categories');
	return data.categories;
}

export function ucsLookup(catId: string): Promise<Record<string, any>> {
	return json(`/ucs/lookup/${catId}`);
}

export function parseFilename(filename: string): Promise<Record<string, any>> {
	return json('/ucs/parse-filename', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ filename })
	});
}

export function generateFilename(params: {
	cat_id: string;
	fx_name?: string;
	creator_id?: string;
	source_id?: string;
}): Promise<Record<string, any>> {
	return json('/ucs/generate-filename', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(params)
	});
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export function fetchSettings(): Promise<AppSettings> {
	return json('/settings');
}

export function updateSettings(updates: Partial<AppSettings>): Promise<AppSettings> {
	return json('/settings', {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(updates)
	});
}

export function resetDatabase(): Promise<{ status: string }> {
	return json('/settings/reset-db', { method: 'POST' });
}

// ---------------------------------------------------------------------------
// Audio
// ---------------------------------------------------------------------------

export async function getAudioUrl(id: string): Promise<string> {
	const port = await getSidecarPort();
	return `http://127.0.0.1:${port}/files/${id}/audio`;
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------

export function analyzeFile(
	id: string,
	tiers: number[] = [1],
	force = false
): Promise<FileRecord> {
	return json(`/files/${id}/analyze`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ tiers, force })
	});
}

export interface BatchCallbacks {
	onProgress?: (data: {
		file_id: string;
		filename: string;
		current: number;
		total: number;
	}) => void;
	onResult?: (data: { file_id: string; success: boolean; file: FileRecord }) => void;
	onError?: (data: { file_id: string; success: boolean; error: string }) => void;
	onComplete?: (data: {
		analyzed_count: number;
		failed_count: number;
		total_time_ms: number;
	}) => void;
}

export function analyzeBatch(
	files: Array<{ id: string; filename: string }>,
	tiers: number[] = [1],
	force = false,
	callbacks: BatchCallbacks = {}
): AbortController {
	const controller = new AbortController();
	_runSequentialAnalysis(files, tiers, force, callbacks, controller.signal);
	return controller;
}

async function _runSequentialAnalysis(
	files: Array<{ id: string; filename: string }>,
	tiers: number[],
	force: boolean,
	callbacks: BatchCallbacks,
	signal: AbortSignal
): Promise<void> {
	const startTime = performance.now();
	let analyzedCount = 0;
	let failedCount = 0;

	for (let i = 0; i < files.length; i++) {
		if (signal.aborted) break;

		const { id, filename } = files[i];
		callbacks.onProgress?.({ file_id: id, filename, current: i + 1, total: files.length });

		try {
			const file = await analyzeFile(id, tiers, force);
			analyzedCount++;
			callbacks.onResult?.({ file_id: id, success: true, file });
		} catch (e) {
			failedCount++;
			callbacks.onError?.({
				file_id: id,
				success: false,
				error: e instanceof Error ? e.message : 'Unknown error'
			});
		}
	}

	callbacks.onComplete?.({
		analyzed_count: analyzedCount,
		failed_count: failedCount,
		total_time_ms: Math.round(performance.now() - startTime)
	});
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export function fetchModelsStatus(): Promise<ModelsStatus> {
	return json('/models/status');
}
