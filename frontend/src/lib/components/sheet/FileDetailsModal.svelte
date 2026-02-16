<script lang="ts">
	import type { FileRecord } from '$lib/types';
	import { formatDuration, formatFileSize, formatSampleRate } from '$lib/utils/format';
	import * as Dialog from '$lib/components/ui/dialog';

	interface Props {
		file: FileRecord;
		open: boolean;
		onClose: () => void;
	}

	let { file, open, onClose }: Props = $props();
</script>

<Dialog.Root bind:open onOpenChange={(v) => { if (!v) onClose(); }}>
	<Dialog.Content class="max-w-2xl bg-[var(--bg-raised)] border-[var(--border-default)] text-[var(--text-primary)]">
		<Dialog.Header>
			<Dialog.Title class="text-[13px] font-semibold font-mono text-[var(--tech-gold)]">{file.filename}</Dialog.Title>
			{#if file.suggested_filename && file.suggested_filename !== file.filename}
				<p class="font-mono text-[12px]" style="color: #00FF00">{file.suggested_filename}</p>
			{/if}
			<Dialog.Description class="text-[11px] text-[var(--text-muted)]">
				File details — read-only metadata
			</Dialog.Description>
		</Dialog.Header>

		<div class="max-h-[60vh] space-y-4 overflow-y-auto text-[11px]">
			<!-- Technical -->
			<section>
				<h3 class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Technical</h3>
				<div class="grid grid-cols-2 gap-x-4 gap-y-1">
					<span class="text-[var(--text-muted)]">Sample Rate</span>
					<span class="font-mono">{formatSampleRate(file.technical.sample_rate)}</span>
					<span class="text-[var(--text-muted)]">Bit Depth</span>
					<span class="font-mono">{file.technical.bit_depth}-bit</span>
					<span class="text-[var(--text-muted)]">Channels</span>
					<span class="font-mono">{file.technical.channels}</span>
					<span class="text-[var(--text-muted)]">Duration</span>
					<span class="font-mono">{formatDuration(file.technical.duration_seconds)}</span>
					<span class="text-[var(--text-muted)]">Format</span>
					<span class="font-mono">{file.technical.audio_format}</span>
					<span class="text-[var(--text-muted)]">File Size</span>
					<span class="font-mono">{formatFileSize(file.technical.file_size_bytes)}</span>
					<span class="text-[var(--text-muted)]">Frames</span>
					<span class="font-mono">{file.technical.frame_count.toLocaleString()}</span>
				</div>
			</section>

			<!-- BEXT -->
			{#if file.bext}
				<section>
					<h3 class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">BEXT</h3>
					<div class="grid grid-cols-2 gap-x-4 gap-y-1">
						{#if file.bext.description}
							<span class="text-[var(--text-muted)]">Description</span>
							<span>{file.bext.description}</span>
						{/if}
						{#if file.bext.originator}
							<span class="text-[var(--text-muted)]">Originator</span>
							<span>{file.bext.originator}</span>
						{/if}
						{#if file.bext.originator_date}
							<span class="text-[var(--text-muted)]">Date</span>
							<span class="font-mono">{file.bext.originator_date}</span>
						{/if}
						{#if file.bext.originator_time}
							<span class="text-[var(--text-muted)]">Time</span>
							<span class="font-mono">{file.bext.originator_time}</span>
						{/if}
						{#if file.bext.coding_history}
							<span class="text-[var(--text-muted)]">Coding History</span>
							<span class="font-mono">{file.bext.coding_history}</span>
						{/if}
					</div>
				</section>
			{/if}

			<!-- RIFF INFO -->
			{#if file.info}
				<section>
					<h3 class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">RIFF INFO</h3>
					<div class="grid grid-cols-2 gap-x-4 gap-y-1">
						{#each Object.entries(file.info) as [key, val] (key)}
							{#if val}
								<span class="text-[var(--text-muted)]">{key}</span>
								<span>{val}</span>
							{/if}
						{/each}
					</div>
				</section>
			{/if}

			<!-- Custom Fields -->
			{#if file.custom_fields && Object.keys(file.custom_fields).length > 0}
				<section>
					<h3 class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Custom Fields</h3>
					<div class="grid grid-cols-2 gap-x-4 gap-y-1">
						{#each Object.entries(file.custom_fields) as [key, val] (key)}
							<span class="font-mono text-[var(--text-muted)]">{key}</span>
							<span>{val}</span>
						{/each}
					</div>
				</section>
			{/if}
		</div>
	</Dialog.Content>
</Dialog.Root>
