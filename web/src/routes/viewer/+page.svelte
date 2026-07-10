<script lang="ts">
	import { onMount } from 'svelte';
	import CardItem from '$lib/components/CardItem.svelte';
	import {
		loadCards,
		connectedSources,
		initCrypto,
		decryptCard,
		lockCard,
		getEncryptedBlob,
		cryptoReady,
		getKeyForDisplay
	} from '$lib/state.svelte';
	import type { Tier } from '$lib/types';

	type Filter = 'all' | Tier;
	let filter = $state<Filter>('all');
	let showKey = $state(false);
	let decryptingId = $state<string | null>(null);

	const cards = $derived(loadCards());
	const connected = $derived(connectedSources());
	const privateCount = $derived(cards.filter((c) => c.tier === 'private').length);
	const sharedCount = $derived(cards.filter((c) => c.tier === 'shared').length);
	const shown = $derived(filter === 'all' ? cards : cards.filter((c) => c.tier === filter));

	const filters: { id: Filter; label: string }[] = [
		{ id: 'all', label: 'All' },
		{ id: 'shared', label: 'Shared' },
		{ id: 'private', label: 'Private' }
	];

	async function handleDecrypt(cardId: string) {
		decryptingId = cardId;
		try {
			await decryptCard(cardId);
		} finally {
			decryptingId = null;
		}
	}

	onMount(() => {
		initCrypto();
	});
</script>

<section class="head">
	<div>
		<h1>Your context</h1>
		<p class="sub mono">
			{cards.length} card{cards.length === 1 ? '' : 's'} · {connected.length} source{connected.length ===
			1
				? ''
				: 's'} ·
			<span class="c-shared">{sharedCount} shared</span> ·
			<span class="c-private">{privateCount} private</span>
		</p>
	</div>
	<div class="head-right">
		{#if cryptoReady.value}
			<button class="chip chip-key" onclick={() => (showKey = !showKey)} title="Key management">
				🔑 {showKey ? 'Hide key' : 'Key sync'}
			</button>
		{/if}
		{#if cards.length}
			<div class="filters">
				{#each filters as f (f.id)}
					<button class="chip" class:active={filter === f.id} onclick={() => (filter = f.id)}>
						{f.label}
					</button>
				{/each}
			</div>
		{/if}
	</div>
</section>

{#if showKey && cryptoReady.value}
	<div class="key-panel">
		<p class="key-label mono">PRIVATE KEY — copy to server .env or scan QR on another device</p>
		<code class="key-val mono">{getKeyForDisplay()}</code>
		<p class="key-hint mono">
			Set <strong>CONTXT_PRIVATE_KEY=</strong>&lt;above&gt; in .env, then restart the MCP server.
		</p>
	</div>
{/if}

{#if cards.length === 0}
	<div class="empty">
		<svg class="empty-icon" viewBox="0 0 32 32" aria-hidden="true">
			<path d="M4 4 H28 V28 H4 Z M28 4 L4 28" fill="none" stroke="currentColor" stroke-width="2.2" />
		</svg>
		<h2>No context yet</h2>
		<p>Connect a source and Contxt will ingest it, then show your distilled context cards here.</p>
		<a class="btn btn-primary" href="/onboarding">Connect a source →</a>
	</div>
{:else}
	<div class="grid">
		{#each shown as card (card.id)}
			<CardItem
				{card}
				encryptedBlob={cryptoReady.value ? getEncryptedBlob(card.id) : null}
				onDecrypt={card.tier === 'private'
					? () => handleDecrypt(card.id)
					: undefined}
				onLock={card.tier === 'private' ? () => lockCard(card.id) : undefined}
			/>
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
		margin-bottom: 28px;
		flex-wrap: wrap;
	}
	.sub {
		color: var(--text-muted);
		margin: 10px 0 0;
		font-size: 0.76rem;
		letter-spacing: 0.06em;
	}
	.c-shared {
		color: var(--patina-text);
	}
	.c-private {
		color: var(--gold);
	}
	.head-right {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.filters {
		display: flex;
		gap: 2px;
		background: var(--raised);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		padding: 3px;
	}
	.chip {
		border: none;
		background: transparent;
		color: var(--text-muted);
		font-family: var(--font-mono);
		font-size: 0.72rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		padding: 7px 15px;
		border-radius: var(--r-xs);
		cursor: pointer;
		transition:
			background 0.15s var(--ease),
			color 0.15s var(--ease);
	}
	.chip:hover {
		color: var(--champagne);
	}
	.chip.active {
		background: var(--graphite-2);
		color: var(--gold);
	}
	.chip-key {
		border: 1px solid var(--rule);
		font-size: 0.7rem;
		padding: 6px 12px;
	}
	.key-panel {
		background: var(--lacquer-deep);
		border: 1px solid color-mix(in srgb, var(--gold) 30%, var(--rule));
		border-radius: var(--r-lg);
		padding: 20px;
		margin-bottom: 24px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.key-label {
		color: var(--gold);
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		margin: 0;
	}
	.key-val {
		display: block;
		word-break: break-all;
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		padding: 10px 12px;
		font-size: 0.78rem;
		color: var(--champagne);
		user-select: all;
	}
	.key-hint {
		margin: 0;
		color: var(--text-faint);
		font-size: 0.68rem;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
		gap: 14px;
		align-items: start;
	}
	.none {
		color: var(--text-faint);
		text-align: center;
		padding: 48px;
	}
	.empty {
		text-align: center;
		padding: 80px 20px;
		background: var(--raised);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
	}
	.empty-icon {
		width: 34px;
		height: 34px;
		margin: 0 auto 14px;
		color: var(--gold);
	}
	.empty h2 {
		font-size: 1.6rem;
		margin-bottom: 10px;
	}
	.empty p {
		color: var(--text-muted);
		max-width: 46ch;
		margin: 0 auto 24px;
		line-height: 1.7;
	}
</style>
