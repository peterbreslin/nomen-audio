<script lang="ts">
	import { uiStore } from '$lib/stores/ui.svelte';
	import { fileStore } from '$lib/stores/files.svelte';
	import FileTree from './FileTree.svelte';

	interface Props {
		onBrowse: () => void;
	}

	let { onBrowse }: Props = $props();
	let isResizing = $state(false);

	const MIN_WIDTH = 200;
	const MAX_WIDTH = 400;

	function onPointerDown(e: PointerEvent) {
		e.preventDefault();
		isResizing = true;
		const target = e.currentTarget as HTMLElement;
		target.setPointerCapture(e.pointerId);
	}

	function onPointerMove(e: PointerEvent) {
		if (!isResizing) return;
		const clamped = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX));
		uiStore.sidebarWidth = clamped;
	}

	function onPointerUp() {
		isResizing = false;
	}

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		uiStore.isDragOver = true;
	}

	function onDragLeave() {
		uiStore.isDragOver = false;
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		uiStore.isDragOver = false;
	}
</script>

{#if uiStore.sidebarCollapsed}
	<!-- Collapsed sidebar: thin strip with expand button -->
	<div class="flex w-8 shrink-0 flex-col items-center border-r border-[var(--border-default)] bg-[var(--bg-surface)] pt-2">
		<button
			class="rounded-sm p-1 text-[var(--text-muted)] hover:bg-[var(--bg-raised)] hover:text-[var(--text-primary)]"
			onclick={() => { uiStore.sidebarCollapsed = false; }}
			title="Expand sidebar"
		>
			<svg class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
				<path d="M6 3l5 5-5 5" />
			</svg>
		</button>
	</div>
{:else}
	<div
		class="relative flex shrink-0 flex-col border-r border-[var(--border-default)] bg-[var(--bg-surface)]"
		style="width: {uiStore.sidebarWidth}px"
		role="complementary"
		ondragover={onDragOver}
		ondragleave={onDragLeave}
		ondrop={onDrop}
	>
		<!-- Header -->
		<div class="flex h-10 items-center justify-between border-b border-[var(--border-default)] px-3">
			<div class="flex items-center gap-1.5">
				<button
					class="rounded-sm p-0.5 text-[var(--text-muted)] hover:bg-[var(--bg-raised)] hover:text-[var(--text-primary)]"
					onclick={() => { uiStore.sidebarCollapsed = true; }}
					title="Collapse sidebar"
				>
					<svg class="h-3 w-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
						<path d="M10 3L5 8l5 5" />
					</svg>
				</button>
				<span class="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
					Files
				</span>
			</div>
			<button
				class="rounded-sm border border-[var(--border-default)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)] hover:bg-[var(--bg-raised)] hover:text-[var(--text-primary)]"
				onclick={onBrowse}
			>
				Browse
			</button>
		</div>

		<!-- Search -->
		<div class="border-b border-[var(--border-default)] px-2 py-1.5">
			<div class="relative">
				<svg class="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--text-muted)]" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
					<circle cx="6.5" cy="6.5" r="5" />
					<path d="M10.5 10.5L14.5 14.5" />
				</svg>
				<input
					type="text"
					placeholder="Search files..."
					class="h-7 w-full rounded-sm border border-[var(--border-default)] bg-[var(--bg-input)] pl-7 pr-6 text-[11px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--border-focus)] focus:outline-none"
					bind:value={fileStore.sidebarFilter}
				/>
				{#if fileStore.sidebarFilter}
					<button
						class="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-sm p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
						onclick={() => { fileStore.sidebarFilter = ''; }}
						aria-label="Clear search"
					>
						<svg class="h-3 w-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
							<path d="M4 4l8 8M12 4l-8 8" />
						</svg>
					</button>
				{/if}
			</div>
		</div>

		<!-- File tree -->
		<div class="flex-1 overflow-y-auto">
			<FileTree />
		</div>

		<!-- Drop overlay -->
		{#if uiStore.isDragOver}
			<div class="absolute inset-0 z-10 flex items-center justify-center bg-[var(--accent-muted)] border-2 border-dashed border-[var(--nomen-accent)]">
				<span class="text-[11px] text-[var(--accent-text)]">Drop files here</span>
			</div>
		{/if}
	</div>

	<!-- Resize handle -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="w-px shrink-0 cursor-col-resize transition-colors duration-100
			{isResizing ? 'bg-[var(--nomen-accent)]/50' : 'hover:bg-[var(--nomen-accent)]/30'}"
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
	></div>
{/if}
