<script lang="ts">
	import { onMount } from 'svelte';
	import { ext, detectExtension, loadExtensionContext } from '$lib/extension.svelte';

	const REPO = 'https://github.com/Blackx16/contxt';

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
		{#if ext.loading}
			<p class="note mono">Pulling your live context…</p>
		{:else if ext.cards.length}
			<div class="cards">
				{#each ext.cards as c (c.source + c.title)}
					<div class="card">
						<div class="c-top">
							<span class="tag tag-shared">{c.source}</span>
							<span class="c-title">{c.title}</span>
						</div>
						{#if c.summary || c.body}<p class="c-sum">{c.summary || c.body}</p>{/if}
					</div>
				{/each}
			</div>
			<p class="note mono">
				🔒 {ext.privateTotal} private item(s) kept on-device — never sent to this page.
			</p>
		{:else}
			<p class="note mono">
				No shared context yet — open the extension popup and connect a source, then refresh.
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
	.note {
		margin: 10px 0 0;
		color: var(--text-muted);
		font-size: 0.86rem;
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
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 10px;
		margin-top: 14px;
	}
	.card {
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-md);
		padding: 11px 13px;
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
	}
	.c-sum {
		margin: 6px 0 0;
		color: var(--text-faint);
		font-size: 0.78rem;
		line-height: 1.5;
	}
	.note :global(em),
	.head .tag {
		margin-left: 4px;
	}
</style>
