import { describe, it, expect } from 'vitest';
import {
	COLUMN_GROUPS,
	getCatShort,
	getCellValue,
	isEditableField,
	getColumnPx,
	getTableWidthPx,
	AI_BADGE_FIELDS,
	COMBOBOX_FIELDS,
	SETTINGS_COMBOBOX_FIELDS
} from '../columns';
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

describe('getCatShort', () => {
	it('extracts uppercase prefix from CatID', () => {
		expect(getCatShort('DOORWood')).toBe('DOORW');
		expect(getCatShort('GUNAuto')).toBe('GUNA');
		expect(getCatShort('WATRBubl')).toBe('WATRB');
	});

	it('returns empty for null/empty', () => {
		expect(getCatShort(null)).toBe('');
		expect(getCatShort('')).toBe('');
	});

	it('returns empty for lowercase start', () => {
		expect(getCatShort('abc')).toBe('');
	});
});

describe('getCellValue', () => {
	it('returns field value from FileRecord', () => {
		const file = makeFile({ fx_name: 'Door Slam' });
		const sub = COLUMN_GROUPS[2].subs[0]; // fx_name
		expect(getCellValue(file, sub)).toBe('Door Slam');
	});

	it('returns empty string for null fields', () => {
		const file = makeFile();
		const sub = COLUMN_GROUPS[2].subs[0]; // fx_name
		expect(getCellValue(file, sub)).toBe('');
	});

	it('derives cat_short from cat_id', () => {
		const file = makeFile({ cat_id: 'DOORWood' });
		const catShortSub = COLUMN_GROUPS[1].subs.find((s) => s.key === 'cat_short')!;
		expect(getCellValue(file, catShortSub)).toBe('DOORW');
	});

	it('returns empty cat_short when cat_id is null', () => {
		const file = makeFile();
		const catShortSub = COLUMN_GROUPS[1].subs.find((s) => s.key === 'cat_short')!;
		expect(getCellValue(file, catShortSub)).toBe('');
	});
});

describe('isEditableField', () => {
	it('filename is read-only', () => {
		expect(isEditableField('filename')).toBe(false);
	});

	it('cat_short, category_full, cat_id are read-only', () => {
		expect(isEditableField('cat_short')).toBe(false);
		expect(isEditableField('category_full')).toBe(false);
		expect(isEditableField('cat_id')).toBe(false);
	});

	it('category, subcategory, fx_name, description are editable', () => {
		expect(isEditableField('category')).toBe(true);
		expect(isEditableField('subcategory')).toBe(true);
		expect(isEditableField('fx_name')).toBe(true);
		expect(isEditableField('description')).toBe(true);
	});
});

describe('getColumnPx', () => {
	const containerWidth = 1200;
	const nameGroup = COLUMN_GROUPS[0]; // NAME, 22%, 2 subs
	const ucsGroup = COLUMN_GROUPS[1]; // UCS, 20%, 5 subs

	it('returns pixel width when nothing expanded (default percentage of available)', () => {
		// NAME: 22% of (1200 - 32) = 22% of 1168 = 257px
		expect(getColumnPx(nameGroup, new Set(), false, containerWidth)).toBe(Math.round(0.22 * (containerWidth - 32)));
	});

	it('returns pixel width for expanded column based on sub count', () => {
		// UCS: 5 subs * 130px = 650px
		expect(getColumnPx(ucsGroup, new Set(['ucs']), false, containerWidth)).toBe(650);
	});

	it('returns default pixel width for non-expanded column when something else is expanded', () => {
		// NAME: 22% of (1200 - 32) = 22% of 1168 = 257px
		const px = getColumnPx(nameGroup, new Set(['ucs']), false, containerWidth);
		expect(px).toBe(Math.round(0.22 * (containerWidth - 32)));
	});

	it('returns at least default width in allExpanded mode (never narrower)', () => {
		const nameDefault = Math.round(0.22 * (containerWidth - 32));
		const nameExpanded = 2 * 120; // 240px
		// NAME default (257) > expanded (240), so default wins
		expect(getColumnPx(nameGroup, new Set(), true, containerWidth)).toBe(Math.max(nameExpanded, nameDefault));
		// UCS: 5 subs * 120px = 600px > default (234), so expanded wins
		expect(getColumnPx(ucsGroup, new Set(), true, containerWidth)).toBe(600);
	});
});

describe('getTableWidthPx', () => {
	const containerWidth = 1200;

	it('returns approximately containerWidth when nothing expanded', () => {
		const width = getTableWidthPx(new Set(), false, containerWidth);
		// May be slightly larger due to rounding of individual column pixel widths
		expect(width).toBeGreaterThanOrEqual(containerWidth);
		expect(width).toBeLessThanOrEqual(containerWidth + COLUMN_GROUPS.length);
	});

	it('returns total px width when columns are expanded', () => {
		const width = getTableWidthPx(new Set(['ucs']), false, containerWidth);
		expect(width).toBeGreaterThan(containerWidth);
		expect(typeof width).toBe('number');
	});

	it('returns at least containerWidth', () => {
		// Even with small expansions, table should be at least container width
		const width = getTableWidthPx(new Set(['additional']), false, containerWidth);
		expect(width).toBeGreaterThanOrEqual(containerWidth);
	});
});

describe('COLUMN_GROUPS', () => {
	it('has 6 groups', () => {
		expect(COLUMN_GROUPS.length).toBe(6);
	});

	it('each group has at least one sub-column', () => {
		for (const group of COLUMN_GROUPS) {
			expect(group.subs.length).toBeGreaterThan(0);
		}
	});

	it('group keys are unique', () => {
		const keys = COLUMN_GROUPS.map((g) => g.key);
		expect(new Set(keys).size).toBe(keys.length);
	});

	it('UCS group starts with category_full (Full)', () => {
		const ucsGroup = COLUMN_GROUPS.find((g) => g.key === 'ucs')!;
		expect(ucsGroup.subs[0].key).toBe('category_full');
		expect(ucsGroup.subs[0].label).toBe('Full');
	});

	it('defaultWidth values sum to 100', () => {
		const total = COLUMN_GROUPS.reduce((sum, g) => sum + g.defaultWidth, 0);
		expect(total).toBe(100);
	});
});

describe('AI_BADGE_FIELDS', () => {
	it('includes expected fields', () => {
		expect(AI_BADGE_FIELDS.has('category')).toBe(true);
		expect(AI_BADGE_FIELDS.has('fx_name')).toBe(true);
		expect(AI_BADGE_FIELDS.has('suggested_filename')).toBe(true);
	});

	it('excludes non-AI fields', () => {
		expect(AI_BADGE_FIELDS.has('filename')).toBe(false);
		expect(AI_BADGE_FIELDS.has('notes')).toBe(false);
	});
});

describe('COMBOBOX_FIELDS', () => {
	it('includes UCS and settings fields', () => {
		expect(COMBOBOX_FIELDS.has('category')).toBe(true);
		expect(COMBOBOX_FIELDS.has('subcategory')).toBe(true);
		expect(COMBOBOX_FIELDS.has('creator_id')).toBe(true);
		expect(COMBOBOX_FIELDS.has('source_id')).toBe(true);
		expect(COMBOBOX_FIELDS.has('library')).toBe(true);
		expect(COMBOBOX_FIELDS.has('designer')).toBe(true);
		expect(COMBOBOX_FIELDS.size).toBe(6);
	});

	it('SETTINGS_COMBOBOX_FIELDS is subset of COMBOBOX_FIELDS', () => {
		for (const f of SETTINGS_COMBOBOX_FIELDS) {
			expect(COMBOBOX_FIELDS.has(f)).toBe(true);
		}
		expect(SETTINGS_COMBOBOX_FIELDS.has('creator_id')).toBe(true);
		expect(SETTINGS_COMBOBOX_FIELDS.has('source_id')).toBe(true);
		expect(SETTINGS_COMBOBOX_FIELDS.has('library')).toBe(true);
		expect(SETTINGS_COMBOBOX_FIELDS.has('designer')).toBe(true);
		expect(SETTINGS_COMBOBOX_FIELDS.size).toBe(4);
	});
});
