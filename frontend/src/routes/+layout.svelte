<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { Toaster } from '$lib/components/ui/sonner';
	import { TooltipProvider } from '$lib/components/ui/tooltip';
	import { waitForBackend } from '$lib/health';
	import { modelsStore } from '$lib/stores/models.svelte';
	import { ucsStore } from '$lib/stores/ucs.svelte';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { onMount } from 'svelte';

	let { children } = $props();
	let status: 'loading' | 'ready' | 'error' = $state('loading');
	let errorMsg = $state('');

	onMount(async () => {
		try {
			await waitForBackend();
			await Promise.all([ucsStore.loadCategories(), settingsStore.loadSettings()]);
			status = 'ready';
			modelsStore.poll();
		} catch (e) {
			status = 'error';
			errorMsg = e instanceof Error ? e.message : 'Unknown error';
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{#if status === 'loading'}
	<div class="flex h-screen flex-col items-center justify-center gap-4 animate-fade-in">
		<div
			class="h-5 w-5 rounded-full border-2 border-muted-foreground/20 border-t-primary"
			style="animation: nomen-spin 0.7s linear infinite;"
		></div>
		<p class="text-xs uppercase tracking-widest text-muted-foreground">Starting backend</p>
	</div>
{:else if status === 'error'}
	<div class="flex h-screen flex-col items-center justify-center gap-3 animate-fade-in">
		<div class="flex h-9 w-9 items-center justify-center rounded-full bg-destructive/15">
			<span class="text-sm font-semibold text-destructive">!</span>
		</div>
		<p class="text-sm font-medium text-foreground">Failed to start backend</p>
		<p class="max-w-xs text-center text-xs text-muted-foreground">{errorMsg}</p>
	</div>
{:else}
	<TooltipProvider>
		<div class="animate-fade-in">
			{@render children()}
		</div>
	</TooltipProvider>
{/if}

<Toaster />
