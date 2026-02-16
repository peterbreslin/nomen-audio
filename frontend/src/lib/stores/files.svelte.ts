import type { AnalysisResult, FileRecord, FileStatus, SuggestionsResult } from '$lib/types';
import { uiStore } from '$lib/stores/ui.svelte';

export interface FolderInfo {
	id: string;
	name: string;
	path: string;
	count: number;
}

class FileStore {
	files = $state<Map<string, FileRecord>>(new Map());
	selectedFileId = $state<string | null>(null);
	selectedFileIds = $state<Set<string>>(new Set());
	sidebarFilter = $state('');
	sidebarStatusFilter = $state<FileStatus | null>(null);
	dismissedSuggestions = $state<Map<string, Set<string>>>(new Map());

	/** Active file drives waveform — separate from selection */
	activeFileId = $state<string | null>(null);
	/** Per-file per-field AI generation tracking */
	aiGeneratedFields = $state<Map<string, Set<string>>>(new Map());
	/** Per-file per-field manual edit tracking (for tech-gold dot) */
	manualEditedFields = $state<Map<string, Set<string>>>(new Map());

	/** Last-clicked file ID for shift-range selection */
	private lastClickedId: string | null = null;

	get selectedFile(): FileRecord | null {
		if (!this.selectedFileId) return null;
		return this.files.get(this.selectedFileId) ?? null;
	}

	get activeFile(): FileRecord | null {
		if (!this.activeFileId) return null;
		return this.files.get(this.activeFileId) ?? null;
	}

	get aiGeneratedCount(): number {
		let count = 0;
		for (const fields of this.aiGeneratedFields.values()) {
			if (fields.size > 0) count++;
		}
		return count;
	}

	get filteredFiles(): FileRecord[] {
		let result = Array.from(this.files.values());

		if (this.sidebarStatusFilter) {
			const status = this.sidebarStatusFilter;
			result = result.filter((f) => f.status === status);
		}

		const q = this.sidebarFilter.toLowerCase().trim();
		if (q) {
			result = result.filter(
				(f) =>
					f.filename.toLowerCase().includes(q) ||
					(f.category && f.category.toLowerCase().includes(q)) ||
					(f.subcategory && f.subcategory.toLowerCase().includes(q)) ||
					(f.fx_name && f.fx_name.toLowerCase().includes(q)) ||
					(f.description && f.description.toLowerCase().includes(q)) ||
					(f.keywords && f.keywords.toLowerCase().includes(q))
			);
		}

		return result;
	}

	get fileStats() {
		let total = 0;
		let modified = 0;
		let saved = 0;
		let flagged = 0;
		for (const f of this.files.values()) {
			total++;
			if (f.status === 'modified') modified++;
			if (f.status === 'saved') saved++;
			if (f.status === 'flagged') flagged++;
		}
		return { total, modified, saved, flagged };
	}

	get modifiedFileIds(): string[] {
		const ids: string[] = [];
		for (const f of this.files.values()) {
			if (f.status === 'modified') ids.push(f.id);
		}
		return ids;
	}

	get folders(): FolderInfo[] {
		const counts = new Map<string, number>();
		for (const f of this.filteredFiles) {
			counts.set(f.directory, (counts.get(f.directory) ?? 0) + 1);
		}
		return Array.from(counts.entries()).map(([dir, count]) => ({
			id: dir,
			name: dir.split(/[/\\]/).pop() || dir,
			path: dir,
			count
		}));
	}

	get visibleFiles(): FileRecord[] {
		// Flat view or legacy activeFolderId='__all__' → show everything
		if (uiStore.sidebarFlatView) return this.filteredFiles;
		// Tree view → only files in expanded folders
		const expanded = uiStore.expandedFolders;
		if (expanded.size === 0) return [];
		return this.filteredFiles.filter((f) => expanded.has(f.directory));
	}

	setActiveFile(id: string) {
		this.activeFileId = id;
	}

	setFiles(records: FileRecord[]) {
		const map = new Map<string, FileRecord>();
		for (const r of records) map.set(r.id, r);
		this.files = map;
		this.selectedFileId = null;
		this.selectedFileIds = new Set();
		this.lastClickedId = null;
		this.activeFileId = null;
		this.aiGeneratedFields = new Map();
		this.manualEditedFields = new Map();
	}

	addFiles(records: FileRecord[]) {
		const next = new Map(this.files);
		for (const r of records) next.set(r.id, r);
		this.files = next;
	}

	updateFile(record: FileRecord) {
		const next = new Map(this.files);
		next.set(record.id, record);
		this.files = next;
	}

	removeFiles(ids: string[]) {
		const next = new Map(this.files);
		for (const id of ids) next.delete(id);
		this.files = next;
		if (this.selectedFileId && ids.includes(this.selectedFileId)) {
			this.selectedFileId = null;
		}
		if (this.activeFileId && ids.includes(this.activeFileId)) {
			this.activeFileId = null;
		}
		const nextSel = new Set(this.selectedFileIds);
		for (const id of ids) nextSel.delete(id);
		this.selectedFileIds = nextSel;
		// Clean AI + manual tracking
		const nextAi = new Map(this.aiGeneratedFields);
		const nextManual = new Map(this.manualEditedFields);
		for (const id of ids) {
			nextAi.delete(id);
			nextManual.delete(id);
		}
		this.aiGeneratedFields = nextAi;
		this.manualEditedFields = nextManual;
	}

	removeFolder(directory: string) {
		const ids = Array.from(this.files.values())
			.filter((f) => f.directory === directory)
			.map((f) => f.id);
		this.removeFiles(ids);
		const next = new Set(uiStore.expandedFolders);
		next.delete(directory);
		uiStore.expandedFolders = next;
	}

	selectFile(id: string) {
		this.selectedFileId = id;
		this.selectedFileIds = new Set([id]);
		this.lastClickedId = id;
	}

	toggleSelect(id: string) {
		const next = new Set(this.selectedFileIds);
		if (next.has(id)) {
			next.delete(id);
			if (this.selectedFileId === id) {
				this.selectedFileId = next.size > 0 ? Array.from(next)[0] : null;
			}
		} else {
			next.add(id);
			this.selectedFileId = id;
		}
		this.selectedFileIds = next;
		this.lastClickedId = id;
	}

	rangeSelect(id: string) {
		const list = this.visibleFiles;
		const lastIdx = this.lastClickedId
			? list.findIndex((f) => f.id === this.lastClickedId)
			: -1;
		const curIdx = list.findIndex((f) => f.id === id);
		if (lastIdx === -1 || curIdx === -1) {
			this.selectFile(id);
			return;
		}
		const start = Math.min(lastIdx, curIdx);
		const end = Math.max(lastIdx, curIdx);
		const next = new Set<string>();
		for (let i = start; i <= end; i++) {
			next.add(list[i].id);
		}
		this.selectedFileIds = next;
		this.selectedFileId = id;
	}

	clearSelection() {
		this.selectedFileId = null;
		this.selectedFileIds = new Set();
		this.lastClickedId = null;
	}

	/** Optimistic local field update — mark file modified + add to changed_fields */
	updateFieldLocally(id: string, key: string, value: string | null) {
		const file = this.files.get(id);
		if (!file) return;
		const changed = new Set(file.changed_fields);
		changed.add(key);
		const updated: FileRecord = {
			...file,
			[key]: value,
			status: 'modified',
			changed_fields: Array.from(changed)
		};
		this.updateFile(updated);
	}

	/** Update a file with analysis results and suggestions */
	setAnalysis(
		fileId: string,
		analysis: AnalysisResult | null,
		suggestions: SuggestionsResult | null
	) {
		const file = this.files.get(fileId);
		if (!file) return;
		this.updateFile({ ...file, analysis, suggestions });
		const next = new Map(this.dismissedSuggestions);
		next.delete(fileId);
		this.dismissedSuggestions = next;
	}

	/** Accept a suggestion — copy value to field, mark modified */
	acceptSuggestion(fileId: string, field: string) {
		const file = this.files.get(fileId);
		if (!file?.suggestions) return;
		const suggestion = file.suggestions[field as keyof SuggestionsResult];
		if (!suggestion) return;
		this.updateFieldLocally(fileId, field, suggestion.value);
	}

	/** Dismiss a suggestion — track in frontend state only */
	dismissSuggestion(fileId: string, field: string) {
		const next = new Map(this.dismissedSuggestions);
		const fields = new Set(next.get(fileId) ?? []);
		fields.add(field);
		next.set(fileId, fields);
		this.dismissedSuggestions = next;
	}

	/** Mark fields as AI-generated for a file */
	markAiGenerated(fileId: string, fields: string[]) {
		const next = new Map(this.aiGeneratedFields);
		const existing = new Set(next.get(fileId) ?? []);
		for (const f of fields) existing.add(f);
		next.set(fileId, existing);
		this.aiGeneratedFields = next;
	}

	/** Clear AI badge for a specific field (after manual edit) */
	clearAiField(fileId: string, field: string) {
		const next = new Map(this.aiGeneratedFields);
		const existing = next.get(fileId);
		if (!existing) return;
		const updated = new Set(existing);
		updated.delete(field);
		if (updated.size === 0) {
			next.delete(fileId);
		} else {
			next.set(fileId, updated);
		}
		this.aiGeneratedFields = next;
	}

	/** Clear all AI + manual field tracking for a file (e.g. on revert) */
	clearFieldTracking(fileId: string) {
		const nextAi = new Map(this.aiGeneratedFields);
		nextAi.delete(fileId);
		this.aiGeneratedFields = nextAi;
		const nextManual = new Map(this.manualEditedFields);
		nextManual.delete(fileId);
		this.manualEditedFields = nextManual;
	}

	/** Mark a field as manually edited (for tech-gold dot) */
	markManualEdit(fileId: string, field: string) {
		const next = new Map(this.manualEditedFields);
		const existing = new Set(next.get(fileId) ?? []);
		existing.add(field);
		next.set(fileId, existing);
		this.manualEditedFields = next;
	}
}

export const fileStore = new FileStore();
