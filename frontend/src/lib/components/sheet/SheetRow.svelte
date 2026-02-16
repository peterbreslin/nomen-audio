<script lang="ts">
	import type { FileRecord } from '$lib/types';
	import type { SubColumn } from './columns';
	import { fileStore } from '$lib/stores/files.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import { modelsStore } from '$lib/stores/models.svelte';
	import { COLUMN_GROUPS, getCellValue, isEditableField, AI_BADGE_FIELDS } from './columns';
	import * as ContextMenu from '$lib/components/ui/context-menu';
	import * as api from '$lib/api/client';
	import { toast } from 'svelte-sonner';
	import { friendlyMessage } from '$lib/utils/errors';

	interface Props {
		file: FileRecord;
		index: number;
		onGenerate: (id: string) => void;
		getVisibleSubs: (groupKey: string) => SubColumn[];
		onToggleDetail: () => void;
		onViewDetails: (id: string) => void;
	}

	let { file, index, onGenerate, getVisibleSubs, onToggleDetail, onViewDetails }: Props = $props();

	let isGenerating = $state(false);
	let isSelected = $derived(fileStore.selectedFileIds.has(file.id));
	let aiFields = $derived(fileStore.aiGeneratedFields.get(file.id));
	let manualFields = $derived(fileStore.manualEditedFields.get(file.id));
	let isModified = $derived(file.status === 'modified');
	let selectedCount = $derived(fileStore.selectedFileIds.size);
	let hasMultipleSelected = $derived(selectedCount > 1);

	function onRowClick(e: MouseEvent) {
		if (e.shiftKey) e.preventDefault();
		fileStore.setActiveFile(file.id);
		if (e.ctrlKey || e.metaKey) {
			fileStore.toggleSelect(file.id);
		} else if (e.shiftKey) {
			fileStore.rangeSelect(file.id);
		} else {
			fileStore.selectFile(file.id);
		}
	}

	function onCellDblClick(subKey: string, e: MouseEvent) {
		if (!isEditableField(subKey)) return;
		const td = (e.target as HTMLElement).closest('td');
		if (!td) return;
		const rect = td.getBoundingClientRect();
		uiStore.openCellEdit(file.id, subKey, rect);
	}

	function onCellKeyDown(subKey: string, e: KeyboardEvent) {
		if (e.key === 'Enter' && isEditableField(subKey)) {
			const td = (e.target as HTMLElement).closest('td');
			if (!td) return;
			const rect = td.getBoundingClientRect();
			uiStore.openCellEdit(file.id, subKey, rect);
		}
	}

	async function handleGenerate() {
		isGenerating = true;
		try {
			await onGenerate(file.id);
		} finally {
			isGenerating = false;
		}
	}

	function onSparkleClick(e: MouseEvent) {
		e.stopPropagation();
		if (file.analysis) {
			onToggleDetail();
		} else {
			handleGenerate();
		}
	}

	async function handleSave() {
		try {
			const res = await api.saveFile(file.id, file.rename_on_save);
			fileStore.updateFile(res.file);
			toast.success('File saved');
		} catch (e) {
			toast.error('Save failed', { description: friendlyMessage(e) });
		}
	}

	async function handleRevert() {
		try {
			const reverted = await api.revertFile(file.id);
			fileStore.updateFile(reverted);
			fileStore.clearFieldTracking(file.id);
			toast.success('File reverted');
		} catch (e) {
			toast.error('Revert failed', { description: friendlyMessage(e) });
		}
	}

	async function handleRevertSelected() {
		const ids = [...fileStore.selectedFileIds];
		const modifiedIds = ids.filter((id) => fileStore.files.get(id)?.status === 'modified');
		if (modifiedIds.length === 0) return;
		let succeeded = 0;
		for (const id of modifiedIds) {
			try {
				const reverted = await api.revertFile(id);
				fileStore.updateFile(reverted);
				fileStore.clearFieldTracking(id);
				succeeded++;
			} catch {
				// continue with remaining files
			}
		}
		if (succeeded === modifiedIds.length) {
			toast.success(`Reverted ${succeeded} files`);
		} else {
			toast.warning(`Reverted ${succeeded} of ${modifiedIds.length} files`);
		}
	}

	function handleRemove() {
		fileStore.removeFiles([file.id]);
	}

	/** Determine dot color for a cell: hologram-cyan for AI, tech-gold for manual, null for none */
	function getDotColor(subKey: string): string | null {
		if (AI_BADGE_FIELDS.has(subKey) && (aiFields?.has(subKey) ?? false)) {
			return 'var(--hologram-cyan)';
		}
		if (manualFields?.has(subKey) ?? false) {
			return 'var(--tech-gold)';
		}
		return null;
	}
</script>

<ContextMenu.Root>
	<ContextMenu.Trigger>
		{#snippet child({ props })}
			<tr
				{...props}
				class="h-8 select-none transition-colors duration-75
					{isSelected
						? 'bg-[var(--accent-muted)]'
						: index % 2 === 0
							? 'bg-[var(--bg-base)]'
							: 'bg-[var(--bg-surface)]'}
					hover:bg-[var(--bg-raised)]"
				onclick={onRowClick}
			>
				<!-- Wand column -->
				<td class="w-8 text-center">
					<button
						class="inline-flex items-center justify-center p-1 {file.analysis ? 'opacity-100' : 'opacity-40'} hover:opacity-100"
						onclick={onSparkleClick}
						title={file.analysis ? 'Show/hide analysis results' : 'Generate AI suggestions'}
					>
						<svg
							class="h-4 w-4"
							class:animate-[nomen-spin_0.8s_linear_infinite]={isGenerating}
							viewBox="0 0 16 16"
							fill="currentColor"
							style="color: {file.analysis ? 'var(--hologram-cyan)' : 'var(--text-secondary)'}"
						>
							<path d="M9.5 1L4 9h4l-1.5 6L13 7H9l.5-6z" />
						</svg>
					</button>
				</td>

				<!-- Data cells -->
				{#each COLUMN_GROUPS as group (group.key)}
					{#each getVisibleSubs(group.key) as sub (sub.key)}
						{@const dotColor = getDotColor(sub.key)}
						<td
							class="overflow-hidden border-r border-[var(--border-default)]/30 py-1 pl-2 pr-3"
							ondblclick={(e) => onCellDblClick(sub.key, e)}
						>
							<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
							<div
								class="flex items-center gap-1.5 text-[11px] text-[var(--text-primary)]
									{sub.mono ? 'font-mono' : ''}"
								tabindex={isEditableField(sub.key) ? 0 : -1}
								onkeydown={(e) => onCellKeyDown(sub.key, e)}
							>
								<span class="truncate" title={getCellValue(file, sub)}>{getCellValue(file, sub)}</span>
								{#if dotColor}
									<span
										class="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
										style="background: {dotColor}; box-shadow: 0 0 4px {dotColor}, 0 0 8px {dotColor}"
									></span>
								{/if}
							</div>
						</td>
					{/each}
				{/each}
			</tr>
		{/snippet}
	</ContextMenu.Trigger>

	<ContextMenu.Content class="w-48">
		<ContextMenu.Item onclick={handleGenerate} disabled={!modelsStore.isReady || isGenerating}>
			<svg class="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
				<path d="M9.5 1L4 9h4l-1.5 6L13 7H9l.5-6z" />
			</svg>
			Generate
		</ContextMenu.Item>

		<ContextMenu.Separator />

		<ContextMenu.Item onclick={handleSave} disabled={!isModified}>
			Save
			<ContextMenu.Shortcut>Ctrl+S</ContextMenu.Shortcut>
		</ContextMenu.Item>

		<ContextMenu.Item onclick={handleRevert} disabled={!isModified}>
			Revert
		</ContextMenu.Item>

		{#if hasMultipleSelected}
			<ContextMenu.Item onclick={handleRevertSelected}>
				Revert Selected ({selectedCount})
			</ContextMenu.Item>
		{/if}

		<ContextMenu.Separator />

		<ContextMenu.Item onclick={() => onViewDetails(file.id)}>
			View Details
		</ContextMenu.Item>

		<ContextMenu.Item variant="destructive" onclick={handleRemove}>
			Remove from List
		</ContextMenu.Item>
	</ContextMenu.Content>
</ContextMenu.Root>
