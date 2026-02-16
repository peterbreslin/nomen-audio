<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { open } from '@tauri-apps/plugin-dialog';
	import { getCurrentWebview } from '@tauri-apps/api/webview';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import Toolbar from '$lib/components/Toolbar.svelte';
	import StatusBar from '$lib/components/StatusBar.svelte';
	import Sidebar from '$lib/components/sidebar/Sidebar.svelte';
	import Sheet from '$lib/components/sheet/Sheet.svelte';
	import WaveformPanel from '$lib/components/main/WaveformPanel.svelte';
	import FindReplaceModal from '$lib/components/FindReplaceModal.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import { fileStore } from '$lib/stores/files.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import { toast } from 'svelte-sonner';
	import * as api from '$lib/api/client';
	import { friendlyMessage } from '$lib/utils/errors';
	import type { SuggestionsResult } from '$lib/types';

	let unlisten: (() => void) | null = null;
	let unlistenClose: (() => void) | null = null;
	let showSaveAllDialog = $state(false);
	let showCloseWarning = $state(false);
	let showFindReplace = $state(false);

	// Batch generation state
	let batchProgress = $state<{ current: number; total: number; filename: string } | null>(null);
	let batchAborted = $state(false);

	async function handleImport() {
		const dir = await open({ title: 'Select folder to import', directory: true });
		if (!dir) return;
		await doImport(dir);
	}

	async function doImport(directory: string) {
		uiStore.isImporting = true;
		try {
			const res = await api.importDirectory(directory);
			fileStore.addFiles(res.files);
			if (res.files.length > 0 && !fileStore.activeFileId) {
				fileStore.setActiveFile(res.files[0].id);
				fileStore.selectFile(res.files[0].id);
			}
			toast.success(`Imported ${res.count} files`, {
				description: res.skipped > 0 ? `${res.skipped} skipped` : undefined
			});
		} catch (e) {
			toast.error('Import failed', { description: friendlyMessage(e) });
		} finally {
			uiStore.isImporting = false;
		}
	}

	function handleSaveAll() {
		const ids = fileStore.modifiedFileIds;
		if (ids.length === 0) return;
		showSaveAllDialog = true;
	}

	async function confirmSaveAll() {
		showSaveAllDialog = false;
		const ids = fileStore.modifiedFileIds;
		try {
			const res = await api.saveBatch(ids, true);
			const successIds = res.results.filter((r) => r.success).map((r) => r.id);
			const files = await Promise.all(successIds.map((id) => api.fetchFile(id)));
			for (const file of files) {
				fileStore.updateFile(file);
			}
			if (res.failed_count > 0) {
				toast.warning(`Saved ${res.saved_count} files, ${res.failed_count} failed`);
			} else {
				toast.success(`Saved ${res.saved_count} files`);
			}
		} catch (e) {
			toast.error('Save All failed', { description: friendlyMessage(e) });
		}
	}

	/** Generate AI suggestions for a single file (auto-apply). Returns true on success. */
	async function handleGenerate(fileId: string): Promise<boolean> {
		try {
			const res = await api.analyzeFile(fileId, [1, 2]);
			fileStore.setAnalysis(fileId, res.analysis, res.suggestions);
			// Auto-apply suggestions
			if (res.suggestions) {
				const applied: string[] = [];
				const sug = res.suggestions;
				const fields: (keyof SuggestionsResult)[] = [
					'category', 'subcategory', 'cat_id', 'category_full',
					'fx_name', 'description', 'keywords', 'suggested_filename'
				];
				const updates: Record<string, string | null> = {};
				for (const f of fields) {
					if (sug[f]?.value) {
						fileStore.updateFieldLocally(fileId, f, sug[f]!.value);
						applied.push(f);
						updates[f] = sug[f]!.value;
					}
				}
				if (applied.length > 0) {
					fileStore.markAiGenerated(fileId, applied);
					// Sync to backend so save persists the values;
					// use response to get server-regenerated suggested_filename
					api.updateMetadata(fileId, updates as any).then((res) => {
						if (res?.suggested_filename) {
							fileStore.updateFieldLocally(fileId, 'suggested_filename', res.suggested_filename);
						}
					}).catch(() => {});
				}
			}
			return true;
		} catch (e) {
			toast.error('Analysis failed', { description: friendlyMessage(e) });
			return false;
		}
	}

	/** Generate for selected files (if multiple selected) or all visible files */
	async function handleGenerateAll() {
		const selected = fileStore.selectedFileIds;
		const useSelected = selected.size > 1;
		const pool = useSelected
			? fileStore.visibleFiles.filter((f) => selected.has(f.id) && !f.analysis)
			: fileStore.visibleFiles.filter((f) => !f.analysis);
		if (pool.length === 0) {
			toast.info(useSelected ? 'Selected files already analyzed' : 'All visible files already analyzed');
			return;
		}
		uiStore.isGenerating = true;
		batchAborted = false;
		let current = 0;
		let succeeded = 0;
		try {
			for (const file of pool) {
				if (batchAborted) break;
				current++;
				batchProgress = { current, total: pool.length, filename: file.filename };
				if (await handleGenerate(file.id)) succeeded++;
			}
			const failed = current - succeeded;
			if (batchAborted) {
				toast.info(`Stopped after ${succeeded} of ${pool.length} files`);
			} else if (failed > 0) {
				toast.warning(`Generated ${succeeded} of ${pool.length} files (${failed} failed)`);
			} else {
				toast.success(`Generated suggestions for ${pool.length} files`);
			}
		} finally {
			uiStore.isGenerating = false;
			batchProgress = null;
			batchAborted = false;
		}
	}

	function handleCancelGenerate() {
		batchAborted = true;
	}

	async function handleSaveCurrent() {
		const id = fileStore.activeFileId ?? fileStore.selectedFileId;
		if (!id) return;
		const file = fileStore.files.get(id);
		if (!file || file.status !== 'modified') return;
		try {
			const res = await api.saveFile(id, file.rename_on_save);
			fileStore.updateFile(res.file);
			toast.success('File saved');
		} catch (e) {
			toast.error('Save failed', { description: friendlyMessage(e) });
		}
	}

	function isInputFocused(e: KeyboardEvent): boolean {
		const el = e.target;
		if (!el || !(el instanceof HTMLElement)) return false;
		const tag = el.tagName;
		return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.hasAttribute('contenteditable');
	}

	function handleKeydown(e: KeyboardEvent) {
		const mod = e.ctrlKey || e.metaKey;

		if (mod && e.key === 's') {
			e.preventDefault();
			handleSaveCurrent();
			return;
		}

		if (mod && e.key === 'h') {
			e.preventDefault();
			showFindReplace = !showFindReplace;
			return;
		}

		if (e.key === ' ' && !isInputFocused(e)) {
			e.preventDefault();
			globalThis.dispatchEvent(new Event('nomen:toggle-play'));
		}

		if (e.key === 'Escape') {
			uiStore.closeCellEdit();
		}
	}

	onMount(async () => {
		uiStore.startHealthPolling();

		try {
			const webview = getCurrentWebview();
			unlisten = await webview.onDragDropEvent((event) => {
				if (event.payload.type === 'enter' || event.payload.type === 'over') {
					uiStore.isDragOver = true;
				} else if (event.payload.type === 'leave') {
					uiStore.isDragOver = false;
				} else if (event.payload.type === 'drop') {
					uiStore.isDragOver = false;
					const paths = event.payload.paths;
					(async () => {
						for (const path of paths) {
							await doImport(path);
						}
					})().catch(() => {});
				}
			});
		} catch {
			// Drag-drop not available outside Tauri
		}

		try {
			const appWindow = getCurrentWindow();
			unlistenClose = await appWindow.onCloseRequested(async (event) => {
				if (fileStore.modifiedFileIds.length > 0) {
					event.preventDefault();
					showCloseWarning = true;
				}
			});
		} catch {
			// Close handler not available outside Tauri
		}
	});

	async function confirmClose() {
		showCloseWarning = false;
		try {
			await getCurrentWindow().destroy();
		} catch {
			globalThis.close();
		}
	}

	onDestroy(() => {
		unlisten?.();
		unlistenClose?.();
		uiStore.stopHealthPolling();
	});
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="grid h-screen grid-rows-[auto_1fr_24px]">
	<Toolbar
		onSaveAll={handleSaveAll}
		onGenerateAll={handleGenerateAll}
		onCancelGenerate={handleCancelGenerate}
		isGenerating={uiStore.isGenerating}
		{batchProgress}
	/>

	{#if !uiStore.backendConnected}
		<div class="flex items-center justify-center gap-2 bg-destructive px-3 py-1 text-xs text-destructive-foreground">
			<span class="inline-block h-2 w-2 rounded-full bg-destructive-foreground/70"></span>
			Backend disconnected — retrying...
		</div>
	{/if}

	<main class="flex min-h-0 overflow-hidden">
		<Sidebar onBrowse={handleImport} />

		<div class="flex min-h-0 flex-1 flex-col overflow-hidden">
			<Sheet onGenerate={handleGenerate} />
			<WaveformPanel />
		</div>
	</main>

	<StatusBar />
</div>

<ConfirmDialog
	bind:open={showSaveAllDialog}
	title="Save All"
	message="Save and rename {fileStore.modifiedFileIds.length} modified files?"
	confirmLabel="Save All"
	onConfirm={confirmSaveAll}
	onCancel={() => { showSaveAllDialog = false; }}
/>

<FindReplaceModal bind:open={showFindReplace} />

<ConfirmDialog
	bind:open={showCloseWarning}
	title="Unsaved Changes"
	message="You have {fileStore.modifiedFileIds.length} unsaved files. Close without saving?"
	confirmLabel="Close"
	destructive={true}
	onConfirm={confirmClose}
	onCancel={() => { showCloseWarning = false; }}
/>
