<script lang="ts">
	import type { CustomFieldDef } from '$lib/types';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { modelsStore } from '$lib/stores/models.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import { Switch } from '$lib/components/ui/switch';
	import { Separator } from '$lib/components/ui/separator';
	import { ScrollArea } from '$lib/components/ui/scroll-area';
	import { toast } from 'svelte-sonner';
	import { friendlyMessage } from '$lib/utils/errors';
	import * as api from '$lib/api/client';
	import { fileStore } from '$lib/stores/files.svelte';
	import * as Popover from '$lib/components/ui/popover';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';

	interface Props {
		open: boolean;
	}

	let { open = $bindable(false) }: Props = $props();

	const TAG_RE = /^[A-Z0-9_]+$/;
	const MAX_TAG_LENGTH = 32;
	const BUILTIN_TAGS = new Set([
		'CATEGORY', 'SUBCATEGORY', 'CATID', 'CATEGORYFULL', 'FXNAME', 'DESCRIPTION',
		'KEYWORDS', 'NOTES', 'DESIGNER', 'LIBRARY', 'USERCATEGORY', 'MICROPHONE',
		'MICPERSPECTIVE', 'RECMEDIUM', 'RELEASEDATE', 'RATING', 'EMBEDDER',
		'MANUFACTURER', 'RECTYPE', 'CREATORID', 'SOURCEID'
	]);
	const LLM_OPTIONS = [
		{ value: '__none__', label: 'None' },
		{ value: 'openai', label: 'OpenAI' },
		{ value: 'anthropic', label: 'Anthropic' }
	];

	// Local form state — reset from store when modal opens
	let creatorId = $state('');
	let sourceId = $state('');
	let libraryName = $state('');
	let libraryTemplate = $state('');
	let renameOnSave = $state(true);
	let llmProvider = $state('__none__');
	let llmApiKey = $state('');
	let customFields = $state<CustomFieldDef[]>([]);
	let showApiKey = $state(false);
	let saving = $state(false);
	let resetting = $state(false);
	let tagErrors = $state<Record<number, string>>({});

	$effect(() => {
		if (open && settingsStore.settings) {
			const s = settingsStore.settings;
			creatorId = s.creator_id;
			sourceId = s.source_id;
			libraryName = s.library_name;
			libraryTemplate = s.library_template;
			renameOnSave = s.rename_on_save_default;
			llmProvider = s.llm_provider ?? '__none__';
			llmApiKey = '';
			customFields = s.custom_fields.map((f) => ({ ...f }));
			showApiKey = false;
			tagErrors = {};
		}
	});

	function addCustomField() {
		customFields = [...customFields, { tag: '', label: '' }];
	}

	function removeCustomField(index: number) {
		customFields = customFields.filter((_, i) => i !== index);
		const newErrors = { ...tagErrors };
		delete newErrors[index];
		tagErrors = newErrors;
	}

	function validateTags(): boolean {
		const errors: Record<number, string> = {};
		for (let i = 0; i < customFields.length; i++) {
			const tag = customFields[i].tag;
			if (!tag) {
				errors[i] = 'Required';
			} else if (!TAG_RE.test(tag)) {
				errors[i] = 'A-Z, 0-9, _ only';
			} else if (tag.length > MAX_TAG_LENGTH) {
				errors[i] = `Max ${MAX_TAG_LENGTH} characters`;
			} else if (BUILTIN_TAGS.has(tag)) {
				errors[i] = 'Reserved tag name';
			}
		}
		tagErrors = errors;
		return Object.keys(errors).length === 0;
	}

	async function handleSave() {
		if (!validateTags()) return;
		saving = true;
		try {
			const updates: Record<string, unknown> = {
				creator_id: creatorId,
				source_id: sourceId,
				library_name: libraryName,
				library_template: libraryTemplate,
				rename_on_save_default: renameOnSave,
				llm_provider: llmProvider === '__none__' ? null : llmProvider,
				custom_fields: customFields
			};
			if (llmApiKey) {
				updates.llm_api_key = llmApiKey;
			}
			await settingsStore.saveSettings(updates);
			open = false;
			toast.success('Settings saved');
		} catch (e) {
			toast.error('Failed to save settings', {
				description: friendlyMessage(e)
			});
		} finally {
			saving = false;
		}
	}

	async function handleResetDb() {
		resetting = true;
		try {
			await api.resetDatabase();
			fileStore.setFiles([]);
			open = false;
			toast.success('Database reset successfully');
		} catch (e) {
			toast.error('Reset failed', { description: friendlyMessage(e) });
		} finally {
			resetting = false;
		}
	}

	let providerLabel = $derived(
		LLM_OPTIONS.find((o) => o.value === llmProvider)?.label ?? 'None'
	);
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="max-w-lg gap-0 p-0">
		<Dialog.Header class="px-5 pt-5 pb-3">
			<Dialog.Title class="text-base font-semibold">Settings</Dialog.Title>
		</Dialog.Header>

		<ScrollArea class="max-h-[60vh] px-5">
			<div class="space-y-5 pb-5">
				<!-- User Profile -->
				<section>
					<h3 class="mb-2.5 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
						User Profile
					</h3>
					<div class="grid grid-cols-[120px_1fr] items-center gap-x-3 gap-y-2">
						<label for="s-creator" class="text-sm text-muted-foreground">Creator ID</label>
						<Input id="s-creator" bind:value={creatorId} placeholder="e.g. JD" class="h-9 text-sm" />
						<label for="s-source" class="text-sm text-muted-foreground">Source ID</label>
						<Input id="s-source" bind:value={sourceId} placeholder="e.g. STUDIO01" class="h-9 text-sm" />
					</div>
				</section>

				<Separator />

				<!-- File Naming -->
				<section>
					<h3 class="mb-2.5 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
						File Naming
					</h3>
					<div class="grid grid-cols-[120px_1fr] items-center gap-x-3 gap-y-2">
						<label for="s-libname" class="text-sm text-muted-foreground">Library Name</label>
						<Input id="s-libname" bind:value={libraryName} placeholder="e.g. MyLibrary" class="h-9 text-sm" />
						<label for="s-template" class="text-sm text-muted-foreground">Template</label>
						<Input id="s-template" bind:value={libraryTemplate} placeholder={'{source_id} {library_name}'} class="h-9 text-sm" />
						<label for="s-rename" class="text-sm text-muted-foreground">Rename on Save</label>
						<div class="flex items-center">
							<Switch checked={renameOnSave} onCheckedChange={(v) => { renameOnSave = v; }} />
						</div>
					</div>
				</section>

				<Separator />

				<!-- AI Features -->
				<section>
					<h3 class="mb-2.5 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
						AI Features
					</h3>
					<div class="grid grid-cols-[120px_1fr] items-center gap-x-3 gap-y-2">
						<span class="text-sm text-muted-foreground">LLM Provider</span>
						<Select.Root type="single" value={llmProvider} onValueChange={(v) => { llmProvider = v; }}>
							<Select.Trigger class="h-9 w-full text-sm">
								{providerLabel}
							</Select.Trigger>
							<Select.Content>
								{#each LLM_OPTIONS as opt (opt.value)}
									<Select.Item value={opt.value}>{opt.label}</Select.Item>
								{/each}
							</Select.Content>
						</Select.Root>
						<label for="s-apikey" class="text-sm text-muted-foreground">API Key</label>
						<div class="relative">
							<Input
								id="s-apikey"
								type={showApiKey ? 'text' : 'password'}
								bind:value={llmApiKey}
								placeholder={settingsStore.settings?.llm_api_key ? '••••••••' : 'Not set'}
								class="h-9 pr-9 text-sm"
							/>
							<button
								type="button"
								class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
								onclick={() => { showApiKey = !showApiKey; }}
							>
								{#if showApiKey}
									<EyeOff class="h-3.5 w-3.5" />
								{:else}
									<Eye class="h-3.5 w-3.5" />
								{/if}
							</button>
						</div>
					</div>
				</section>

				<Separator />

				<!-- Custom Fields -->
				<section>
					<div class="mb-2.5 flex items-center justify-between">
						<h3 class="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
							Custom Fields
						</h3>
						<Button variant="ghost" size="sm" class="h-6 gap-1 px-2 text-xs" onclick={addCustomField}>
							<Plus class="h-3 w-3" />
							Add
						</Button>
					</div>
					{#if customFields.length > 0}
						<div class="mb-1 grid grid-cols-[100px_1fr_28px] gap-x-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
							<span>Tag</span>
							<span>Label</span>
							<span></span>
						</div>
						<ScrollArea class={customFields.length > 4 ? 'max-h-36' : ''}>
							<div class="space-y-1.5">
								{#each customFields as field, i (i)}
									<div class="grid grid-cols-[100px_1fr_28px] items-start gap-x-2">
										<div>
											<Input
												bind:value={field.tag}
												placeholder="TAG"
												class="h-7 font-mono text-xs uppercase {tagErrors[i] ? 'border-destructive' : ''}"
												oninput={(e) => {
													const target = e.currentTarget;
													field.tag = target.value.toUpperCase();
												}}
											/>
											{#if tagErrors[i]}
												<p class="mt-0.5 text-[10px] text-destructive">{tagErrors[i]}</p>
											{/if}
										</div>
										<Input bind:value={field.label} placeholder="Display label" class="h-7 text-xs" />
										<Button
											variant="ghost"
											size="sm"
											class="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
											onclick={() => removeCustomField(i)}
										>
											<Trash2 class="h-3 w-3" />
										</Button>
									</div>
								{/each}
							</div>
						</ScrollArea>
					{:else}
						<p class="text-xs text-muted-foreground/60">No custom fields defined.</p>
					{/if}
				</section>

				<Separator />

				<!-- Models -->
				<section>
					<div class="mb-2.5 flex items-center gap-1.5">
						<h3 class="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
							Models
						</h3>
						<Popover.Root>
							<Popover.Trigger>
								{#snippet child({ props })}
									<button
										{...props}
										class="flex h-4 w-4 items-center justify-center rounded-full border border-muted-foreground/40 text-[10px] font-semibold text-muted-foreground/60 hover:border-muted-foreground hover:text-muted-foreground"
									>?</button>
								{/snippet}
							</Popover.Trigger>
							<Popover.Content class="w-[540px] space-y-3 p-4 text-xs leading-relaxed">
								<div>
									<p class="mb-1 font-semibold text-foreground">Classifier</p>
									<p class="text-muted-foreground">Uses the pre-trained MS-CLAP 2023 model to compare an asset to various audio embeddings against text embeddings for all 753 UCS subcategories. It's zero-shot and works to understand semantic relationship between sounds and text descriptions. The subcategories have been modified to include two text prompts (a curated acoustic description + the raw UCS explanation), and the scores from the model output are blended. The filename is also tokenized and keyword-matched against UCS synonyms, then combined with the CLAP score to produce a final ranking. Output: top-N subcategory matches with confidence scores, which map directly to UCS category, subcategory, CatID, and a suggested filename.</p>
								</div>
								<div>
									<p class="mb-1 font-semibold text-foreground">Captioner</p>
									<p class="text-muted-foreground">Uses MS-CLAP's clapcap variant, which pairs CLAP audio embeddings with a GPT-2 decoder to generate natural language captions (e.g. "a wooden door creaking open slowly with a long metallic squeak"). That caption populates the Description field; key terms are extracted for FX Name. The model is lazy-loaded on first use (~2.1 GB).</p>
								</div>
								<p class="text-muted-foreground/80 italic">In short: CLAP tells you what category the sound belongs to. ClapCap tells you what the sound actually sounds like in plain English. Together they fill in the full metadata set — category, subcategory, filename, description, and keywords — from the audio alone.</p>
							</Popover.Content>
						</Popover.Root>
					</div>
					{#if modelsStore.status}
						<div class="flex items-center gap-4">
							<div class="flex items-center gap-1.5">
								<span class="inline-block h-2 w-2 rounded-full {modelsStore.status.clap_loaded ? 'bg-green-500' : 'bg-red-500'}"></span>
								<span class="text-xs text-muted-foreground">CLAP</span>
							</div>
							<div class="flex items-center gap-1.5">
								<span class="inline-block h-2 w-2 rounded-full {modelsStore.status.clapcap_loaded ? 'bg-green-500' : 'bg-muted-foreground/30'}"></span>
								<span class="text-xs text-muted-foreground">
									ClapCap{#if !modelsStore.status.clapcap_loaded}&nbsp;<span class="text-muted-foreground/50">(on demand)</span>{/if}
								</span>
							</div>
						</div>
					{/if}
				</section>

				<Separator />

				<!-- Danger Zone -->
				<section>
					<h3 class="mb-2.5 text-[11px] font-medium uppercase tracking-widest text-destructive">
						Danger Zone
					</h3>
					<div class="flex items-center justify-between">
						<div>
							<p class="text-sm text-muted-foreground">Reset Database</p>
							<p class="text-xs text-muted-foreground/60">Deletes all imported files and analysis cache. Files on disk are not affected.</p>
						</div>
						<Button variant="destructive" size="sm" onclick={handleResetDb} disabled={resetting}>
							{resetting ? 'Resetting...' : 'Reset'}
						</Button>
					</div>
				</section>
			</div>
		</ScrollArea>

		<Dialog.Footer class="border-t border-border px-5 py-3">
			<Button variant="outline" size="sm" onclick={() => { open = false; }}>Cancel</Button>
			<Button size="sm" onclick={handleSave} disabled={saving}>
				{saving ? 'Saving...' : 'Save'}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
