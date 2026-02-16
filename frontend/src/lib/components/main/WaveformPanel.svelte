<script lang="ts">
	import { fileStore } from '$lib/stores/files.svelte';
	import WaveSurfer from 'wavesurfer.js';
	import { getAudioUrl } from '$lib/api/client';
	import { onDestroy } from 'svelte';

	let isPlaying = $state(false);
	let currentTime = $state(0);
	let totalDuration = $state(0);
	let container: HTMLDivElement | undefined = $state();
	let ws: WaveSurfer | null = null;
	let loadedFileId = '';
	let generation = 0;

	let file = $derived(fileStore.activeFile);

	$effect(() => {
		if (!container || !file) {
			if (!file && ws) {
				ws.destroy();
				ws = null;
				loadedFileId = '';
				isPlaying = false;
				currentTime = 0;
				totalDuration = 0;
			}
			return;
		}
		if (file.id === loadedFileId) return;
		const gen = ++generation;
		loadedFileId = file.id;
		isPlaying = false;
		currentTime = 0;
		totalDuration = file.technical.duration_seconds;

		ws?.destroy();
		ws = null;
		getAudioUrl(file.id).then((url) => {
			if (gen !== generation || !container) return;
			ws = WaveSurfer.create({
				container,
				waveColor: 'oklch(0.50 0.06 300)',
				progressColor: 'oklch(0.62 0.08 300)',
				cursorColor: 'oklch(0.76 0.08 300)',
				height: 64,
				barWidth: 2,
				barGap: 1,
				barRadius: 1,
				dragToSeek: true,
				url
			});
			ws.on('ready', () => { totalDuration = ws!.getDuration(); });
			ws.on('timeupdate', (t: number) => { currentTime = t; });
			ws.on('finish', () => { isPlaying = false; });
		});
	});

	function handleTogglePlay() {
		togglePlay();
	}

	$effect(() => {
		globalThis.addEventListener('nomen:toggle-play', handleTogglePlay);
		return () => {
			globalThis.removeEventListener('nomen:toggle-play', handleTogglePlay);
		};
	});

	onDestroy(() => {
		ws?.destroy();
		ws = null;
	});

	function togglePlay() {
		if (!ws) return;
		ws.playPause();
		isPlaying = ws.isPlaying();
	}

	function stop() {
		if (!ws) return;
		ws.stop();
		isPlaying = false;
		currentTime = 0;
	}

	let hasFile = $derived(file !== null);

	function fmtTime(s: number): string {
		const m = Math.floor(s / 60);
		const sec = Math.floor(s % 60);
		const tenths = Math.round((s % 1) * 10);
		return `${m}:${String(sec).padStart(2, '0')}.${tenths}`;
	}
</script>

<div class="shrink-0 border-t border-[var(--border-default)]">
	<!-- Transport bar (28px) -->
	<div class="flex h-7 items-center gap-2 bg-[var(--bg-base)] px-3">
		<!-- Play/Pause -->
		<button
			class="p-1 {hasFile ? 'hover:bg-[var(--bg-raised)]' : 'opacity-30'}"
			onclick={togglePlay}
			disabled={!hasFile}
			aria-label={isPlaying ? 'Pause' : 'Play'}
		>
			{#if isPlaying}
				<!-- Pause (double bar) -->
				<svg class="h-3 w-3" viewBox="0 0 12 12" fill="var(--text-primary)">
					<rect x="2" y="1" width="3" height="10" rx="0.5" />
					<rect x="7" y="1" width="3" height="10" rx="0.5" />
				</svg>
			{:else}
				<!-- Play (triangle) -->
				<svg class="h-3 w-3" viewBox="0 0 12 12" fill="var(--text-primary)">
					<path d="M2 1.5v9l8-4.5z" />
				</svg>
			{/if}
		</button>

		<!-- Stop -->
		<button
			class="p-1 {hasFile ? 'hover:bg-[var(--bg-raised)]' : 'opacity-30'}"
			onclick={stop}
			disabled={!hasFile}
			aria-label="Stop"
		>
			<svg class="h-3 w-3" viewBox="0 0 12 12" fill="var(--text-primary)">
				<rect x="2" y="2" width="8" height="8" rx="0.5" />
			</svg>
		</button>

		<!-- Separator -->
		<div class="h-3.5 w-px bg-[var(--border-default)]"></div>

		<!-- Time -->
		<span class="font-mono text-[10px] text-[var(--text-primary)]">{fmtTime(currentTime)}</span>
		<span class="font-mono text-[10px] text-[var(--text-muted)]">{fmtTime(totalDuration)}</span>

		<!-- Filename(s) -->
		<div class="ml-auto flex min-w-0 items-center gap-1.5 font-mono text-[10px]">
			{#if file}
				<span class="truncate" style="color: var(--tech-gold)">{file.filename}</span>
				{#if file.suggested_filename && file.suggested_filename !== file.filename}
					<svg class="h-3 w-6 shrink-0" viewBox="0 0 24 12" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
						<path d="M2 6h18m0 0l-4-4m4 4l-4 4" />
					</svg>
					<span class="truncate" style="color: #00FF00">{file.suggested_filename}</span>
				{/if}
			{:else}
				<span style="color: var(--text-muted)">Select a file to preview waveform</span>
			{/if}
		</div>
	</div>

	<!-- Waveform canvas (64px) -->
	<div class="h-16 bg-[var(--bg-base)]">
		{#if file}
			<div bind:this={container} class="h-full cursor-crosshair"></div>
		{:else}
			<div class="flex h-full items-center justify-center">
				<span class="text-[11px] text-[var(--text-muted)]">Select a file to preview waveform</span>
			</div>
		{/if}
	</div>
</div>
