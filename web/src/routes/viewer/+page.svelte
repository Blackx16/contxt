<script lang="ts">
	import CardItem from '$lib/components/CardItem.svelte';
	import { loadCards, connectedSources } from '$lib/state.svelte';
	import type { Tier } from '$lib/types';

	type Filter = 'all' | Tier;
	let filter = $state<Filter>('all');

	const cards = $derived(loadCards());
	const connected = $derived(connectedSources());
	const privateCount = $derived(cards.filter((c) => c.tier === 'private').length);
	const sharedCount = $derived(cards.filter((c) => c.tier === 'shared').length);
	const shown = $derived(filter === 'all' ? cards : cards.filter((c) => c.tier === filter));

	const filters: { id: Filter; label: string }[] = [
		{ id: 'all', label: 'All' },
		{ id: 'shared', label: '↗ Shared' },
		{ id: 'private', label: '🔒 Private' }
	];
</script>

<section class="head">
	<div>
		<h1>Your context</h1>
		<p class="sub">
			{cards.length} card{cards.length === 1 ? '' : 's'} from {connected.length} source{connected.length ===
			1
				? ''
				: 's'} ·
			<span class="c-shared">{sharedCount} shared</span> ·
			<span class="c-private">{privateCount} private</span>
		</p>
	</div>
	{#if cards.length}
		<div class="filters">
			{#each filters as f (f.id)}
				<button class="chip" class:active={filter === f.id} onclick={() => (filter = f.id)}>
					{f.label}
				</button>
			{/each}
		</div>
	{/if}
</section>

{#if cards.length === 0}
	<div class="empty">
		<div class="empty-icon">◆</div>
		<h2>No context yet</h2>
		<p>Connect a source and Contxt will ingest it, then show your distilled context cards here.</p>
		<a class="btn btn-primary" href="/onboarding">Connect a source →</a>
	</div>
{:else}
	<div class="grid">
		{#each shown as card (card.id)}
			<CardItem {card} />
		{/each}
	</div>
	{#if shown.length === 0}
		<p class="none">No {filter} cards.</p>
	{/if}
{/if}

<style>
	.head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 24px;
		flex-wrap: wrap;
	}
	h1 {
		font-size: 2rem;
	}
	.sub {
		color: var(--text-muted);
		margin: 6px 0 0;
		font-size: 0.92rem;
	}
	.c-shared {
		color: var(--shared);
	}
	.c-private {
		color: var(--private);
	}
	.filters {
		display: flex;
		gap: 6px;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 4px;
	}
	.chip {
		border: none;
		background: transparent;
		color: var(--text-muted);
		font: inherit;
		font-size: 0.86rem;
		font-weight: 550;
		padding: 6px 14px;
		border-radius: 999px;
		cursor: pointer;
	}
	.chip:hover {
		color: var(--text);
	}
	.chip.active {
		background: var(--surface-2);
		color: var(--text);
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 16px;
	}
	.none {
		color: var(--text-faint);
		text-align: center;
		padding: 40px;
	}
	.empty {
		text-align: center;
		padding: 70px 20px;
		background: var(--surface);
		border: 1px dashed var(--border-strong);
		border-radius: var(--radius);
	}
	.empty-icon {
		font-size: 2rem;
		color: var(--brand);
		margin-bottom: 8px;
	}
	.empty h2 {
		font-size: 1.3rem;
		margin-bottom: 8px;
	}
	.empty p {
		color: var(--text-muted);
		max-width: 420px;
		margin: 0 auto 22px;
	}
</style>
