<script lang="ts">
	import { uiStore } from '$lib/stores/ui.svelte';
	import { fileStore } from '$lib/stores/files.svelte';
	import { ucsStore } from '$lib/stores/ucs.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { SETTINGS_COMBOBOX_FIELDS } from './columns';
	import { cascadeCategory, cascadeSubcategory } from '$lib/utils/ucs-cascade';
	import * as api from '$lib/api/client';
	import { tick } from 'svelte';

	let searchValue = $state('');
	let inputEl: HTMLInputElement | undefined = $state();

	let cell = $derived(uiStore.editingCell);
	let file = $derived(cell ? fileStore.files.get(cell.rowId) : null);
	let isCategory = $derived(cell?.field === 'category');
	let isSettingsField = $derived(cell ? SETTINGS_COMBOBOX_FIELDS.has(cell.field) : false);

	/** Map settings field names to their settings store values */
	function getSettingsValue(field: string): string {
		const s = settingsStore.settings;
		if (!s) return '';
		if (field === 'creator_id' || field === 'designer') return s.creator_id;
		if (field === 'source_id') return s.source_id;
		if (field === 'library') return s.library_name;
		return '';
	}

	let items = $derived.by(() => {
		const q = searchValue.toLowerCase().trim();

		// Settings fields: show settings value as option (if set)
		if (isSettingsField && cell) {
			const settingsVal = getSettingsValue(cell.field);
			const opts = settingsVal ? [settingsVal] : [];
			return q ? opts.filter((o) => o.toLowerCase().includes(q)) : opts;
		}

		if (isCategory) {
			const cats = ucsStore.categories.map((c) => c.name);
			return q ? cats.filter((c) => c.toLowerCase().includes(q)) : cats;
		}
		// Subcategory — filter by current file's category
		const cat = file?.category;
		const catObj = cat ? ucsStore.categories.find((c) => c.name === cat) : null;
		const subs = catObj?.subcategories ?? [];
		const names = subs.map((s) => s.name);
		return q ? names.filter((n) => n.toLowerCase().includes(q)) : names;
	});

	$effect(() => {
		if (cell) {
			searchValue = '';
			tick().then(() => inputEl?.focus());
		}
	});

	/** Apply a simple field value (no cascade) */
	function applySimpleField(value: string) {
		if (!cell || !file) return;
		const id = cell.rowId;
		const field = cell.field;
		fileStore.updateFieldLocally(id, field, value || null);
		fileStore.clearAiField(id, field);
		fileStore.markManualEdit(id, field);
		api.updateMetadata(id, { [field]: value || null } as any).catch(() => {});
		uiStore.closeCellEdit();
	}

	function selectItem(name: string) {
		if (!cell || !file) return;

		// Settings fields: simple single-field update
		if (isSettingsField) {
			applySimpleField(name);
			return;
		}

		const id = cell.rowId;
		if (isCategory) {
			cascadeCategory(id, name, ucsStore.categories);
			fileStore.clearAiField(id, 'category');
			fileStore.clearAiField(id, 'subcategory');
			fileStore.clearAiField(id, 'cat_id');
			fileStore.clearAiField(id, 'category_full');
			fileStore.markManualEdit(id, 'category');
		} else {
			cascadeSubcategory(id, name, ucsStore.categories);
			fileStore.clearAiField(id, 'subcategory');
			fileStore.clearAiField(id, 'cat_id');
			fileStore.clearAiField(id, 'category_full');
			fileStore.markManualEdit(id, 'subcategory');
		}
		// Sync cascaded fields to backend
		const updated = fileStore.files.get(id);
		if (updated) {
			const syncFields: Record<string, string | null> = isCategory
				? { category: updated.category, subcategory: updated.subcategory, cat_id: updated.cat_id, category_full: updated.category_full }
				: { subcategory: updated.subcategory, cat_id: updated.cat_id, category_full: updated.category_full };
			api.updateMetadata(id, syncFields as any).catch(() => {});
		}
		uiStore.closeCellEdit();
	}

	function onKeyDown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			uiStore.closeCellEdit();
		}
		// Settings fields: Enter confirms typed value
		if (e.key === 'Enter' && isSettingsField) {
			e.preventDefault();
			applySimpleField(searchValue.trim());
		}
	}

	function onClickOutside(e: MouseEvent) {
		const el = document.getElementById('cell-combobox');
		if (el && !el.contains(e.target as Node)) {
			uiStore.closeCellEdit();
		}
	}

	let placeholder = $derived.by(() => {
		if (!cell) return '';
		if (isSettingsField) {
			const labels: Record<string, string> = {
				creator_id: 'Creator ID',
				source_id: 'Source ID',
				library: 'Library',
				designer: 'Designer'
			};
			return `Type or select ${labels[cell.field] ?? cell.field}...`;
		}
		return `Search ${isCategory ? 'categories' : 'subcategories'}...`;
	});

	let style = $derived.by(() => {
		if (!cell) return '';
		let left = cell.rect.left;
		const minW = 280;
		if (left + minW > window.innerWidth - 12) {
			left = window.innerWidth - 12 - minW;
		}
		return `position: fixed; top: ${cell.rect.top}px; left: ${left}px; min-width: ${minW}px; z-index: 50;`;
	});
</script>

<svelte:window onclick={onClickOutside} />

{#if cell}
	<div
		id="cell-combobox"
		class="max-h-64 overflow-hidden rounded-[3px] border border-[var(--border-focus)] bg-[var(--bg-raised)] shadow-[0_4px_20px_rgba(0,0,0,0.5)]"
		{style}
	>
		<div class="border-b border-[var(--border-default)] px-2 py-1">
			<input
				bind:this={inputEl}
				bind:value={searchValue}
				class="w-full bg-transparent text-[11px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
				placeholder={placeholder}
				onkeydown={onKeyDown}
			/>
		</div>
		<div class="max-h-52 overflow-y-auto">
			{#each items as item (item)}
				<button
					class="flex w-full px-2 py-1 text-left text-[11px] text-[var(--text-primary)] hover:bg-[var(--accent-muted)]"
					onclick={() => selectItem(item)}
				>
					{#if isSettingsField}
						<span class="mr-1.5 text-[9px] text-[var(--text-muted)]">from settings</span>
					{/if}
					{item}
				</button>
			{/each}
			{#if items.length === 0 && !isSettingsField}
				<p class="px-2 py-2 text-[10px] text-[var(--text-muted)]">
					{!isCategory && !file?.category ? 'Select a category first' : 'No matches'}
				</p>
			{/if}
			{#if isSettingsField && items.length === 0}
				<p class="px-2 py-2 text-[10px] text-[var(--text-muted)]">
					Type a value and press Enter
				</p>
			{/if}
		</div>
	</div>
{/if}
