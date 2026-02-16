<script lang="ts">
	import { uiStore } from '$lib/stores/ui.svelte';
	import { fileStore } from '$lib/stores/files.svelte';
	import * as api from '$lib/api/client';
	import { tick } from 'svelte';

	let textareaEl: HTMLTextAreaElement | undefined = $state();
	let value = $state('');

	let cell = $derived(uiStore.editingCell);
	let file = $derived(cell ? fileStore.files.get(cell.rowId) : null);
	let mounted = $state(false);

	$effect(() => {
		if (cell && file) {
			mounted = false;
			const raw = file[cell.field as keyof typeof file];
			value = raw != null ? String(raw) : '';
			tick().then(() => {
				textareaEl?.focus();
				textareaEl?.select();
				requestAnimationFrame(() => { mounted = true; });
			});
		}
	});

	function finishEdit() {
		if (!cell || !file) { uiStore.closeCellEdit(); return; }
		const raw = file[cell.field as keyof typeof file];
		const oldStr = raw != null ? String(raw) : '';
		const newStr = value || '';
		if (newStr !== oldStr) {
			fileStore.updateFieldLocally(cell.rowId, cell.field, value || null);
			fileStore.clearAiField(cell.rowId, cell.field);
			fileStore.markManualEdit(cell.rowId, cell.field);
			// Sync to backend
			api.updateMetadata(cell.rowId, { [cell.field]: value || null }).catch(() => {});
		}
		uiStore.closeCellEdit();
	}

	function cancel() {
		uiStore.closeCellEdit();
	}

	function onKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			finishEdit();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			cancel();
		}
	}

	function onClickOutside(e: MouseEvent) {
		if (!mounted) return;
		if (textareaEl && !textareaEl.contains(e.target as Node)) {
			finishEdit();
		}
	}

	// Compute position
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
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="rounded-[3px] border border-[var(--border-focus)] bg-[var(--bg-raised)] shadow-[0_4px_20px_rgba(0,0,0,0.5),0_0_0_1px_var(--border-focus)/40]"
		{style}
		onclick={(e) => e.stopPropagation()}
	>
		<textarea
			bind:this={textareaEl}
			bind:value
			class="w-full resize-none bg-transparent px-2 py-1 text-[11px] text-[var(--text-primary)] outline-none font-mono"
			rows={Math.max(1, Math.ceil(value.length / 40))}
			onkeydown={onKeyDown}
		></textarea>
	</div>
{/if}
