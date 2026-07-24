<script lang="ts">
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { conn, connectSource, disconnectSource } from '$lib/state.svelte';
	import { PROVIDERS, type Provider } from '$lib/sources';
	import { demo } from '$lib/demo.svelte';
	import { ext, detectExtension, loadExtensionContext } from '$lib/extension.svelte';

	function providerStatus(p: Provider): 'connected' | 'connecting' | 'idle' {
		const st = p.sources.map((s) => conn[s]);
		if (st.every((x) => x === 'connected')) return 'connected';
		if (st.some((x) => x === 'connecting')) return 'connecting';
		return 'idle';
	}
	async function connectProvider(p: Provider) {
		await Promise.all(p.sources.map((s) => connectSource(s)));
	}
	function disconnectProvider(p: Provider) {
		p.sources.forEach((s) => disconnectSource(s));
	}
	const count = $derived(
		PROVIDERS.filter((p) => p.sources.every((s) => conn[s] === 'connected')).length
	);

	// Live mode: reflect the extension's real connection state, not the sim.
	let probed = false;
	$effect(() => {
		if (!demo.on && !probed) {
			probed = true;
			detectExtension().then((p) => {
				if (p) {
					loadExtensionContext();
				}
			});
		}
	});
</script>

{#if demo.on}
<section class="head">
	<span class="step eyebrow">Step 1 of 2 · Connect sources</span>
	<h1>Bring your context in.</h1>
	<p class="lede">
		Connect a source and Contxt ingests it, then the Crown-Jewels Gateway sorts each item into
		Private or Shared. Connect at least one to continue — nothing is shared until the Gateway decides
		it's safe.
	</p>
</section>

<div class="sources">
	{#each PROVIDERS as p (p.id)}
		{@const status = providerStatus(p)}
		<div class="source" class:connected={status === 'connected'}>
			<div class="source-icon">{@html p.logo}</div>
			<div class="source-body">
				<div class="source-title">
					{p.label}{#if p.sub}<span class="source-sub"> — {p.sub}</span>{/if}
				</div>
				<div class="source-blurb">{p.blurb}</div>
			</div>
			<div class="source-action">
				{#if status === 'connected'}
					<span class="done mono">Connected</span>
					<button class="btn ghost" onclick={() => disconnectProvider(p)} aria-label="Disconnect {p.label}">Disconnect</button>
				{:else if status === 'connecting'}
					<button class="btn" disabled aria-label="Connecting {p.label}">
						<span class="spinner"></span> Ingesting…
					</button>
				{:else}
					<button class="btn btn-primary" onclick={() => connectProvider(p)} aria-label="Connect {p.label}">Connect</button>
				{/if}
			</div>
		</div>
	{/each}
</div>

<div class="foot">
	<span class="count mono">{count} of {PROVIDERS.length} connected</span>
	<button class="btn btn-primary" disabled={count === 0} onclick={() => goto(`${base}/viewer`)}>
		Continue to your context →
	</button>
</div>
{:else}
	<!-- LIVE: real connection state from the extension -->
	<section class="head">
		<span class="step eyebrow">Live mode</span>
		<h1>Your connections</h1>
		<p class="lede">
			In live mode Contxt reads your sources through the browser extension. Manage connections in
			the extension popup — click the Contxt icon → Connect.
		</p>
	</section>

	{#if !ext.checked}
		<p class="live-msg mono">Checking for the Contxt extension…</p>
	{:else if ext.present}
		<div class="sources">
			<div class="source" class:connected={ext.connections.google}>
				<div class="source-icon">◈</div>
				<div class="source-body">
					<div class="source-title">Google — Gmail + Calendar</div>
					<div class="source-blurb">
						{ext.connections.google
							? ext.connections.googleEmail || 'connected'
							: 'not connected — open the extension to connect'}
					</div>
				</div>
				<span class="done mono">{ext.connections.google ? 'Connected' : '—'}</span>
			</div>
			<div class="source" class:connected={ext.connections.notion}>
				<div class="source-icon">◈</div>
				<div class="source-body">
					<div class="source-title">Notion</div>
					<div class="source-blurb">
						{ext.connections.notion
							? ext.connections.notionWorkspace || 'connected'
							: 'not connected — open the extension to connect'}
					</div>
				</div>
				<span class="done mono">{ext.connections.notion ? 'Connected' : '—'}</span>
			</div>
		</div>
		<div class="foot">
			<span class="count mono">Managed in the Contxt extension</span>
			<a class="btn btn-primary" href="{base}/viewer">See your live context →</a>
		</div>
	{:else}
		<div class="source" style="display:block">
			<p>The Contxt extension isn't installed — live mode reads your context from it.</p>
			<ol class="live-steps mono">
				<li>Clone <a href="https://github.com/Blackx16/contxt">github.com/Blackx16/contxt</a></li>
				<li>chrome://extensions → Developer mode → Load unpacked → <code>extension/</code></li>
				<li>Reload this page</li>
			</ol>
		</div>
	{/if}
{/if}

<style>
	.live-msg {
		color: var(--text-muted);
		font-size: 0.86rem;
	}
	.live-steps {
		margin: 10px 0 0;
		padding-left: 20px;
		color: var(--text-muted);
		font-size: 0.8rem;
		line-height: 1.9;
	}
	.live-steps code {
		background: var(--graphite);
		padding: 1px 5px;
		border-radius: var(--r-xs);
	}
	.head {
		max-width: 640px;
		margin-bottom: 36px;
	}
	.step {
		display: block;
		margin-bottom: 16px;
	}
	.lede {
		color: var(--text-muted);
		margin: 20px 0 0;
		font-size: 1.02rem;
		line-height: 1.7;
		max-width: 64ch;
	}
	.sources {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.source {
		display: flex;
		align-items: center;
		gap: 16px;
		background: var(--raised);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
		padding: 18px 20px;
		transition: border-color 0.15s var(--ease);
	}
	.source.connected {
		border-color: var(--rule-strong);
	}
	.source-icon {
		width: 42px;
		height: 42px;
		display: grid;
		place-items: center;
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-md);
		flex-shrink: 0;
	}
	.source-icon :global(svg) {
		width: 22px;
		height: 22px;
	}
	.source-body {
		flex: 1;
		min-width: 0;
	}
	.source-title {
		font-weight: 500;
		font-size: 1.05rem;
		color: var(--champagne);
	}
	.source-sub {
		color: var(--text-muted);
		font-weight: 400;
	}
	.source-blurb {
		color: var(--text-muted);
		font-size: 0.86rem;
	}
	.source-action {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
	}
	.done {
		color: var(--gold);
		font-size: 0.72rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}
	.btn.ghost {
		background: transparent;
		border-color: var(--rule);
		color: var(--text-muted);
		min-height: 38px;
		padding: 0 14px;
		font-size: 0.85rem;
	}
	.btn.ghost:hover {
		color: var(--vermilion);
		border-color: var(--vermilion);
	}
	.foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		margin-top: 32px;
		padding-top: 24px;
		border-top: 1px solid var(--rule);
		flex-wrap: wrap;
	}
	.count {
		color: var(--text-muted);
		font-size: 0.78rem;
		letter-spacing: 0.06em;
	}
	.spinner {
		width: 13px;
		height: 13px;
		border: 2px solid var(--graphite-2);
		border-top-color: var(--gold);
		border-radius: 50%;
		display: inline-block;
		animation: spin 0.7s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
