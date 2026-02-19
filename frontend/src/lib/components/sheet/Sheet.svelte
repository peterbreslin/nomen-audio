<script lang="ts">
	import { fileStore } from '$lib/stores/files.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { COLUMN_GROUPS, buildColumnGroups, COMBOBOX_FIELDS, getColumnPx, getTableWidthPx } from './columns';
	import SheetRow from './SheetRow.svelte';
	import CellEditOverlay from './CellEditOverlay.svelte';
	import CellCombobox from './CellCombobox.svelte';
	import AnalysisDetailRow from './AnalysisDetailRow.svelte';
	import FileDetailsModal from './FileDetailsModal.svelte';

	interface Props {
		onGenerate: (id: string) => void;
		onGenerateSelected: () => void;
	}

	let { onGenerate, onGenerateSelected }: Props = $props();

	/** Local state: which row has the analysis detail expanded */
	let expandedDetailRowId = $state<string | null>(null);
	/** Local state: which file to show in details modal */
	let detailsModalFileId = $state<string | null>(null);
	/** Container width for pixel-based column sizing */
	let containerWidth = $state(0);

	let detailsModalOpen = $derived(detailsModalFileId !== null);
	let detailsFile = $derived(detailsModalFileId ? fileStore.files.get(detailsModalFileId) ?? null : null);

	let expandedCols = $derived(uiStore.expandedColumns);
	let allExpanded = $derived(uiStore.allColumnsExpanded);

	let allGroups = $derived(buildColumnGroups(settingsStore.settings?.custom_fields ?? []));

	let showSubHeaders = $derived(expandedCols.size > 0 || allExpanded);

	let tableWidthPx = $derived(getTableWidthPx(allGroups, expandedCols, allExpanded, containerWidth));

	function isExpanded(groupKey: string): boolean {
		return allExpanded || expandedCols.has(groupKey);
	}

	function getVisibleSubs(groupKey: string) {
		const group = allGroups.find((g) => g.key === groupKey)!;
		return isExpanded(groupKey) ? group.subs : [group.subs[0]];
	}

	/** Get column width style — always pixel-based to prevent layout shifts */
	function colStyle(group: typeof COLUMN_GROUPS[number]): string {
		const px = getColumnPx(group, expandedCols, allExpanded, containerWidth);
		return `width: ${px}px`;
	}

	/** Static alternating neon colors for column headers (by position) */
	const HEADER_COLORS = ['var(--plasma-violet)', 'var(--hyper-pink)'];

	function getHeaderColor(groupKey: string): string {
		const idx = allGroups.findIndex((g) => g.key === groupKey);
		return HEADER_COLORS[idx % 2];
	}

	function onHeaderClick(groupKey: string) {
		uiStore.toggleExpandColumn(groupKey);
	}

	function toggleDetailRow(fileId: string) {
		expandedDetailRowId = expandedDetailRowId === fileId ? null : fileId;
	}

	function openDetailsModal(fileId: string) {
		detailsModalFileId = fileId;
	}

	function closeDetailsModal() {
		detailsModalFileId = null;
	}
</script>

<div class="flex-1 overflow-auto" bind:clientWidth={containerWidth}>
	{#if fileStore.visibleFiles.length === 0}
		<div class="flex h-full items-center justify-center">
			<p class="text-[11px] text-[var(--text-muted)]">Import files to get started</p>
		</div>
	{:else}
		<table
			class="border-collapse"
			style="table-layout: fixed; width: {tableWidthPx}px; min-width: 100%;"
		>
			<!-- Main column headers -->
			<thead>
				<tr class="h-[30px]" style="position: sticky; top: 0; z-index: 6;">
					<!-- Wand column header -->
					<th
						class="w-8 border-b border-[var(--border-default)] bg-[var(--bg-surface)]"
					></th>

					{#each allGroups as group (group.key)}
						<th
							class="cursor-pointer select-none whitespace-nowrap border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-2 text-left text-[10px] font-semibold uppercase tracking-wider"
							style="{colStyle(group)}; color: {getHeaderColor(group.key)}"
							colspan={isExpanded(group.key) ? group.subs.length : 1}
							onclick={() => onHeaderClick(group.key)}
						>
							<span class="flex items-center gap-1">
								{group.label}
								{#if !allExpanded}
									<svg
										class="h-2.5 w-2.5 transition-transform duration-100"
										class:rotate-90={isExpanded(group.key)}
										viewBox="0 0 16 16"
										fill="currentColor"
									>
										<path d="M6.646 3.646a.5.5 0 0 1 .708 0l4 4a.5.5 0 0 1 0 .708l-4 4a.5.5 0 0 1-.708-.708L10.293 8 6.646 4.354a.5.5 0 0 1 0-.708z"/>
									</svg>
								{/if}
							</span>
						</th>
					{/each}
				</tr>

				<!-- Sub-column headers -->
				{#if showSubHeaders}
					<tr class="h-[26px]" style="position: sticky; top: 30px; z-index: 5;">
						<th class="border-b border-[var(--border-default)] bg-[var(--bg-raised)]"></th>
						{#each allGroups as group (group.key)}
							{#each getVisibleSubs(group.key) as sub (sub.key)}
								<th
									class="whitespace-nowrap border-b border-[var(--border-default)] bg-[var(--bg-raised)] px-2 text-left text-[10px] font-medium"
									style="color: {getHeaderColor(group.key)}"
								>
									{sub.label}
								</th>
							{/each}
						{/each}
					</tr>
				{/if}
			</thead>

			<tbody>
				{#each fileStore.visibleFiles as file, index (file.id)}
					<SheetRow
						{file}
						{index}
						{onGenerate}
						{onGenerateSelected}
						{allGroups}
						getVisibleSubs={getVisibleSubs}
						onToggleDetail={() => toggleDetailRow(file.id)}
						onViewDetails={openDetailsModal}
					/>
					{#if expandedDetailRowId === file.id && file.analysis}
						<AnalysisDetailRow
							{file}
							{allGroups}
							onClose={() => { expandedDetailRowId = null; }}
						/>
					{/if}
				{/each}
			</tbody>
		</table>
	{/if}
</div>

<!-- Cell edit overlays -->
{#if uiStore.editingCell && !COMBOBOX_FIELDS.has(uiStore.editingCell.field)}
	<CellEditOverlay />
{/if}
{#if uiStore.editingCell && COMBOBOX_FIELDS.has(uiStore.editingCell.field)}
	<CellCombobox />
{/if}

<!-- File details modal -->
{#if detailsFile}
	<FileDetailsModal
		file={detailsFile}
		open={detailsModalOpen}
		onClose={closeDetailsModal}
	/>
{/if}
