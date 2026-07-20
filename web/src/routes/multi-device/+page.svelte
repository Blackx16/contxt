<script lang="ts">
	import { onMount } from 'svelte';
	import {
		md,
		initDemo,
		sealOnA,
		pushToRelay,
		pullOnB,
		transferKey,
		decryptOnB,
		reset
	} from '$lib/multidevice.svelte';
	import { demo } from '$lib/demo.svelte';
	import { ext, detectExtension, loadExtensionContext } from '$lib/extension.svelte';

	let pasteVal = $state('');
	let showPaste = $state(false);

	const sameKey = $derived(!!md.fpA && !!md.fpB && md.fpA === md.fpB);

	function shorten(s: string, n = 40): string {
		return s.length > n ? s.slice(0, n) + '…' : s;
	}

	async function importPasted() {
		await transferKey(pasteVal.trim());
		if (!md.error) {
			pasteVal = '';
			showPaste = false;
		}
	}

	onMount(() => {
		initDemo();
	});

	// Live mode: reflect the extension's real on-device encryption state.
	let probed = false;
	$effect(() => {
		if (!demo.on && !probed) {
			probed = true;
			detectExtension().then((p) => { if(p) loadExtensionContext(); });
		}
	});
</script>

{#if demo.on}
<section class="head">
	<div class="head-copy">
		<span class="eyebrow">Multi-device · QR key transfer · blind relay</span>
		<h1>Carry your crown jewels to a second device.</h1>
		<p class="lede">
			The same encrypted private card is sealed on Device A, relayed as ciphertext through the
			cloud, and decrypted on Device B — but only after the key crosses over by QR. The relay never
			holds the key. Ciphertext alone is useless.
		</p>
	</div>
	<button class="chip reset" onclick={reset} title="Restart the demo">↻ Reset</button>
</section>

{#if md.error}
	<p class="banner mono">{md.error}</p>
{/if}

<ol class="steps mono">
	<li class:done={md.sealed}>1 · Seal on A</li>
	<li class:done={md.pushed}>2 · Relay ciphertext</li>
	<li class:done={md.pulled}>3 · Pull on B</li>
	<li class:done={md.transferred}>4 · Transfer key (QR)</li>
	<li class:done={md.decrypted}>5 · Decrypt on B</li>
</ol>

<div class="stage">
	<!-- ── DEVICE A ─────────────────────────────────────────────── -->
	<article class="device">
		<header class="device-head">
			<div>
				<span class="device-name">Device A</span>
				<span class="device-role mono">holds your key</span>
			</div>
			{#if md.fpA}<span class="fp mono" title="key fingerprint">🔑 {md.fpA}</span>{/if}
		</header>

		<div class="demo-card">
			<div class="dc-head">
				<span class="src mono">{md.cardSource}</span>
				<span class="tag tag-private">Private</span>
			</div>
			<h3 class="dc-title">{md.cardTitle || '—'}</h3>

			{#if !md.sealed}
				<p class="dc-note mono">Plaintext on this device. Nothing has left yet.</p>
				<button class="btn btn-primary sm" onclick={sealOnA} disabled={!md.ready}>
					Seal · AES-256-GCM
				</button>
			{:else}
				<div class="inset">
					<div class="inset-label mono">
						<svg class="lk" viewBox="0 0 16 16" aria-hidden="true">
							<rect x="3" y="7" width="10" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5" />
							<path d="M5 7V5a3 3 0 1 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
						</svg>
						ciphertext
					</div>
					<code class="cipher mono">{md.cipherPreview}…</code>
				</div>
				{#if !md.pushed}
					<button class="btn btn-primary sm" onclick={pushToRelay}>Push to relay →</button>
				{:else}
					<p class="ok mono">✓ pushed to relay as ciphertext</p>
				{/if}
			{/if}
		</div>

		<div class="qr-block">
			<div class="qr-chip">
				{#if md.qr}
					<!-- eslint-disable-next-line svelte/no-at-html-tags -->
					{@html md.qr}
				{/if}
			</div>
			<div class="qr-copy">
				<span class="qr-label mono">Your key — scan on Device B</span>
				<span class="qr-note mono">This QR is shown device-to-device. It never touches the cloud.</span>
			</div>
		</div>
	</article>

	<!-- ── BLIND RELAY ──────────────────────────────────────────── -->
	<article class="relay">
		<header class="relay-head">
			<span class="relay-name mono">Blind relay · cloud</span>
			<span class="relay-badge mono" class:live={md.pushed}>ciphertext only</span>
		</header>

		<div class="relay-body">
			{#if md.relayRecords.length === 0}
				<p class="relay-empty mono">empty — nothing relayed yet</p>
			{:else}
				{#each md.relayRecords as r (r.id)}
					<div class="relay-rec">
						<div class="rr-row mono"><span class="rr-k">id</span>{shorten(r.id, 22)}</div>
						<div class="rr-row mono"><span class="rr-k">ciphertext</span>{shorten(r.ciphertext, 30)}</div>
						<div class="rr-row mono"><span class="rr-k">iv</span>{shorten(r.iv, 22)}</div>
					</div>
				{/each}
			{/if}
		</div>

		<footer class="relay-foot mono">
			<div class="holds"><span class="hk">holds</span> id · ciphertext · iv · created_at</div>
			<div class="never"><span class="nk">never</span> your key <span class="check">✓</span></div>
		</footer>
	</article>

	<!-- ── DEVICE B ─────────────────────────────────────────────── -->
	<article class="device" class:armed={md.transferred}>
		<header class="device-head">
			<div>
				<span class="device-name">Device B</span>
				<span class="device-role mono">{md.transferred ? 'key received' : 'no key yet'}</span>
			</div>
			{#if md.fpB}
				<span class="fp mono" class:match={sameKey} title="key fingerprint">🔑 {md.fpB}</span>
			{/if}
		</header>

		{#if sameKey}
			<p class="samekey mono">✓ same key as Device A — transferred over QR, not the cloud</p>
		{/if}

		<div class="demo-card">
			<div class="dc-head">
				<span class="src mono">{md.cardSource}</span>
				<span class="tag tag-private">Private</span>
			</div>
			<h3 class="dc-title">{md.cardTitle || '—'}</h3>

			{#if !md.pulled}
				<p class="dc-note mono">Nothing here yet. Pull the ciphertext the relay is holding.</p>
				<button class="btn btn-secondary sm" onclick={pullOnB} disabled={!md.pushed}>
					Pull ciphertext
				</button>
			{:else if !md.decrypted}
				<div class="inset">
					<div class="inset-label mono">
						<svg class="lk" viewBox="0 0 16 16" aria-hidden="true">
							<rect x="3" y="7" width="10" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5" />
							<path d="M5 7V5a3 3 0 1 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
						</svg>
						locked ciphertext {md.transferred ? '· key ready' : '· awaiting key'}
					</div>
					<code class="cipher mono">{md.pulledRecord ? shorten(md.pulledRecord.ciphertext, 56) : ''}…</code>
				</div>
				<button class="btn btn-primary sm" onclick={decryptOnB}>Decrypt locally</button>
			{:else if md.revealed}
				<div class="revealed">
					{#if md.revealed.summary}<p class="rv-summary">{md.revealed.summary}</p>{/if}
					{#if md.revealed.body}<p class="rv-body">{md.revealed.body}</p>{/if}
					{#if md.revealed.entities.length}
						<div class="entities">
							{#each md.revealed.entities as e (e.type + e.value)}
								<span class="entity"><span class="etype mono">{e.type}</span>{e.value}</span>
							{/each}
						</div>
					{/if}
					<p class="ok mono">✓ decrypted on Device B — identical to A. The cloud never saw the key.</p>
				</div>
			{/if}
		</div>

		{#if md.pulled && !md.transferred}
			<div class="transfer">
				<button class="btn btn-primary sm" onclick={() => transferKey()}>Scan Device A's QR</button>
				<button class="btn-link mono" onclick={() => (showPaste = !showPaste)}>
					{showPaste ? 'cancel' : 'or paste key envelope'}
				</button>
				{#if showPaste}
					<textarea
						class="paste mono"
						bind:value={pasteVal}
						placeholder="Paste the key envelope from Device A…"
						rows="3"
					></textarea>
					<button class="btn btn-secondary sm" onclick={importPasted} disabled={!pasteVal.trim()}>
						Import key
					</button>
				{/if}
			</div>
		{/if}
	</article>
</div>
{:else}
	<!-- LIVE: on-device encryption reality -->
	<section class="head">
		<div class="head-copy">
			<span class="eyebrow">Live mode · on-device encryption</span>
			<h1>Your crown jewels stay on this device.</h1>
			{#if !ext.checked}
				<p class="lede mono">Checking for the Contxt extension…</p>
			{:else if ext.present}
				<p class="lede">
					The Contxt extension classified <strong>{ext.privateTotal}</strong> private item(s) on this
					device — encrypted locally, never sent to any AI or the cloud. To move them to another
					device, the extension transfers your key by QR; the cloud only ever relays ciphertext.
				</p>
			{:else}
				<p class="lede">
					Private items are classified and encrypted on your device by the Contxt extension — the
					cloud is only ever a blind relay of ciphertext. Install the extension to see your live
					counts.
				</p>
			{/if}
			<p class="live-hint mono">
				Want the full seal → relay → QR → decrypt walkthrough? Switch to Demo mode (top right).
			</p>
		</div>
	</section>
{/if}

<style>
	.live-hint {
		margin-top: 16px;
		color: var(--text-faint);
		font-size: 0.72rem;
	}
	.head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 20px;
		margin-bottom: 28px;
		flex-wrap: wrap;
	}
	.head-copy {
		max-width: 720px;
	}
	.eyebrow {
		display: block;
		margin-bottom: 16px;
	}
	.lede {
		color: var(--text-muted);
		margin: 18px 0 0;
		font-size: 1rem;
		line-height: 1.7;
		max-width: 70ch;
	}
	.chip.reset {
		border: 1px solid var(--rule);
		background: transparent;
		color: var(--text-muted);
		font-family: var(--font-mono);
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		padding: 8px 14px;
		border-radius: var(--r-sm);
		cursor: pointer;
		transition: color 0.15s var(--ease), border-color 0.15s var(--ease);
		flex-shrink: 0;
	}
	.chip.reset:hover {
		color: var(--champagne);
		border-color: var(--rule-strong);
	}
	.banner {
		background: color-mix(in srgb, var(--vermilion) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--vermilion) 45%, var(--rule));
		color: var(--vermilion);
		border-radius: var(--r-sm);
		padding: 11px 14px;
		font-size: 0.76rem;
		margin: 0 0 22px;
	}
	.steps {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		list-style: none;
		padding: 0;
		margin: 0 0 26px;
	}
	.steps li {
		color: var(--text-faint);
		font-size: 0.68rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		border: 1px solid var(--rule);
		border-radius: var(--r-pill);
		padding: 5px 12px;
		transition: color 0.2s var(--ease), border-color 0.2s var(--ease);
	}
	.steps li.done {
		color: var(--gold);
		border-color: var(--rule-strong);
	}

	.stage {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 14px;
		align-items: stretch;
	}
	@media (max-width: 900px) {
		.stage {
			grid-template-columns: 1fr;
		}
	}

	/* device panels */
	.device {
		background: var(--raised);
		border: 1px solid color-mix(in srgb, var(--gold) 20%, var(--rule));
		border-radius: var(--r-lg);
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.device.armed {
		border-color: var(--rule-strong);
	}
	.device-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
	}
	.device-name {
		font-family: var(--font-display);
		font-size: 1.2rem;
		color: var(--champagne);
		letter-spacing: 0.04em;
	}
	.device-role {
		color: var(--text-faint);
		font-size: 0.66rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		margin-left: 8px;
	}
	.fp {
		font-size: 0.68rem;
		color: var(--text-muted);
		border: 1px solid var(--rule);
		border-radius: var(--r-xs);
		padding: 3px 8px;
		letter-spacing: 0.04em;
	}
	.fp.match {
		color: var(--gold);
		border-color: var(--rule-strong);
	}
	.samekey {
		color: var(--gold);
		font-size: 0.72rem;
		margin: -4px 0 0;
	}

	.demo-card {
		background: var(--lacquer-deep);
		border: 1px solid var(--rule);
		border-radius: var(--r-md);
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 11px;
	}
	.dc-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.src {
		color: var(--text-faint);
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}
	.dc-title {
		font-size: 1.02rem;
		line-height: 1.3;
	}
	.dc-note {
		color: var(--text-faint);
		font-size: 0.72rem;
		margin: 0;
		line-height: 1.5;
	}
	.inset {
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		padding: 11px;
		display: flex;
		flex-direction: column;
		gap: 7px;
	}
	.inset-label {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--gold);
		font-size: 0.68rem;
		letter-spacing: 0.02em;
	}
	.lk {
		width: 12px;
		height: 12px;
		flex-shrink: 0;
	}
	.cipher {
		color: var(--text-muted);
		font-size: 0.72rem;
		word-break: break-all;
		opacity: 0.8;
	}
	.ok {
		color: var(--gold-rich);
		font-size: 0.72rem;
		margin: 0;
		line-height: 1.5;
	}

	/* QR */
	.qr-block {
		display: flex;
		gap: 14px;
		align-items: center;
	}
	.qr-chip {
		width: 116px;
		height: 116px;
		flex-shrink: 0;
		background: #f4efe6;
		border-radius: var(--r-sm);
		padding: 7px;
		display: grid;
		place-items: center;
		border: 1px solid color-mix(in srgb, var(--gold) 40%, var(--rule));
	}
	.qr-chip :global(svg) {
		width: 100%;
		height: 100%;
		display: block;
	}
	.qr-copy {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.qr-label {
		color: var(--champagne);
		font-size: 0.74rem;
		letter-spacing: 0.02em;
	}
	.qr-note {
		color: var(--text-faint);
		font-size: 0.66rem;
		line-height: 1.5;
	}

	/* relay */
	.relay {
		background: var(--lacquer-deep);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
		padding: 18px;
		display: flex;
		flex-direction: column;
		gap: 14px;
		min-height: 220px;
	}
	.relay-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.relay-name {
		color: var(--patina-text);
		font-size: 0.74rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.relay-badge {
		font-size: 0.62rem;
		color: var(--text-faint);
		border: 1px solid var(--rule);
		border-radius: var(--r-pill);
		padding: 3px 9px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.relay-badge.live {
		color: var(--patina-text);
		border-color: var(--rule-patina);
	}
	.relay-body {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.relay-empty {
		color: var(--text-faint);
		font-size: 0.72rem;
		text-align: center;
		padding: 24px 0;
	}
	.relay-rec {
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		padding: 10px;
		display: flex;
		flex-direction: column;
		gap: 5px;
	}
	.rr-row {
		font-size: 0.68rem;
		color: var(--text-muted);
		word-break: break-all;
	}
	.rr-k {
		display: inline-block;
		min-width: 74px;
		color: var(--text-faint);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 0.6rem;
	}
	.relay-foot {
		border-top: 1px solid var(--rule);
		padding-top: 12px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		font-size: 0.68rem;
	}
	.holds {
		color: var(--text-muted);
	}
	.hk,
	.nk {
		display: inline-block;
		min-width: 46px;
		text-transform: uppercase;
		font-size: 0.6rem;
		letter-spacing: 0.08em;
	}
	.hk {
		color: var(--patina-text);
	}
	.never {
		color: var(--text-muted);
	}
	.nk {
		color: var(--gold);
	}
	.check {
		color: var(--gold);
	}

	/* revealed content */
	.revealed {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.rv-summary {
		margin: 0;
		color: var(--text);
		font-size: 0.9rem;
		line-height: 1.6;
	}
	.rv-body {
		margin: 0;
		color: var(--text-muted);
		font-size: 0.82rem;
		line-height: 1.6;
	}
	.entities {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.entity {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		padding: 3px 8px;
		font-size: 0.76rem;
		color: var(--text);
	}
	.etype {
		color: var(--text-faint);
		font-size: 0.58rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	/* transfer controls */
	.transfer {
		display: flex;
		flex-direction: column;
		gap: 9px;
		align-items: flex-start;
	}
	.btn-link {
		background: none;
		border: none;
		color: var(--text-faint);
		font-size: 0.68rem;
		letter-spacing: 0.04em;
		cursor: pointer;
		padding: 2px 0;
		text-decoration: underline;
		text-underline-offset: 3px;
	}
	.btn-link:hover {
		color: var(--champagne);
	}
	.paste {
		width: 100%;
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		color: var(--text);
		font-size: 0.72rem;
		padding: 9px;
		resize: vertical;
	}
	.paste:focus {
		outline: none;
		border-color: var(--rule-strong);
	}

	/* small button variant */
	.btn.sm {
		min-height: 34px;
		padding: 0 14px;
		font-size: 0.78rem;
		align-self: flex-start;
	}
</style>
