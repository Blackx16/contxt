<script lang="ts">
	import type { ContextCard } from '$lib/types';

	let { card }: { card: ContextCard } = $props();

	const SOURCE_ICON: Record<string, string> = {
		gmail: '✉️',
		calendar: '📅',
		notion: '📓'
	};

	const isPrivate = $derived(card.tier === 'private');
	const isEncrypted = $derived(!!card.encryption);
	const pct = $derived(Math.round(card.sensitivity_score * 100));

	function shortCipher(c: string): string {
		return c.length > 56 ? c.slice(0, 56) + '…' : c;
	}
</script>

<article class="card" class:private={isPrivate}>
	<header class="card-head">
		<div class="src">
			<span class="src-icon">{SOURCE_ICON[card.source] ?? '•'}</span>
			<span class="src-name">{card.source}</span>
		</div>
		<span class="tag {isPrivate ? 'tag-private' : 'tag-shared'}">
			{isPrivate ? '🔒 Private' : '↗ Shared'}
		</span>
	</header>

	<h3 class="card-title">{card.title}</h3>

	{#if isEncrypted}
		<div class="locked">
			<div class="locked-row">
				<span class="lock">🔒</span>
				<span>Encrypted on-device · cloud stores ciphertext only</span>
			</div>
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
					<span class="entity"><span class="etype">{e.type}</span>{e.value}</span>
				{/each}
			</div>
		{/if}
		{#if isPrivate}
			<div class="ondevice mono">● decrypted locally — never leaves this device</div>
		{/if}
	{/if}

	<footer class="card-foot">
		<div class="sens" title="Sensitivity score">
			<span class="sens-label">sensitivity</span>
			<span class="meter"><span class="fill" class:hot={pct >= 70} style="width:{pct}%"></span></span>
			<span class="sens-val mono">{pct}%</span>
		</div>
		<time class="ts mono">{new Date(card.created_at).toLocaleDateString()}</time>
	</footer>
</article>

<style>
	.card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 18px 18px 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
		transition: border-color 0.15s ease, transform 0.1s ease;
	}
	.card:hover {
		border-color: var(--border-strong);
		transform: translateY(-2px);
	}
	.card.private {
		border-left: 3px solid var(--private);
	}
	.card-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.src {
		display: flex;
		align-items: center;
		gap: 7px;
		color: var(--text-muted);
		font-size: 0.82rem;
	}
	.src-icon {
		font-size: 0.95rem;
	}
	.src-name {
		text-transform: capitalize;
	}
	.card-title {
		font-size: 1.02rem;
		line-height: 1.3;
	}
	.summary {
		margin: 0;
		color: var(--text);
		font-size: 0.92rem;
	}
	.body {
		margin: 0;
		color: var(--text-muted);
		font-size: 0.86rem;
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
		gap: 5px;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 7px;
		padding: 2px 8px;
		font-size: 0.78rem;
		color: var(--text);
	}
	.etype {
		color: var(--text-faint);
		font-size: 0.66rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.ondevice {
		color: var(--private);
		font-size: 0.75rem;
		opacity: 0.85;
	}
	.locked {
		background: var(--private-soft);
		border: 1px dashed var(--private-border);
		border-radius: var(--radius-sm);
		padding: 12px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.locked-row {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--private);
		font-size: 0.82rem;
		font-weight: 550;
	}
	.lock {
		font-size: 0.95rem;
	}
	.cipher {
		display: block;
		background: rgba(0, 0, 0, 0.35);
		border-radius: 6px;
		padding: 8px 10px;
		font-size: 0.74rem;
		color: var(--text-muted);
		word-break: break-all;
	}
	.crypto-meta {
		font-size: 0.68rem;
		color: var(--text-faint);
	}
	.card-foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: 4px;
		padding-top: 10px;
		border-top: 1px solid var(--border);
	}
	.sens {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.sens-label {
		font-size: 0.7rem;
		color: var(--text-faint);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.meter {
		width: 70px;
		height: 5px;
		border-radius: 3px;
		background: var(--surface-2);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--shared);
	}
	.fill.hot {
		background: var(--private);
	}
	.sens-val {
		font-size: 0.72rem;
		color: var(--text-muted);
	}
	.ts {
		font-size: 0.72rem;
		color: var(--text-faint);
	}
</style>
