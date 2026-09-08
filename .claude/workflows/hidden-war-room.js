export const meta = {
  name: 'hidden-war-room',
  description: 'Optimist -> Skeptic -> User Advocate -> Arbitrator sequential role-play debate (Claude-native port of orchestration/hidden_war_room.py)',
  phases: [
    { title: 'Optimist' },
    { title: 'Skeptic' },
    { title: 'User Advocate' },
    { title: 'Arbitrator' },
  ],
}

// Claude-subagent variant of hidden_war_room.py's run_war_room(). Same 4-role sequential shape,
// each role sees all prior roles' output (not a shared free-for-all context) — Optimist sets an
// unguarded frame, Skeptic attacks it, User Advocate re-centers on the end user, Arbitrator
// synthesizes. Deliberately descoped: the source script's "DNA" user-preference-profile layer
// (load_dna/build_dna_block/veto scoring) is NOT ported here — that's a separate personalization
// system, out of scope for "make the debate mechanism visible," and not mentioned in this
// workflow's originating task card. Flagging explicitly rather than silently dropping it.
// See tasks/done/.../port-hidden-war-room-*.md for the design record.

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['approved', 'rejected', 'conditional'] },
    conditions: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'number' },
    summary: { type: 'string' },
  },
  required: ['status', 'conditions', 'confidence', 'summary'],
}

const topic = args && args.topic
const context = (args && args.context) || ''
// Optional: layer a real agent's rules onto the Skeptic role (e.g. red-team.md) — same
// fixed-pair-augmentation technique used by the council-of-sages workflow.
const skepticPersona = (args && args.skepticPersona) || ''

if (!topic) {
  throw new Error(
    'hidden-war-room requires args.topic (the question/proposal to debate). ' +
    'Optional: args.context (extra background), args.skepticPersona (a real agent\'s rules to layer onto the Skeptic).'
  )
}

const fullContext = context ? `${context}\n\nTopic: ${topic}` : `Topic: ${topic}`

phase('Optimist')
const optimistArg = await agent(
  `You are the OPTIMIST in a structured debate. Defend and promote this topic. Highlight all ` +
  `benefits and positive aspects.\n\n${fullContext}`,
  { label: 'optimist' }
)

phase('Skeptic')
const skepticPrompt =
  (skepticPersona
    ? `You are the SKEPTIC in a structured debate. In addition to the role below, audit against ` +
      `these domain-expert rules:\n${skepticPersona}\n\n`
    : `You are the SKEPTIC in a structured debate. `) +
  `Critique this proposal. Find hidden complexity, risks, edge cases.\n\n${fullContext}\n\n` +
  `The Optimist argues:\n${optimistArg}`
const skepticArg = await agent(skepticPrompt, { label: 'skeptic' })

phase('User Advocate')
const advocateArg = await agent(
  `You are the USER ADVOCATE in a structured debate. Represent the end user's interests — is this ` +
  `actually good for the people who will use it, independent of what's technically elegant or ` +
  `technically risky?\n\n${fullContext}\n\nOptimist: ${optimistArg}\n\nSkeptic: ${skepticArg}`,
  { label: 'user-advocate' }
)

phase('Arbitrator')
const verdict = await agent(
  `You are the ARBITRATOR in a structured debate. Analyze the following debate and issue a final ` +
  `structured verdict.\n\nTopic: ${topic}\n\n` +
  `OPTIMIST:\n${optimistArg}\n\nSKEPTIC:\n${skepticArg}\n\nUSER ADVOCATE:\n${advocateArg}`,
  { label: 'arbitrator', schema: VERDICT_SCHEMA }
)

log(`Verdict: ${verdict.status} (confidence: ${verdict.confidence})`)

return {
  topic,
  ...verdict,
  responses: { optimist: optimistArg, skeptic: skepticArg, user_advocate: advocateArg },
}
