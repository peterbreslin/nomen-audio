/** TypeScript interfaces matching backend Pydantic models. */

export interface TechnicalInfo {
	sample_rate: number;
	bit_depth: number;
	channels: number;
	duration_seconds: number;
	frame_count: number;
	audio_format: string;
	file_size_bytes: number;
}

export interface BextInfo {
	description: string | null;
	originator: string | null;
	originator_date: string | null;
	originator_time: string | null;
	time_reference: number | null;
	coding_history: string | null;
}

export interface RiffInfo {
	title: string | null;
	artist: string | null;
	genre: string | null;
	comment: string | null;
	created_date: string | null;
	software: string | null;
	copyright: string | null;
	product: string | null;
	keywords: string | null;
}

// ML / Analysis types

export interface ClassificationMatch {
	cat_id: string;
	category: string;
	subcategory: string;
	category_full: string;
	confidence: number;
}

export interface AnalysisResult {
	classification: ClassificationMatch[];
	caption: string | null;
	model_version: string;
	analyzed_at: string;
}

export type SuggestionSource = 'clap' | 'clapcap' | 'derived' | 'generated';

export interface Suggestion {
	value: string;
	source: SuggestionSource;
	confidence: number | null;
}

export interface SuggestionsResult {
	category: Suggestion | null;
	subcategory: Suggestion | null;
	cat_id: Suggestion | null;
	category_full: Suggestion | null;
	fx_name: Suggestion | null;
	description: Suggestion | null;
	keywords: Suggestion | null;
	suggested_filename: Suggestion | null;
}

export interface ModelsStatus {
	clap_loaded: boolean;
	clapcap_loaded: boolean;
	embeddings_ready: boolean;
	embeddings_count: number;
	loading: boolean;
	error: string | null;
	status_message: string;
}

export interface AnalyzeRequest {
	tiers?: number[];
	force?: boolean;
}

export interface BatchAnalyzeRequest {
	file_ids?: string[];
	tiers?: number[];
	force?: boolean;
}

export type FileStatus = 'unmodified' | 'modified' | 'saved' | 'flagged';

export interface FileRecord {
	id: string;
	path: string;
	filename: string;
	directory: string;
	status: FileStatus;
	changed_fields: string[];
	technical: TechnicalInfo;

	// UCS Classification
	category: string | null;
	subcategory: string | null;
	cat_id: string | null;
	category_full: string | null;
	user_category: string | null;

	// Naming & Description
	fx_name: string | null;
	description: string | null;
	keywords: string | null;
	notes: string | null;

	// Project & Creator
	designer: string | null;
	library: string | null;
	project: string | null;

	// Preserved fields
	microphone: string | null;
	mic_perspective: string | null;
	rec_medium: string | null;
	release_date: string | null;
	rating: string | null;
	is_designed: string | null;

	// ASWG extended fields
	manufacturer: string | null;
	rec_type: string | null;
	creator_id: string | null;
	source_id: string | null;

	// Custom fields
	custom_fields: Record<string, string> | null;

	// Filename generation
	suggested_filename: string | null;
	rename_on_save: boolean;

	// Embedded chunks (read-only)
	bext: BextInfo | null;
	info: RiffInfo | null;

	// ML pipeline (Phase 4)
	analysis: AnalysisResult | null;
	suggestions: SuggestionsResult | null;
}

export interface MetadataUpdate {
	category?: string | null;
	subcategory?: string | null;
	cat_id?: string | null;
	category_full?: string | null;
	user_category?: string | null;
	fx_name?: string | null;
	description?: string | null;
	keywords?: string | null;
	notes?: string | null;
	designer?: string | null;
	library?: string | null;
	project?: string | null;
	microphone?: string | null;
	mic_perspective?: string | null;
	rec_medium?: string | null;
	release_date?: string | null;
	rating?: string | null;
	is_designed?: string | null;
	manufacturer?: string | null;
	rec_type?: string | null;
	creator_id?: string | null;
	source_id?: string | null;
	suggested_filename?: string | null;
	custom_fields?: Record<string, string> | null;
}

export interface SaveRequest {
	rename?: boolean;
	save_copy?: boolean;
	copy_path?: string;
}

export interface SaveResponse {
	success: boolean;
	file: FileRecord;
	old_path: string;
	new_path: string;
	renamed: boolean;
	copied: boolean;
	copy_path: string | null;
}

export interface BatchSaveRequest {
	file_ids: string[];
	rename?: boolean;
}

export interface BatchSaveResult {
	id: string;
	success: boolean;
	renamed: boolean;
	new_path: string | null;
	error: string | null;
}

export interface BatchSaveResponse {
	results: BatchSaveResult[];
	saved_count: number;
	failed_count: number;
}

export interface ApplyMetadataRequest {
	source_id: string;
	target_ids: string[];
	fields: string[];
}

export interface ApplyMetadataResponse {
	updated: FileRecord[];
	count: number;
}

export interface BatchUpdateResponse {
	updated: FileRecord[];
	count: number;
}

export interface ImportRequest {
	directory: string;
	recursive?: boolean;
}

export interface ImportResponse {
	files: FileRecord[];
	count: number;
	skipped: number;
	skipped_paths: string[];
	import_time_ms: number;
}

// UCS types (matching /ucs/categories response)

export interface UCSSubcategory {
	name: string;
	cat_id: string;
	category_full: string;
	explanation: string;
}

export interface UCSCategory {
	name: string;
	explanation: string;
	subcategories: UCSSubcategory[];
}

// Settings types (matching backend AppSettings)

export interface CustomFieldDef {
	tag: string;
	label: string;
}

export interface AppSettings {
	version: number;
	creator_id: string;
	source_id: string;
	library_name: string;
	library_template: string;
	rename_on_save_default: boolean;
	custom_fields: CustomFieldDef[];
	llm_provider: string | null;
	llm_api_key: string | null;
	model_directory: string;
}
