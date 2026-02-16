<script lang="ts">
	import { fileStore } from '$lib/stores/files.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import * as ContextMenu from '$lib/components/ui/context-menu';

	interface FileNode {
		id: string;
		filename: string;
		status: string;
		hasAi: boolean;
	}

	interface FolderNode {
		path: string;
		name: string;
		files: FileNode[];
	}

	// Build tree structure from visible files grouped by directory
	let tree = $derived.by(() => {
		const folders = new Map<string, FolderNode>();
		for (const f of fileStore.filteredFiles) {
			let node = folders.get(f.directory);
			if (!node) {
				const name = f.directory.split(/[/\\]/).pop() || f.directory;
				node = { path: f.directory, name, files: [] };
				folders.set(f.directory, node);
			}
			const hasAi = fileStore.aiGeneratedFields.has(f.id);
			node.files.push({ id: f.id, filename: f.filename, status: f.status, hasAi });
		}
		return Array.from(folders.values());
	});

	let allFiles = $derived(tree.flatMap((f) => f.files));

	// Auto-expand all folders on first import only
	let hasAutoExpanded = false;
	$effect(() => {
		if (tree.length > 0 && !hasAutoExpanded) {
			hasAutoExpanded = true;
			uiStore.expandedFolders = new Set(tree.map((f) => f.path));
		}
	});

	let anyExpanded = $derived(
		tree.length > 0 && tree.some((f) => uiStore.expandedFolders.has(f.path))
	);

	function toggleFolder(path: string) {
		const next = new Set(uiStore.expandedFolders);
		if (next.has(path)) {
			next.delete(path);
		} else {
			next.add(path);
		}
		uiStore.expandedFolders = next;
	}

	function collapseAll() {
		uiStore.expandedFolders = new Set();
	}

	function expandAll() {
		uiStore.expandedFolders = new Set(tree.map((f) => f.path));
	}

	function toggleFlatView() {
		uiStore.sidebarFlatView = !uiStore.sidebarFlatView;
	}

	function onFileClick(id: string, e: MouseEvent) {
		if (e.shiftKey) e.preventDefault();
		fileStore.setActiveFile(id);
		if (e.ctrlKey || e.metaKey) {
			fileStore.toggleSelect(id);
		} else if (e.shiftKey) {
			fileStore.rangeSelect(id);
		} else {
			fileStore.selectFile(id);
		}
	}

	function isSelected(id: string): boolean {
		return fileStore.selectedFileIds.has(id);
	}

	function removeFolder(path: string) {
		fileStore.removeFolder(path);
	}

	function getFileColor(file: FileNode): string {
		if (file.status === 'modified') return 'var(--cyber-sky)';
		if (file.hasAi) return 'var(--hologram-cyan)';
		return '';
	}

	function toggleModifiedFilter() {
		fileStore.sidebarStatusFilter = fileStore.sidebarStatusFilter === 'modified' ? null : 'modified';
	}
</script>

<div class="select-none py-1">
	{#if tree.length > 0 || fileStore.sidebarStatusFilter}
		<!-- View controls -->
		<div class="flex items-center gap-1 px-3 pb-1">
			<button
				class="rounded-sm px-1.5 py-0.5 text-[9px] uppercase tracking-wider
					{uiStore.sidebarFlatView
						? 'bg-[var(--accent-muted)] text-[var(--accent-text)]'
						: 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}"
				onclick={toggleFlatView}
				title={uiStore.sidebarFlatView ? 'Switch to folder view' : 'Switch to flat file list'}
			>
				{uiStore.sidebarFlatView ? 'Tree' : 'Flat'}
			</button>
			{#if !uiStore.sidebarFlatView}
				<button
					class="rounded-sm px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
					onclick={anyExpanded ? collapseAll : expandAll}
					title={anyExpanded ? 'Collapse all folders' : 'Expand all folders'}
				>
					{anyExpanded ? 'Collapse' : 'Expand'}
				</button>
			{/if}
			<button
				class="rounded-sm px-1.5 py-0.5 text-[9px] uppercase tracking-wider
					{fileStore.sidebarStatusFilter === 'modified'
						? 'bg-[var(--accent-muted)] text-[var(--accent-text)]'
						: 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}"
				onclick={toggleModifiedFilter}
				title={fileStore.sidebarStatusFilter === 'modified' ? 'Show all files' : 'Show modified files only'}
			>
				Modified
			</button>
		</div>
	{/if}

	{#if uiStore.sidebarFlatView}
		<!-- Flat view: all files without folder grouping -->
		{#each allFiles as file (file.id)}
			{@const fileColor = getFileColor(file)}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="flex cursor-pointer items-center gap-1.5 py-0.5 pl-3 pr-3 font-mono text-[11px]
					{fileStore.activeFileId === file.id
						? 'border-l-2 border-l-[var(--nomen-accent)] bg-[var(--accent-muted)]'
						: isSelected(file.id)
							? 'border-l-2 border-l-transparent bg-[var(--bg-raised)]'
							: 'border-l-2 border-l-transparent hover:bg-[var(--bg-raised)]'}"
				onclick={(e) => onFileClick(file.id, e)}
			>
				<svg class="h-3 w-3 shrink-0 text-[var(--text-muted)]" viewBox="0 0 16 16" fill="currentColor">
					<path d="M4 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V4.707A1 1 0 0 0 13.707 4L10 .293A1 1 0 0 0 9.293 0H4z"/>
				</svg>
				<span class="truncate" style={fileColor ? `color: ${fileColor}` : ''}>{file.filename}</span>
			</div>
		{/each}
	{:else}
		{#each tree as folder (folder.path)}
			<!-- Folder node with right-click context menu -->
			<ContextMenu.Root>
				<ContextMenu.Trigger>
					{#snippet child({ props })}
						<button
							{...props}
							class="flex w-full items-center gap-1.5 px-3 py-1 text-[11px] font-mono text-[var(--text-secondary)] hover:bg-[var(--bg-raised)] hover:text-[var(--text-primary)]"
							onclick={() => toggleFolder(folder.path)}
						>
							<svg
								class="h-3 w-3 shrink-0 transition-transform duration-100"
								class:rotate-90={uiStore.expandedFolders.has(folder.path)}
								viewBox="0 0 16 16"
								fill="currentColor"
							>
								<path d="M6.646 3.646a.5.5 0 0 1 .708 0l4 4a.5.5 0 0 1 0 .708l-4 4a.5.5 0 0 1-.708-.708L10.293 8 6.646 4.354a.5.5 0 0 1 0-.708z"/>
							</svg>
							<svg class="h-3 w-3 shrink-0 text-[var(--text-muted)]" viewBox="0 0 16 16" fill="currentColor">
								<path d="M1 3.5A1.5 1.5 0 0 1 2.5 2h2.764c.958 0 1.76.56 2.311 1.184C7.985 3.648 8.48 4 9 4h4.5A1.5 1.5 0 0 1 15 5.5v7a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 12.5v-9z"/>
							</svg>
							<span class="truncate">{folder.name}</span>
							<span class="ml-auto text-[10px] text-[var(--text-muted)]">{folder.files.length}</span>
						</button>
					{/snippet}
				</ContextMenu.Trigger>
				<ContextMenu.Content class="w-40">
					<ContextMenu.Item onclick={() => removeFolder(folder.path)}>
						Remove Folder
					</ContextMenu.Item>
				</ContextMenu.Content>
			</ContextMenu.Root>

			<!-- File nodes -->
			{#if uiStore.expandedFolders.has(folder.path)}
				{#each folder.files as file (file.id)}
					{@const fileColor = getFileColor(file)}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						class="flex cursor-pointer items-center gap-1.5 py-0.5 pl-[26px] pr-3 font-mono text-[11px]
							{fileStore.activeFileId === file.id
								? 'border-l-2 border-l-[var(--nomen-accent)] bg-[var(--accent-muted)]'
								: isSelected(file.id)
									? 'border-l-2 border-l-transparent bg-[var(--bg-raised)]'
									: 'border-l-2 border-l-transparent hover:bg-[var(--bg-raised)]'}"
						onclick={(e) => onFileClick(file.id, e)}
					>
						<svg class="h-3 w-3 shrink-0 text-[var(--text-muted)]" viewBox="0 0 16 16" fill="currentColor">
							<path d="M4 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V4.707A1 1 0 0 0 13.707 4L10 .293A1 1 0 0 0 9.293 0H4z"/>
						</svg>
						<span class="truncate" style={fileColor ? `color: ${fileColor}` : ''}>{file.filename}</span>
					</div>
				{/each}
			{/if}
		{/each}
	{/if}

	{#if tree.length === 0}
		<p class="px-3 py-4 text-center text-[11px] text-[var(--text-muted)]">
			No files imported
		</p>
	{/if}
</div>
