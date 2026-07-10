<script lang="ts">
	import type { ContextCard } from '$lib/types';

	let { card }: { card: ContextCard } = $props();

	const isPrivate = $derived(card.tier === 'private');
	const isEncrypted = $derived(!!card.encryption);
	const pct = $derived(Math.round(card.sensitivity_score * 100));

	function shortCipher(c: string): string {
		return c.length > 52 ? c.slice(0, 52) + '…' : c;
	}
</script>

<article class="card">
	<header class="card-head">
		<span class="src mono">{card.source}</span>
		<span class="tag {isPrivate ? 'tag-private' : 'tag-shared'}">
			{isPrivate ? 'Private' : 'Shared'}
		</span>
	</header>

	<h3 class="card-title">{card.title}</h3>

	{#if isEncrypted}
		<div class="locked">
			<div class="locked-row mono">Encrypted on-device · cloud stores ciphertext only</div>
			<code class="cipher mono">{shortCipher(card.encryption!.ciphertext)}</code>
			<div class="crypto-meta mono">
				{card.encryption!.alg} · key {card.encryption!.key_ref}
			</div>
		</div>
	{:else}
		{#if card.summary}
			<p class="summary">{card.summary}</p>
		{/if}
		{#if card.body}
			<p class="body">{card.body}</p>
		{/if}
		{#if card.entities.length}
			<div class="entities">
				{#each card.entities as e (e.type + e.value)}
					<span class="entity"><span class="etype mono">{e.type}</span>{e.value}</span>
				{/each}
			</div>
		{/if}
		{#if isPrivate}
			<div class="ondevice mono">Decrypted locally — never leaves this device</div>
		{/if}
	{/if}

	<footer class="card-foot">
		<div class="sens" title="Sensitivity score">
			<span class="sens-label mono">sensitivity</span>
			<span class="meter"
				><span class="fill" class:hot={isPrivate} style="width:{pct}%"></span></span
			>
			<span class="sens-val mono">{pct}%</span>
		</div>
		<time class="ts mono">{new Date(card.created_at).toLocaleDateString()}</time>
	</footer>
</article>

<style>
	.card {
		background: var(--raised);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
		padding: 22px;
		display: flex;
		flex-direction: column;
		gap: 12px;
		transition:
			border-color 0.15s var(--ease),
			transform 0.12s var(--ease);
	}
	.card:hover {
		border-color: var(--rule-strong);
		transform: translateY(-2px);
	}
	.card-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.src {
		color: var(--text-faint);
		font-size: 0.68rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}
	.card-title {
		font-size: 1.08rem;
		line-height: 1.3;
	}
	.summary {
		margin: 0;
		color: var(--text);
		font-size: 0.94rem;
		line-height: 1.6;
	}
	.body {
		margin: 0;
		color: var(--text-muted);
		font-size: 0.86rem;
		line-height: 1.6;
	}
	.entities {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 2px;
	}
	.entity {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		padding: 3px 8px;
		font-size: 0.78rem;
		color: var(--text);
	}
	.etype {
		color: var(--text-faint);
		font-size: 0.6rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.ondevice {
		color: var(--gold-rich);
		font-size: 0.72rem;
		letter-spacing: 0.02em;
	}
	/* Inset technical panel — a distinct material surface, not a nested card */
	.locked {
		background: var(--lacquer-deep);
		border: 1px solid var(--rule-strong);
		border-radius: var(--r-sm);
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 9px;
	}
	.locked-row {
		color: var(--gold);
		font-size: 0.72rem;
		letter-spacing: 0.02em;
	}
	.cipher {
		display: block;
		color: var(--text-muted);
		font-size: 0.74rem;
		letter-spacing: 0;
		word-break: break-all;
		opacity: 0.85;
	}
	.crypto-meta {
		font-size: 0.66rem;
		color: var(--text-faint);
		letter-spacing: 0;
	}
	.card-foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: 2px;
		padding-top: 12px;
		border-top: 1px solid var(--rule);
	}
	.sens {
		display: flex;
		align-items: center;
		gap: 9px;
	}
	.sens-label {
		font-size: 0.62rem;
		color: var(--text-faint);
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}
	.meter {
		width: 64px;
		height: 4px;
		border-radius: var(--r-pill);
		background: var(--graphite-2);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--patina);
	}
	.fill.hot {
		background: var(--gold);
	}
	.sens-val {
		font-size: 0.7rem;
		color: var(--text-muted);
		letter-spacing: 0;
	}
	.ts {
		font-size: 0.7rem;
		color: var(--text-faint);
		letter-spacing: 0;
	}
</style>
