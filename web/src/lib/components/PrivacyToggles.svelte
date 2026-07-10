<script lang="ts">
	import { PRIVACY_CATEGORIES } from '$lib/gateway';
	import {
		isPolicyActive,
		togglePolicy,
		policyAffectedCount,
		activeCategoryIds,
		overrideProtectedCount
	} from '$lib/state.svelte';

	const activeCount = $derived(activeCategoryIds().length);
	const protectedCount = $derived(overrideProtectedCount());

	let busy = $state<string | null>(null);

	async function flip(id: (typeof PRIVACY_CATEGORIES)[number]['id']) {
		busy = id;
		try {
			await togglePolicy(id);
		} finally {
			busy = null;
		}
	}
</script>

<section class="panel" aria-labelledby="privacy-heading">
	<header class="panel-head">
		<div>
			<h3 id="privacy-heading">Privacy controls</h3>
			<p class="lede">
				Choose what should <em>never</em> leave your device. Anything matching a rule you turn on is
				held on-device and encrypted — the cloud only ever sees a locked blob.
			</p>
		</div>
		<div class="tally mono" aria-live="polite">
			<span class="tally-num">{activeCount}</span> on ·
			<span class="tally-num">{protectedCount}</span> card{protectedCount === 1 ? '' : 's'} held
		</div>
	</header>

	<ul class="rules">
		{#each PRIVACY_CATEGORIES as cat (cat.id)}
			{@const on = isPolicyActive(cat.id)}
			{@const affected = policyAffectedCount(cat.id)}
			<li class="rule" class:on>
				<span class="glyph" class:on aria-hidden="true">{cat.icon}</span>
				<div class="copy">
					<span class="label">Never share {cat.label.toLowerCase()}</span>
					<span class="blurb">{cat.blurb}</span>
				</div>
				<span class="count mono" title="Cards this rule matches right now">
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

<style>
	.panel {
		background: var(--raised);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
		padding: 22px 24px;
		margin-bottom: 24px;
	}
	.panel-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 20px;
		flex-wrap: wrap;
		padding-bottom: 16px;
		border-bottom: 1px solid var(--rule);
	}
	#privacy-heading {
		font-size: 1.02rem;
	}
	.lede {
		margin: 7px 0 0;
		color: var(--text-muted);
		font-size: 0.86rem;
		line-height: 1.6;
		max-width: 62ch;
	}
	.lede em {
		color: var(--gold);
		font-style: normal;
	}
	.tally {
		color: var(--text-faint);
		font-size: 0.68rem;
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
		gap: 16px;
		padding: 15px 2px;
		border-bottom: 1px solid var(--rule);
	}
	.rule:last-child {
		border-bottom: none;
		padding-bottom: 2px;
	}
	.glyph {
		display: grid;
		place-items: center;
		width: 30px;
		height: 30px;
		flex-shrink: 0;
		border: 1px solid var(--rule);
		border-radius: var(--r-sm);
		color: var(--text-faint);
		font-size: 0.95rem;
		transition:
			color 0.15s var(--ease),
			border-color 0.15s var(--ease);
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
		font-size: 0.94rem;
		font-weight: 500;
	}
	.blurb {
		color: var(--text-faint);
		font-size: 0.78rem;
		line-height: 1.5;
	}
	.count {
		color: var(--text-faint);
		font-size: 0.68rem;
		letter-spacing: 0.04em;
		white-space: nowrap;
	}
	/* Switch — gold = on = private (the crown-jewels anchor). Flat, hairline, no glow. */
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
</style>
