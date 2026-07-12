<script lang="ts">
	import type { ContextCard } from '$lib/types';

	let {
		card,
		onDecrypt,
		onLock,
		encryptedBlob = null,
		isDecrypting = false
	}: {
		card: ContextCard;
		onDecrypt?: () => void;
		onLock?: () => void;
		encryptedBlob?: { ciphertext: string; iv: string } | null;
		isDecrypting?: boolean;
	} = $props();

	const isPrivate = $derived(card.tier === 'private');
	const isLocked = $derived(isPrivate && !card.summary && !card.body);
	const pct = $derived(Math.round(card.sensitivity_score * 100));

	// Set when a user privacy toggle (not the base gateway decision) forced this private.
	const override = $derived(
		(card.meta && typeof card.meta === 'object'
			? ((card.meta as Record<string, unknown>)._override ?? null)
			: null) as { categories: string[]; reason: string } | null
	);

	function shortCipher(c: string): string {
		return c.length > 64 ? c.slice(0, 64) + '…' : c;
	}
</script>

<article class="card" class:card-private={isPrivate} class:card-locked={isLocked}>
	<header class="card-head">
		<span class="src mono">{card.source}</span>
		<span class="tag {isPrivate ? 'tag-private' : 'tag-shared'}">
			{isPrivate ? 'Private' : 'Shared'}
		</span>
	</header>

	<h3 class="card-title">{card.title}</h3>

	{#if override}
		<p class="rule-note mono">
			<svg class="note-mark" viewBox="0 0 16 16" aria-hidden="true">
				<path d="M8 2 L14 13 H2 Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
				<path d="M8 6.5 V9.5 M8 11 v0.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
			</svg>
			{override.reason}
		</p>
	{/if}

	{#if isLocked && encryptedBlob}
		<!-- Locked PRIVATE card — show the ciphertext blob (the money-shot) -->
		<div class="locked">
			<div class="locked-label mono">
				<svg class="lock-icon" viewBox="0 0 16 16" aria-hidden="true">
					<rect x="3" y="7" width="10" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/>
					<path d="M5 7V5a3 3 0 1 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
				</svg>
				AES-256-GCM · cloud holds ciphertext only
			</div>
			<code class="cipher mono">{shortCipher(encryptedBlob.ciphertext)}</code>
			<div class="cipher-meta mono">iv: {encryptedBlob.iv.slice(0, 16)}…</div>
			{#if onDecrypt}
				<button class="btn-decrypt" onclick={onDecrypt} disabled={isDecrypting} aria-busy={isDecrypting}>
					{isDecrypting ? 'Decrypting…' : 'Decrypt locally'}
				</button>
			{/if}
		</div>
	{:else if isPrivate && !isLocked}
		<!-- Revealed PRIVATE card -->
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
		<div class="ondevice mono">
			Decrypted locally — plaintext never left this device
			{#if onLock}
				<button class="btn-lock" onclick={onLock} aria-label="Lock {card.title}">Lock</button>
			{/if}
		</div>
	{:else}
		<!-- SHARED card -->
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
	{/if}

	<footer class="card-foot">
		<div class="sens" title="Sensitivity score">
			<span class="sens-label mono">sensitivity</span>
			<span class="meter"><span class="fill" class:hot={isPrivate} style="width:{pct}%"></span></span>
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
	.card-private {
		border-color: color-mix(in srgb, var(--gold) 22%, var(--rule));
	}
	.card-locked {
		border-color: color-mix(in srgb, var(--gold) 38%, var(--rule));
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
	.rule-note {
		display: flex;
		align-items: center;
		gap: 7px;
		margin: -4px 0 0;
		color: var(--gold);
		font-size: 0.7rem;
		letter-spacing: 0.02em;
	}
	.note-mark {
		width: 13px;
		height: 13px;
		flex-shrink: 0;
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
		display: flex;
		align-items: center;
		gap: 10px;
		color: var(--gold-rich);
		font-size: 0.72rem;
		letter-spacing: 0.02em;
	}
	.btn-lock {
		border: none;
		background: transparent;
		color: var(--text-faint);
		font-family: var(--font-mono);
		font-size: 0.68rem;
		letter-spacing: 0.06em;
		cursor: pointer;
		padding: 2px 6px;
		border-radius: var(--r-xs);
		border: 1px solid var(--rule);
		transition: color 0.12s var(--ease), border-color 0.12s var(--ease);
	}
	.btn-lock:hover {
		color: var(--champagne);
		border-color: var(--rule-strong);
	}
	/* Locked panel — shows the raw ciphertext blob */
	.locked {
		background: var(--lacquer-deep);
		border: 1px solid var(--rule-strong);
		border-radius: var(--r-sm);
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 9px;
	}
	.locked-label {
		display: flex;
		align-items: center;
		gap: 7px;
		color: var(--gold);
		font-size: 0.72rem;
		letter-spacing: 0.02em;
	}
	.lock-icon {
		width: 13px;
		height: 13px;
		flex-shrink: 0;
	}
	.cipher {
		display: block;
		color: var(--text-muted);
		font-size: 0.74rem;
		letter-spacing: 0;
		word-break: break-all;
		opacity: 0.75;
	}
	.cipher-meta {
		font-size: 0.65rem;
		color: var(--text-faint);
	}
	.btn-decrypt {
		align-self: flex-start;
		border: 1px solid color-mix(in srgb, var(--gold) 45%, var(--rule));
		background: color-mix(in srgb, var(--gold) 8%, transparent);
		color: var(--gold);
		font-family: var(--font-mono);
		font-size: 0.72rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		padding: 6px 14px;
		border-radius: var(--r-sm);
		cursor: pointer;
		transition:
			background 0.15s var(--ease),
			border-color 0.15s var(--ease);
	}
	.btn-decrypt:hover:not(:disabled) {
		background: color-mix(in srgb, var(--gold) 15%, transparent);
		border-color: var(--gold);
	}
	.btn-decrypt:disabled {
		opacity: 0.6;
		cursor: wait;
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
