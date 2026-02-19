<script lang="ts">
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { Button } from '$lib/components/ui/button';
	import { modelsStore } from '$lib/stores/models.svelte';
	import { fileStore } from '$lib/stores/files.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import SettingsModal from '$lib/components/SettingsModal.svelte';

	interface Props {
		onSaveAll: () => void;
		onGenerateAll: () => void;
		onGenerateSelected: () => void;
		onCancelGenerate: () => void;
		isGenerating: boolean;
		batchProgress: { current: number; total: number; filename: string } | null;
	}

	let { onSaveAll, onGenerateAll, onGenerateSelected, onCancelGenerate, isGenerating, batchProgress }: Props = $props();

	let settingsOpen = $state(false);
	let hasModified = $derived(fileStore.modifiedFileIds.length > 0);
	let selectedCount = $derived(fileStore.selectedFileIds.size);
</script>

<div>
	<header class="flex h-10 items-center border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
		<!-- Brand -->
		<div class="flex items-center gap-1.5 pl-3 pr-4">
			<span class="text-[13px] font-semibold tracking-[-0.3px] text-[var(--text-primary)]">Nomen Audio</span>
			<span class="font-mono text-[10px] text-[var(--text-muted)]">v0.1.0</span>
		</div>

		<div class="ml-auto flex items-center gap-1 pr-2">
			<!-- Save All -->
			<Tooltip.Root>
				<Tooltip.Trigger>
					{#snippet child({ props })}
						<Button
							{...props}
							variant="ghost"
							size="sm"
							onclick={onSaveAll}
							disabled={!hasModified}
							class="h-8 w-8 p-0"
						>
							<svg class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
								<path d="M13 1H3a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3a2 2 0 0 0-2-2z" />
								<path d="M4 1v4h8V1" />
								<rect x="5" y="8" width="6" height="5" rx="0.5" />
							</svg>
						</Button>
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content><p>Save All</p></Tooltip.Content>
			</Tooltip.Root>

			<!-- Settings -->
			<Tooltip.Root>
				<Tooltip.Trigger>
					{#snippet child({ props })}
						<Button
							{...props}
							variant="ghost"
							size="sm"
							onclick={() => { settingsOpen = true; }}
							class="h-8 w-8 p-0"
						>
							<svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
								<circle cx="12" cy="12" r="3" />
							</svg>
						</Button>
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content><p>Settings</p></Tooltip.Content>
			</Tooltip.Root>

			<div class="mx-1 h-4 w-px bg-[var(--border-default)]"></div>

			<!-- Expand All toggle -->
			<button
				class="rounded-sm border px-2 py-1 text-[10px]
					{uiStore.allColumnsExpanded
						? 'border-[var(--nomen-accent)] bg-[var(--accent-muted)] text-[var(--accent-text)]'
						: 'border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-raised)] hover:text-[var(--text-primary)]'}"
				onclick={() => uiStore.toggleExpandAll()}
			>
				{uiStore.allColumnsExpanded ? 'Collapse All' : 'Expand All'}
			</button>

			<!-- Generate Selected (visible when >1 selected) -->
			{#if selectedCount > 1}
				<button
					class="rounded-sm border border-[var(--border-default)] px-2 py-1 text-[10px] text-[var(--text-secondary)] hover:bg-[var(--bg-raised)] hover:text-[var(--text-primary)] disabled:cursor-default disabled:opacity-40"
					onclick={onGenerateSelected}
					disabled={isGenerating || !modelsStore.isReady}
				>
					Generate ({selectedCount})
				</button>
			{/if}

			<!-- Generate All -->
			<Tooltip.Root>
				<Tooltip.Trigger>
					{#snippet child({ props })}
						<button
							{...props}
							class="flex cursor-pointer items-center justify-center rounded-sm p-1.5 transition-[filter,opacity] duration-75
								hover:brightness-125
								disabled:cursor-default disabled:opacity-50 disabled:hover:brightness-100"
							style="background: {isGenerating ? 'var(--accent-muted)' : 'var(--nomen-accent)'}; color: {isGenerating ? 'var(--accent-text)' : 'var(--bg-base)'}; opacity: {isGenerating ? 0.7 : 1}; box-shadow: 0 0 6px var(--nomen-accent), 0 0 12px color-mix(in srgb, var(--nomen-accent) 30%, transparent)"
							onclick={onGenerateAll}
							disabled={isGenerating || !modelsStore.isReady || fileStore.files.size === 0}
						>
							<svg
								class="h-4 w-4"
								class:animate-[nomen-spin_0.8s_linear_infinite]={isGenerating}
								viewBox="0 0 16 16"
								fill="currentColor"
							>
								<path d="M9.5 1L4 9h4l-1.5 6L13 7H9l.5-6z" />
							</svg>
						</button>
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content><p>Generate All</p></Tooltip.Content>
			</Tooltip.Root>
		</div>
	</header>

	<!-- Batch progress bar -->
	{#if isGenerating && batchProgress}
		<div class="border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1">
			<div class="h-0.5 w-full overflow-hidden rounded-full bg-[var(--border-default)]">
				<div
					class="h-full bg-[var(--nomen-accent)] transition-[width] duration-300 ease-linear"
					style="width: {batchProgress.total > 0 ? (batchProgress.current / batchProgress.total * 100) : 0}%"
				></div>
			</div>
			<div class="mt-0.5 flex items-center gap-2">
				<p class="font-mono text-[10px] text-[var(--text-secondary)]">
					Analyzing {batchProgress.current} / {batchProgress.total} — {batchProgress.filename}
				</p>
				<button
					class="cursor-pointer rounded-sm px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-raised)] hover:text-[var(--text-primary)]"
					onclick={onCancelGenerate}
				>
					Stop
				</button>
			</div>
		</div>
	{/if}
</div>

<SettingsModal bind:open={settingsOpen} />
