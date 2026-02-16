<script lang="ts">
	import type { FileRecord } from '$lib/types';
	import { fileStore } from '$lib/stores/files.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { ScrollArea } from '$lib/components/ui/scroll-area';
	import * as Select from '$lib/components/ui/select';
	import { toast } from 'svelte-sonner';
	import * as api from '$lib/api/client';
	import { friendlyMessage } from '$lib/utils/errors';

	interface Props {
		open: boolean;
	}

	let { open = $bindable(false) }: Props = $props();

	const FIELDS = [
		{ value: 'category', label: 'Category' },
		{ value: 'subcategory', label: 'SubCategory' },
		{ value: 'fx_name', label: 'FX Name' },
		{ value: 'description', label: 'Description' },
		{ value: 'keywords', label: 'Keywords' },
		{ value: 'notes', label: 'Notes' },
		{ value: 'designer', label: 'Designer' },
		{ value: 'library', label: 'Library' },
		{ value: 'project', label: 'Project' },
		{ value: 'user_category', label: 'User Category' }
	];

	let field = $state('description');
	let findText = $state('');
	let replaceText = $state('');
	let useRegex = $state(false);
	let applying = $state(false);
	// regexError is derived from searchResult (no $state needed)

	$effect(() => {
		if (open) {
			findText = '';
			replaceText = '';
			// regexError is derived — clears automatically when findText changes
		}
	});

	let fieldLabel = $derived(FIELDS.find((f) => f.value === field)?.label ?? field);

	interface MatchResult {
		file: FileRecord;
		original: string;
		replaced: string;
	}

	let searchResult = $derived.by((): { matches: MatchResult[]; error: string } => {
		if (!findText.trim()) return { matches: [], error: '' };

		let pattern: RegExp;
		try {
			pattern = useRegex ? new RegExp(findText, 'g') : new RegExp(escapeRegex(findText), 'gi');
		} catch (e) {
			return { matches: [], error: e instanceof Error ? e.message : 'Invalid regex' };
		}

		const results: MatchResult[] = [];
		for (const file of fileStore.files.values()) {
			const val = file[field as keyof typeof file];
			if (typeof val !== 'string' || !val) continue;
			if (!pattern.test(val)) continue;
			pattern.lastIndex = 0;
			const replaced = val.replace(pattern, replaceText);
			pattern.lastIndex = 0;
			results.push({ file, original: val, replaced });
			if (results.length >= 100) break;
		}
		return { matches: results, error: '' };
	});

	let matches = $derived(searchResult.matches);
	let regexErrorDerived = $derived(searchResult.error);

	function escapeRegex(s: string): string {
		return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	}

	async function handleApply() {
		if (matches.length === 0) return;
		applying = true;
		try {
			let count = 0;
			for (const match of matches) {
				const updates: Record<string, string> = { [field]: match.replaced };
				const updated = await api.updateMetadata(match.file.id, updates);
				fileStore.updateFile(updated);
				count++;
			}
			open = false;
			toast.success(`Replaced in ${count} files`);
		} catch (e) {
			toast.error('Replace failed', { description: friendlyMessage(e) });
		} finally {
			applying = false;
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="max-w-lg">
		<Dialog.Header>
			<Dialog.Title>Find & Replace</Dialog.Title>
			<Dialog.Description>
				Search across all {fileStore.files.size} loaded files (ignores sidebar filters)
			</Dialog.Description>
		</Dialog.Header>

		<div class="space-y-3 py-2">
			<div class="grid grid-cols-[80px_1fr] items-center gap-2">
				<span class="text-xs text-muted-foreground">Field</span>
				<Select.Root type="single" value={field} onValueChange={(v) => { field = v; }}>
					<Select.Trigger class="h-8 w-full text-sm">{fieldLabel}</Select.Trigger>
					<Select.Content>
						{#each FIELDS as f (f.value)}
							<Select.Item value={f.value}>{f.label}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>

			<div class="grid grid-cols-[80px_1fr] items-center gap-2">
				<span class="text-xs text-muted-foreground">Find</span>
				<Input bind:value={findText} placeholder="Search text..." class="h-8 text-sm" />
			</div>

			<div class="grid grid-cols-[80px_1fr] items-center gap-2">
				<span class="text-xs text-muted-foreground">Replace</span>
				<Input bind:value={replaceText} placeholder="Replacement text..." class="h-8 text-sm" />
			</div>

			<div class="flex items-center gap-2 pl-[88px]">
				<label class="flex items-center gap-1.5 text-xs text-muted-foreground">
					<Checkbox checked={useRegex} onCheckedChange={(v) => { useRegex = !!v; }} />
					Regular expression
				</label>
			</div>

			{#if regexErrorDerived}
				<p class="pl-[88px] text-xs text-destructive">{regexErrorDerived}</p>
			{/if}

			{#if matches.length > 0}
				<div class="pl-[88px] text-xs text-muted-foreground">
					{matches.length}{matches.length >= 100 ? '+' : ''} matches
				</div>
				<ScrollArea class="max-h-40 rounded border border-border">
					<div class="divide-y divide-border">
						{#each matches.slice(0, 50) as match (match.file.id)}
							<div class="px-3 py-1.5">
								<div class="truncate text-xs font-medium">{match.file.filename}</div>
								<div class="mt-0.5 truncate text-xs text-muted-foreground line-through">{match.original}</div>
								<div class="truncate text-xs text-success">{match.replaced}</div>
							</div>
						{/each}
					</div>
				</ScrollArea>
			{:else if findText.trim() && !regexErrorDerived}
				<p class="pl-[88px] text-xs text-muted-foreground">No matches found</p>
			{/if}
		</div>

		<Dialog.Footer>
			<Button variant="outline" size="sm" onclick={() => { open = false; }}>Cancel</Button>
			<Button
				size="sm"
				onclick={handleApply}
				disabled={matches.length === 0 || applying}
			>
				{applying ? 'Replacing...' : `Replace ${matches.length} matches`}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
