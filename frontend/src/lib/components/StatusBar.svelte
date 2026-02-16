<script lang="ts">
	import { fileStore } from '$lib/stores/files.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import { modelsStore } from '$lib/stores/models.svelte';
	import { getPhrase, type LoadingContext } from '$lib/utils/loading-phrases';

	const ROTATE_MS = 4000;

	let phrase = $state('');

	let activeContext = $derived.by((): LoadingContext | null => {
		if (modelsStore.isLoading) return 'models';
		if (uiStore.isGenerating) return 'generating';
		if (uiStore.isImporting) return 'importing';
		return null;
	});

	$effect(() => {
		if (activeContext) {
			phrase = getPhrase(activeContext);
			const ctx = activeContext;
			const id = setInterval(() => { phrase = getPhrase(ctx); }, ROTATE_MS);
			return () => clearInterval(id);
		} else {
			phrase = '';
		}
	});
</script>

<footer class="flex h-6 items-center border-t border-[var(--border-default)] bg-[var(--bg-surface)] px-3 font-mono text-[10px] text-[var(--text-muted)]">
	<span>
		{fileStore.fileStats.total} files
		{#if fileStore.selectedFileIds.size > 0}
			<span class="opacity-40"> · </span>{fileStore.selectedFileIds.size} selected
		{/if}
		{#if fileStore.aiGeneratedCount > 0}
			<span class="opacity-40"> · </span>{fileStore.aiGeneratedCount} auto-generated
		{/if}
	</span>
	<span class="ml-auto truncate text-[var(--tech-gold)]">
		{phrase}
	</span>
</footer>
