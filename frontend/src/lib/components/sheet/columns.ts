import type { FileRecord } from '$lib/types';

export interface SubColumn {
	key: string;
	label: string;
	mono: boolean;
	fileRecordKey: string;
}

export interface ColumnGroup {
	key: string;
	label: string;
	subs: SubColumn[];
	defaultWidth: number; // percentage of available space (0-100)
}

export const COLUMN_GROUPS: ColumnGroup[] = [
	{
		key: 'name',
		label: 'NAME',
		defaultWidth: 22,
		subs: [
			{ key: 'filename', label: 'Original', mono: true, fileRecordKey: 'filename' },
			{
				key: 'suggested_filename',
				label: 'New Filename',
				mono: true,
				fileRecordKey: 'suggested_filename'
			}
		]
	},
	{
		key: 'ucs',
		label: 'UCS',
		defaultWidth: 20,
		subs: [
			{
				key: 'category_full',
				label: 'Full',
				mono: true,
				fileRecordKey: 'category_full'
			},
			{ key: 'category', label: 'Category', mono: false, fileRecordKey: 'category' },
			{ key: 'subcategory', label: 'SubCategory', mono: false, fileRecordKey: 'subcategory' },
			{ key: 'cat_id', label: 'CatID', mono: true, fileRecordKey: 'cat_id' },
			{ key: 'cat_short', label: 'CatShort', mono: true, fileRecordKey: 'cat_short' }
		]
	},
	{
		key: 'descriptors',
		label: 'DESCRIPTORS',
		defaultWidth: 20,
		subs: [
			{ key: 'fx_name', label: 'FX Name', mono: false, fileRecordKey: 'fx_name' },
			{ key: 'description', label: 'Description', mono: false, fileRecordKey: 'description' }
		]
	},
	{
		key: 'creator',
		label: 'CREATOR',
		defaultWidth: 15,
		subs: [
			{ key: 'designer', label: 'Designer', mono: false, fileRecordKey: 'designer' },
			{ key: 'library', label: 'Library', mono: false, fileRecordKey: 'library' },
			{
				key: 'manufacturer',
				label: 'Manufacturer',
				mono: false,
				fileRecordKey: 'manufacturer'
			}
		]
	},
	{
		key: 'source_specs',
		label: 'SOURCE SPECS',
		defaultWidth: 13,
		subs: [
			{ key: 'source_id', label: 'Source ID', mono: true, fileRecordKey: 'source_id' },
			{ key: 'creator_id', label: 'Creator ID', mono: true, fileRecordKey: 'creator_id' },
			{ key: 'rec_medium', label: 'Rec Medium', mono: false, fileRecordKey: 'rec_medium' },
			{ key: 'microphone', label: 'Microphone', mono: false, fileRecordKey: 'microphone' },
			{
				key: 'mic_perspective',
				label: 'Mic Persp',
				mono: false,
				fileRecordKey: 'mic_perspective'
			},
			{ key: 'rec_type', label: 'Rec Type', mono: false, fileRecordKey: 'rec_type' },
			{
				key: 'user_category',
				label: 'User Cat',
				mono: false,
				fileRecordKey: 'user_category'
			}
		]
	},
	{
		key: 'additional',
		label: 'ADDITIONAL INFO',
		defaultWidth: 10,
		subs: [{ key: 'notes', label: 'Notes', mono: false, fileRecordKey: 'notes' }]
	}
];

/** Build column groups with optional custom field columns appended. */
export function buildColumnGroups(
	customDefs: { tag: string; label: string }[]
): ColumnGroup[] {
	if (!customDefs.length) return COLUMN_GROUPS;
	const customGroup: ColumnGroup = {
		key: 'custom',
		label: 'CUSTOM',
		defaultWidth: 10,
		subs: customDefs.map((def) => ({
			key: 'cf_' + def.tag,
			label: def.label,
			mono: false,
			fileRecordKey: 'cf_' + def.tag
		}))
	};
	return [...COLUMN_GROUPS, customGroup];
}

/** Derive CatShort from CatID: uppercase prefix letters */
export function getCatShort(catId: string | null): string {
	return catId?.match(/^[A-Z]+/)?.[0] ?? '';
}

/** Get display value for a sub-column from a FileRecord */
export function getCellValue(file: FileRecord, sub: SubColumn): string {
	if (sub.key === 'cat_short') {
		return getCatShort(file.cat_id);
	}
	if (sub.key.startsWith('cf_')) {
		return file.custom_fields?.[sub.key.slice(3)] ?? '';
	}
	const val = file[sub.fileRecordKey as keyof FileRecord];
	if (val === null || val === undefined) return '';
	return String(val);
}

/** Fields that are read-only (derived or identity) */
const READ_ONLY_FIELDS = new Set(['filename', 'cat_short', 'category_full', 'cat_id']);

export function isEditableField(key: string): boolean {
	if (key.startsWith('cf_')) return true;
	return !READ_ONLY_FIELDS.has(key);
}

/** Fields that show AI badge when AI-generated */
export const AI_BADGE_FIELDS = new Set([
	'category',
	'subcategory',
	'cat_id',
	'fx_name',
	'description',
	'keywords',
	'suggested_filename'
]);

/** Fields that use combobox editing instead of textarea */
export const COMBOBOX_FIELDS = new Set(['category', 'subcategory', 'creator_id', 'source_id', 'library', 'designer']);

/** Subset of COMBOBOX_FIELDS that pull options from settings (free-text with suggestions) */
export const SETTINGS_COMBOBOX_FIELDS = new Set(['creator_id', 'source_id', 'library', 'designer']);

/** Width of the wand column in px */
const WAND_COL_PX = 32;
/** Min-width per sub-column when a group is expanded (px) */
const SUB_COL_MIN_WIDTH = 130;
/** Min-width per sub-column in allExpanded mode (px) */
const ALL_EXPANDED_SUB_WIDTH = 120;

/** Convert a group's default percentage to pixels given the available width */
function defaultPx(group: ColumnGroup, availWidth: number): number {
	return Math.round((group.defaultWidth / 100) * availWidth);
}

/** Compute the pixel width for a single column.
 *  Always returns a pixel value to prevent layout shifts when toggling expansion.
 *  Expanded width is never narrower than the default to prevent leftward shifts. */
export function getColumnPx(
	group: ColumnGroup,
	expandedCols: Set<string>,
	allExpanded: boolean,
	containerWidth: number
): number {
	const availWidth = containerWidth - WAND_COL_PX;
	const base = defaultPx(group, availWidth);
	if (allExpanded) {
		return Math.max(group.subs.length * ALL_EXPANDED_SUB_WIDTH, base);
	}
	if (expandedCols.has(group.key)) {
		return Math.max(group.subs.length * SUB_COL_MIN_WIDTH, base);
	}
	return base;
}

/** Compute the total table width in px (always pixel-based). */
export function getTableWidthPx(
	groups: ColumnGroup[],
	expandedCols: Set<string>,
	allExpanded: boolean,
	containerWidth: number
): number {
	let total = WAND_COL_PX;
	for (const g of groups) {
		total += getColumnPx(g, expandedCols, allExpanded, containerWidth);
	}
	return Math.max(total, containerWidth);
}
