export const meta = {
  name: 'council-of-sages',
  description: 'Challenger -> Proposer -> Judge debate over a plan (Claude-native port of orchestration/arbitrator.py)',
  phases: [
    { title: 'Challenge', detail: 'Adversarial critique of the plan' },
    { title: 'Defend', detail: 'Resolve each critique point-by-point' },
    { title: 'Judge', detail: 'Final structured verdict' },
  ],
}

// Claude-subagent variant of arbitrator.py's run_consensus(). Same debate shape, same verdict
// contract (status/conditions/confidence/risk_areas/summary) — but agent() always calls a Claude
// subagent, never the local/cloud LLM stack arbitrator.py routes through via mcp-llm-broker. Both
// are worth having: this one for zero local-infra dependency, arbitrator.py for zero token cost.
// See tasks/done/.../port-council-of-sages-*.md for the design record.

const CRITIQUE_SCHEMA = {
  type: 'object',
  properties: {
    critiques: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'e.g. CRIT-001' },
          category: { type: 'string', enum: ['security', 'performance', 'design'] },
          severity: { type: 'string', enum: ['blocker', 'warning'] },
          description: { type: 'string' },
          suggested_action: { type: 'string' },
        },
        required: ['id', 'category', 'severity', 'description', 'suggested_action'],
      },
    },
  },
  required: ['critiques'],
}

const RESOLUTION_SCHEMA = {
  type: 'object',
  properties: {
    resolutions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          critique_id: { type: 'string' },
          accepted: { type: 'boolean' },
          resolution: { type: 'string' },
        },
        required: ['critique_id', 'accepted', 'resolution'],
      },
    },
  },
  required: ['resolutions'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['approved', 'rejected', 'conditional'] },
    conditions: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'number' },
    risk_areas: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['status', 'conditions', 'confidence', 'risk_areas', 'summary'],
}

// Matches arbitrator.py's actual hardcoded Challenger/Proposer/Judge prompts near-verbatim — the
// source script itself uses generic role prompts here, NOT named `.agent/agents/*.md` personas.
// The one place it layers in a real persona is optional "expert_rules" appended to the Challenger
// (via agent_auctioneer's dynamic file-type-based selection) — args.expertPersona below is the
// fixed-pair simplification of that (see the card: "start with a fixed pair... rather than
// porting arbitrator.py's dynamic agent_auctioneer.py-based selection").
const CHALLENGER_ROLE = `You are CHALLENGER, a ruthless security and architecture auditor.
Find every weakness. Be specific with risk areas.`

const PROPOSER_ROLE = `You are PROPOSER, a confident architect.
You have received a list of architectural critiques. You must respond to each point.`

const JUDGE_ROLE = `You are ARBITRATOR, the judge for this Council of Sages review.
Review the structured debate between Challenger and Proposer and issue a final structured
verdict. confidence must be a real assessment (0.0-1.0), not a made-up round number.`

const planId = (args && args.planId) || 'plan'
const planText = args && args.planText
const expertPersona = (args && args.expertPersona) || '' // optional: e.g. red-team.md's core rules

if (!planText) {
  throw new Error(
    "council-of-sages requires args.planText (the plan/proposal text to review). " +
    "Optional: args.planId (label), args.expertPersona (a real agent's rules to layer onto the Challenger)."
  )
}

phase('Challenge')
const challengerPrompt =
  (expertPersona
    ? `${CHALLENGER_ROLE}\n\nIn addition, audit against these domain-expert rules:\n${expertPersona}\n\n`
    : `${CHALLENGER_ROLE}\n\n`) +
  `Critique the following plan with maximum severity. Output structured critiques.\n\nPlan:\n${planText}`
const critiqueResult = await agent(challengerPrompt, { label: 'challenger', schema: CRITIQUE_SCHEMA })
const critiques = (critiqueResult && critiqueResult.critiques) || []

phase('Defend')
const proposerPrompt =
  `${PROPOSER_ROLE}\n\nDefend the following plan by responding to each point in the critiques.\n\n` +
  `Plan:\n${planText}\n\nCritiques:\n${JSON.stringify({ critiques }, null, 2)}`
const resolutionResult = await agent(proposerPrompt, { label: 'proposer', schema: RESOLUTION_SCHEMA })
const resolutions = (resolutionResult && resolutionResult.resolutions) || []

// Automated validation (mirrors arbitrator.py): every blocker-severity critique must have an
// accepted=true resolution, or the verdict is forced to rejected regardless of what the Judge says.
const resolutionByCritique = {}
for (const r of resolutions) resolutionByCritique[r.critique_id] = r
const unresolvedBlockers = critiques
  .filter((c) => c.severity === 'blocker')
  .filter((c) => !(resolutionByCritique[c.id] && resolutionByCritique[c.id].accepted))
  .map((c) => `${c.id} (${c.category})`)

phase('Judge')
const judgePrompt =
  `${JUDGE_ROLE}\n\nPlan: ${planText}\n\n` +
  `CRITIQUES (Challenger):\n${JSON.stringify({ critiques }, null, 2)}\n\n` +
  `RESOLUTIONS (Proposer):\n${JSON.stringify({ resolutions }, null, 2)}`
const verdict = await agent(judgePrompt, { label: 'judge', schema: VERDICT_SCHEMA })

if (unresolvedBlockers.length > 0) {
  verdict.status = 'rejected'
  verdict.conditions = [...(verdict.conditions || []), `Resolve blocker critiques: ${unresolvedBlockers.join(', ')}`]
  verdict.risk_areas = [...(verdict.risk_areas || []), 'Automated check-off failed: unresolved blocker critique(s)']
  log(`Automated validation overrode verdict to 'rejected' — unresolved blockers: ${unresolvedBlockers.join(', ')}`)
}

log(`Verdict: ${verdict.status} (confidence: ${verdict.confidence})`)

return { planId, ...verdict, critiques, resolutions }
