<script lang="ts">
	import type { FileRecord } from '$lib/types';
	import { fileStore } from '$lib/stores/files.svelte';
	import { COLUMN_GROUPS } from './columns';
	import { uiStore } from '$lib/stores/ui.svelte';
	import * as api from '$lib/api/client';

	interface Props {
		file: FileRecord;
		onClose: () => void;
	}

	let { file, onClose }: Props = $props();

	let matches = $derived(file.analysis?.classification?.slice(0, 3) ?? []);

	/** Color per rank: best → hacker-green, middle → glitch-orange, worst → blazing-crimson */
	const RANK_COLORS = ['var(--hacker-green)', 'var(--glitch-orange)', 'var(--blazing-crimson)'];

	// Total visible columns: 1 (wand) + sum of visible sub-columns
	let totalCols = $derived.by(() => {
		let count = 1; // wand col
		for (const g of COLUMN_GROUPS) {
			count += uiStore.allColumnsExpanded || uiStore.expandedColumns.has(g.key)
				? g.subs.length
				: 1;
		}
		return count;
	});

	function useClassification(idx: number) {
		const match = matches[idx];
		if (!match) return;
		const updates: Record<string, string> = {
			category: match.category,
			subcategory: match.subcategory,
			cat_id: match.cat_id,
			category_full: match.category_full,
		};
		for (const [key, value] of Object.entries(updates)) {
			fileStore.updateFieldLocally(file.id, key, value);
		}
		fileStore.markAiGenerated(file.id, Object.keys(updates));
		// Sync to backend — response includes regenerated filename
		api.updateMetadata(file.id, updates as any).then((res) => {
			if (res?.suggested_filename) {
				fileStore.updateFieldLocally(file.id, 'suggested_filename', res.suggested_filename);
				fileStore.markAiGenerated(file.id, ['suggested_filename']);
			}
		}).catch(() => {});
		onClose();
	}
</script>

<tr class="border-t border-[var(--border-focus)]">
	<td colspan={totalCols} class="bg-[var(--bg-raised)] px-3 py-2">
		<div class="flex items-center gap-4">
			{#each matches as match, i (match.cat_id + i)}
				{@const rankColor = RANK_COLORS[i] ?? RANK_COLORS[2]}
				<div class="flex items-center gap-2 text-[11px]">
					<span
						class="rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-semibold"
						style="background: color-mix(in srgb, {rankColor} 20%, transparent); color: {rankColor}"
					>
						{match.category}
					</span>
					<span style="color: {rankColor}">{match.subcategory}</span>
					<!-- Confidence bar -->
					<div class="h-1.5 w-16 rounded-full bg-[var(--border-default)]">
						<div
							class="h-full rounded-full"
							style="width: {Math.round(match.confidence * 100)}%; background: {rankColor}"
						></div>
					</div>
					<span class="font-mono text-[10px] text-[var(--text-muted)]">
						{Math.round(match.confidence * 100)}%
					</span>
					<button
						class="rounded-sm border border-[var(--border-default)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)] hover:bg-[var(--accent-muted)] hover:text-[var(--text-primary)]"
						onclick={() => useClassification(i)}
					>
						Use
					</button>
				</div>
			{/each}
			<button
				class="ml-auto text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
				onclick={onClose}
			>
				Close
			</button>
		</div>
	</td>
</tr>
