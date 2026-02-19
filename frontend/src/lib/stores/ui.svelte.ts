import { sidecarFetch } from '$lib/sidecar';

const HEALTH_INTERVAL_MS = 30_000;
const FAILURE_THRESHOLD = 2;

export interface EditingCell {
	rowId: string;
	field: string;
	rect: DOMRect;
}

/** All column group keys — kept in sync with COLUMN_GROUPS in columns.ts */
const ALL_COLUMN_KEYS = ['name', 'ucs', 'descriptors', 'creator', 'source_specs', 'additional', 'custom'];

class UIStore {
	sidebarWidth = $state(220);
	sidebarCollapsed = $state(false);
	isImporting = $state(false);
	isGenerating = $state(false);
	isDragOver = $state(false);
	backendConnected = $state(true);

	/** Sidebar: expanded folder paths (collapsed = hidden from sheet) */
	expandedFolders = $state<Set<string>>(new Set());
	/** Sidebar: flat view shows all files without folder grouping */
	sidebarFlatView = $state(false);

	/** Which column groups are expanded (show all sub-columns) */
	expandedColumns = $state<Set<string>>(new Set());
	/** When true, all columns expanded — overrides expandedColumns */
	allColumnsExpanded = $state(false);
	/** Currently editing cell overlay state */
	editingCell = $state<EditingCell | null>(null);

	private _pollTimer: ReturnType<typeof setInterval> | null = null;
	private _consecutiveFailures = 0;

	startHealthPolling() {
		if (this._pollTimer) return;
		this._pollTimer = setInterval(() => this._checkHealth(), HEALTH_INTERVAL_MS);
	}

	stopHealthPolling() {
		if (this._pollTimer) {
			clearInterval(this._pollTimer);
			this._pollTimer = null;
		}
	}

	toggleExpandColumn(key: string) {
		if (this.allColumnsExpanded) {
			// Transition from "all expanded" to "all except this one"
			this.allColumnsExpanded = false;
			this.expandedColumns = new Set(ALL_COLUMN_KEYS.filter((k) => k !== key));
			return;
		}
		const next = new Set(this.expandedColumns);
		if (next.has(key)) {
			next.delete(key);
		} else {
			next.add(key);
		}
		this.expandedColumns = next;
	}

	toggleExpandAll() {
		this.allColumnsExpanded = !this.allColumnsExpanded;
		if (this.allColumnsExpanded) {
			this.expandedColumns = new Set();
		}
	}

	openCellEdit(rowId: string, field: string, rect: DOMRect) {
		this.editingCell = { rowId, field, rect };
	}

	closeCellEdit() {
		this.editingCell = null;
	}

	private async _checkHealth() {
		try {
			const res = await sidecarFetch('/health');
			if (res.ok) {
				this._consecutiveFailures = 0;
				this.backendConnected = true;
			} else {
				this._onHealthFailure();
			}
		} catch {
			this._onHealthFailure();
		}
	}

	private _onHealthFailure() {
		this._consecutiveFailures++;
		if (this._consecutiveFailures >= FAILURE_THRESHOLD) {
			this.backendConnected = false;
		}
	}
}

export const uiStore = new UIStore();
