<script lang="ts">
	import { uiStore } from '$lib/stores/ui.svelte';
	import FolderOpen from '@lucide/svelte/icons/folder-open';
</script>

{#if uiStore.isDragOver}
	<div class="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-background/85 backdrop-blur-sm animate-fade-in">
		<div class="flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-primary/60 bg-card/90 px-10 py-8">
			<FolderOpen class="h-8 w-8 text-primary" />
			<p class="text-sm font-medium text-foreground">Drop folder to import</p>
			<p class="text-[11px] text-muted-foreground">WAV files will be scanned recursively</p>
		</div>
	</div>
{/if}
