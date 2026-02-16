import { describe, it, expect, beforeEach } from 'vitest';
import { fileStore } from '../files.svelte';
import { uiStore } from '../ui.svelte';
import type { FileRecord, TechnicalInfo } from '$lib/types';

const tech: TechnicalInfo = {
	sample_rate: 48000,
	bit_depth: 24,
	channels: 2,
	duration_seconds: 3.5,
	frame_count: 168000,
	audio_format: 'PCM',
	file_size_bytes: 1_008_044
};

function makeFile(overrides: Partial<FileRecord> = {}): FileRecord {
	return {
		id: 'id-1',
		path: '/data/test.wav',
		filename: 'test.wav',
		directory: '/data',
		status: 'unmodified',
		changed_fields: [],
		technical: tech,
		category: null,
		subcategory: null,
		cat_id: null,
		category_full: null,
		user_category: null,
		fx_name: null,
		description: null,
		keywords: null,
		notes: null,
		designer: null,
		library: null,
		project: null,
		microphone: null,
		mic_perspective: null,
		rec_medium: null,
		release_date: null,
		rating: null,
		is_designed: null,
		manufacturer: null,
		rec_type: null,
		creator_id: null,
		source_id: null,
		custom_fields: null,
		suggested_filename: null,
		rename_on_save: true,
		bext: null,
		info: null,
		analysis: null,
		suggestions: null,
		...overrides
	};
}

describe('FileStore', () => {
	beforeEach(() => {
		fileStore.setFiles([]);
		fileStore.sidebarFilter = '';
		fileStore.sidebarStatusFilter = null;
		uiStore.expandedFolders = new Set();
		uiStore.sidebarFlatView = false;
	});

	it('setFiles populates the store and clears selection', () => {
		const f1 = makeFile({ id: 'a', filename: 'a.wav' });
		const f2 = makeFile({ id: 'b', filename: 'b.wav' });
		fileStore.setFiles([f1, f2]);

		expect(fileStore.files.size).toBe(2);
		expect(fileStore.selectedFileId).toBeNull();
	});

	it('updateFile replaces an existing record', () => {
		const f = makeFile({ id: 'a', fx_name: 'old' });
		fileStore.setFiles([f]);
		fileStore.updateFile({ ...f, fx_name: 'new' });

		expect(fileStore.files.get('a')?.fx_name).toBe('new');
	});

	it('selectFile sets primary + multi selection', () => {
		const f = makeFile({ id: 'a' });
		fileStore.setFiles([f]);
		fileStore.selectFile('a');

		expect(fileStore.selectedFileId).toBe('a');
		expect(fileStore.selectedFileIds.has('a')).toBe(true);
	});

	it('selectedFile getter returns correct record', () => {
		const f = makeFile({ id: 'a', filename: 'hello.wav' });
		fileStore.setFiles([f]);
		fileStore.selectFile('a');

		expect(fileStore.selectedFile?.filename).toBe('hello.wav');
	});

	it('filteredFiles applies text filter', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', filename: 'impact_metal.wav' }),
			makeFile({ id: 'b', filename: 'whoosh_air.wav' })
		]);
		fileStore.sidebarFilter = 'metal';

		expect(fileStore.filteredFiles.length).toBe(1);
		expect(fileStore.filteredFiles[0].id).toBe('a');
	});

	it('filteredFiles applies status filter', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', status: 'modified' }),
			makeFile({ id: 'b', status: 'unmodified' })
		]);
		fileStore.sidebarStatusFilter = 'modified';

		expect(fileStore.filteredFiles.length).toBe(1);
		expect(fileStore.filteredFiles[0].id).toBe('a');
	});

	it('fileStats computes totals correctly', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', status: 'modified' }),
			makeFile({ id: 'b', status: 'saved' }),
			makeFile({ id: 'c', status: 'unmodified' })
		]);

		expect(fileStore.fileStats).toEqual({ total: 3, modified: 1, saved: 1, flagged: 0 });
	});

	it('toggleSelect adds/removes from multi selection', () => {
		fileStore.setFiles([
			makeFile({ id: 'a' }),
			makeFile({ id: 'b' })
		]);
		fileStore.selectFile('a');
		fileStore.toggleSelect('b');

		expect(fileStore.selectedFileIds.size).toBe(2);

		fileStore.toggleSelect('a');
		expect(fileStore.selectedFileIds.size).toBe(1);
		expect(fileStore.selectedFileIds.has('b')).toBe(true);
	});

	it('rangeSelect selects contiguous range', () => {
		uiStore.sidebarFlatView = true;
		fileStore.setFiles([
			makeFile({ id: 'a', filename: 'a.wav' }),
			makeFile({ id: 'b', filename: 'b.wav' }),
			makeFile({ id: 'c', filename: 'c.wav' }),
			makeFile({ id: 'd', filename: 'd.wav' })
		]);
		fileStore.selectFile('a');
		fileStore.rangeSelect('c');

		expect(fileStore.selectedFileIds.size).toBe(3);
		expect(fileStore.selectedFileIds.has('a')).toBe(true);
		expect(fileStore.selectedFileIds.has('b')).toBe(true);
		expect(fileStore.selectedFileIds.has('c')).toBe(true);
	});

	it('rangeSelect replaces previous range on shift+click back', () => {
		uiStore.sidebarFlatView = true;
		fileStore.setFiles([
			makeFile({ id: 'a', filename: 'a.wav' }),
			makeFile({ id: 'b', filename: 'b.wav' }),
			makeFile({ id: 'c', filename: 'c.wav' }),
			makeFile({ id: 'd', filename: 'd.wav' })
		]);
		fileStore.selectFile('a');
		fileStore.rangeSelect('d');
		expect(fileStore.selectedFileIds.size).toBe(4);

		// Shift+click back to b — should deselect c and d
		fileStore.rangeSelect('b');
		expect(fileStore.selectedFileIds.size).toBe(2);
		expect(fileStore.selectedFileIds.has('a')).toBe(true);
		expect(fileStore.selectedFileIds.has('b')).toBe(true);
		expect(fileStore.selectedFileIds.has('c')).toBe(false);
		expect(fileStore.selectedFileIds.has('d')).toBe(false);
	});

	it('modifiedFileIds returns only modified files', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', status: 'modified' }),
			makeFile({ id: 'b', status: 'unmodified' }),
			makeFile({ id: 'c', status: 'modified' })
		]);

		expect(fileStore.modifiedFileIds).toEqual(['a', 'c']);
	});

	it('updateFieldLocally marks file as modified + adds to changed_fields', () => {
		fileStore.setFiles([makeFile({ id: 'a', fx_name: 'old' })]);
		fileStore.updateFieldLocally('a', 'fx_name', 'new');

		const f = fileStore.files.get('a')!;
		expect(f.fx_name).toBe('new');
		expect(f.status).toBe('modified');
		expect(f.changed_fields).toContain('fx_name');
	});

	it('addFiles merges new records alongside existing', () => {
		fileStore.setFiles([makeFile({ id: 'a', filename: 'a.wav' })]);
		fileStore.addFiles([makeFile({ id: 'b', filename: 'b.wav' })]);

		expect(fileStore.files.size).toBe(2);
		expect(fileStore.files.get('a')?.filename).toBe('a.wav');
		expect(fileStore.files.get('b')?.filename).toBe('b.wav');
	});

	it('addFiles updates existing records by ID', () => {
		fileStore.setFiles([makeFile({ id: 'a', filename: 'a.wav', fx_name: 'old' })]);
		fileStore.addFiles([makeFile({ id: 'a', filename: 'a.wav', fx_name: 'new' })]);

		expect(fileStore.files.size).toBe(1);
		expect(fileStore.files.get('a')?.fx_name).toBe('new');
	});

	it('removeFiles deletes files and updates selection', () => {
		fileStore.setFiles([
			makeFile({ id: 'a' }),
			makeFile({ id: 'b' })
		]);
		fileStore.selectFile('a');
		fileStore.removeFiles(['a']);

		expect(fileStore.files.size).toBe(1);
		expect(fileStore.selectedFileId).toBeNull();
	});

	// --- Folder navigation ---

	it('folders groups by directory with correct counts', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', directory: '/data/impacts' }),
			makeFile({ id: 'b', directory: '/data/impacts' }),
			makeFile({ id: 'c', directory: '/data/whooshes' })
		]);

		const folders = fileStore.folders;
		expect(folders.length).toBe(2);
		const impacts = folders.find((f) => f.id === '/data/impacts');
		expect(impacts?.count).toBe(2);
		expect(impacts?.name).toBe('impacts');
		const whooshes = folders.find((f) => f.id === '/data/whooshes');
		expect(whooshes?.count).toBe(1);
	});

	it('visibleFiles shows only files in expanded folders', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', directory: '/data/impacts' }),
			makeFile({ id: 'b', directory: '/data/whooshes' })
		]);
		uiStore.sidebarFlatView = false;
		uiStore.expandedFolders = new Set(['/data/impacts']);

		expect(fileStore.visibleFiles.length).toBe(1);
		expect(fileStore.visibleFiles[0].id).toBe('a');
	});

	it('visibleFiles empty when no folders expanded', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', directory: '/data/impacts' }),
			makeFile({ id: 'b', directory: '/data/whooshes' })
		]);
		uiStore.sidebarFlatView = false;
		uiStore.expandedFolders = new Set();

		expect(fileStore.visibleFiles.length).toBe(0);
	});

	it('visibleFiles shows all in flat view regardless of expanded folders', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', directory: '/data/impacts' }),
			makeFile({ id: 'b', directory: '/data/whooshes' })
		]);
		uiStore.sidebarFlatView = true;
		uiStore.expandedFolders = new Set();

		expect(fileStore.visibleFiles.length).toBe(2);
	});

	it('folders getter returns correct counts', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', directory: '/data' }),
			makeFile({ id: 'b', directory: '/data' })
		]);

		expect(fileStore.folders.length).toBe(1);
		expect(fileStore.folders[0].count).toBe(2);
	});

	it('removeFolder removes all files in that directory', () => {
		fileStore.setFiles([
			makeFile({ id: 'a', directory: '/data/impacts' }),
			makeFile({ id: 'b', directory: '/data/impacts' }),
			makeFile({ id: 'c', directory: '/data/whooshes' })
		]);
		fileStore.setActiveFile('a');
		fileStore.selectFile('b');

		fileStore.removeFolder('/data/impacts');

		expect(fileStore.files.size).toBe(1);
		expect(fileStore.files.has('c')).toBe(true);
		expect(fileStore.activeFileId).toBeNull();
		expect(fileStore.selectedFileId).toBeNull();
	});

	// --- Analysis / Suggestions ---

	it('setAnalysis updates file with analysis and suggestions', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		const analysis = {
			classification: [{ cat_id: 'EXPLGun', category: 'Explosions', subcategory: 'Gunshot', category_full: 'EXPLOSIONS - Gunshot', confidence: 0.85 }],
			caption: null,
			model_version: '2023',
			analyzed_at: '2026-02-14T00:00:00Z'
		};
		const suggestions = {
			category: { value: 'Explosions', source: 'clap' as const, confidence: 0.85 },
			subcategory: null, cat_id: null, category_full: null,
			fx_name: null, description: null, keywords: null, suggested_filename: null
		};
		fileStore.setAnalysis('a', analysis, suggestions);

		const f = fileStore.files.get('a')!;
		expect(f.analysis).toBe(analysis);
		expect(f.suggestions).toBe(suggestions);
	});

	it('setAnalysis clears dismissed suggestions for the file', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.dismissSuggestion('a', 'category');
		expect(fileStore.dismissedSuggestions.get('a')?.has('category')).toBe(true);

		fileStore.setAnalysis('a', null, null);
		expect(fileStore.dismissedSuggestions.has('a')).toBe(false);
	});

	it('acceptSuggestion copies suggestion value to field', () => {
		const suggestions = {
			category: null, subcategory: null, cat_id: null, category_full: null,
			fx_name: { value: 'Door Slam', source: 'clapcap' as const, confidence: 0.7 },
			description: null, keywords: null, suggested_filename: null
		};
		fileStore.setFiles([makeFile({ id: 'a', suggestions })]);
		fileStore.acceptSuggestion('a', 'fx_name');

		const f = fileStore.files.get('a')!;
		expect(f.fx_name).toBe('Door Slam');
		expect(f.status).toBe('modified');
		expect(f.changed_fields).toContain('fx_name');
	});

	it('acceptSuggestion is no-op for missing suggestion', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.acceptSuggestion('a', 'fx_name');

		expect(fileStore.files.get('a')!.fx_name).toBeNull();
	});

	it('dismissSuggestion tracks field in dismissedSuggestions', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.dismissSuggestion('a', 'category');
		fileStore.dismissSuggestion('a', 'keywords');

		const dismissed = fileStore.dismissedSuggestions.get('a');
		expect(dismissed?.has('category')).toBe(true);
		expect(dismissed?.has('keywords')).toBe(true);
		expect(dismissed?.has('fx_name')).toBeFalsy();
	});

	// --- Active File ---

	it('setActiveFile sets activeFileId and activeFile', () => {
		const f = makeFile({ id: 'a', filename: 'hello.wav' });
		fileStore.setFiles([f]);
		fileStore.setActiveFile('a');

		expect(fileStore.activeFileId).toBe('a');
		expect(fileStore.activeFile?.filename).toBe('hello.wav');
	});

	it('activeFile returns null when no active file', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		expect(fileStore.activeFile).toBeNull();
	});

	it('setActiveFile clears when file removed', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.setActiveFile('a');
		fileStore.removeFiles(['a']);

		expect(fileStore.activeFileId).toBeNull();
	});

	// --- AI Generated Fields ---

	it('markAiGenerated tracks fields per file', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.markAiGenerated('a', ['category', 'fx_name']);

		const fields = fileStore.aiGeneratedFields.get('a');
		expect(fields?.has('category')).toBe(true);
		expect(fields?.has('fx_name')).toBe(true);
		expect(fields?.has('description')).toBeFalsy();
	});

	it('clearAiField removes single field badge', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.markAiGenerated('a', ['category', 'fx_name']);
		fileStore.clearAiField('a', 'category');

		const fields = fileStore.aiGeneratedFields.get('a');
		expect(fields?.has('category')).toBe(false);
		expect(fields?.has('fx_name')).toBe(true);
	});

	it('clearAiField removes file entry when last field cleared', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.markAiGenerated('a', ['category']);
		fileStore.clearAiField('a', 'category');

		expect(fileStore.aiGeneratedFields.has('a')).toBe(false);
	});

	it('aiGeneratedCount reflects files with AI fields', () => {
		fileStore.setFiles([
			makeFile({ id: 'a' }),
			makeFile({ id: 'b' }),
			makeFile({ id: 'c' })
		]);
		fileStore.markAiGenerated('a', ['category']);
		fileStore.markAiGenerated('c', ['fx_name']);

		expect(fileStore.aiGeneratedCount).toBe(2);
	});

	it('markManualEdit tracks fields per file', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.markManualEdit('a', 'fx_name');

		const fields = fileStore.manualEditedFields.get('a');
		expect(fields?.has('fx_name')).toBe(true);
	});

	it('manualEditedFields cleared on setFiles', () => {
		fileStore.setFiles([makeFile({ id: 'a' })]);
		fileStore.markManualEdit('a', 'fx_name');
		fileStore.setFiles([makeFile({ id: 'b' })]);

		expect(fileStore.manualEditedFields.size).toBe(0);
	});

	it('manualEditedFields cleaned on removeFiles', () => {
		fileStore.setFiles([makeFile({ id: 'a' }), makeFile({ id: 'b' })]);
		fileStore.markManualEdit('a', 'fx_name');
		fileStore.removeFiles(['a']);

		expect(fileStore.manualEditedFields.has('a')).toBe(false);
	});

	it('clearFieldTracking removes both AI and manual tracking for a file', () => {
		fileStore.setFiles([makeFile({ id: 'a' }), makeFile({ id: 'b' })]);
		fileStore.markAiGenerated('a', ['category', 'subcategory']);
		fileStore.markManualEdit('a', 'fx_name');
		fileStore.markAiGenerated('b', ['description']);

		fileStore.clearFieldTracking('a');

		expect(fileStore.aiGeneratedFields.has('a')).toBe(false);
		expect(fileStore.manualEditedFields.has('a')).toBe(false);
		// Other file's tracking should be unaffected
		expect(fileStore.aiGeneratedFields.has('b')).toBe(true);
	});
});
