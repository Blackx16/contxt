<script lang="ts">
	import { onMount } from 'svelte';
	import { ext, detectExtension, loadExtensionContext, setPolicy } from '$lib/extension.svelte';
	import { PRIVACY_CATEGORIES } from '$lib/gateway';
	import { GOOGLE_LOGO, NOTION_LOGO, sourceLogo } from '$lib/sources';

	const REPO = 'https://github.com/Blackx16/contxt';

	type Filter = 'all' | 'shared' | 'private';
	let filter = $state<Filter>('all');
	let busy = $state<string | null>(null);

	const sharedCount = $derived(ext.cards.length);
	const privateCount = $derived(ext.privateTotal);
	const total = $derived(sharedCount + privateCount);
	const sourceCount = $derived(
		new Set([...ext.cards.map((c) => c.source), ...ext.privateCards.map((c) => c.source)]).size
	);
	const activeRules = $derived(
		ext.policy ? Object.values(ext.policy).filter(Boolean).length : 0
	);
	const showShared = $derived(filter === 'all' || filter === 'shared');
	const showPrivate = $derived(filter === 'all' || filter === 'private');

	const filters: { id: Filter; label: string }[] = [
		{ id: 'all', label: 'All' },
		{ id: 'shared', label: 'Shared' },
		{ id: 'private', label: 'Private' }
	];

	async function flip(id: string) {
		if (!ext.policy) return;
		busy = id;
		try {
			await setPolicy(id, !ext.policy[id]);
		} finally {
			busy = null;
		}
	}

	onMount(async () => {
		const present = await detectExtension();
		if (present) await loadExtensionContext();
	});
</script>

<section class="ext" class:on={ext.present} class:off={ext.checked && !ext.present}>
	{#if !ext.checked}
		<p class="head mono"><span class="dot"></span> Checking for the Contxt extension…</p>
	{:else if ext.present}
		<p class="head mono">
			<span class="dot live"></span> Extension connected
			{#if ext.source}<span class="tag tag-shared">{ext.source}</span>{/if}
		</p>
		<div class="conns mono">
			<span class="conn" class:on={ext.connections.google}>
				<span class="conn-logo">{@html GOOGLE_LOGO}</span>
				Google — Gmail + Calendar · {ext.connections.google
					? ext.connections.googleEmail || 'connected'
					: 'not connected'}
			</span>
			<span class="conn" class:on={ext.connections.notion}>
				<span class="conn-logo">{@html NOTION_LOGO}</span>
				Notion · {ext.connections.notion
					? ext.connections.notionWorkspace || 'connected'
					: 'not connected'}
			</span>
		</div>

		{#if ext.loading}
			<p class="note mono">Pulling your live context…</p>
		{:else if total > 0}
			<p class="counts mono">
				{total} card{total === 1 ? '' : 's'} · {sourceCount} source{sourceCount === 1 ? '' : 's'} ·
				<span class="c-shared">{sharedCount} shared</span> ·
				<span class="c-private">{privateCount} private</span>
			</p>

			{#if ext.policy}
				<section class="panel" aria-labelledby="live-privacy">
					<header class="panel-head">
						<div>
							<h3 id="live-privacy">Privacy controls</h3>
							<p class="lede">
								Choose what should <em>never</em> leave your device. Anything matching a rule you turn
								on is held on-device and sealed — the cloud only ever sees a locked blob.
							</p>
						</div>
						<div class="tally mono" aria-live="polite">
							<span class="tally-num">{activeRules}</span> on ·
							<span class="tally-num">{ext.heldTotal}</span> card{ext.heldTotal === 1 ? '' : 's'} held
						</div>
					</header>
					<ul class="rules">
						{#each PRIVACY_CATEGORIES as cat (cat.id)}
							{@const on = !!ext.policy[cat.id]}
							{@const affected = ext.categoryCounts?.[cat.id] ?? 0}
							<li class="rule" class:on>
								<span class="glyph" class:on aria-hidden="true">{cat.icon}</span>
								<div class="copy">
									<span class="label">Never share {cat.label.toLowerCase()}</span>
									<span class="blurb">{cat.blurb}</span>
								</div>
								<span class="count mono" title="Live items this rule matches">
									{affected} card{affected === 1 ? '' : 's'}
								</span>
								<button
									type="button"
									role="switch"
									aria-checked={on}
									aria-label="Never share {cat.label}"
									class="switch"
									class:on
									disabled={busy === cat.id}
									onclick={() => flip(cat.id)}
								>
									<span class="knob"></span>
								</button>
							</li>
						{/each}
					</ul>
				</section>
			{/if}

			<div class="filters mono">
				{#each filters as f (f.id)}
					<button class="chip" class:active={filter === f.id} onclick={() => (filter = f.id)}>
						{f.label}
					</button>
				{/each}
			</div>

			{#if showShared && ext.cards.length}
				<div class="cards">
					{#each ext.cards as c (c.source + c.title)}
						<div class="card">
							<div class="c-top">
								<span class="src-logo">{@html sourceLogo(c.source)}</span>
								<span class="tag tag-shared">{c.source}</span>
								<span class="c-title">{c.title}</span>
							</div>
							{#if c.summary || c.body}<p class="c-sum">{c.summary || c.body}</p>{/if}
						</div>
					{/each}
				</div>
			{/if}

			{#if showShared && !ext.cards.length && filter === 'shared'}
				<p class="note mono">No shared context yet — connect a source in the extension and refresh.</p>
			{/if}

			{#if showPrivate && privateCount}
				<div class="masked">
					<p class="masked-head mono">
						🔒 {privateCount} private item{privateCount === 1 ? '' : 's'} detected & kept in your Contxt
						extension
					</p>
					<p class="masked-sub">
						The on-device model flagged {privateCount === 1 ? 'this' : 'these'} as crown jewels. The
						content is masked — it stays in your Contxt extension and is never shown on the web or sent
						to any AI.
					</p>
				</div>
			{/if}
		{:else}
			<p class="note mono">
				No context yet — open the extension popup and connect a source, then refresh.
			</p>
		{/if}
	{:else}
		<p class="head mono"><span class="dot"></span> Contxt extension not installed</p>
		<p class="note">
			This page shows demo data below. To see <em>your own</em> live context here, install the
			Contxt extension — it's currently an unpacked dev build:
		</p>
		<ol class="steps mono">
			<li>Clone <a href={REPO} target="_blank" rel="noreferrer">{REPO}</a></li>
			<li>Open <code>chrome://extensions</code> and enable <b>Developer mode</b></li>
			<li><b>Load unpacked</b> → select the <code>extension/</code> folder</li>
			<li>Reload this page</li>
		</ol>
	{/if}
</section>

<style>
	.ext {
		border: 1px solid var(--rule);
		border-left: 2px solid var(--rule);
		border-radius: var(--r-lg);
		background: var(--raised);
		padding: 18px 20px;
		margin-bottom: 24px;
	}
	.ext.on {
		border-left-color: var(--patina);
	}
	.ext.off {
		border-left-color: var(--gold-deep);
	}
	.head {
		display: flex;
		align-items: center;
		gap: 9px;
		margin: 0;
		font-size: 0.82rem;
		color: var(--champagne);
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-faint);
		flex-shrink: 0;
	}
	.dot.live {
		background: var(--patina);
	}
	.conns {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 20px;
		margin: 10px 0 0;
		font-size: 0.72rem;
	}
	.conn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--text-faint);
	}
	.conn.on {
		color: var(--patina-text);
	}
	.conn-logo,
	.src-logo {
		display: inline-flex;
		flex-shrink: 0;
	}
	.conn-logo :global(svg) {
		width: 15px;
		height: 15px;
	}
	.src-logo :global(svg) {
		width: 14px;
		height: 14px;
	}
	.counts {
		margin: 14px 0 0;
		color: var(--text-muted);
		font-size: 0.74rem;
		letter-spacing: 0.06em;
	}
	.c-shared {
		color: var(--patina-text);
	}
	.c-private {
		color: var(--gold);
	}
	.note {
		margin: 12px 0 0;
		color: var(--text-muted);
		font-size: 0.82rem;
		line-height: 1.6;
	}
	.steps {
		margin: 12px 0 0;
		padding-left: 20px;
		color: var(--text-muted);
		font-size: 0.78rem;
		line-height: 1.9;
	}
	.steps code {
		background: var(--graphite);
		padding: 1px 5px;
		border-radius: var(--r-xs);
	}

	/* Privacy controls — mirrors the demo PrivacyToggles panel. */
	.panel {
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
		padding: 18px 20px;
		margin: 16px 0 4px;
	}
	.panel-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 20px;
		flex-wrap: wrap;
		padding-bottom: 14px;
		border-bottom: 1px solid var(--rule);
	}
	#live-privacy {
		font-size: 0.98rem;
	}
	.lede {
		margin: 6px 0 0;
		color: var(--text-muted);
		font-size: 0.8rem;
		line-height: 1.6;
		max-width: 60ch;
	}
	.lede em {
		color: var(--gold);
		font-style: normal;
	}
	.tally {
		color: var(--text-faint);
		font-size: 0.66rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		white-space: nowrap;
		padding-top: 4px;
	}
	.tally-num {
		color: var(--gold);
	}
	.rules {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.rule {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 13px 2px;
		border-bottom: 1px solid var(--rule);
	}
	.rule:last-child {
		border-bottom: none;
		padding-bottom: 2px;
	}
	.glyph {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		flex-shrink: 0;
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		color: var(--text-faint);
		font-size: 0.9rem;
	}
	.glyph.on {
		color: var(--gold);
		border-color: var(--rule-strong);
	}
	.copy {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
		min-width: 0;
	}
	.label {
		color: var(--text);
		font-size: 0.9rem;
		font-weight: 500;
	}
	.blurb {
		color: var(--text-faint);
		font-size: 0.74rem;
		line-height: 1.5;
	}
	.count {
		color: var(--text-faint);
		font-size: 0.66rem;
		letter-spacing: 0.04em;
		white-space: nowrap;
	}
	.switch {
		position: relative;
		flex-shrink: 0;
		width: 44px;
		height: 24px;
		padding: 0;
		border: 1px solid var(--rule);
		border-radius: var(--r-pill);
		background: var(--graphite-2);
		cursor: pointer;
		transition:
			background 0.16s var(--ease),
			border-color 0.16s var(--ease);
	}
	.switch:hover {
		border-color: var(--rule-strong);
	}
	.switch.on {
		background: var(--gold);
		border-color: var(--gold);
	}
	.switch:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.knob {
		position: absolute;
		top: 50%;
		left: 3px;
		width: 16px;
		height: 16px;
		border-radius: var(--r-pill);
		background: var(--text-muted);
		transform: translate(0, -50%);
		transition:
			transform 0.16s var(--ease),
			background 0.16s var(--ease);
	}
	.switch.on .knob {
		background: var(--lacquer-deep);
		transform: translate(20px, -50%);
	}

	.filters {
		display: inline-flex;
		gap: 2px;
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		padding: 3px;
		margin: 16px 0 2px;
	}
	.chip {
		border: none;
		background: transparent;
		color: var(--text-muted);
		font-family: var(--font-mono);
		font-size: 0.7rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		padding: 6px 14px;
		border-radius: var(--r-xs);
		cursor: pointer;
	}
	.chip:hover {
		color: var(--champagne);
	}
	.chip.active {
		background: var(--graphite-2);
		color: var(--gold);
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 10px;
		margin-top: 14px;
		align-items: start;
	}
	.card {
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-md);
		padding: 12px 13px;
		display: flex;
		flex-direction: column;
		min-height: 108px;
	}
	.c-top {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.c-title {
		font-weight: 500;
		font-size: 0.9rem;
		color: var(--champagne);
		line-height: 1.35;
	}
	.c-sum {
		margin: 7px 0 0;
		color: var(--text-faint);
		font-size: 0.78rem;
		line-height: 1.5;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		overflow: hidden;
	}
	.masked {
		margin-top: 14px;
		background: var(--lacquer-deep);
		border: 1px solid color-mix(in srgb, var(--gold) 26%, var(--rule));
		border-radius: var(--r-md);
		padding: 16px 18px;
	}
	.masked-head {
		margin: 0;
		color: var(--gold);
		font-size: 0.8rem;
		letter-spacing: 0.02em;
	}
	.masked-sub {
		margin: 8px 0 0;
		color: var(--text-muted);
		font-size: 0.8rem;
		line-height: 1.6;
		max-width: 64ch;
	}
	.note :global(em),
	.head .tag {
		margin-left: 4px;
	}
</style>
